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


class SearchRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Question text to search with")
    limit: int = Field(default=5, ge=1, le=20, description="Maximum number of pages to return")


class SearchResult(BaseModel):
    pdf_name: str
    page_number: int
    excerpt: str
    similarity_score: float


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Question text to answer")
    limit: int = Field(default=5, ge=1, le=10, description="Maximum number of source pages to use")


class ReferencePage(BaseModel):
    pdf_name: str
    page_number: int
    excerpt: str
    similarity_score: float


class ChatResponse(BaseModel):
    answer: str
    references: list[ReferencePage]
