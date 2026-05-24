from pydantic import BaseModel, Field


class IngestPathRequest(BaseModel):
    path: str = Field(..., description="Path to a PDF file on the backend host/container")


class IngestResponse(BaseModel):
    document_id: str
    file_name: str
    page_count: int
    stored_pages: int
    skipped_pages: list[int]


class DocumentSummary(BaseModel):
    document_id: str
    file_name: str
    source_path: str | None
    page_count: int
    stored_pages: int
    created_at: str


class HealthResponse(BaseModel):
    status: str
