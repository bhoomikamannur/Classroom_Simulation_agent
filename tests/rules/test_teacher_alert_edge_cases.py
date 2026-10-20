
import pytest

from backend.app.agents.teacher_alert_rules import determine_teacher_alert


def test_learning_difficulty_unknown_but_academic_performance_poor():
    result = determine_teacher_alert(
        None,
        True,
        academic_evidence=["Academic performance meets the review threshold."],
    )

    assert result["teacher_alert"] is True
    assert result["priority"] == "medium"
    assert result["data_incomplete"] is True


def test_learning_difficulty_unknown_and_academic_performance_good():
    result = determine_teacher_alert(None, False)

    assert result["teacher_alert"] is False
    assert result["priority"] == "none"
    assert result["data_incomplete"] is True


def test_academic_performance_unknown_and_no_persistent_difficulty():
    result = determine_teacher_alert(False, None)

    assert result["teacher_alert"] is False
    assert result["priority"] == "none"
    assert result["data_incomplete"] is True


def test_improving_student_does_not_trigger_difficulty_alert():
    # The upstream assessment has determined that difficulty is no
    # longer persistent. Improvement itself must be assessed upstream.
    result = determine_teacher_alert(
        False,
        False,
        learning_evidence=[
            "The student corrected the earlier misconception after tutoring."
        ],
    )

    assert result["teacher_alert"] is False
    assert result["priority"] == "none"


def test_evidence_is_preserved_without_changing_alert_decision():
    learning_evidence = [
        "The student struggled initially.",
        "The student improved after a targeted explanation.",
    ]
    academic_evidence = ["Current marks meet course requirements."]

    result = determine_teacher_alert(
        False,
        False,
        learning_evidence=learning_evidence,
        academic_evidence=academic_evidence,
    )

    assert result["teacher_alert"] is False
    assert result["learning_evidence"] == learning_evidence
    assert result["academic_evidence"] == academic_evidence


def test_empty_evidence_is_returned_as_empty_lists():
    result = determine_teacher_alert(False, False, [], [])

    assert result["learning_evidence"] == []
    assert result["academic_evidence"] == []
    assert result["data_incomplete"] is False


def test_invalid_condition_strings_are_rejected():
    with pytest.raises(ValueError):
        determine_teacher_alert("yes", False)


def test_integer_one_is_rejected_as_an_invalid_boolean():
    # Python considers 1 == True. The function should accept only
    # actual booleans or None for these condition inputs.
    with pytest.raises(ValueError):
        determine_teacher_alert(1, False)


def test_duplicate_evidence_does_not_change_priority():
    result = determine_teacher_alert(
        True,
        False,
        learning_evidence=[
            "The same misconception persisted.",
            "The same misconception persisted.",
            "The same misconception persisted.",
        ],
    )

    assert result["teacher_alert"] is True
    assert result["priority"] == "medium"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
