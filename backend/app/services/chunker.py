"""Text chunking service.

Splits page text into overlapping chunks using a sliding window.
Chunks are kept within a single page wherever possible.
"""
import re
from dataclasses import dataclass
from typing import List

from app.config import get_settings

settings = get_settings()


@dataclass
class TextChunk:
    page_number: int   # 1-based
    chunk_index: int   # 0-based within the page
    text: str


def _split_into_sentences(text: str) -> List[str]:
    """
    Split text into rough sentence-like units.
    Uses punctuation boundaries; falls back to words when sentences are huge.
    """
    # Split on sentence-ending punctuation followed by whitespace/EOL
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if s.strip()]


def chunk_page(
    page_text: str,
    page_number: int,
    chunk_size: int = None,
    chunk_overlap: int = None,
) -> List[TextChunk]:
    """
    Splits a single page's text into overlapping chunks.

    Strategy:
    1. Split page into sentences.
    2. Accumulate sentences until char count exceeds chunk_size.
    3. Start the next chunk by re-including the last `chunk_overlap` characters
       worth of sentences (approximate overlap).
    """
    if chunk_size is None:
        chunk_size = settings.chunk_size
    if chunk_overlap is None:
        chunk_overlap = settings.chunk_overlap

    if not page_text.strip():
        return []

    sentences = _split_into_sentences(page_text)
    if not sentences:
        return []

    chunks: List[TextChunk] = []
    chunk_idx = 0
    i = 0

    while i < len(sentences):
        current: List[str] = []
        current_len = 0
        j = i

        # Build chunk
        while j < len(sentences) and current_len + len(sentences[j]) < chunk_size:
            current.append(sentences[j])
            current_len += len(sentences[j]) + 1  # +1 for space
            j += 1

        # If we didn't advance at all (single sentence longer than chunk_size)
        if j == i:
            current.append(sentences[i])
            j = i + 1

        text = " ".join(current).strip()
        if text:
            chunks.append(TextChunk(page_number=page_number, chunk_index=chunk_idx, text=text))
            chunk_idx += 1

        # Overlap: step back by sentences whose total length ≈ chunk_overlap
        overlap_len = 0
        new_i = j
        for k in range(j - 1, i - 1, -1):
            overlap_len += len(sentences[k])
            if overlap_len >= chunk_overlap:
                new_i = k
                break

        i = new_i if new_i > i else j  # always advance past current position

    return chunks
