"""End-to-end RAG pipeline for answering student questions."""
import logging
import uuid
from dataclasses import dataclass, field
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.rag.retriever import RetrievedChunk, retrieve
from app.rag.groq_client import generate_answer
from app.rag.embedder import embed_query

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class CitationResult:
    chunk_id: uuid.UUID
    document_title: str
    document_version: int
    page_number: int
    excerpt: str
    similarity_score: float
    storage_path: str


@dataclass
class RAGResult:
    answer: str
    citations: List[CitationResult] = field(default_factory=list)
    insufficient_evidence: bool = False
    error: Optional[str] = None


async def _resolve_standalone_query(
    question: str,
    history: List[dict],
) -> str:
    """
    If there's conversation history, use a lightweight prompt to rephrase
    a follow-up question into a self-contained retrieval query.
    Returns the original question when history is empty.
    """
    if not history:
        return question

    # Simple heuristic: if the question contains pronouns or references,
    # prepend context. For a production system you'd call an LLM here.
    # We do a lightweight version: append the last user message as context.
    last_user = next(
        (h["content"] for h in reversed(history) if h.get("role") == "user"), ""
    )
    if last_user and any(
        w in question.lower() for w in ["it", "that", "this", "they", "those", "the rule", "the policy"]
    ):
        return f"{last_user} {question}"
    return question


async def answer_question(
    question: str,
    db: AsyncSession,
    conversation_history: Optional[List[dict]] = None,
) -> RAGResult:
    """
    Full RAG pipeline:
    1. Resolve follow-up into standalone query.
    2. Retrieve relevant chunks.
    3. Call Groq with context.
    4. Map cited source IDs back to chunk metadata.
    5. Return structured result.
    """
    history = conversation_history or []

    # Step 1: Standalone query resolution
    retrieval_query = await _resolve_standalone_query(question, history)

    # Step 2: Retrieve
    chunks: List[RetrievedChunk] = await retrieve(retrieval_query, db)

    if not chunks:
        return RAGResult(
            answer="This information is not available in the uploaded college documents.",
            insufficient_evidence=True,
        )

    # Step 3: Build passages for Groq
    passages = []
    chunk_map: dict[str, RetrievedChunk] = {}
    for chunk in chunks:
        source_id = str(chunk.chunk_id)
        passages.append(
            {
                "id": source_id,
                "title": chunk.document_title,
                "version": chunk.document_version,
                "page": chunk.page_number,
                "text": chunk.text,
            }
        )
        chunk_map[source_id] = chunk

    # Step 4: Generate answer
    try:
        groq_result = await generate_answer(
            question=question,
            passages=passages,
            conversation_history=history[-6:],  # last 3 turns
        )
    except ValueError as exc:
        return RAGResult(answer="", error=str(exc), insufficient_evidence=True)

    # Step 5: Validate cited source IDs
    valid_source_ids = set(chunk_map.keys())
    cited_ids = [sid for sid in groq_result["raw_source_ids"] if sid in valid_source_ids]

    # If the model cited nothing valid, use top chunks as citations anyway
    if not cited_ids and not groq_result["insufficient_evidence"]:
        cited_ids = [str(chunks[0].chunk_id)]

    citations: List[CitationResult] = []
    seen = set()
    for sid in cited_ids:
        if sid in seen:
            continue
        seen.add(sid)
        chunk = chunk_map[sid]
        citations.append(
            CitationResult(
                chunk_id=chunk.chunk_id,
                document_title=chunk.document_title,
                document_version=chunk.document_version,
                page_number=chunk.page_number,
                excerpt=chunk.text[:400],
                similarity_score=chunk.similarity_score,
                storage_path=chunk.storage_path,
            )
        )

    return RAGResult(
        answer=groq_result["answer"],
        citations=citations,
        insufficient_evidence=groq_result["insufficient_evidence"],
    )
