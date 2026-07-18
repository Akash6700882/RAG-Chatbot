"""Pydantic schemas for document ingestion endpoints."""

from datetime import datetime

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    chunk_count: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
