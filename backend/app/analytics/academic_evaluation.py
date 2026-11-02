from pathlib import Path
from typing import Any

import pandas as pd

from backend.app.analytics.academic_analysis import load_marks_file, _prepare_marks
from backend.app.analytics.assessment_columns import normalize_marks_for_policy
from backend.app.analytics.academic_policy import calculate_weighted_result
from backend.app.analytics.policy_store import get_policy


def evaluate_marks(
    df: pd.DataFrame,
    course_id: str,
    student_id_column: str | None = None,
) -> dict[str, Any]:
    """Evaluate uploaded marks using the saved course grading policy."""
    policy = get_policy(course_id)
    if policy is None:
        raise ValueError(f"No academic grading policy exists for course '{course_id}'.")

    normalized, id_column = normalize_marks_for_policy(df, policy, student_id_column)
    prepared, assessment_columns = _prepare_marks(normalized, id_column)
    results = []
    for _, row in prepared.iterrows():
        marks = {
            assessment: float(row[assessment]) if pd.notna(row[assessment]) else None
            for assessment in assessment_columns
        }
        result = calculate_weighted_result(marks, policy)
        results.append({"student_id": str(row[id_column]), **result})

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
    return evaluate_marks(load_marks_file(file_path), course_id, student_id_column)
