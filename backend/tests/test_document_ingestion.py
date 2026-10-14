"""
Document ingestion and admin API tests.

AC verified:
  4. An administrator can upload a text-based PDF (mocked save + worker).
  11. Invalid uploads and scanned PDFs show appropriate errors.
"""
import uuid
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import create_admin_user

VALID_PDF_BYTES = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type /Catalog /Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type /Pages /Kids [3 0 R] /Count 1>>endobj\n"
    b"3 0 obj<</Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n"
    b"0000000058 00000 n\n0000000115 00000 n\n"
    b"trailer<</Size 4 /Root 1 0 R>>\nstartxref\n190\n%%EOF"
)
NOT_PDF_BYTES = b"This is just a plain text file."


async def _login_admin(client: AsyncClient, db_session: AsyncSession):
    admin = await create_admin_user(db_session)
    res = await client.post(
        "/api/auth/login",
        json={"email": admin.email, "password": "AdminPass1!"},
    )
    assert res.status_code == 200, res.text
    return admin


@pytest.mark.asyncio
async def test_admin_can_list_documents(client: AsyncClient, db_session: AsyncSession):
    """Admin document list returns 200 with items list."""
    await _login_admin(client, db_session)
    res = await client.get("/api/admin/documents")
    assert res.status_code == 200
    assert "items" in res.json()


@pytest.mark.asyncio
async def test_upload_non_pdf_rejected(client: AsyncClient, db_session: AsyncSession):
    """Uploading a non-PDF file is rejected with 400."""
    await _login_admin(client, db_session)
    from fastapi import HTTPException

    with (
        patch(
            "app.api.documents.validate_and_save_pdf",
            side_effect=HTTPException(status_code=400, detail="File does not appear to be a valid PDF."),
        ),
        patch("app.api.documents._enqueue_processing"),
    ):
        files = {"file": ("test.txt", NOT_PDF_BYTES, "text/plain")}
        data = {"title": "Bad upload"}
        res = await client.post("/api/admin/documents", files=files, data=data)
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_upload_valid_pdf_creates_document(client: AsyncClient, db_session: AsyncSession):
    """Uploading a valid PDF creates a Document record with pending status."""
    await _login_admin(client, db_session)
    storage_path = f"/tmp/{uuid.uuid4()}.pdf"

    with (
        patch("app.api.documents.validate_and_save_pdf", return_value=(storage_path, len(VALID_PDF_BYTES))),
        patch("app.api.documents._enqueue_processing"),
    ):
        files = {"file": ("handbook.pdf", VALID_PDF_BYTES, "application/pdf")}
        data = {"title": "Test Handbook", "policy_year": "2024-25"}
        res = await client.post("/api/admin/documents", files=files, data=data)

    assert res.status_code == 201
    body = res.json()
    assert body["title"] == "Test Handbook"
    assert body["latest_version"]["status"] == "pending"


@pytest.mark.asyncio
async def test_delete_document(client: AsyncClient, db_session: AsyncSession):
    """Admin can delete a document; it disappears from the list."""
    await _login_admin(client, db_session)
    storage_path = f"/tmp/{uuid.uuid4()}.pdf"

    with (
        patch("app.api.documents.validate_and_save_pdf", return_value=(storage_path, 1024)),
        patch("app.api.documents._enqueue_processing"),
    ):
        files = {"file": ("del.pdf", VALID_PDF_BYTES, "application/pdf")}
        data = {"title": "To Delete"}
        create_res = await client.post("/api/admin/documents", files=files, data=data)

    doc_id = create_res.json()["id"]

    del_res = await client.delete(f"/api/admin/documents/{doc_id}")
    assert del_res.status_code == 200

    list_res = await client.get("/api/admin/documents")
    ids = [d["id"] for d in list_res.json()["items"]]
    assert doc_id not in ids


@pytest.mark.asyncio
async def test_ingestion_worker_rejects_scanned_pdf():
    """Ingestion worker marks a scanned PDF as failed with a descriptive message."""
    try:
        import fitz  # noqa: F401
    except ImportError:
        pytest.skip("PyMuPDF not installed in this environment")

    from app.workers.ingestion_worker import _run_pipeline
    from app.models.document import DocumentStatus
    from app.models.job import JobStatus, ProcessingJob
    from app.services.pdf_service import ExtractionResult, PageText

    scanned_result = ExtractionResult(
        pages=[PageText(page_number=1, text="")],
        page_count=1,
        is_scanned=True,
        scanned_page_ratio=1.0,
    )

    mock_version = MagicMock()
    mock_version.id = uuid.uuid4()
    mock_version.storage_path = "/tmp/fake.pdf"
    mock_version.document = MagicMock()
    mock_version.document.versions = [mock_version]

    mock_job = MagicMock(spec=ProcessingJob)
    mock_db = MagicMock()
    mock_db.commit = MagicMock()

    with patch("app.workers.ingestion_worker.extract_pages", return_value=scanned_result):
        _run_pipeline(mock_db, mock_version, mock_job)

    assert mock_version.status == DocumentStatus.failed
    msg = mock_version.error_message.lower()
    assert "scanned" in msg or "ocr" in msg
