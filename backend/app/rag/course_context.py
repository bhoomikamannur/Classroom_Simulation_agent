
from typing import Any

from backend.app.rag.retriever import retrieve


def build_course_context(
    query: str,
    top_k: int = 5,
    relevance_threshold: float = 0.85,
) -> str | None:
    """Build course context from relevant retrieved course chunks."""

    if not query or not query.strip():
        return None

    results: list[dict[str, Any]] = retrieve(
        query=query,
        top_k=top_k,
        relevance_threshold=relevance_threshold,
    )

    if not results:
        return None

    context_parts = []

    for index, result in enumerate(results, start=1):
        text = result.get("text", "").strip()

        if not text:
            continue

        metadata = result.get("metadata") or {}
        source_name = metadata.get("source_name", "Unknown source")
        page = metadata.get("page")
        slide = metadata.get("slide")

        location = ""
        if page is not None:
            location = f", page {page}"
        elif slide is not None:
            location = f", slide {slide}"

        context_parts.append(
            f"[Source {index}: {source_name}{location}]\n{text}"
        )

    if not context_parts:
        return None

    return "\n\n".join(context_parts)
