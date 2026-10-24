
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.agents.tutor_agent import TutorAgent


router = APIRouter(prefix="/tutor", tags=["Tutor Agent"])

agent = TutorAgent()


class TutorRequest(BaseModel):
    student_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    course_id: str | None = Field(default=None, min_length=1)
    professor_id: str | None = Field(default=None, min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


@router.post("/chat")
def tutor_chat(request: TutorRequest):
    try:
        return agent.answer(
            student_id=request.student_id,
            subject_id=request.subject_id,
            session_id=request.session_id,
            message=request.message,
            top_k=request.top_k,
            course_id=request.course_id,
            professor_id=request.professor_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
