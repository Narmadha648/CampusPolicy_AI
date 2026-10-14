"""Admin-only endpoints: statistics."""
import logging
import re
from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.conversation import Message
from app.models.document import Document, DocumentStatus, DocumentVersion
from app.models.job import JobStatus, ProcessingJob
from app.models.user import User, UserRole
from app.schemas.admin import StatsDetailOut, TopicStat
from app.services.deps import require_admin

logger = logging.getLogger(__name__)
router = APIRouter()

# Simple keyword → topic grouping for FAQ statistics
_TOPIC_KEYWORDS = {
    "Attendance": ["attendance", "absent", "leave", "present"],
    "Examinations": ["exam", "examination", "test", "paper", "revaluation", "marks", "grade"],
    "Fees": ["fee", "fees", "payment", "tuition", "scholarship"],
    "Academic Calendar": ["calendar", "schedule", "holiday", "semester", "break", "vacation"],
    "Student Handbook": ["handbook", "conduct", "rules", "regulation", "policy"],
    "Admissions": ["admission", "enroll", "enrolment", "application"],
}


def _classify_topic(question: str) -> str:
    q_lower = question.lower()
    for topic, keywords in _TOPIC_KEYWORDS.items():
        if any(kw in q_lower for kw in keywords):
            return topic
    return "General"


@router.get("/stats", response_model=StatsDetailOut)
async def get_stats(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    # Ready documents
    ready_result = await db.execute(
        select(func.count(DocumentVersion.id))
        .join(Document, DocumentVersion.document_id == Document.id)
        .where(DocumentVersion.is_active == True)
        .where(DocumentVersion.status == DocumentStatus.ready)
        .where(Document.is_deleted == False)
    )
    ready_docs = ready_result.scalar() or 0

    # Student count
    student_result = await db.execute(
        select(func.count(User.id)).where(User.role == UserRole.student).where(User.is_active == True)
    )
    student_count = student_result.scalar() or 0

    # Total questions (user messages)
    questions_result = await db.execute(
        select(func.count(Message.id)).where(Message.role == "user")
    )
    total_questions = questions_result.scalar() or 0

    # Total conversations
    from app.models.conversation import Conversation
    conv_result = await db.execute(select(func.count(Conversation.id)))
    total_conversations = conv_result.scalar() or 0

    # Pending jobs
    pending_result = await db.execute(
        select(func.count(ProcessingJob.id)).where(
            ProcessingJob.status.in_([JobStatus.queued, JobStatus.running])
        )
    )
    pending_jobs = pending_result.scalar() or 0

    # Failed jobs
    failed_result = await db.execute(
        select(func.count(ProcessingJob.id)).where(ProcessingJob.status == JobStatus.failed)
    )
    failed_jobs = failed_result.scalar() or 0

    # Topic stats (last 500 user messages)
    msgs_result = await db.execute(
        select(Message.content)
        .where(Message.role == "user")
        .order_by(Message.created_at.desc())
        .limit(500)
    )
    questions = msgs_result.scalars().all()
    topic_counts: Counter = Counter(_classify_topic(q) for q in questions)
    top_topics = [
        TopicStat(topic=t, count=c)
        for t, c in topic_counts.most_common(8)
    ]

    return StatsDetailOut(
        ready_documents=ready_docs,
        student_count=student_count,
        total_questions=total_questions,
        total_conversations=total_conversations,
        pending_jobs=pending_jobs,
        failed_jobs=failed_jobs,
        top_topics=top_topics,
    )
