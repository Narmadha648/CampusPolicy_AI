"""RAG retrieval: embed query → FAISS search → load chunk metadata from DB."""
import logging
import uuid
from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.chunk import Chunk
from app.models.document import DocumentStatus, DocumentVersion
from app.rag.embedder import embed_query
from app.rag.index_manager import get_index_manager

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class RetrievedChunk:
    chunk_id: uuid.UUID
    chunk_key: str
    page_number: int
    text: str
    similarity_score: float
    document_title: str
    document_version: int
    version_id: uuid.UUID
    document_id: uuid.UUID
    storage_path: str


async def retrieve(
    query: str,
    db: AsyncSession,
    top_k: Optional[int] = None,
    threshold: Optional[float] = None,
) -> List[RetrievedChunk]:
    """
    1. Embed the query (L2-normalised).
    2. Search FAISS for top-k chunks above threshold.
    3. Load chunk + version metadata from DB.
    4. Filter to chunks belonging to active, ready document versions.
    Returns list sorted by descending similarity.
    """
    if top_k is None:
        top_k = settings.max_chunks_per_query
    if threshold is None:
        threshold = settings.similarity_threshold

    # Embed
    qvec = embed_query(query, normalize=True)

    # FAISS search
    manager = get_index_manager()
    raw_results = manager.search(qvec, top_k=top_k * 2, threshold=threshold)
    # raw_results: List[(chunk_uuid, score)]

    if not raw_results:
        return []

    chunk_uuids = [cid for cid, _ in raw_results]
    score_map = {cid: score for cid, score in raw_results}

    # Load chunks with their version info
    result = await db.execute(
        select(Chunk, DocumentVersion)
        .join(DocumentVersion, Chunk.version_id == DocumentVersion.id)
        .where(Chunk.id.in_(chunk_uuids))
        .where(DocumentVersion.is_active == True)
        .where(DocumentVersion.status == DocumentStatus.ready)
    )
    rows = result.all()

    retrieved: List[RetrievedChunk] = []
    for chunk, version in rows:
        # Eagerly load document title
        from app.models.document import Document
        doc_result = await db.execute(
            select(Document).where(Document.id == version.document_id).where(Document.is_deleted == False)
        )
        doc = doc_result.scalar_one_or_none()
        if not doc:
            continue

        retrieved.append(
            RetrievedChunk(
                chunk_id=chunk.id,
                chunk_key=chunk.chunk_key,
                page_number=chunk.page_number,
                text=chunk.text,
                similarity_score=score_map.get(chunk.id, 0.0),
                document_title=doc.title,
                document_version=version.version_number,
                version_id=version.id,
                document_id=doc.id,
                storage_path=version.storage_path,
            )
        )

    # Sort by score descending and return top_k
    retrieved.sort(key=lambda x: x.similarity_score, reverse=True)
    return retrieved[:top_k]
