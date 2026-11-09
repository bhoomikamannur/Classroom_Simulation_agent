from io import BytesIO
from pathlib import Path
from typing import Any

import fitz


def load_pdf(source: str | Path | bytes, source_name: str | None = None) -> list[dict[str, Any]]:
    """Extract text page-by-page from a path or in-memory PDF bytes."""
    pages: list[dict[str, Any]] = []
    if isinstance(source, bytes):
        document_name = source_name or "uploaded.pdf"
        document_context = fitz.open(stream=source, filetype="pdf")
    else:
        path = Path(source)
        document_name = path.name
        document_context = fitz.open(path)

    with document_context as document:
        for page_number, page in enumerate(document, start=1):
            text = page.get_text("text").strip()
            if not text:
                continue
            pages.append({
                "text": text,
                "metadata": {
                    "source_name": document_name,
                    "source_type": "pdf",
                    "page": page_number,
                },
            })
    return pages
