from typing import Any
from datetime import date, datetime

from bson import ObjectId

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.app.agents.performance_agent import PerformanceAgent
from backend.app.llm.ollama_client import LLMTimeoutError
from backend.app.agents.intervention_agent import InterventionAgent
from backend.app.orchestrator.classroom_orchestrator import ClassroomOrchestrator
from backend.app.api.auth import require_role
from backend.app.database.mongodb import get_mongodb_database
from backend.app.services.course_access import get_accessible_course


router = APIRouter(
    prefix="/performance",
    tags=["Performance & Intervention"],
)

performance_agent = PerformanceAgent()
intervention_agent = InterventionAgent()
orchestrator = ClassroomOrchestrator(
    performance_agent=performance_agent,
    intervention_agent=intervention_agent,
)


class PerformanceInterventionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_id: str | None = Field(default=None, min_length=1)
    roll_number: str | None = Field(default=None, min_length=3, max_length=20)
    course_id: str = Field(min_length=1)
    course_context: str | None = None
    interaction_limit: int = Field(default=500, ge=1, le=5000)

    @model_validator(mode="after")
    def require_student_identifier(self):
        if not self.student_id and not self.roll_number:
            raise ValueError("Provide either student_id or roll_number.")
        if self.student_id and self.roll_number:
            raise ValueError("Provide student_id or roll_number, not both.")
        return self


@router.post("/intervene")
def analyze_and_recommend(
    request: PerformanceInterventionRequest,
    current_user: dict = Depends(require_role("professor")),
) -> dict[str, Any]:
    """Analyze persisted learning evidence for an enrolled student.

    The caller supplies the student and course identifiers, but never the
    interaction contents. Evidence is retrieved by the Orchestrator from
    MongoDB after course ownership and enrollment have been verified.
    """
    course = get_accessible_course(request.course_id, current_user)
    student_id = request.student_id
    if request.roll_number:
        normalized_roll = request.roll_number.strip().lower()
        student = get_mongodb_database()["users"].find_one(
            {"roll_number": normalized_roll, "role": "student", "is_active": True},
            {"_id": 0, "user_id": 1},
        )
        if student is None:
            raise HTTPException(status_code=404, detail="No active student found with that roll number.")
        student_id = student["user_id"]

    enrollment = get_mongodb_database()["course_enrollments"].find_one(
        {
            "course_id": request.course_id,
            "student_id": student_id,
            "status": "active",
        },
        {"_id": 1},
    )
    if enrollment is None:
        raise HTTPException(
            status_code=404,
            detail="Student is not enrolled in this course.",
        )


    try:
        # Both the legacy manual endpoint and /reanalyze now delegate to the
        # exact same pending-evidence analysis pipeline.
        from backend.app.services.incremental_performance import process_all_pending_analysis
        return process_all_pending_analysis(
            student_id=student_id,
            course_id=request.course_id,
            course_name=course.get("name", "Course"),
            professor_id=course["professor_id"],
            force=True,
        )
    except LLMTimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail=f"Performance analysis timed out: {exc}",
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


class IncrementalAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    roll_number: str = Field(min_length=3, max_length=20)
    course_id: str = Field(min_length=1)


def _resolve_enrolled_student(roll_number: str, course_id: str) -> tuple[dict, str]:
    student = get_mongodb_database()["users"].find_one(
        {"roll_number": roll_number.strip().lower(), "role": "student", "is_active": True},
        {"_id": 0, "user_id": 1, "roll_number": 1},
    )
    if student is None:
        raise HTTPException(status_code=404, detail="No active student found with that roll number.")
    enrollment = get_mongodb_database()["course_enrollments"].find_one({
        "course_id": course_id,
        "student_id": student["user_id"],
        "status": "active",
    }, {"_id": 1})
    if enrollment is None:
        raise HTTPException(status_code=404, detail="Student is not enrolled in this course.")
    return student, student["user_id"]


@router.get("/status")
def incremental_analysis_status(
    roll_number: str,
    course_id: str,
    current_user: dict = Depends(require_role("professor")),
) -> dict[str, Any]:
    """Return pending activity and the saved concept-wise learning profile."""
    get_accessible_course(course_id, current_user)
    student, student_id = _resolve_enrolled_student(roll_number, course_id)
    from backend.app.services.incremental_performance import get_analysis_status
    result = get_analysis_status(student_id, course_id)
    result["roll_number"] = student.get("roll_number")
    return result


