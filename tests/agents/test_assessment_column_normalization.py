import pandas as pd
import pytest

from backend.app.analytics.assessment_columns import normalize_marks_for_policy


@pytest.fixture
def policy():
    return {
        "assessment_weights": {"Assignment 1": 30, "Exam": 70},
        "assessment_max_marks": {"Assignment 1": 10, "Exam": 100},
    }


def test_normalizes_assessment_aliases_and_excludes_max_columns(policy):
    frame = pd.DataFrame({
        "roll_number": ["23bcs000", "23bcs001"],
        "assignment_1_marks": [8, 9],
        "assignment_1_max": [10, 10],
        "EXAM_SCORE": [70, 80],
        "exam_maximum_marks": [100, 100],
    })
    normalized, student_column = normalize_marks_for_policy(frame, policy)
    assert student_column == "roll_number"
    assert list(normalized.columns) == ["roll_number", "Assignment 1", "Exam"]
    assert normalized["Assignment 1"].tolist() == [8, 9]


def test_rejects_duplicate_alias_columns(policy):
    frame = pd.DataFrame({
        "roll_number": ["23bcs000"],
        "Assignment 1": [8],
        "assignment_1_marks": [9],
        "Exam": [70],
    })
    with pytest.raises(ValueError, match="Ambiguous duplicate"):
        normalize_marks_for_policy(frame, policy)


def test_rejects_mismatched_uploaded_maximum(policy):
    frame = pd.DataFrame({
        "roll_number": ["23bcs000"],
        "assignment1": [8],
        "assignment1_max": [20],
        "exam": [70],
    })
    with pytest.raises(ValueError, match="do not match the saved policy maximum"):
        normalize_marks_for_policy(frame, policy)
