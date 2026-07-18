"""Pydantic schemas for chat endpoints."""

from datetime import datetime

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    sources: list[str]


class HistoryMessage(BaseModel):
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}
