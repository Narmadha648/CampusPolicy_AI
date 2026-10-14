"""Conversation endpoints: create, list, get, delete, post message (RAG)."""
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.conversation import Conversation, Message, MessageCitation
from app.models.document import Document, DocumentStatus, DocumentVersion
from app.rag.pipeline import answer_question
from app.schemas.conversation import (
    AskRequest,
    AskResponse,
    CitationOut,
    ConversationDetailOut,
    ConversationListOut,
    ConversationOut,
    MessageOut,
)
from app.services.deps import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


def _conv_to_out(conv: Conversation) -> ConversationOut:
    return ConversationOut(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        message_count=len(conv.messages) if conv.messages else 0,
    )


def _msg_to_out(msg: Message) -> MessageOut:
    return MessageOut(
        id=msg.id,
        role=msg.role,
        content=msg.content,
        insufficient_evidence=msg.insufficient_evidence,
        created_at=msg.created_at,
        citations=[CitationOut.model_validate(c) for c in (msg.citations or [])],
    )


# ── Create conversation ───────────────────────────────────────────────────────

@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conv = Conversation(user_id=current_user.id)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return ConversationOut(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        message_count=0,
    )


# ── List conversations ────────────────────────────────────────────────────────

@router.get("", response_model=ConversationListOut)
async def list_conversations(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
        .offset(skip)
        .limit(limit)
    )
    convs = result.scalars().all()

    count_result = await db.execute(
        select(Conversation).where(Conversation.user_id == current_user.id)
    )
    total = len(count_result.scalars().all())

    return ConversationListOut(items=[_conv_to_out(c) for c in convs], total=total)


# ── Get conversation detail ───────────────────────────────────────────────────

@router.get("/{conversation_id}", response_model=ConversationDetailOut)
async def get_conversation(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Conversation)
        .options(
            selectinload(Conversation.messages).selectinload(Message.citations)
        )
        .where(Conversation.id == conversation_id)
        .where(Conversation.user_id == current_user.id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return ConversationDetailOut(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=[_msg_to_out(m) for m in conv.messages],
    )


# ── Delete conversation ───────────────────────────────────────────────────────

@router.delete("/{conversation_id}", status_code=status.HTTP_200_OK)
async def delete_conversation(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .where(Conversation.user_id == current_user.id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await db.delete(conv)
    await db.commit()
    return {"message": "Conversation deleted"}


# ── Post message (RAG) ────────────────────────────────────────────────────────

@router.post("/{conversation_id}/messages", response_model=AskResponse)
async def post_message(
    conversation_id: uuid.UUID,
    body: AskRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify ownership
    result = await db.execute(
        select(Conversation)
        .options(
            selectinload(Conversation.messages).selectinload(Message.citations)
        )
        .where(Conversation.id == conversation_id)
        .where(Conversation.user_id == current_user.id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if any ready documents exist
    ready_result = await db.execute(
        select(DocumentVersion)
        .join(Document, DocumentVersion.document_id == Document.id)
        .where(DocumentVersion.is_active == True)
        .where(DocumentVersion.status == DocumentStatus.ready)
        .where(Document.is_deleted == False)
        .limit(1)
    )
    has_documents = ready_result.scalar_one_or_none() is not None

    if not has_documents:
        # Save the user message and return a system notice
        user_msg = Message(
            conversation_id=conv.id,
            role="user",
            content=body.question,
        )
        db.add(user_msg)
        await db.flush()

        notice = (
            "No college documents have been uploaded yet. "
            "Please ask your administrator to upload the relevant policy documents before asking questions."
        )
        assistant_msg = Message(
            conversation_id=conv.id,
            role="assistant",
            content=notice,
            insufficient_evidence=True,
        )
        db.add(assistant_msg)
        await db.commit()
        await db.refresh(assistant_msg)

        return AskResponse(
            message_id=assistant_msg.id,
            answer=notice,
            citations=[],
            insufficient_evidence=True,
            conversation_id=conv.id,
        )

    # Build conversation history for context
    history = [
        {"role": m.role, "content": m.content}
        for m in conv.messages[-10:]  # last 5 turns
    ]

    # Save user message first
    user_msg = Message(
        conversation_id=conv.id,
        role="user",
        content=body.question,
    )
    db.add(user_msg)
    await db.flush()

    # Run RAG pipeline
    rag_result = await answer_question(body.question, db, history)

    if rag_result.error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=rag_result.error,
        )

    # Save assistant message
    assistant_msg = Message(
        conversation_id=conv.id,
        role="assistant",
        content=rag_result.answer,
        insufficient_evidence=rag_result.insufficient_evidence,
    )
    db.add(assistant_msg)
    await db.flush()

    # Save citations
    citation_outs = []
    for cit in rag_result.citations:
        citation = MessageCitation(
            message_id=assistant_msg.id,
            chunk_id=cit.chunk_id,
            document_title=cit.document_title,
            document_version=cit.document_version,
            page_number=cit.page_number,
            excerpt=cit.excerpt,
            similarity_score=cit.similarity_score,
        )
        db.add(citation)
        citation_outs.append(
            CitationOut(
                id=citation.id,
                document_title=cit.document_title,
                document_version=cit.document_version,
                page_number=cit.page_number,
                excerpt=cit.excerpt,
                similarity_score=cit.similarity_score,
                source_deleted=False,
            )
        )

    # Update conversation title from first question if untitled
    if not conv.title and user_msg:
        conv.title = body.question[:100]

    await db.commit()
    await db.refresh(assistant_msg)

    return AskResponse(
        message_id=assistant_msg.id,
        answer=rag_result.answer,
        citations=citation_outs,
        insufficient_evidence=rag_result.insufficient_evidence,
        conversation_id=conv.id,
    )
