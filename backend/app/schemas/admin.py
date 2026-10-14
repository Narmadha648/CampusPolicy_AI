"""Admin schemas."""
from pydantic import BaseModel


class StatsOut(BaseModel):
    ready_documents: int
    student_count: int
    total_questions: int
    total_conversations: int
    pending_jobs: int
    failed_jobs: int


class TopicStat(BaseModel):
    topic: str
    count: int


class StatsDetailOut(StatsOut):
    top_topics: list[TopicStat] = []
