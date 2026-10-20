from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, field_validator


def _as_utc(value: datetime) -> datetime:
    """SQLite stores datetimes without a timezone. Everything is saved as UTC, so label it as UTC again;
    otherwise the browser reads '2026-10-20T10:00:00' as LOCAL time and shows the wrong hour."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    filename: str
    file_hash: str
    size_bytes: int
    uploaded_at: datetime
    page_count: int
    char_count: int
    chunk_count: int
    status: str
    error_message: str | None = None
    embedding_model: str | None = None

    @field_validator("uploaded_at")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return _as_utc(v)


class UploadResult(BaseModel):
    filename: str
    outcome: str  # created | duplicate | failed | rejected
    message: str
    document: DocumentOut | None = None


class UploadResponse(BaseModel):
    results: list[UploadResult]
    request_id: str | None = None


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    timestamp: datetime
    kind: str
    message: str

    @field_validator("timestamp")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return _as_utc(v)


class StatsOut(BaseModel):
    total_documents: int
    ready_documents: int
    failed_documents: int
    total_pages: int
    total_chunks: int
    recent_documents: list[DocumentOut]
    recent_activity: list[ActivityOut]
    llm_configured: bool
