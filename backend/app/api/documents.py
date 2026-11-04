from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pymongo import ASCENDING, DESCENDING

from backend.app.api.auth import get_current_user, require_role
from backend.app.services.course_access import get_accessible_course
from backend.app.database.mongodb import get_mongodb_database
from backend.app.rag.chunker import chunk_text
from backend.app.rag.loaders.pdf_loader import load_pdf
from backend.app.rag.loaders.pptx_loader import load_pptx
from backend.app.rag.vector_store import add_chunks, delete_document_chunks


router = APIRouter(prefix="/documents", tags=["Documents"])

BACKEND_ROOT = Path(__file__).resolve().parents[2]
UPLOADS_DIR = BACKEND_ROOT / "data" / "uploads"
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


def _documents():
    return get_mongodb_database()["documents"]


def _ensure_indexes() -> None:
    _documents().create_index(
        [("document_id", ASCENDING)], unique=True, name="unique_document_id"
    )
    _documents().create_index(
        [("course_id", ASCENDING), ("uploaded_at", DESCENDING)],
        name="course_documents_recent",
    )
    _documents().create_index(
        [("professor_id", ASCENDING), ("uploaded_at", DESCENDING)],
        name="professor_documents_recent",
    )


def _owned_course(course_id: str, professor_id: str) -> dict:
    course = get_mongodb_database()["courses"].find_one(
        {
            "course_id": course_id,
            "professor_id": professor_id,
            "status": "active",
        },
        {"_id": 0},
    )
    if course is None:
        # Do not allow uploads to another professor's course or archived courses.
        raise HTTPException(
            status_code=404,
            detail="Active course not found for this professor.",
        )
    return course


def _public_document(document: dict) -> dict:
    return {
        key: document.get(key)
        for key in (
            "document_id", "course_id", "professor_id", "filename",
            "file_type", "file_size", "sha256", "pages_or_slides_extracted",
            "chunk_count", "status", "uploaded_at", "processed_at", "error",
        )
        if key in document
    }


@router.post("/upload", status_code=201)
async def upload_document(
    course_id: str = Form(..., min_length=1),
    file: UploadFile = File(...),
    current_user: dict = Depends(require_role("professor")),
):
    _ensure_indexes()
    course_id = course_id.strip()
    _owned_course(course_id, current_user["user_id"])

    filename = Path(file.filename or "").name
    suffix = Path(filename).suffix.lower()
    if suffix not in {".pdf", ".pptx"}:
        raise HTTPException(
            status_code=400,
            detail="Only PDF and PPTX files are supported.",
        )

    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail="File is too large. Maximum upload size is 25 MB.",
        )

    document_id = str(uuid4())
    now = datetime.now(timezone.utc)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    stored_path = UPLOADS_DIR / f"{document_id}{suffix}"
    relative_path = stored_path.relative_to(BACKEND_ROOT).as_posix()

    record = {
        "document_id": document_id,
        "course_id": course_id,
        "professor_id": current_user["user_id"],
        "filename": filename,
        "file_type": suffix[1:],
        "file_size": len(data),
        "sha256": sha256(data).hexdigest(),
        "file_path": relative_path,
        "pages_or_slides_extracted": 0,
        "chunk_count": 0,
        "status": "processing",
        "uploaded_at": now,
        "processed_at": None,
    }
    _documents().insert_one(record)

    try:
        stored_path.write_bytes(data)
        pages_or_slides = (
            load_pdf(stored_path) if suffix == ".pdf" else load_pptx(stored_path)
        )
        for item in pages_or_slides:
            metadata = item.setdefault("metadata", {})
            metadata.update({
                "source_name": filename,
                "source_type": suffix[1:],
                "document_id": document_id,
                "course_id": course_id,
                "professor_id": current_user["user_id"],
            })

        chunks = chunk_text(pages_or_slides)
        if not chunks:
            raise ValueError("No readable text was extracted from the document.")

        stored_count = add_chunks(chunks)
        processed_at = datetime.now(timezone.utc)
        _documents().update_one(
            {"document_id": document_id},
            {"$set": {
                "pages_or_slides_extracted": len(pages_or_slides),
                "chunk_count": stored_count,
                "status": "processed",
                "processed_at": processed_at,
            }},
        )
        record.update({
            "pages_or_slides_extracted": len(pages_or_slides),
            "chunk_count": stored_count,
            "status": "processed",
            "processed_at": processed_at,
        })
        return {
            "message": "Document uploaded and indexed successfully.",
            "document": _public_document(record),
        }
    except Exception as exc:
        # Best-effort rollback prevents partially indexed documents from being
        # returned by RAG. Keep the MongoDB record for troubleshooting.
        try:
            delete_document_chunks(document_id)
        except Exception:
            pass
        try:
            if stored_path.is_file():
                stored_path.unlink()
        except OSError:
            pass
        _documents().update_one(
            {"document_id": document_id},
            {"$set": {
                "status": "failed",
                "error": str(exc)[:500],
                "processed_at": datetime.now(timezone.utc),
            }},
        )
        raise HTTPException(
            status_code=422,
            detail=f"Document processing failed: {str(exc)[:300]}",
        ) from exc


