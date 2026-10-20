
from typing import Any


def determine_teacher_alert(
    persistent_learning_difficulty: bool | None,
    poor_academic_performance: bool | None,
    learning_evidence: list[str] | None = None,
    academic_evidence: list[str] | None = None,
) -> dict[str, Any]:
    """
    Decide whether teacher review is recommended.

    True  = condition meets its predefined threshold.
    False = condition was evaluated and threshold was not met.
    None  = condition could not be evaluated due to missing data.

    Thresholds for persistent difficulty and poor academic performance
    must be defined by the system using its evidence and assessment policy.
    """

    if (
        persistent_learning_difficulty is not True
        and persistent_learning_difficulty is not False
        and persistent_learning_difficulty is not None
    ):
        raise ValueError(
            "persistent_learning_difficulty must be True, False, or None."
        )

    if (
        poor_academic_performance is not True
        and poor_academic_performance is not False
        and poor_academic_performance is not None
    ):
        raise ValueError(
            "poor_academic_performance must be True, False, or None."
        )

    learning_evidence = learning_evidence or []
    academic_evidence = academic_evidence or []

    difficulty_present = persistent_learning_difficulty is True
    poor_performance_present = poor_academic_performance is True

    data_incomplete = (
        persistent_learning_difficulty is None
        or poor_academic_performance is None
    )

    reasons = []

    if difficulty_present:
        reasons.append("Persistent learning difficulty meets the review threshold.")

    if poor_performance_present:
        reasons.append("Poor academic performance meets the review threshold.")

    if difficulty_present and poor_performance_present:
        alert = True
        priority = "high"
        recommendation = (
            "Prompt teacher review is recommended because both persistent "
            "learning difficulty and poor academic performance are present."
        )

    elif difficulty_present or poor_performance_present:
        alert = True
        priority = "medium"
        recommendation = (
            "Teacher review is recommended based on the condition that "
            "meets its review threshold. Review the available evidence."
        )

    else:
        alert = False
        priority = "none"

        if data_incomplete:
            recommendation = (
                "No alert is triggered by the currently confirmed conditions. "
                "Some data is unavailable, so gather the missing evidence "
                "before concluding that no support is needed."
            )
        else:
            recommendation = (
                "Neither condition meets its review threshold. Continue "
                "routine tutoring and monitor the student's progress."
            )

    return {
        "teacher_alert": alert,
        "priority": priority,
        "reasons": reasons,
        "learning_evidence": learning_evidence,
        "academic_evidence": academic_evidence,
        "data_incomplete": data_incomplete,
        "recommendation": recommendation,
    }
