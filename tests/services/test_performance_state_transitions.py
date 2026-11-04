from backend.app.services.incremental_performance import (
    _alert_lifecycle_action,
    _apply_longitudinal_transitions,
    _transition_state,
)


def test_confused_student_requires_convincing_evidence_to_resolve():
    assert _transition_state("confused", "understood", ["Correct answer."], "medium") == "partial"
    assert _transition_state(
        "confused",
        "understood",
        ["The student explains the mechanism and why it works in this example."],
        "high",
    ) == "understood"


def test_partial_can_progress_to_understood_with_high_confidence():
    assert _transition_state("partial", "understood", ["Clear explanation."], "high") == "understood"


def test_missing_evidence_retains_previous_state():
    assert _transition_state("confused", "unclear", [], "low") == "confused"
    assert _transition_state("understood", "insufficient_evidence", [], "low") == "understood"


def test_later_conflicting_evidence_reopens_diagnostic_state():
    assert _transition_state("understood", "confused", ["The claim conflicts with the course reference."], "high") == "confused"


def test_longitudinal_transition_is_reflected_in_shared_diagnosis():
    performance = {
        "diagnosis": {
            "confidence": "medium",
            "concepts": [{
                "concept": "Binary Search",
                "understanding": "understood",
                "evidence": ["It works."],
                "misconceptions": [],
            }],
        }
    }
    _apply_longitudinal_transitions(
        performance,
        {"concepts": {"binary_search": {"current_state": "confused"}}},
    )
    item = performance["diagnosis"]["concepts"][0]
    assert item["proposed_understanding"] == "understood"
    assert item["understanding"] == "partial"



def test_resolved_misconception_alert_leaves_active_alert_list():
    assert _alert_lifecycle_action("understood", alert_exists=True, prior_separate_session=False) == "resolve"


def test_returning_misconception_reopens_existing_alert():
    assert _alert_lifecycle_action("confused", alert_exists=True, prior_separate_session=False) == "open"


def test_new_alert_requires_persistent_evidence():
    assert _alert_lifecycle_action("confused", alert_exists=False, prior_separate_session=False) == "none"
    assert _alert_lifecycle_action("confused", alert_exists=False, prior_separate_session=True) == "open"
