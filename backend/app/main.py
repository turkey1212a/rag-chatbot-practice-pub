from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile

from app.config import get_settings
from app.db import db_cursor, init_db
from app.ingest import ingest_pdf
from app.schemas import DocumentSummary, HealthResponse, IngestPathRequest, IngestResponse

app = FastAPI(title="RAG PDF Ingestion API", version="0.1.0")


@app.on_event("startup")
def on_startup() -> None:
    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    init_db()


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    with db_cursor() as cur:
        cur.execute("SELECT 1")
    return HealthResponse(status="ok")


@app.post("/documents/upload", response_model=IngestResponse)
async def upload_document(file: UploadFile = File(...)) -> IngestResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF uploads are supported")

    settings = get_settings()
    safe_name = Path(file.filename).name
    destination = settings.upload_dir / safe_name

    try:
        with destination.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                out.write(chunk)
        return IngestResponse(**ingest_pdf(destination, display_name=safe_name).__dict__)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/documents/ingest", response_model=IngestResponse)
def ingest_document(request: IngestPathRequest) -> IngestResponse:
    try:
        return IngestResponse(**ingest_pdf(request.path).__dict__)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/documents", response_model=list[DocumentSummary])
def list_documents() -> list[DocumentSummary]:
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT
                d.id::text AS document_id,
                d.file_name,
                d.source_path,
                d.page_count,
                count(c.id)::int AS stored_pages,
                d.created_at::text AS created_at
            FROM documents d
            LEFT JOIN page_chunks c ON c.document_id = d.id
            GROUP BY d.id
            ORDER BY d.created_at DESC
            """
        )
        return [DocumentSummary(**row) for row in cur.fetchall()]


@app.get("/documents/{document_id}/chunks")
def list_document_chunks(document_id: str) -> list[dict]:
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT
                id,
                document_id::text AS document_id,
                file_name,
                page_number,
                length(chunk_text) AS text_length,
                created_at::text AS created_at
            FROM page_chunks
            WHERE document_id = %s
            ORDER BY page_number
            """,
            (document_id,),
        )
        return cur.fetchall()
