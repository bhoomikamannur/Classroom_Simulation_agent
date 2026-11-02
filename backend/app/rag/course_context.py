from typing import Any

from backend.app.rag.retriever import retrieve


def build_course_context(
    query: str,
    course_id: str,
    top_k: int = 5,
    relevance_threshold: float = 0.85,
) -> str | None:
    """Build context only from the specified course's material."""
    if not query or not query.strip():
        return None

    results: list[dict[str, Any]] = retrieve(
        query=query,
        course_id=course_id,
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
        location = f", page {page}" if page is not None else (
            f", slide {slide}" if slide is not None else ""
        )
        context_parts.append(f"[Source {index}: {source_name}{location}]\n{text}")

    return "\n\n".join(context_parts) if context_parts else None
