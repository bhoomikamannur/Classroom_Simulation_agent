from io import BytesIO
from pathlib import Path
from typing import Any

from pptx import Presentation


def load_pptx(source: str | Path | bytes, source_name: str | None = None) -> list[dict[str, Any]]:
    """Extract text slide-by-slide from a path or in-memory PPTX bytes."""
    if isinstance(source, bytes):
        presentation = Presentation(BytesIO(source))
        document_name = source_name or "uploaded.pptx"
    else:
        path = Path(source)
        presentation = Presentation(str(path))
        document_name = path.name

    slides: list[dict[str, Any]] = []
    for slide_number, slide in enumerate(presentation.slides, start=1):
        parts: list[str] = []
        for shape in slide.shapes:
            if not hasattr(shape, "text"):
                continue
            text = shape.text.strip()
            if text:
                parts.append(text)
        combined = "\n".join(parts).strip()
        if not combined:
            continue
        slides.append({
            "text": combined,
            "metadata": {
                "source_name": document_name,
                "source_type": "pptx",
                "slide": slide_number,
            },
        })
    return slides
