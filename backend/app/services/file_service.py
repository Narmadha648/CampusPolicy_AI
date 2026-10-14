"""File storage helpers — safe path generation, validation, and cleanup."""
import logging
import mimetypes
import os
import re
import uuid
from pathlib import Path
from typing import Tuple

from fastapi import UploadFile, HTTPException, status

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# PDF magic bytes
_PDF_MAGIC = b"%PDF"


def _safe_upload_dir() -> Path:
    p = Path(settings.upload_dir).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _make_storage_path(document_id: uuid.UUID, version: int, suffix: str = ".pdf") -> Path:
    """Returns an application-generated path that cannot escape the upload dir."""
    upload_dir = _safe_upload_dir()
    filename = f"{document_id}_v{version}{suffix}"
    # Verify no path traversal (redundant but defensive)
    dest = (upload_dir / filename).resolve()
    if not str(dest).startswith(str(upload_dir)):
        raise ValueError("Path traversal detected")
    return dest


async def validate_and_save_pdf(
    upload: UploadFile,
    document_id: uuid.UUID,
    version_number: int,
) -> Tuple[Path, int]:
    """
    Validates a PDF upload (type, magic bytes, size) then saves it.
    Returns (storage_path, file_size_bytes).
    Raises HTTPException on any validation failure.
    """
    # 1. Content-type check (advisory)
    content_type = upload.content_type or ""
    if content_type not in ("application/pdf", "application/octet-stream", ""):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Expected a PDF file, received content-type '{content_type}'.",
        )

    # 2. Read file into memory (up to limit + 1 to detect over-size)
    max_bytes = settings.max_upload_bytes
    data = await upload.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {settings.max_upload_mb} MB limit.",
        )
    if len(data) < 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="File is empty or too small."
        )

    # 3. Magic bytes check
    if not data.startswith(_PDF_MAGIC):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File does not appear to be a valid PDF (missing %PDF header).",
        )

    # 4. Save
    dest = _make_storage_path(document_id, version_number)
    dest.write_bytes(data)
    logger.info("Saved upload → %s (%d bytes)", dest, len(data))
    return dest, len(data)


def delete_file(storage_path: str) -> None:
    """Deletes a stored file, logging but not raising if already absent."""
    try:
        Path(storage_path).unlink(missing_ok=True)
        logger.info("Deleted file %s", storage_path)
    except Exception as exc:
        logger.warning("Could not delete %s: %s", storage_path, exc)
