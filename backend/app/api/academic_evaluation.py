
from pathlib import Path
import tempfile

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from backend.app.analytics.academic_evaluation import evaluate_marks_file


router = APIRouter(
    prefix="/academic-evaluation",
    tags=["Academic Evaluation"],
)


@router.post("/upload")
async def upload_marks_for_evaluation(
    course_id: str = Form(..., min_length=1),
    file: UploadFile = File(...),
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
