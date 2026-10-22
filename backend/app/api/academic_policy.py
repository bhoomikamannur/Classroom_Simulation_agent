
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.analytics.policy_store import (
    create_policy,
    get_policy,
    update_policy,
)


router = APIRouter(
    prefix="/academic-policies",
    tags=["Academic Policies"],
)


class AcademicPolicyRequest(BaseModel):
    course_id: str = Field(min_length=1)
    assessment_weights: dict[str, float]
    assessment_max_marks: dict[str, float]
    pass_percentage: float = Field(ge=0, le=100)
    missing_marks_policy: Literal["exclude", "zero"]


class AcademicPolicyUpdateRequest(BaseModel):
    assessment_weights: dict[str, float]
    assessment_max_marks: dict[str, float]
    pass_percentage: float = Field(ge=0, le=100)
    missing_marks_policy: Literal["exclude", "zero"]


@router.post("", status_code=201)
def create_academic_policy(request: AcademicPolicyRequest):
    """Create a grading policy for a course."""
    try:
        return create_policy(request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{course_id}")
def read_academic_policy(course_id: str):
    """Retrieve the grading policy for a course."""
    try:
        policy = get_policy(course_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if policy is None:
        raise HTTPException(
            status_code=404,
            detail=f"No academic policy found for course '{course_id}'.",
        )

    return policy


@router.put("/{course_id}")
def replace_academic_policy(
    course_id: str,
    request: AcademicPolicyUpdateRequest,
):
    """Replace an existing course policy; do not create one implicitly."""
    policy_data = request.model_dump()
    policy_data["course_id"] = course_id

    try:
        updated = update_policy(course_id, policy_data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"No academic policy found for course '{course_id}'.",
        )

    return updated
