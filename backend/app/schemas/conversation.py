"""Conversation, message, citation schemas."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CitationOut(BaseModel):
    id: UUID
    document_title: str
    document_version: int
    page_number: int
    excerpt: str
    similarity_score: Optional[float]
    source_deleted: bool

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    id: UUID
    role: str
    content: str
    insufficient_evidence: bool
    created_at: datetime
    citations: list[CitationOut] = []

    model_config = {"from_attributes": True}


class ConversationOut(BaseModel):
    id: UUID
    title: Optional[str]
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    model_config = {"from_attributes": True}


class ConversationDetailOut(BaseModel):
    id: UUID
    title: Optional[str]
    created_at: datetime
    updated_at: datetime
    messages: list[MessageOut] = []

    model_config = {"from_attributes": True}


class ConversationListOut(BaseModel):
    items: list[ConversationOut]
    total: int


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)


class AskResponse(BaseModel):
    message_id: UUID
    answer: str
    citations: list[CitationOut]
    insufficient_evidence: bool
    conversation_id: UUID
