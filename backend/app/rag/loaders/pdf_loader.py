from pathlib import Path
from typing import Any

import fitz


def load_pdf(path: str | Path) -> list[dict[str, Any]]:
    """Extract text page-by-page and preserve page metadata."""
    path = Path(path)
    pages: list[dict[str, Any]] = []

    with fitz.open(path) as document:
        for page_number, page in enumerate(document, start=1):
            text = page.get_text("text").strip()
            if not text:
                continue

            pages.append({
                "text": text,
                "metadata": {
                    "source_name": path.name,
                    "source_type": "pdf",
                    "page": page_number,
                },
            })

    return pages
