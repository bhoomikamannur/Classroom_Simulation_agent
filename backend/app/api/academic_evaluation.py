
from pathlib import Path
import tempfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from backend.app.analytics.academic_evaluation import evaluate_marks_file
from backend.app.analytics.policy_store import get_policy
from backend.app.api.auth import require_role
from backend.app.services.course_access import get_accessible_course
from backend.app.analytics.assessment_columns import normalize_marks_for_policy
from backend.app.analytics.academic_analysis import load_marks_file, analyze_marks

router = APIRouter(
    prefix="/academic-evaluation",
    tags=["Academic Evaluation"],
)


@router.post("/upload")
async def upload_marks_for_evaluation(
    course_id: str = Form(..., min_length=1),
    file: UploadFile = File(...),
    current_user: dict = Depends(require_role("professor")),
):
    """Evaluate uploaded student marks using the saved course policy."""
    filename = file.filename or ""
    suffix = Path(filename).suffix.lower()

    if suffix not in {".csv", ".xlsx"}:
        raise HTTPException(
            status_code=400,
            detail="Only CSV and XLSX marks files are supported.",
        )

    if not course_id.strip():
        raise HTTPException(
            status_code=422,
            detail="course_id must not be empty.",
        )

    get_accessible_course(course_id.strip(), current_user)
    data = await file.read()

    if not data:
        raise HTTPException(
            status_code=400,
            detail="The uploaded marks file is empty.",
        )

    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            suffix=suffix,
            delete=False,
        ) as temp:
            temp.write(data)
            temp_path = Path(temp.name)

        return evaluate_marks_file(
            file_path=temp_path,
            course_id=course_id.strip(),
        )

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        message = str(exc)
        status_code = (
            404
            if message.startswith("No academic grading policy")
            else 422
        )
        raise HTTPException(
            status_code=status_code,
            detail=message,
        ) from exc

    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


@router.post("/analyze")
async def analyze_class_marks(
    course_id: str = Form(..., min_length=1),
    file: UploadFile = File(...),
    current_user: dict = Depends(require_role("professor")),
):
    """Return descriptive class and student analytics using the saved policy."""
    filename = file.filename or ""
    suffix = Path(filename).suffix.lower()

    if suffix not in {".csv", ".xlsx"}:
        raise HTTPException(
            status_code=400,
            detail="Only CSV and XLSX marks files are supported.",
        )

    if not course_id.strip():
        raise HTTPException(
            status_code=422,
            detail="course_id must not be empty.",
        )

    get_accessible_course(course_id.strip(), current_user)
    data = await file.read()

    if not data:
        raise HTTPException(
            status_code=400,
            detail="The uploaded marks file is empty.",
        )

    temp_path = None

    try:
        policy = get_policy(course_id.strip())

        if policy is None:
            raise HTTPException(
                status_code=404,
                detail=f"No academic policy found for course '{course_id}'.",
            )

        with tempfile.NamedTemporaryFile(
            suffix=suffix,
            delete=False,
        ) as temp:
            temp.write(data)
            temp_path = Path(temp.name)

        frame = load_marks_file(temp_path)
        normalized, student_id_column = normalize_marks_for_policy(frame, policy)
        return analyze_marks(
            df=normalized,
            student_id_column=student_id_column,
            assessment_max_marks=policy["assessment_max_marks"],
        )

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
