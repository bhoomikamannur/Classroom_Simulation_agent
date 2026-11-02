from pathlib import Path
from typing import Any

import chromadb

from backend.app.rag.embeddings import embed_texts, embed_query


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHROMA_PATH = PROJECT_ROOT / "data" / "chroma"

_client = chromadb.PersistentClient(path=str(CHROMA_PATH))
_collection = _client.get_or_create_collection(
    name="course_materials",
    metadata={"description": "Faculty-provided course material chunks"},
)


def add_chunks(chunks: list[dict[str, Any]]) -> int:
    """Embed and store chunks, requiring explicit course ownership metadata."""
    if not chunks:
        return 0

    for item in chunks:
        metadata = item.get("metadata") or {}
        required = ("document_id", "course_id", "professor_id")
        if any(not metadata.get(key) for key in required):
            raise ValueError(
                "Every chunk must include document_id, course_id and professor_id."
            )

    texts = [item["text"] for item in chunks]
    embeddings = embed_texts(texts)
    ids = [
        f"{item['metadata']['document_id']}-{index}"
        for index, item in enumerate(chunks)
    ]

    # Deterministic IDs make a retry idempotent for a given document.
    _collection.upsert(
        ids=ids,
        documents=texts,
        embeddings=embeddings,
        metadatas=[item["metadata"] for item in chunks],
    )
    return len(chunks)


def delete_document_chunks(document_id: str) -> int:
    """Delete every vector belonging to one uploaded document."""
    existing = _collection.get(
        where={"document_id": document_id},
        include=[],
    )
    ids = existing.get("ids", [])
    if ids:
        _collection.delete(ids=ids)
    return len(ids)


def search(
    query: str,
    course_id: str,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Search only chunks belonging to the specified course."""
    if top_k < 1:
        raise ValueError("top_k must be at least 1")
    if not course_id or not course_id.strip():
        raise ValueError("course_id is required for course-scoped retrieval.")

    query_embedding = embed_query(query)
    result = _collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where={"course_id": course_id.strip()},
        include=["documents", "metadatas", "distances"],
    )

    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]

    return [
        {"text": document, "metadata": metadata, "distance": distance}
        for document, metadata, distance in zip(documents, metadatas, distances)
    ]