@router.get("/course/{course_id}")
def list_course_documents(
    course_id: str,
    current_user: dict = Depends(get_current_user),
):
    """List course materials for the owning professor or an enrolled student."""
    _ensure_indexes()
    course = get_accessible_course(course_id, current_user)
    query = {"course_id": course_id}
    if current_user.get("role") == "professor":
        query["professor_id"] = current_user["user_id"]
    documents = list(
        _documents()
        .find(query, {"_id": 0, "file_path": 0, "sha256": 0})
        .sort("uploaded_at", DESCENDING)
    )
    return {"course_id": course_id, "course_name": course.get("name"), "documents": documents}


def _authorized_document_file(document_id: str, current_user: dict) -> dict:
    """Fetch a stored document only after validating access to its active course."""
    document = _documents().find_one({"document_id": document_id}, {"_id": 0})
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    course = get_accessible_course(document["course_id"], current_user)
    if document.get("professor_id") != course.get("professor_id"):
        raise HTTPException(status_code=404, detail="Document not found.")

    relative_path = document.get("file_path")
    if not relative_path:
        raise HTTPException(status_code=404, detail="Original file is unavailable.")

    uploads_root = UPLOADS_DIR.resolve()
    file_path = (BACKEND_ROOT / relative_path).resolve()
    if file_path != uploads_root and uploads_root not in file_path.parents:
        raise HTTPException(status_code=404, detail="Original file is unavailable.")
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Original file is unavailable.")

    return {"document": document, "file_path": file_path}


@router.get("/{document_id}/view")
def view_document(
    document_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Stream the original course document for in-browser viewing where supported."""
    result = _authorized_document_file(document_id, current_user)
    document = result["document"]
    media_type = (
        "application/pdf" if document.get("file_type") == "pdf"
        else "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )
    return FileResponse(
        result["file_path"],
        media_type=media_type,
        filename=document.get("filename", "course-material"),
        content_disposition_type="inline",
    )


@router.get("/{document_id}/download")
def download_document(
    document_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Download the original uploaded course document."""
    result = _authorized_document_file(document_id, current_user)
    document = result["document"]
    media_type = (
        "application/pdf" if document.get("file_type") == "pdf"
        else "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )
    return FileResponse(
        result["file_path"],
        media_type=media_type,
        filename=document.get("filename", "course-material"),
        content_disposition_type="attachment",
    )


@router.delete("/{document_id}")
def delete_document(
    document_id: str,
    current_user: dict = Depends(require_role("professor")),
):
    _ensure_indexes()
    document = _documents().find_one(
        {
            "document_id": document_id,
            "professor_id": current_user["user_id"],
        }
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    # Remove vectors first. If this fails, retain the registry record so the
    # professor can retry rather than silently orphaning vectors.
    deleted_chunks = delete_document_chunks(document_id)
    file_path = BACKEND_ROOT / document.get("file_path", "")
    if document.get("file_path") and file_path.is_file():
        file_path.unlink()

    _documents().delete_one({"document_id": document_id})
    return {
        "message": "Document deleted successfully.",
        "document_id": document_id,
        "chunks_deleted": deleted_chunks,
    }
