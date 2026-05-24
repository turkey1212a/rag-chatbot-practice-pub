from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

from app.config import get_settings
from app.db import db_cursor, init_db
from app.embeddings import create_embedding, vector_literal


@dataclass(frozen=True)
class IngestResult:
    document_id: str
    file_name: str
    page_count: int
    stored_pages: int
    skipped_pages: list[int]


def _extract_pages(pdf_path: Path) -> tuple[int, list[tuple[int, str]], list[int]]:
    settings = get_settings()
    reader = PdfReader(str(pdf_path))
    page_count = len(reader.pages)

    if page_count > settings.max_pdf_pages:
        raise ValueError(
            f"PDF has {page_count} pages, which exceeds MAX_PDF_PAGES={settings.max_pdf_pages}"
        )

    extracted_pages: list[tuple[int, str]] = []
    skipped_pages: list[int] = []

    for index, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if not text:
            skipped_pages.append(index)
            continue
        extracted_pages.append((index, text))

    return page_count, extracted_pages, skipped_pages


def ingest_pdf(pdf_path: str | Path, display_name: str | None = None) -> IngestResult:
    init_db()

    path = Path(pdf_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError("Only PDF files can be ingested")

    file_name = Path(display_name).name if display_name else path.name
    page_count, pages, skipped_pages = _extract_pages(path)

    if not pages:
        raise ValueError("No extractable text was found in this PDF")

    embeddings: list[tuple[int, str, list[float]]] = []
    for page_number, chunk_text in pages:
        embeddings.append((page_number, chunk_text, create_embedding(chunk_text)))

    with db_cursor(commit=True) as cur:
        cur.execute("DELETE FROM documents WHERE file_name = %s", (file_name,))
        cur.execute(
            """
            INSERT INTO documents (file_name, source_path, page_count)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (file_name, str(path), page_count),
        )
        document_id = str(cur.fetchone()["id"])

        for page_number, chunk_text, embedding in embeddings:
            cur.execute(
                """
                INSERT INTO page_chunks (
                    document_id,
                    file_name,
                    page_number,
                    chunk_text,
                    embedding
                )
                VALUES (%s, %s, %s, %s, %s::vector)
                """,
                (
                    document_id,
                    file_name,
                    page_number,
                    chunk_text,
                    vector_literal(embedding),
                ),
            )

    return IngestResult(
        document_id=document_id,
        file_name=file_name,
        page_count=page_count,
        stored_pages=len(embeddings),
        skipped_pages=skipped_pages,
    )
