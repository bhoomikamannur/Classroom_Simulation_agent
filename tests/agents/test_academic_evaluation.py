
import pandas as pd
import pytest

from backend.app.analytics.academic_evaluation import evaluate_marks


@pytest.fixture
def grading_policy():
    return {
        "course_id": "CS101",
        "assessment_weights": {
            "quiz": 20,
            "assignment": 30,
            "final_exam": 50,
        },
        "assessment_max_marks": {
            "quiz": 10,
            "assignment": 20,
            "final_exam": 100,
        },
        "pass_percentage": 40,
        "missing_marks_policy": "exclude",
    }


def test_evaluates_multiple_students(monkeypatch, grading_policy):
    monkeypatch.setattr(
        "backend.app.analytics.academic_evaluation.get_policy",
        lambda course_id: grading_policy,
    )

    df = pd.DataFrame({
        "student_id": ["S001", "S002"],
        "quiz": [8, 5],
        "assignment": [16, 10],
        "final_exam": [70, 40],
    })

    result = evaluate_marks(df, "CS101")

    assert result["number_of_students"] == 2

    students = {
        item["student_id"]: item
        for item in result["student_results"]
    }

    assert students["S001"]["weighted_percentage"] == 75
    assert students["S001"]["pass_status"] == "pass"

    assert students["S002"]["weighted_percentage"] == 45
    assert students["S002"]["pass_status"] == "pass"


def test_missing_marks_produce_provisional_result(
    monkeypatch, grading_policy
):
    monkeypatch.setattr(
        "backend.app.analytics.academic_evaluation.get_policy",
        lambda course_id: grading_policy,
    )

    df = pd.DataFrame({
        "student_id": ["S001"],
        "quiz": [8],
        "assignment": [16],
        "final_exam": [None],
    })

    result = evaluate_marks(df, "CS101")
    student = result["student_results"][0]

    assert student["weighted_percentage"] == 80
    assert student["pass_status"] == "provisional"
    assert student["is_complete"] is False
    assert student["missing_assessments"] == ["final_exam"]


def test_rejects_missing_course_policy(monkeypatch):
    monkeypatch.setattr(
        "backend.app.analytics.academic_evaluation.get_policy",
        lambda course_id: None,
    )

    df = pd.DataFrame({
        "student_id": ["S001"],
        "quiz": [8],
        "assignment": [16],
        "final_exam": [70],
    })

    with pytest.raises(ValueError, match="No academic grading policy"):
        evaluate_marks(df, "UNKNOWN")


def test_rejects_assessment_columns_that_do_not_match_policy(
    monkeypatch, grading_policy
):
    monkeypatch.setattr(
        "backend.app.analytics.academic_evaluation.get_policy",
        lambda course_id: grading_policy,
    )

    df = pd.DataFrame({
        "student_id": ["S001"],
        "quiz": [8],
        "assignment": [16],
        "midterm": [70],
    })

    with pytest.raises(ValueError, match="assessment columns must match"):
        evaluate_marks(df, "CS101")
