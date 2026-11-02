from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.app.api.auth import get_current_user
from backend.app.rag.retriever import retrieve
from backend.app.services.course_access import get_accessible_course


router = APIRouter(tags=["Retrieval"])


class RetrievalRequest(BaseModel):
    query: str = Field(min_length=1)
    course_id: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


@router.post("/retrieve")
def retrieve_course_material(
    request: RetrievalRequest,
    current_user: dict = Depends(get_current_user),
):
    get_accessible_course(request.course_id, current_user)
    return {
        "query": request.query,
        "course_id": request.course_id,
        "results": retrieve(
            request.query,
            course_id=request.course_id,
            top_k=request.top_k,
        ),
    }
