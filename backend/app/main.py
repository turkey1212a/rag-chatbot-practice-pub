from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI

from app.config import get_settings
from app.db import db_cursor, init_db
from app.embeddings import create_embedding, vector_literal
from app.ingest import ingest_pdf
from app.schemas import (
    ChatRequest,
    ChatResponse,
    DocumentSummary,
    HealthResponse,
    IngestPathRequest,
    IngestResponse,
    ReferencePage,
    SearchRequest,
    SearchResult,
)

app = FastAPI(title="RAG PDF Ingestion API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200", "http://127.0.0.1:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _excerpt(text: str, max_length: int = 280) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_length:
        return normalized
    return normalized[: max_length - 3].rstrip() + "..."


def _search_page_rows(question: str, limit: int) -> list[dict]:
    query_embedding = vector_literal(create_embedding(question))
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT
                file_name AS pdf_name,
                page_number,
                chunk_text,
                1 - (embedding <=> %s::vector) AS similarity_score
            FROM page_chunks
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (query_embedding, query_embedding, limit),
        )
        return cur.fetchall()


def _reference_pages(rows: list[dict]) -> list[ReferencePage]:
    return [
        ReferencePage(
            pdf_name=row["pdf_name"],
            page_number=row["page_number"],
            excerpt=_excerpt(row["chunk_text"]),
            similarity_score=float(row["similarity_score"]),
        )
        for row in rows
    ]


def _build_context(rows: list[dict]) -> str:
    parts = []
    for index, row in enumerate(rows, start=1):
        context_text = row["chunk_text"][:4000]
        parts.append(
            "\n".join(
                [
                    f"[{index}] PDF: {row['pdf_name']}",
                    f"Page: {row['page_number']}",
                    f"Similarity: {float(row['similarity_score']):.4f}",
                    "Text:",
                    context_text,
                ]
            )
        )
    return "\n\n---\n\n".join(parts)


def _generate_answer(question: str, context: str) -> str:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model=settings.openai_chat_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a careful RAG assistant. Answer only from the provided PDF page context. "
                    "Do not use outside knowledge and do not guess. If the context does not contain "
                    "enough information to answer, say in Japanese that the uploaded documents do not "
                    "contain enough information. Keep the answer concise and include page citations like "
                    "（PDF名 p.ページ番号） when stating facts."
                ),
            },
            {
                "role": "user",
                "content": f"Question:\n{question}\n\nPDF page context:\n{context}",
            },
        ],
        temperature=0,
    )
    return response.choices[0].message.content or ""


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


@app.post("/search", response_model=list[SearchResult])
def search_similar_pages(request: SearchRequest) -> list[SearchResult]:
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question must not be empty")

    try:
        rows = _search_page_rows(question, request.limit)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return [
        SearchResult(
            pdf_name=reference.pdf_name,
            page_number=reference.page_number,
            excerpt=reference.excerpt,
            similarity_score=reference.similarity_score,
        )
        for reference in _reference_pages(rows)
    ]


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question must not be empty")

    try:
        rows = _search_page_rows(question, request.limit)
        references = _reference_pages(rows)
        if not rows:
            return ChatResponse(
                answer="アップロード済み資料に回答に必要な情報が見つかりませんでした。",
                references=[],
            )
        answer = _generate_answer(question, _build_context(rows))
        return ChatResponse(answer=answer, references=references)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
