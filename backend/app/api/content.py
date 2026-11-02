from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends

from backend.app.api.auth import get_current_user
from backend.app.agents.content_agent import ContentAgent
from backend.app.orchestrator.classroom_orchestrator import ClassroomOrchestrator
from backend.app.services.course_access import get_accessible_course


router = APIRouter(prefix="/content", tags=["Content Agent"])
agent = ContentAgent()
orchestrator = ClassroomOrchestrator(content_agent=agent)


class ContentRequest(BaseModel):
    query: str = Field(min_length=1)
    course_id: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


@router.post("/answer")
def content_answer(
    request: ContentRequest,
    current_user: dict = Depends(get_current_user),
):
    return orchestrator.execute(
        operation="content_answer",
        actor=current_user,
        payload=request.model_dump(),
        course=get_accessible_course(request.course_id, current_user),
    )
