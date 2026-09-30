from typing import Any

from backend.app.rag.vector_store import search


RELEVANCE_THRESHOLD = 0.85


def retrieve(
    query: str,
    top_k: int = 5,
    relevance_threshold: float = RELEVANCE_THRESHOLD,
) -> list[dict[str, Any]]:
    """Retrieve course material that is sufficiently relevant to the query."""

    results = search(query, top_k=top_k)

    return [
        result
        for result in results
        if result.get("distance", float("inf")) <= relevance_threshold
    ]