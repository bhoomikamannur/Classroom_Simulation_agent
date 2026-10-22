
import pytest

from backend.app.analytics.academic_policy import (
    calculate_weighted_result,
    validate_academic_policy,
)


@pytest.fixture
def policy():
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


def test_validates_course_policy(policy):
    result = validate_academic_policy(policy)

    assert result["course_id"] == "CS101"
    assert sum(result["assessment_weights"].values()) == 100


def test_calculates_weighted_percentage(policy):
    marks = {
        "quiz": 8,
        "assignment": 15,
        "final_exam": 80,
    }

    result = calculate_weighted_result(marks, policy)

    assert result["weighted_percentage"] == 78.5
    assert result["pass_status"] == "pass"
    assert result["is_complete"] is True


def test_missing_marks_are_excluded_and_result_is_provisional(policy):
    marks = {
        "quiz": 8,
        "assignment": 15,
        "final_exam": None,
    }

    result = calculate_weighted_result(marks, policy)

    assert result["weighted_percentage"] == 77.0
    assert result["pass_status"] == "provisional"
    assert result["is_complete"] is False
    assert result["missing_assessments"] == ["final_exam"]


def test_missing_marks_count_as_zero_only_when_configured(policy):
    policy["missing_marks_policy"] = "zero"

    marks = {
        "quiz": 8,
        "assignment": 15,
        "final_exam": None,
    }

    result = calculate_weighted_result(marks, policy)

    assert result["weighted_percentage"] == 38.5
    assert result["pass_status"] == "fail"
    assert result["is_complete"] is False


def test_all_marks_missing_are_not_assessed(policy):
    marks = {
        "quiz": None,
        "assignment": None,
        "final_exam": None,
    }

    result = calculate_weighted_result(marks, policy)

    assert result["weighted_percentage"] is None
    assert result["pass_status"] == "not_assessed"


def test_rejects_weights_that_do_not_total_100(policy):
    policy["assessment_weights"]["quiz"] = 10

    with pytest.raises(ValueError, match="total exactly 100"):
        validate_academic_policy(policy)


def test_rejects_mismatched_assessment_names(policy):
    policy["assessment_max_marks"]["project"] = 50

    with pytest.raises(ValueError, match="same assessment names"):
        validate_academic_policy(policy)


def test_rejects_invalid_missing_marks_policy(policy):
    policy["missing_marks_policy"] = "guess"

    with pytest.raises(ValueError, match="missing_marks_policy"):
        validate_academic_policy(policy)


def test_rejects_marks_above_maximum(policy):
    marks = {
        "quiz": 11,
        "assignment": 15,
        "final_exam": 80,
    }

    with pytest.raises(ValueError, match="between 0"):
        calculate_weighted_result(marks, policy)


def test_rejects_unknown_assessment_in_marks(policy):
    marks = {
        "quiz": 8,
        "assignment": 15,
        "final_exam": 80,
        "project": 20,
    }

    with pytest.raises(ValueError, match="Unknown assessments"):
        calculate_weighted_result(marks, policy)
