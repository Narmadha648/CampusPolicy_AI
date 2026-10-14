"""Document management endpoints (admin upload/replace/delete + student file access)."""
import asyncio
import logging
import uuid
from pathlib import Path
from typing import Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.document import Document, DocumentStatus, DocumentVersion
from app.models.job import JobStatus, ProcessingJob
from app.schemas.document import DocumentListOut, DocumentOut, DocumentVersionOut, JobOut
from app.services.deps import get_current_user, require_admin
from app.services.file_service import delete_file, validate_and_save_pdf
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


def _version_to_out(v: DocumentVersion) -> DocumentVersionOut:
    return DocumentVersionOut.model_validate(v)


def _doc_to_out(doc: Document) -> DocumentOut:
    active = next((v for v in doc.versions if v.is_active), None)
    latest = doc.versions[-1] if doc.versions else None
    return DocumentOut(
        id=doc.id,
        title=doc.title,
        policy_year=doc.policy_year,
        description=doc.description,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        active_version=_version_to_out(active) if active else None,
        latest_version=_version_to_out(latest) if latest else None,
    )


def _enqueue_processing(version_id: uuid.UUID) -> None:
    """Run the ingestion worker in a thread pool (non-blocking)."""
    import threading
    from app.workers.ingestion_worker import process_version
    t = threading.Thread(target=process_version, args=(version_id,), daemon=True)
    t.start()


# ── Admin: Upload new document ────────────────────────────────────────────────

@router.post("/admin/documents", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(..., min_length=2, max_length=500),
    policy_year: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    doc_id = uuid.uuid4()

    # Save file
    storage_path, file_size = await validate_and_save_pdf(file, doc_id, 1)

    # Create Document + Version + Job records
    doc = Document(id=doc_id, title=title, policy_year=policy_year, description=description)
    db.add(doc)
    await db.flush()

    version = DocumentVersion(
        document_id=doc.id,
        version_number=1,
        storage_path=str(storage_path),
        original_filename=file.filename or "upload.pdf",
        file_size_bytes=file_size,
        status=DocumentStatus.pending,
    )
    db.add(version)
    await db.flush()

    job = ProcessingJob(version_id=version.id, status=JobStatus.queued)
    db.add(job)
    await db.commit()
    await db.refresh(doc)

    # Reload with relationships
    result = await db.execute(
        select(Document)
        .options(selectinload(Document.versions))
        .where(Document.id == doc.id)
    )
    doc = result.scalar_one()

    background_tasks.add_task(_enqueue_processing, version.id)
    logger.info("Document %s uploaded, queued for processing", doc.id)
    return _doc_to_out(doc)


# ── Admin: List documents ─────────────────────────────────────────────────────

@router.get("/admin/documents", response_model=DocumentListOut)
async def list_documents(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(
        select(Document)
        .options(selectinload(Document.versions))
        .where(Document.is_deleted == False)
        .order_by(Document.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    docs = result.scalars().all()

    count_result = await db.execute(
        select(Document).where(Document.is_deleted == False)
    )
    total = len(count_result.scalars().all())

    return DocumentListOut(items=[_doc_to_out(d) for d in docs], total=total)


# ── Admin: Replace document ───────────────────────────────────────────────────

@router.post("/admin/documents/{document_id}/replace", response_model=DocumentOut)
async def replace_document(
    document_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    policy_year: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(
        select(Document)
        .options(selectinload(Document.versions))
        .where(Document.id == document_id)
        .where(Document.is_deleted == False)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    new_version_number = len(doc.versions) + 1
    storage_path, file_size = await validate_and_save_pdf(file, doc.id, new_version_number)

    if policy_year is not None:
        doc.policy_year = policy_year
    if description is not None:
        doc.description = description

    version = DocumentVersion(
        document_id=doc.id,
        version_number=new_version_number,
        storage_path=str(storage_path),
        original_filename=file.filename or "upload.pdf",
        file_size_bytes=file_size,
        status=DocumentStatus.pending,
    )
    db.add(version)
    await db.flush()

    job = ProcessingJob(version_id=version.id, status=JobStatus.queued)
    db.add(job)
    await db.commit()

    result = await db.execute(
        select(Document)
        .options(selectinload(Document.versions))
        .where(Document.id == doc.id)
    )
    doc = result.scalar_one()

    background_tasks.add_task(_enqueue_processing, version.id)
    return _doc_to_out(doc)


# ── Admin: Delete document ────────────────────────────────────────────────────

@router.delete("/admin/documents/{document_id}", status_code=status.HTTP_200_OK)
async def delete_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(
        select(Document)
        .options(selectinload(Document.versions))
        .where(Document.id == document_id)
        .where(Document.is_deleted == False)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Remove from FAISS
    from app.models.chunk import Chunk
    from app.rag.index_manager import get_index_manager
    manager = get_index_manager()

    for version in doc.versions:
        version.is_active = False
        chunk_result = await db.execute(
            select(Chunk).where(Chunk.version_id == version.id)
        )
        chunks = chunk_result.scalars().all()
        if chunks:
            manager.remove_chunks([c.id for c in chunks])

    doc.is_deleted = True
    await db.commit()

    # Mark citations whose chunks came from this document
    from app.models.conversation import MessageCitation
    from sqlalchemy import update
    await db.execute(
        update(MessageCitation)
        .where(
            MessageCitation.chunk_id.in_(
                select(Chunk.id).join(DocumentVersion).where(DocumentVersion.document_id == document_id)
            )
        )
        .values(source_deleted=True)
    )
    await db.commit()

    return {"message": "Document deleted successfully"}


# ── Admin: Retry failed job ───────────────────────────────────────────────────

@router.post("/admin/documents/{document_id}/retry", response_model=DocumentOut)
async def retry_document(
    document_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(
        select(Document)
        .options(selectinload(Document.versions))
        .where(Document.id == document_id)
        .where(Document.is_deleted == False)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    failed_version = next(
        (v for v in reversed(doc.versions) if v.status == DocumentStatus.failed), None
    )
    if not failed_version:
        raise HTTPException(status_code=400, detail="No failed version to retry")

    # Reset version status
    failed_version.status = DocumentStatus.pending
    failed_version.error_message = None

    # Create a new job record
    job = ProcessingJob(version_id=failed_version.id, status=JobStatus.queued)
    db.add(job)
    await db.commit()

    background_tasks.add_task(_enqueue_processing, failed_version.id)
    return _doc_to_out(doc)


# ── Admin: Get job status ─────────────────────────────────────────────────────

@router.get("/admin/jobs/{job_id}", response_model=JobOut)
async def get_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(ProcessingJob).where(ProcessingJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobOut.model_validate(job)


# ── Student: Download/view PDF file ──────────────────────────────────────────

@router.get("/documents/{document_id}/file")
async def get_document_file(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns the active PDF for inline viewing (authenticated users only)."""
    result = await db.execute(
        select(Document)
        .options(selectinload(Document.versions))
        .where(Document.id == document_id)
        .where(Document.is_deleted == False)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    active_version = next((v for v in doc.versions if v.is_active), None)
    if not active_version:
        raise HTTPException(status_code=404, detail="No active version for this document")

    path = Path(active_version.storage_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found on server")

    return FileResponse(
        path=str(path),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{active_version.original_filename}"'},
    )
