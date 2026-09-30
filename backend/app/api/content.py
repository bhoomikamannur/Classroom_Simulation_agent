from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.app.agents.content_agent import ContentAgent


router = APIRouter(prefix="/content", tags=["Content Agent"])
agent = ContentAgent()


class ContentRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


@router.post("/answer")
def content_answer(request: ContentRequest):
    return agent.answer(request.query, top_k=request.top_k)
