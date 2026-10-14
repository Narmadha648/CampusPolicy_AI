"""Embedding service using Sentence Transformers.

A single instance is loaded once at startup and shared across all requests.
Embeddings are L2-normalised so that inner product == cosine similarity,
matching the FAISS IndexFlatIP metric.

sentence_transformers is imported lazily so the test suite can mock it
without requiring the full ML stack.
"""
import logging
import threading
from typing import List, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer as _ST

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_lock = threading.Lock()
_model: "_ST | None" = None


def get_embedder() -> "_ST":
    """Returns the singleton embedding model, loading it on first call."""
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer
                logger.info("Loading embedding model: %s", settings.embedding_model)
                _model = SentenceTransformer(settings.embedding_model)
                logger.info("Embedding model loaded (dim=%d)", _model.get_sentence_embedding_dimension())
    return _model  # type: ignore[return-value]


def embed_texts(texts: List[str], normalize: bool = True) -> np.ndarray:
    """
    Returns a float32 numpy array of shape (N, D).

    normalize=True → L2-normalised vectors for cosine similarity via dot product.
    """
    model = get_embedder()
    embeddings = model.encode(
        texts,
        batch_size=64,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=normalize,
    )
    return embeddings.astype(np.float32)


def embed_query(query: str, normalize: bool = True) -> np.ndarray:
    """Returns a float32 array of shape (1, D)."""
    return embed_texts([query], normalize=normalize)
