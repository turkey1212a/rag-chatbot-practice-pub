from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row

from app.config import get_settings


def get_connection() -> psycopg.Connection:
    return psycopg.connect(get_settings().database_url, row_factory=dict_row)


@contextmanager
def db_cursor(commit: bool = False) -> Iterator[psycopg.Cursor]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            yield cur
        if commit:
            conn.commit()


def init_db() -> None:
    settings = get_settings()
    dimensions = settings.embedding_dimensions
    if dimensions <= 0:
        raise ValueError("EMBEDDING_DIMENSIONS must be a positive integer")

    with db_cursor(commit=True) as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                file_name text NOT NULL UNIQUE,
                source_path text,
                page_count integer NOT NULL DEFAULT 0,
                created_at timestamptz NOT NULL DEFAULT now()
            )
            """
        )
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS page_chunks (
                id bigserial PRIMARY KEY,
                document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                file_name text NOT NULL,
                page_number integer NOT NULL,
                chunk_text text NOT NULL,
                embedding vector({dimensions}) NOT NULL,
                created_at timestamptz NOT NULL DEFAULT now(),
                UNIQUE (document_id, page_number)
            )
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_page_chunks_document_id
            ON page_chunks (document_id)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_page_chunks_embedding_cosine
            ON page_chunks
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
            """
        )
