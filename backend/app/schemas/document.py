"""Document schemas."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class DocumentVersionOut(BaseModel):
    id: UUID
    version_number: int
    original_filename: str
    file_size_bytes: int
    page_count: Optional[int]
    status: str
    error_message: Optional[str]
    is_active: bool
    uploaded_at: datetime
    processed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class DocumentOut(BaseModel):
    id: UUID
    title: str
    policy_year: Optional[str]
    description: Optional[str]
    created_at: datetime
    updated_at: datetime
    active_version: Optional[DocumentVersionOut] = None
    latest_version: Optional[DocumentVersionOut] = None

    model_config = {"from_attributes": True}


class DocumentListOut(BaseModel):
    items: list[DocumentOut]
    total: int


class JobOut(BaseModel):
    id: UUID
    version_id: UUID
    status: str
    attempt_count: int
    error_detail: Optional[str]
    queued_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]

    model_config = {"from_attributes": True}
