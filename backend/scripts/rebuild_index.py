"""
Rebuild the FAISS index from all active chunks stored in PostgreSQL.

Use this when:
  - The index file is lost or corrupted.
  - A version of the code that changed the embedding model is deployed.
  - You need to verify index/DB consistency.

Usage (from backend/ directory):
    python scripts/rebuild_index.py

WARNING: This loads ALL active chunks into memory simultaneously.
         For very large corpora, run during off-hours.
"""
import os
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("rebuild_index")


def rebuild() -> None:
    from sqlalchemy.orm import Session
    from app.database import SyncSessionLocal
    from app.models.chunk import Chunk
    from app.models.document import Document, DocumentStatus, DocumentVersion
    from app.rag.embedder import embed_texts
    from app.rag.index_manager import get_index_manager
    import numpy as np

    db: Session = SyncSessionLocal()
    try:
        logger.info("Loading active chunks from database…")
        chunks = (
            db.query(Chunk)
            .join(DocumentVersion, Chunk.version_id == DocumentVersion.id)
            .join(Document, DocumentVersion.document_id == Document.id)
            .filter(DocumentVersion.is_active == True)
            .filter(DocumentVersion.status == DocumentStatus.ready)
            .filter(Document.is_deleted == False)
            .all()
        )

        if not chunks:
            logger.warning("No active chunks found. Index will be empty.")
            manager = get_index_manager()
            manager.rebuild([], np.zeros((0, 384), dtype="float32"))
            return

        logger.info("Found %d chunks. Generating embeddings…", len(chunks))
        texts = [c.text for c in chunks]
        embeddings = embed_texts(texts, normalize=True)

        chunk_ids = [c.id for c in chunks]
        manager = get_index_manager()
        manager.rebuild(chunk_ids, embeddings)

        logger.info(
            "Index rebuilt: %d vectors (dim=%d)", manager.total_vectors, embeddings.shape[1]
        )
    finally:
        db.close()


if __name__ == "__main__":
    rebuild()
