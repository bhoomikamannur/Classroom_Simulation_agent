from pathlib import Path
import tempfile

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.app.rag.chunker import chunk_text
from backend.app.rag.loaders.pdf_loader import load_pdf
from backend.app.rag.loaders.pptx_loader import load_pptx
from backend.app.rag.vector_store import add_chunks


router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    filename = file.filename or ""
    suffix = Path(filename).suffix.lower()

    if suffix not in {".pdf", ".pptx"}:
        raise HTTPException(
            status_code=400,
            detail="Only PDF and PPTX files are supported.",
        )

    data = await file.read()

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp:
        temp.write(data)
        temp_path = Path(temp.name)

    try:
        pages_or_slides = (
            load_pdf(temp_path) if suffix == ".pdf" else load_pptx(temp_path)
        )

        
        for item in pages_or_slides:
            item["metadata"]["source_name"] = filename

        chunks = chunk_text(pages_or_slides)
        stored = add_chunks(chunks)

        return {
            "filename": filename,
            "source_type": suffix[1:],
            "pages_or_slides_extracted": len(pages_or_slides),
            "chunks_stored": stored,
        }
    finally:
        temp_path.unlink(missing_ok=True)
