from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.app.rag.retriever import retrieve


router = APIRouter(tags=["Retrieval"])


class RetrievalRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


@router.post("/retrieve")
def retrieve_course_material(request: RetrievalRequest):
    return {
        "query": request.query,
        "results": retrieve(request.query, top_k=request.top_k),
    }
