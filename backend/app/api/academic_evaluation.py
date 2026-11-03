from pathlib import Path
import tempfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from backend.app.analytics.marks_store import (
    merge_marks, get_marks_register, get_student_marks, list_marks_uploads,
    delete_marks_upload, edit_student_mark,
)
from backend.app.analytics.academic_analysis import load_marks_file
from backend.app.api.auth import require_role, get_current_user
from backend.app.services.course_access import get_accessible_course


class MarkEditRequest(BaseModel):
    student_identifier: str = Field(min_length=1)
    assessment: str = Field(min_length=1)
    marks: float | None = Field(default=None, ge=0)


router = APIRouter(prefix="/academic-evaluation", tags=["Academic Marks"])


@router.post("/upload")
async def upload_marks(
    course_id: str = Form(..., min_length=1),
    file: UploadFile = File(...),
    current_user: dict = Depends(require_role("professor")),
):
    """Upload and merge raw assessment marks. No grading policy is involved."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".csv", ".xlsx"}:
        raise HTTPException(status_code=400, detail="Only CSV and XLSX marks files are supported.")
    course_id = course_id.strip()
    get_accessible_course(course_id, current_user)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded marks file is empty.")
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp:
            temp.write(data)
            temp_path = Path(temp.name)
        frame = load_marks_file(temp_path)
        return merge_marks(course_id, frame, str(current_user.get("user_id", "")), file.filename)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


@router.get("/register/{course_id}")
def read_marks_register(course_id: str, current_user: dict = Depends(require_role("professor"))):
    get_accessible_course(course_id, current_user)
    return get_marks_register(course_id)


@router.get("/uploads/{course_id}")
def read_marks_uploads(course_id: str, current_user: dict = Depends(require_role("professor"))):
    get_accessible_course(course_id, current_user)
    return list_marks_uploads(course_id)


@router.delete("/uploads/{course_id}/{upload_id}")
def remove_marks_upload(course_id: str, upload_id: str, current_user: dict = Depends(require_role("professor"))):
    get_accessible_course(course_id, current_user)
    result = delete_marks_upload(course_id, upload_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Marks upload not found.")
    return result


@router.patch("/marks/{course_id}")
def update_individual_mark(course_id: str, request: MarkEditRequest, current_user: dict = Depends(require_role("professor"))):
    get_accessible_course(course_id, current_user)
    try:
        result = edit_student_mark(course_id, request.student_identifier, request.assessment, request.marks)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Student or assessment mark not found.")
    return result


@router.get("/student/{course_id}")
def read_own_academic_marks(course_id: str, current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "student":
        raise HTTPException(status_code=403, detail="Only students can access this view.")
    get_accessible_course(course_id, current_user)
    identifiers = [str(current_user.get("user_id", ""))]
    if current_user.get("roll_number"):
        identifiers.append(str(current_user["roll_number"]))
    return get_student_marks(course_id, identifiers)
