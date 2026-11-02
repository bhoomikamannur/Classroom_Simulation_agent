from typing import Any

from backend.app.rag.vector_store import search


RELEVANCE_THRESHOLD = 0.85


def retrieve(
    query: str,
    course_id: str,
    top_k: int = 5,
    relevance_threshold: float = RELEVANCE_THRESHOLD,
) -> list[dict[str, Any]]:
    """Retrieve sufficiently relevant chunks from exactly one course."""
    results = search(query, course_id=course_id, top_k=top_k)
    return [
        result
        for result in results
        if result.get("distance", float("inf")) <= relevance_threshold
    ]
