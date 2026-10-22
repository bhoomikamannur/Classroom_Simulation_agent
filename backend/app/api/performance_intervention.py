
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.agents.performance_agent import PerformanceAgent
from backend.app.agents.intervention_agent import InterventionAgent


router = APIRouter(
    prefix="/performance",
    tags=["Performance & Intervention"],
)

performance_agent = PerformanceAgent()
intervention_agent = InterventionAgent()


class Interaction(BaseModel):
    role: str = Field(min_length=1)
    content: str = Field(min_length=1)


class PerformanceInterventionRequest(BaseModel):
    student_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    interactions: list[Interaction] = Field(min_length=1)
    course_context: str | None = None


@router.post("/intervene")
def analyze_and_recommend(
    request: PerformanceInterventionRequest,
) -> dict[str, Any]:
    interactions = [
        item.model_dump() for item in request.interactions
    ]

    try:
        performance_result = performance_agent.analyze(
            student_id=request.student_id,
            subject_id=request.subject_id,
            interactions=interactions,
            course_context=request.course_context,
        )

        intervention_result = intervention_agent.analyze(
            performance_result=performance_result,
            course_context=request.course_context,
        )

        return {
            "performance": performance_result,
            "intervention": intervention_result,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
