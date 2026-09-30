from typing import Any


def chunk_text(
    documents: list[dict[str, Any]],
    chunk_size: int = 1800,
    overlap: int = 250,
) -> list[dict[str, Any]]:
    """Create simple overlapping character chunks.

    These values are starting points and should be evaluated on real course material.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be >= 0 and smaller than chunk_size")

    chunks: list[dict[str, Any]] = []

    for document in documents:
        text = " ".join(document["text"].split())
        metadata = dict(document["metadata"])

        if not text:
            continue

        start = 0
        chunk_index = 0

        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk = text[start:end].strip()

            if chunk:
                chunks.append({
                    "text": chunk,
                    "metadata": {
                        **metadata,
                        "chunk_index": chunk_index,
                    },
                })

            if end == len(text):
                break

            start = end - overlap
            chunk_index += 1

    return chunks
