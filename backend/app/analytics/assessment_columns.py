"""Normalize assessment column names in uploaded marks files."""
from __future__ import annotations

import re
from typing import Any

import pandas as pd

from backend.app.analytics.academic_analysis import _find_student_id_column


def assessment_key(value: object) -> str:
    text = str(value).strip().lower()
    text = re.sub(r"(?:[_\-\s])*(?:marks?|scores?)$", "", text)
    text = re.sub(r"[^a-z0-9]", "", text)
    return text


def _max_base(value: object) -> tuple[str, bool]:
    raw = str(value).strip()
    match = re.search(r"(?:[_\-\s])*(?:max|maximum)(?:[_\-\s]*(?:marks?|scores?))?$", raw, flags=re.I)
    if match:
        return raw[:match.start()], True
    return raw, False


def normalize_marks_for_policy(
    df: pd.DataFrame,
    policy: dict[str, Any],
    student_id_column: str | None = None,
) -> tuple[pd.DataFrame, str]:
    """Return a marks frame with policy assessment names and max columns excluded.

    Accepted variants include Assignment 1 / assignment_1 / assignment1,
    with optional marks/score suffixes. *_max and *_maximum columns are
    metadata and, when present, must agree with the saved policy.
    """
    frame = df.copy()
    frame.columns = [str(column).strip() for column in frame.columns]
    if not frame.columns.is_unique:
        raise ValueError("The file contains duplicate column names. Rename them before uploading.")
    student_col = _find_student_id_column(frame, student_id_column)

    configured: dict[str, str] = {}
    for name in policy["assessment_weights"]:
        key = assessment_key(name)
        if key in configured:
            raise ValueError("The saved grading policy contains assessment names that become duplicates after normalization.")
        configured[key] = name

    marks_columns: dict[str, str] = {}
    maximum_columns: dict[str, str] = {}
    for column in frame.columns:
        if column == student_col:
            continue
        base, is_max = _max_base(column)
        key = assessment_key(base)
        if key not in configured:
            raise ValueError(f"Uploaded assessment columns must match the saved grading policy; column '{column}' is not configured.")
        assessment = configured[key]
        target = maximum_columns if is_max else marks_columns
        if assessment in target:
            raise ValueError(f"Ambiguous duplicate columns for '{assessment}': '{target[assessment]}' and '{column}'.")
        target[assessment] = column

    missing = sorted(set(policy["assessment_weights"]) - set(marks_columns))
    if missing:
        raise ValueError(f"Uploaded file is missing assessment mark columns: {missing}.")

    normalized = pd.DataFrame({student_col: frame[student_col]})
    for assessment, source in marks_columns.items():
        numeric = pd.to_numeric(frame[source], errors="coerce")
        invalid = frame[source].notna() & frame[source].astype("string").str.strip().ne("") & numeric.isna()
        if invalid.any():
            examples = frame.loc[invalid, source].astype(str).unique().tolist()[:5]
            raise ValueError(f"Assessment '{source}' contains non-numeric values {examples}.")
        normalized[assessment] = numeric

    for assessment, source in maximum_columns.items():
        values = pd.to_numeric(frame[source], errors="coerce").dropna().unique()
        if frame[source].notna().any() and len(values) == 0:
            raise ValueError(f"Maximum marks column '{source}' contains non-numeric values.")
        expected = float(policy["assessment_max_marks"][assessment])
        if any(abs(float(value) - expected) > 1e-8 for value in values):
            raise ValueError(f"Maximum marks in column '{source}' do not match the saved policy maximum ({expected}) for '{assessment}'.")
    return normalized, student_col
