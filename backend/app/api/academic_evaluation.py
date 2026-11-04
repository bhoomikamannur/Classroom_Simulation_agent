from pathlib import Path
import tempfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from typing import Literal

from backend.app.analytics.marks_store import (
    merge_marks, get_marks_register, get_student_marks, list_marks_uploads,
    delete_marks_upload, edit_student_mark,
)
from backend.app.analytics.academic_analysis import load_marks_file
from backend.app.analytics.academic_policy import validate_academic_policy, calculate_weighted_result
from backend.app.analytics.policy_store import create_policy, get_policy, update_policy
from backend.app.api.auth import require_role, get_current_user
from backend.app.services.course_access import get_accessible_course




class AssessmentConfiguration(BaseModel):
    assessment_weights: dict[str, float]
    assessment_max_marks: dict[str, float]
    pass_percentage: float = Field(default=40, ge=0, le=100)
    missing_marks_policy: Literal["exclude", "zero"] = "exclude"


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




@router.post("/evaluate/{course_id}")
def evaluate_course_marks(
    course_id: str,
    request: AssessmentConfiguration,
    current_user: dict = Depends(require_role("professor")),
):
    """Evaluate the persisted course marks using the professor's inline configuration."""
    get_accessible_course(course_id, current_user)
    try:
        policy = validate_academic_policy({
            "course_id": course_id,
            **request.model_dump(),
        })
        register = get_marks_register(course_id)
        if not register.get("students"):
            raise ValueError("Upload marks for at least one enrolled student before evaluating.")
        configured = set(policy["assessment_weights"])
        available = set(register.get("assessment_names", {}))
        unknown = configured - available
        if unknown:
            raise ValueError(
                "These assessments are not present in the marks register: "
                + ", ".join(sorted(unknown))
            )
        results = []
        assessment_totals = {
            key: {"sum_percentage": 0.0, "students_with_marks": 0}
            for key in policy["assessment_weights"]
        }
        for student in register["students"]:
            marks = {
                key: student.get("assessments", {}).get(key)
                for key in policy["assessment_weights"]
            }
            result = calculate_weighted_result(marks, policy)
            results.append({
                "student_id": student["student_id"],
                "display_id": student.get("display_id", student["student_id"]),
                **result,
            })
            for key, mark in marks.items():
                if mark is not None:
                    assessment_totals[key]["sum_percentage"] += (
                        float(mark) / policy["assessment_max_marks"][key]
                    ) * 100.0
                    assessment_totals[key]["students_with_marks"] += 1

        scored = [
            item["weighted_percentage"] for item in results
            if item["weighted_percentage"] is not None
        ]
        complete = [
            item["weighted_percentage"] for item in results
            if item["is_complete"] and item["weighted_percentage"] is not None
        ]
        pass_count = sum(item["pass_status"] == "pass" for item in results)
        fail_count = sum(item["pass_status"] == "fail" for item in results)
        provisional_count = sum(item["pass_status"] == "provisional" for item in results)
        not_assessed_count = sum(item["pass_status"] == "not_assessed" for item in results)
        assessment_summary = []
        for key, totals in assessment_totals.items():
            count = totals["students_with_marks"]
            assessment_summary.append({
                "assessment": key,
                "name": register.get("assessment_names", {}).get(key, key),
                "weight": policy["assessment_weights"][key],
                "maximum_marks": policy["assessment_max_marks"][key],
                "students_with_marks": count,
                "average_percentage": round(totals["sum_percentage"] / count, 2) if count else None,
            })
        summary = {
            "student_count": len(results),
            "evaluated_count": len(scored),
            "complete_count": len(complete),
            "provisional_count": provisional_count,
            "not_assessed_count": not_assessed_count,
            "pass_count": pass_count,
            "fail_count": fail_count,
            "class_average_percentage": round(sum(scored) / len(scored), 2) if scored else None,
            "complete_average_percentage": round(sum(complete) / len(complete), 2) if complete else None,
            "highest_percentage": round(max(scored), 2) if scored else None,
            "lowest_percentage": round(min(scored), 2) if scored else None,
            "pass_rate": round((pass_count / (pass_count + fail_count)) * 100, 2) if pass_count + fail_count else None,
            "assessment_summary": assessment_summary,
        }
        existing = get_policy(course_id)
        if existing is None:
            saved_policy = create_policy(policy)
        else:
            saved_policy = update_policy(course_id, policy)
        return {
            "course_id": course_id,
            "number_of_students": len(results),
            "grading_policy": saved_policy or policy,
            "student_results": results,
            "summary": summary,
            "message": "Academic results evaluated and configuration saved.",
        }
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

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
