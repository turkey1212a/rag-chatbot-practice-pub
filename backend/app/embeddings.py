from openai import OpenAI

from app.config import get_settings


def create_embedding(text: str) -> list[float]:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    client = OpenAI(api_key=settings.openai_api_key)
    request = {
        "model": settings.openai_embedding_model,
        "input": text,
    }
    if settings.openai_embedding_model.startswith("text-embedding-3"):
        request["dimensions"] = settings.embedding_dimensions

    response = client.embeddings.create(**request)
    return response.data[0].embedding


def vector_literal(values: list[float]) -> str:
    return "[" + ",".join(str(value) for value in values) + "]"
