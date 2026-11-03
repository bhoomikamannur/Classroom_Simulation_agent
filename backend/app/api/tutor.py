from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.agents.tutor_agent import TutorAgent
from backend.app.orchestrator.classroom_orchestrator import ClassroomOrchestrator
from backend.app.api.auth import get_current_user
from backend.app.services.course_access import get_accessible_course


router = APIRouter(prefix="/tutor", tags=["Tutor Agent"])
agent = TutorAgent()
orchestrator = ClassroomOrchestrator(tutor_agent=agent)


class TutorRequest(BaseModel):
    session_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    course_id: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


def _run_activity_trigger(student_id: str, course_id: str, course_name: str, professor_id: str) -> None:
    """Run a bounded number of ready batches after the chat response is sent."""
    from backend.app.services.incremental_performance import (
        ANALYSIS_THRESHOLD, get_analysis_status, process_pending_analysis,
    )
    for _ in range(3):
        status = get_analysis_status(student_id, course_id)
        if status["pending_meaningful_responses"] < ANALYSIS_THRESHOLD:
            break
        result = process_pending_analysis(
            student_id=student_id,
            course_id=course_id,
            course_name=course_name,
            professor_id=professor_id,
        )
        if result.get("status") not in {"completed", "insufficient_evidence"}:
            break


@router.post("/chat")
def tutor_chat(
    request: TutorRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") != "student":
        raise HTTPException(
            status_code=403,
            detail="Only students can access the Tutor Agent.",
        )

    course = get_accessible_course(request.course_id, current_user)
    try:
        result = orchestrator.execute(
            operation="tutor_chat",
            actor=current_user,
            payload=request.model_dump(),
            course=course,
        )
        background_tasks.add_task(
            _run_activity_trigger,
            current_user["user_id"],
            course["course_id"],
            course.get("name", "Course"),
            course["professor_id"],
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
