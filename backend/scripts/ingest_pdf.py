import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.ingest import ingest_pdf  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a PDF into PostgreSQL + pgvector")
    parser.add_argument("pdf_path", help="Path to the PDF file")
    args = parser.parse_args()

    result = ingest_pdf(args.pdf_path)
    print(f"document_id={result.document_id}")
    print(f"file_name={result.file_name}")
    print(f"page_count={result.page_count}")
    print(f"stored_pages={result.stored_pages}")
    print(f"skipped_pages={result.skipped_pages}")


if __name__ == "__main__":
    main()
