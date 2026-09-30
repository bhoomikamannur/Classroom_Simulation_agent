from pathlib import Path
from typing import Any
import uuid

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
    if not chunks:
        return 0

    texts = [item["text"] for item in chunks]
    embeddings = embed_texts(texts)

    ids = [
        f"{item['metadata'].get('source_name', 'document')}-"
        f"{item['metadata'].get('source_type', 'unknown')}-"
        f"{item['metadata'].get('page', item['metadata'].get('slide', 'x'))}-"
        f"{item['metadata'].get('chunk_index', 0)}-"
        f"{uuid.uuid4().hex[:8]}"
        for item in chunks
    ]

    _collection.add(
        ids=ids,
        documents=texts,
        embeddings=embeddings,
        metadatas=[item["metadata"] for item in chunks],
    )

    return len(chunks)


def search(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    if top_k < 1:
        raise ValueError("top_k must be at least 1")

    query_embedding = embed_query(query)

    result = _collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]

    return [
        {
            "text": document,
            "metadata": metadata,
            "distance": distance,
        }
        for document, metadata, distance in zip(documents, metadatas, distances)
    ]
