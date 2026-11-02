from fastapi import APIRouter, Depends, HTTPException
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


@router.post("/chat")
def tutor_chat(
    request: TutorRequest,
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") != "student":
        raise HTTPException(
            status_code=403,
            detail="Only students can access the Tutor Agent.",
        )

    course = get_accessible_course(request.course_id, current_user)
    try:
        return orchestrator.execute(
            operation="tutor_chat",
            actor=current_user,
            payload=request.model_dump(),
            course=course,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
