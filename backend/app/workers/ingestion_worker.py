"""Document ingestion worker.

This module processes a single DocumentVersion:
  1. Extract text with PyMuPDF
  2. Detect scanned-only PDFs
  3. Chunk text page-by-page
  4. Embed chunks with Sentence Transformers
  5. Store chunks in PostgreSQL
  6. Index embeddings in FAISS
  7. Mark version active / document ready

Called by the background task runner in the document API endpoint.
Uses the synchronous SQLAlchemy session (safe in a worker thread / process).
"""
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import numpy as np
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SyncSessionLocal
from app.models.chunk import Chunk
from app.models.document import DocumentStatus, DocumentVersion
from app.models.job import JobStatus, ProcessingJob
from app.rag.embedder import embed_texts
from app.rag.index_manager import get_index_manager
from app.services.chunker import TextChunk, chunk_page
from app.services.pdf_service import ExtractionResult, extract_pages

logger = logging.getLogger(__name__)
settings = get_settings()


def _mark_job(db: Session, job: ProcessingJob, status: JobStatus, error: str = "") -> None:
    job.status = status
    job.finished_at = datetime.now(timezone.utc)
    if error:
        job.error_detail = error
    db.commit()


def _mark_version(
    db: Session,
    version: DocumentVersion,
    status: DocumentStatus,
    page_count: int = 0,
    error: str = "",
) -> None:
    version.status = status
    if page_count:
        version.page_count = page_count
    if status == DocumentStatus.ready:
        version.is_active = True
        version.processed_at = datetime.now(timezone.utc)
        # Deactivate all previous versions of the same document
        for v in version.document.versions:
            if v.id != version.id and v.is_active:
                v.is_active = False
    if error:
        version.error_message = error
    db.commit()


def process_version(version_id: uuid.UUID) -> None:
    """
    Entry point for the ingestion worker.
    Loads the version and its pending job, then runs the full pipeline.
    """
    db: Session = SyncSessionLocal()
    try:
        version: DocumentVersion = db.get(DocumentVersion, version_id)
        if not version:
            logger.error("DocumentVersion %s not found", version_id)
            return

        job: ProcessingJob = (
            db.query(ProcessingJob)
            .filter(
                ProcessingJob.version_id == version_id,
                ProcessingJob.status.in_([JobStatus.queued, JobStatus.failed]),
            )
            .order_by(ProcessingJob.queued_at.desc())
            .first()
        )
        if not job:
            logger.warning("No queued/failed job found for version %s", version_id)
            return

        # Mark running
        job.status = JobStatus.running
        job.started_at = datetime.now(timezone.utc)
        job.attempt_count += 1
        version.status = DocumentStatus.processing
        db.commit()

        logger.info(
            "Processing version %s (doc=%s attempt=%d)",
            version_id,
            version.document_id,
            job.attempt_count,
        )

        _run_pipeline(db, version, job)

    except Exception as exc:
        logger.exception("Unexpected error in ingestion worker for version %s", version_id)
        try:
            version = db.get(DocumentVersion, version_id)
            job = db.query(ProcessingJob).filter(
                ProcessingJob.version_id == version_id,
                ProcessingJob.status == JobStatus.running,
            ).first()
            if version:
                _mark_version(db, version, DocumentStatus.failed, error=str(exc))
            if job:
                _mark_job(db, job, JobStatus.failed, error=str(exc))
        except Exception:
            pass
    finally:
        db.close()


def _run_pipeline(db: Session, version: DocumentVersion, job: ProcessingJob) -> None:
    # ── Step 1: Extract text ──────────────────────────────────────────────────
    result: ExtractionResult = extract_pages(version.storage_path)

    if result.error:
        _mark_version(db, version, DocumentStatus.failed, error=result.error)
        _mark_job(db, job, JobStatus.failed, error=result.error)
        return

    if result.is_scanned:
        msg = (
            f"This PDF appears to be scanned (image-only). "
            f"{result.scanned_page_ratio:.0%} of pages have no extractable text. "
            "OCR is required before this document can be indexed."
        )
        _mark_version(db, version, DocumentStatus.failed, page_count=result.page_count, error=msg)
        _mark_job(db, job, JobStatus.failed, error=msg)
        return

    total_text = sum(len(p.text) for p in result.pages)
    if total_text < 100:
        msg = "PDF was processed but no meaningful text could be extracted."
        _mark_version(db, version, DocumentStatus.failed, page_count=result.page_count, error=msg)
        _mark_job(db, job, JobStatus.failed, error=msg)
        return

    # ── Step 2: Chunk ─────────────────────────────────────────────────────────
    all_chunks: List[TextChunk] = []
    for page in result.pages:
        page_chunks = chunk_page(page.text, page.page_number)
        all_chunks.extend(page_chunks)

    if not all_chunks:
        msg = "No text chunks could be produced from this document."
        _mark_version(db, version, DocumentStatus.failed, page_count=result.page_count, error=msg)
        _mark_job(db, job, JobStatus.failed, error=msg)
        return

    logger.info("Produced %d chunks from %d pages", len(all_chunks), result.page_count)

    # ── Step 3: Embed ─────────────────────────────────────────────────────────
    texts = [c.text for c in all_chunks]
    embeddings: np.ndarray = embed_texts(texts, normalize=True)

    # ── Step 4: Persist chunks to DB ─────────────────────────────────────────
    # Delete any existing chunks for this version (retry scenario)
    db.query(Chunk).filter(Chunk.version_id == version.id).delete()
    db.commit()

    chunk_records: List[Chunk] = []
    chunk_uuids: List[uuid.UUID] = []
    for i, (tc, _) in enumerate(zip(all_chunks, embeddings)):
        chunk_key = f"{version.id}-p{tc.page_number}-c{tc.chunk_index}"
        chunk = Chunk(
            version_id=version.id,
            chunk_key=chunk_key,
            page_number=tc.page_number,
            chunk_index=tc.chunk_index,
            text=tc.text,
            char_count=len(tc.text),
        )
        db.add(chunk)
        chunk_records.append(chunk)

    db.flush()  # assign IDs without committing

    for chunk in chunk_records:
        chunk_uuids.append(chunk.id)

    db.commit()

    # ── Step 5: Update FAISS index ────────────────────────────────────────────
    manager = get_index_manager()
    # Remove any old chunks for previous versions of the same document
    # (handles the replace-document flow)
    old_version_ids = [
        v.id for v in version.document.versions
        if v.id != version.id
    ]
    if old_version_ids:
        old_chunks = db.query(Chunk).filter(
            Chunk.version_id.in_(old_version_ids)
        ).all()
        old_uuids = [c.id for c in old_chunks]
        if old_uuids:
            logger.info("Removing %d old chunk vectors from FAISS", len(old_uuids))
            manager.remove_chunks(old_uuids)

    manager.add_chunks(chunk_uuids, embeddings)
    logger.info("Indexed %d vectors in FAISS (total=%d)", len(chunk_uuids), manager.total_vectors)

    # ── Step 6: Mark ready ────────────────────────────────────────────────────
    _mark_version(db, version, DocumentStatus.ready, page_count=result.page_count)
    _mark_job(db, job, JobStatus.completed)
    logger.info(
        "Version %s processed successfully (%d chunks)", version.id, len(chunk_records)
    )
