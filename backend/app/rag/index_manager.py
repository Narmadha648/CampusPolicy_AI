"""FAISS index manager.

Maintains a single IndexFlatIP (inner-product / cosine for L2-normalised
vectors) and a parallel list that maps FAISS integer IDs back to stable
chunk UUIDs.

Thread safety
-------------
A read-write lock pattern (threading.Lock) protects concurrent access.
Index updates (add / remove) use an atomic replace strategy:
  1. Build a new index in memory.
  2. Acquire the write lock.
  3. Swap the in-memory reference.
  4. Persist to disk atomically (write to .tmp then rename).

This means concurrent readers always see a consistent state.

Persistence
-----------
Two files are written to FAISS_INDEX_DIR:
  - index.faiss   — the raw FAISS binary index
  - id_map.npy    — numpy int64 array of chunk UUID integers (128-bit packed as 2×int64)

Because UUIDs are 128-bit we store them as pairs of int64 (high, low) in the
id_map.  A helper converts between uuid.UUID and two int64 values.
"""
import logging
import os
import threading
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _get_faiss():
    """Lazy faiss import so tests without faiss-cpu installed can still import this module."""
    import faiss  # type: ignore[import]
    return faiss


# ── UUID ↔ (int64, int64) helpers ────────────────────────────────────────────

def _uuid_to_pair(u: uuid.UUID) -> Tuple[int, int]:
    n = u.int
    high = n >> 64
    low = n & ((1 << 64) - 1)
    # Convert to signed int64
    if high >= (1 << 63):
        high -= (1 << 64)
    if low >= (1 << 63):
        low -= (1 << 64)
    return high, low


def _pair_to_uuid(high: int, low: int) -> uuid.UUID:
    # Convert signed int64 back to unsigned
    if high < 0:
        high += (1 << 64)
    if low < 0:
        low += (1 << 64)
    n = (high << 64) | low
    return uuid.UUID(int=n)


# ── Index manager ─────────────────────────────────────────────────────────────

class IndexManager:
    """Singleton FAISS index manager."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._index: Optional[faiss.IndexFlatIP] = None
        # Parallel list: position i → uuid.UUID of chunk at FAISS id i
        self._id_map: List[uuid.UUID] = []
        self._dim: Optional[int] = None
        self._index_dir = Path(settings.faiss_index_dir)
        self._index_path = self._index_dir / "index.faiss"
        self._map_path = self._index_dir / "id_map.npy"
        self._load()

    # ── Public API ────────────────────────────────────────────────────────────

    def add_chunks(self, chunk_ids: List[uuid.UUID], embeddings: np.ndarray) -> None:
        """Add new chunks to the index (append-only during ingestion)."""
        if len(chunk_ids) == 0:
            return

        with self._lock:
            if self._index is None or self._dim != embeddings.shape[1]:
                faiss = _get_faiss()
                self._index = faiss.IndexFlatIP(embeddings.shape[1])
                self._dim = embeddings.shape[1]
                self._id_map = []

            self._index.add(embeddings.astype(np.float32))
            self._id_map.extend(chunk_ids)
            self._persist()

    def remove_chunks(self, chunk_ids_to_remove: List[uuid.UUID]) -> None:
        """Remove chunks from the index by rebuilding without the given IDs."""
        if not chunk_ids_to_remove:
            return

        remove_set = set(chunk_ids_to_remove)

        with self._lock:
            if self._index is None or self._index.ntotal == 0:
                return

            # Reconstruct all vectors
            all_vectors = np.zeros((self._index.ntotal, self._index.d), dtype=np.float32)
            for i in range(self._index.ntotal):
                all_vectors[i] = self._index.reconstruct(i)

            keep_indices = [i for i, uid in enumerate(self._id_map) if uid not in remove_set]
            if not keep_indices:
                faiss = _get_faiss()
                self._index = faiss.IndexFlatIP(self._index.d)
                self._id_map = []
                self._persist()
                return

            kept_vectors = all_vectors[keep_indices]
            faiss = _get_faiss()
            new_index = faiss.IndexFlatIP(self._index.d)
            new_index.add(kept_vectors)
            self._index = new_index
            self._id_map = [self._id_map[i] for i in keep_indices]
            self._persist()

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int,
        threshold: float,
    ) -> List[Tuple[uuid.UUID, float]]:
        """
        Returns list of (chunk_uuid, similarity_score) for the top-k results
        above the threshold, sorted by descending score.
        """
        with self._lock:
            if self._index is None or self._index.ntotal == 0:
                return []
            k = min(top_k, self._index.ntotal)
            scores, indices = self._index.search(query_vector.astype(np.float32), k)
            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx < 0 or idx >= len(self._id_map):
                    continue
                if float(score) < threshold:
                    continue
                results.append((self._id_map[idx], float(score)))
            return results

    def rebuild(self, chunk_ids: List[uuid.UUID], embeddings: np.ndarray) -> None:
        """Completely rebuild the index from scratch."""
        faiss = _get_faiss()
        with self._lock:
            if embeddings.shape[0] == 0:
                self._index = faiss.IndexFlatIP(embeddings.shape[1] if embeddings.ndim == 2 else 384)
                self._id_map = []
                self._persist()
                return
            new_index = faiss.IndexFlatIP(embeddings.shape[1])
            new_index.add(embeddings.astype(np.float32))
            self._index = new_index
            self._id_map = list(chunk_ids)
            self._persist()

    @property
    def total_vectors(self) -> int:
        with self._lock:
            return self._index.ntotal if self._index else 0

    # ── Persistence ───────────────────────────────────────────────────────────

    def _persist(self) -> None:
        """Write index and id_map atomically."""
        self._index_dir.mkdir(parents=True, exist_ok=True)
        if self._index is None:
            return

        # Write index
        tmp_index = str(self._index_path) + ".tmp"
        faiss = _get_faiss()
        faiss.write_index(self._index, tmp_index)
        os.replace(tmp_index, str(self._index_path))

        # Write id_map as (N, 2) int64 array
        pairs = np.array([_uuid_to_pair(u) for u in self._id_map], dtype=np.int64)
        if pairs.ndim == 1:
            pairs = pairs.reshape(0, 2)
        tmp_map = str(self._map_path) + ".tmp"
        np.save(tmp_map, pairs)
        os.replace(tmp_map + ".npy" if not tmp_map.endswith(".npy") else tmp_map, str(self._map_path))
        logger.debug("FAISS index persisted: %d vectors", self._index.ntotal)

    def _load(self) -> None:
        """Load index and id_map from disk if they exist."""
        if self._index_path.exists() and self._map_path.exists():
            try:
                faiss = _get_faiss()
                self._index = faiss.read_index(str(self._index_path))
                pairs = np.load(str(self._map_path))  # (N, 2) int64
                self._id_map = [_pair_to_uuid(int(h), int(l)) for h, l in pairs]
                self._dim = self._index.d
                logger.info(
                    "FAISS index loaded: %d vectors (dim=%d)", self._index.ntotal, self._dim
                )
            except Exception as exc:
                logger.warning("Could not load FAISS index: %s — starting fresh", exc)
                self._index = None
                self._id_map = []
        else:
            logger.info("No existing FAISS index found — will create on first ingestion")


# ── Singleton ─────────────────────────────────────────────────────────────────
_manager: Optional[IndexManager] = None
_init_lock = threading.Lock()


def get_index_manager() -> IndexManager:
    global _manager
    if _manager is None:
        with _init_lock:
            if _manager is None:
                _manager = IndexManager()
    return _manager
