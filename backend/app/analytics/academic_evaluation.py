
from pathlib import Path
from typing import Any

import pandas as pd

from backend.app.analytics.academic_analysis import (
    _find_student_id_column,
    _prepare_marks,
    load_marks_file,
)
from backend.app.analytics.academic_policy import calculate_weighted_result
from backend.app.analytics.policy_store import get_policy


def evaluate_marks(
    df: pd.DataFrame,
    course_id: str,
    student_id_column: str | None = None,
) -> dict[str, Any]:
    """
    Evaluate student marks using the saved grading policy for a course.

    Official weighted results are calculated only when a course policy
    exists. Descriptive analysis remains a separate operation.
    """
    policy = get_policy(course_id)

    if policy is None:
        raise ValueError(
            f"No academic grading policy exists for course '{course_id}'."
        )

    student_id_column = _find_student_id_column(
        df, student_id_column
    )

    prepared, assessment_columns = _prepare_marks(
        df, student_id_column
    )

    configured_assessments = set(policy["assessment_weights"])
    uploaded_assessments = set(assessment_columns)

    if uploaded_assessments != configured_assessments:
        missing_columns = sorted(
            configured_assessments - uploaded_assessments
        )
        unexpected_columns = sorted(
            uploaded_assessments - configured_assessments
        )

        raise ValueError(
            "Uploaded assessment columns must match the saved course "
            f"policy. Missing columns: {missing_columns}; "
            f"unexpected columns: {unexpected_columns}."
        )

    results = []

    for _, row in prepared.iterrows():
        marks = {
            assessment: (
                float(row[assessment])
                if pd.notna(row[assessment])
                else None
            )
            for assessment in assessment_columns
        }

        result = calculate_weighted_result(marks, policy)
        results.append({
            "student_id": str(row[student_id_column]),
            **result,
        })

    return {
        "course_id": policy["course_id"],
        "number_of_students": len(results),
        "grading_policy": policy,
        "student_results": results,
    }


def evaluate_marks_file(
    file_path: str | Path,
    course_id: str,
    student_id_column: str | None = None,
) -> dict[str, Any]:
    """Load a CSV/XLSX marks file and evaluate it under course policy."""
    df = load_marks_file(file_path)

    return evaluate_marks(
        df=df,
        course_id=course_id,
        student_id_column=student_id_column,
    )