@router.post("/reanalyze")
def manually_reanalyze(
    request: IncrementalAnalysisRequest,
    current_user: dict = Depends(require_role("professor")),
) -> dict[str, Any]:
    """Professor-triggered analysis of pending evidence, even below threshold."""
    course = get_accessible_course(request.course_id, current_user)
    _, student_id = _resolve_enrolled_student(request.roll_number, request.course_id)
    from backend.app.services.incremental_performance import process_all_pending_analysis
    try:
        return process_all_pending_analysis(
            student_id=student_id,
            course_id=request.course_id,
            course_name=course.get("name", "Course"),
            professor_id=course["professor_id"],
            force=True,
        )
    except LLMTimeoutError as exc:
        raise HTTPException(status_code=504, detail=f"Performance analysis timed out: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Could not complete incremental analysis: {exc}") from exc



def _json_safe(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


@router.get("/alerts")
def list_course_alerts(
    course_id: str,
    current_user: dict = Depends(require_role("professor")),
) -> dict[str, Any]:
    """Return active alerts for every enrolled student in a professor-owned course."""
    get_accessible_course(course_id, current_user)
    db = get_mongodb_database()
    query = {
        "course_id": course_id,
        "professor_id": current_user.get("user_id"),
        "status": "open",
    }
    alerts = list(db["teacher_alerts"].find(query))
    priority_rank = {"high": 0, "medium": 1, "low": 2}
    alerts.sort(
        key=lambda alert: (
            priority_rank.get(str(alert.get("priority", "medium")).lower(), 1),
            -(alert.get("created_at").timestamp() if isinstance(alert.get("created_at"), datetime) else 0),
        )
    )
    student_ids = list({str(alert.get("student_id", "")) for alert in alerts if alert.get("student_id")})
    users = list(db["users"].find(
        {"user_id": {"$in": student_ids}, "role": "student"},
        {"_id": 0, "user_id": 1, "roll_number": 1, "name": 1, "full_name": 1, "display_name": 1, "email": 1},
    )) if student_ids else []
    user_by_id = {str(user.get("user_id")): user for user in users}

    items = []
    for alert in alerts:
        student = user_by_id.get(str(alert.get("student_id", "")), {})
        name = (
            student.get("display_name")
            or student.get("full_name")
            or student.get("name")
            or student.get("email")
            or "Student"
        )
        item = {
            "id": str(alert.get("_id", "")),
            "student_id": str(alert.get("student_id", "")),
            "student_name": name,
            "roll_number": student.get("roll_number"),
            "alert_type": alert.get("alert_type"),
            "concept": alert.get("concept"),
            "priority": alert.get("priority", "medium"),
            "message": alert.get("message", ""),
            "status": alert.get("status", "open"),
            "created_at": alert.get("created_at"),
            "updated_at": alert.get("updated_at"),
            "latest_seen_at": alert.get("latest_seen_at"),
            "acknowledged_at": alert.get("acknowledged_at"),
            "acknowledged_by": alert.get("acknowledged_by"),
            "priority_reasons": alert.get("priority_reasons", []),
            "academic_context": alert.get("academic_context"),
        }
        items.append(_json_safe(item))
    return {"course_id": course_id, "alerts": items, "count": len(items)}


def _update_open_alert(
    alert_id: str,
    course_id: str,
    current_user: dict,
    update: dict,
) -> dict[str, Any]:
    get_accessible_course(course_id, current_user)
    if not ObjectId.is_valid(alert_id):
        raise HTTPException(status_code=404, detail="Active alert not found.")
    result = get_mongodb_database()["teacher_alerts"].update_one(
        {
            "_id": ObjectId(alert_id),
            "course_id": course_id,
            "professor_id": current_user.get("user_id"),
            "status": "open",
        },
        update,
    )
    if result.matched_count != 1:
        raise HTTPException(status_code=404, detail="Active alert not found.")
    return {"message": "Alert updated.", "alert_id": alert_id}


@router.post("/alerts/{alert_id}/acknowledge")
def acknowledge_course_alert(
    alert_id: str,
    course_id: str,
    current_user: dict = Depends(require_role("professor")),
) -> dict[str, Any]:
    """Record that the professor has seen an alert; do not resolve or close it."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    return _update_open_alert(alert_id, course_id, current_user, {"$set": {
        "acknowledged_at": now,
        "acknowledged_by": current_user.get("user_id"),
        "updated_at": now,
    }})


@router.post("/alerts/{alert_id}/close")
def close_course_alert(
    alert_id: str,
    course_id: str,
    current_user: dict = Depends(require_role("professor")),
) -> dict[str, Any]:
    """Dismiss an alert from the active view while retaining its audit history."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    return _update_open_alert(alert_id, course_id, current_user, {"$set": {
        "status": "closed",
        "closed_at": now,
        "closed_by": current_user.get("user_id"),
        "updated_at": now,
    }})
