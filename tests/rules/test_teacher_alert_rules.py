
from backend.app.agents.teacher_alert_rules import determine_teacher_alert


def test_neither_condition():
    result = determine_teacher_alert(False, False)

    assert result["teacher_alert"] is False
    assert result["priority"] == "none"


def test_persistent_difficulty_only():
    result = determine_teacher_alert(
        True,
        False,
        learning_evidence=[
            "The same misconception persisted after multiple explanations."
        ],
    )

    assert result["teacher_alert"] is True
    assert result["priority"] == "medium"
    assert result["data_incomplete"] is False


def test_poor_academic_performance_only():
    result = determine_teacher_alert(
        False,
        True,
        academic_evidence=[
            "Assessment results meet the defined low-performance threshold."
        ],
    )

    assert result["teacher_alert"] is True
    assert result["priority"] == "medium"
    assert result["data_incomplete"] is False


def test_both_conditions_high_priority():
    result = determine_teacher_alert(
        True,
        True,
        learning_evidence=[
            "Persistent difficulty despite targeted explanations."
        ],
        academic_evidence=[
            "Assessment results meet the defined low-performance threshold."
        ],
    )

    assert result["teacher_alert"] is True
    assert result["priority"] == "high"
    assert len(result["reasons"]) == 2


def test_missing_academic_data():
    result = determine_teacher_alert(
        True,
        None,
        learning_evidence=[
            "Persistent difficulty meets the review threshold."
        ],
    )

    # The confirmed learning difficulty is enough for a review.
    assert result["teacher_alert"] is True
    assert result["priority"] == "medium"

    # Missing marks must still be disclosed.
    assert result["data_incomplete"] is True


def test_no_alert_when_only_unconfirmed_data_is_missing():
    result = determine_teacher_alert(None, None)

    assert result["teacher_alert"] is False
    assert result["priority"] == "none"
    assert result["data_incomplete"] is True


if __name__ == "__main__":
    tests = [
        test_neither_condition,
        test_persistent_difficulty_only,
        test_poor_academic_performance_only,
        test_both_conditions_high_priority,
        test_missing_academic_data,
        test_no_alert_when_only_unconfirmed_data_is_missing,
    ]

    for test in tests:
        test()
        print(f"PASS: {test.__name__}")

    print(f"\nAll {len(tests)} teacher-alert rule tests passed.")
