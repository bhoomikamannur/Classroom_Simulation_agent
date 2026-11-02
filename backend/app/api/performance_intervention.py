from typing import Any

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
        return orchestrator.execute(
            operation="performance_intervention",
            actor=current_user,
            payload={
                "student_id": student_id,
                "course_context": request.course_context,
                "interaction_limit": request.interaction_limit,
            },
            course=course,
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
