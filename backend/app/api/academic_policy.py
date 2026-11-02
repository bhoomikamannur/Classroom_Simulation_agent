
from typing import Literal
from pathlib import Path
import tempfile
import pandas as pd

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from pydantic import BaseModel, Field
from backend.app.api.auth import get_current_user, require_role
from backend.app.services.course_access import get_accessible_course

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
def create_academic_policy(request: AcademicPolicyRequest, current_user: dict = Depends(require_role("professor")),):
    """Create a grading policy for a course."""
    get_accessible_course(request.course_id.strip(), current_user)
    try:
        return create_policy(request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{course_id}")
def read_academic_policy(course_id: str, current_user: dict = Depends(get_current_user),):
    """Retrieve the grading policy for a course."""
    get_accessible_course(course_id, current_user)
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
    current_user: dict = Depends(require_role("professor")),
):
    """Replace an existing course policy; do not create one implicitly."""
    get_accessible_course(course_id, current_user)
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


def _header_key(value: object) -> str:
    import re
    return re.sub(r"[^a-z0-9]", "", str(value).strip().lower())


@router.post("/import")
async def import_academic_policy(
    course_id: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(require_role("professor")),
):
    """Parse a CSV/XLSX grading-policy template and return editable policy data."""
    get_accessible_course(course_id.strip(), current_user)
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".csv", ".xlsx"}:
        raise HTTPException(status_code=400, detail="Upload a CSV or XLSX grading-policy file.")
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="The grading-policy file is empty.")
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp:
            temp.write(raw)
            temp_path = Path(temp.name)
        frame = pd.read_csv(temp_path) if suffix == ".csv" else pd.read_excel(temp_path)
        if frame.empty:
            raise ValueError("The grading-policy file has no assessment rows.")
        aliases = {
            "name": {"assessment", "assessmentname", "name", "component"},
            "weight": {"weight", "weightpercent", "weightpercentage", "percentage"},
            "maximum": {"max", "maxmarks", "maximum", "maximummarks", "outof", "totalmarks"},
        }
        columns: dict[str, list[str]] = {}
        for col in frame.columns:
            columns.setdefault(_header_key(col), []).append(col)
        found = {}
        for field, names in aliases.items():
            matches = [col for name in names for col in columns.get(name, [])]
            if len(matches) != 1:
                raise ValueError(f"Expected exactly one {field} column. Recognized headers: {sorted(names)}.")
            found[field] = matches[0]
        weights, maximums = {}, {}
        normalized_names: dict[str, str] = {}
        for _, row in frame.iterrows():
            name = str(row[found["name"]]).strip()
            if not name or name.lower() == "nan":
                continue
            normalized_name = _header_key(name)
            if normalized_name in normalized_names:
                raise ValueError(
                    f"Assessment names '{normalized_names[normalized_name]}' and '{name}' "
                    "are ambiguous after case/space/underscore/hyphen normalization."
                )
            normalized_names[normalized_name] = name
            weight = pd.to_numeric(row[found["weight"]], errors="coerce")
            maximum = pd.to_numeric(row[found["maximum"]], errors="coerce")
            if pd.isna(weight) or pd.isna(maximum):
                raise ValueError(f"Assessment '{name}' has a missing or non-numeric weight/maximum.")
            weights[name] = float(weight)
            maximums[name] = float(maximum)
        pass_matches = [col for key in ("passpercentage", "passingpercentage", "passmark") for col in columns.get(key, [])]
        missing_matches = [col for key in ("missingmarkspolicy", "missingpolicy") for col in columns.get(key, [])]
        if len(pass_matches) > 1:
            raise ValueError("The policy file contains ambiguous pass-percentage columns.")
        if len(missing_matches) > 1:
            raise ValueError("The policy file contains ambiguous missing-marks-policy columns.")
        pass_col = pass_matches[0] if pass_matches else None
        missing_col = missing_matches[0] if missing_matches else None
        pass_percentage = 40.0
        missing_policy = "exclude"
        if pass_col and pd.notna(frame[pass_col].iloc[0]):
            pass_percentage = float(frame[pass_col].iloc[0])
        if missing_col and pd.notna(frame[missing_col].iloc[0]):
            missing_policy = str(frame[missing_col].iloc[0]).strip().lower()
        candidate = {
            "course_id": course_id.strip(),
            "assessment_weights": weights,
            "assessment_max_marks": maximums,
            "pass_percentage": pass_percentage,
            "missing_marks_policy": missing_policy,
        }
        from backend.app.analytics.academic_policy import validate_academic_policy
        validated = validate_academic_policy(candidate)
        return {
            "course_id": validated["course_id"],
            "assessments": [
                {"name": name, "weight": validated["assessment_weights"][name],
                 "maximum": validated["assessment_max_marks"][name]}
                for name in validated["assessment_weights"]
            ],
            "pass_percentage": validated["pass_percentage"],
            "missing_marks_policy": validated["missing_marks_policy"],
        }
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        if temp_path:
            temp_path.unlink(missing_ok=True)
