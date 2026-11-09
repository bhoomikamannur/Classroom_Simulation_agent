from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pymongo import ASCENDING, DESCENDING

from backend.app.api.auth import get_current_user, require_role
from backend.app.services.course_access import get_accessible_course
from backend.app.database.mongodb import get_mongodb_database
from backend.app.storage.file_storage import save_file, read_file_record, delete_file_record
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
    record = {
        "document_id": document_id,
        "course_id": course_id,
        "professor_id": current_user["user_id"],
        "filename": filename,
        "file_type": suffix[1:],
        "file_size": len(data),
        "sha256": sha256(data).hexdigest(),
        "storage_provider": "gridfs",
        "storage_file_id": document_id,
        "pages_or_slides_extracted": 0,
        "chunk_count": 0,
        "status": "processing",
        "uploaded_at": now,
        "processed_at": None,
    }
    _documents().insert_one(record)

    try:
        save_file(
            document_id,
            filename,
            data,
            metadata={
                "document_id": document_id,
                "course_id": course_id,
                "professor_id": current_user["user_id"],
                "file_type": suffix[1:],
            },
        )
        pages_or_slides = (
            load_pdf(data, filename) if suffix == ".pdf" else load_pptx(data, filename)
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
            delete_file_record(record)
        except Exception:
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

    try:
        if document.get("storage_provider") == "gridfs":
            data = read_file_record(document)
        else:
            # Preserve the old local-file path contract for pre-migration records,
            # while preventing paths from escaping the uploads directory.
            relative_path = document.get("file_path")
            if not relative_path:
                raise FileNotFoundError
            uploads_root = UPLOADS_DIR.resolve()
            file_path = (BACKEND_ROOT / relative_path).resolve()
            if uploads_root not in file_path.parents or not file_path.is_file():
                raise FileNotFoundError
            data = file_path.read_bytes()
    except (FileNotFoundError, OSError, RuntimeError):
        raise HTTPException(status_code=404, detail="Original file is unavailable.")
    return {"document": document, "data": data}


def _document_response(document: dict, data: bytes, disposition: str) -> Response:
    media_type = (
        "application/pdf" if document.get("file_type") == "pdf"
        else "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )
    from urllib.parse import quote
    filename = document.get("filename", "course-material")
    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(filename)}"},
    )


@router.get("/{document_id}/view")
def view_document(
    document_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Return the original course document inline for browser viewing."""
    result = _authorized_document_file(document_id, current_user)
    return _document_response(result["document"], result["data"], "inline")


@router.get("/{document_id}/download")
def download_document(
    document_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Download the original uploaded course document."""
    result = _authorized_document_file(document_id, current_user)
    return _document_response(result["document"], result["data"], "attachment")


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
    delete_file_record(document)

    _documents().delete_one({"document_id": document_id})
    return {
        "message": "Document deleted successfully.",
        "document_id": document_id,
        "chunks_deleted": deleted_chunks,
    }
