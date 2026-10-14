"""PDF text extraction using PyMuPDF (fitz).

Each page is extracted independently.  Pages with fewer than MIN_CHARS
characters are flagged as likely-scanned.  If the majority of pages are
below the threshold the whole document is rejected.
"""
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

# A page is considered "text-bearing" if it has at least this many characters
MIN_CHARS_PER_PAGE = 30
# If this fraction of pages lack text, the document is considered scanned
SCANNED_THRESHOLD = 0.6


@dataclass
class PageText:
    page_number: int  # 1-based
    text: str


@dataclass
class ExtractionResult:
    pages: List[PageText] = field(default_factory=list)
    page_count: int = 0
    is_scanned: bool = False
    scanned_page_ratio: float = 0.0
    error: str = ""


def _clean_text(raw: str) -> str:
    """
    Light cleaning that preserves policy content:
    - Normalise Unicode whitespace
    - Collapse runs of 3+ blank lines to 2
    - Strip leading/trailing whitespace per paragraph
    """
    # Normalise non-breaking spaces and similar
    text = raw.replace("\u00a0", " ").replace("\u2019", "'").replace("\u2018", "'")
    text = re.sub(r"[ \t]+", " ", text)           # collapse horizontal whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)         # collapse excessive blank lines
    text = "\n".join(line.rstrip() for line in text.splitlines())
    return text.strip()


def extract_pages(pdf_path: str | Path) -> ExtractionResult:
    """Extract text from every page of a PDF and detect scanned-only documents."""
    result = ExtractionResult()
    try:
        doc = fitz.open(str(pdf_path))
    except Exception as exc:
        result.error = f"Could not open PDF: {exc}"
        logger.error(result.error)
        return result

    result.page_count = len(doc)
    empty_pages = 0

    for i in range(result.page_count):
        page = doc[i]
        raw = page.get_text("text")
        cleaned = _clean_text(raw)
        if len(cleaned) < MIN_CHARS_PER_PAGE:
            empty_pages += 1
        result.pages.append(PageText(page_number=i + 1, text=cleaned))

    doc.close()

    if result.page_count > 0:
        ratio = empty_pages / result.page_count
        result.scanned_page_ratio = ratio
        result.is_scanned = ratio >= SCANNED_THRESHOLD

    return result
