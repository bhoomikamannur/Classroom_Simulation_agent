
from typing import Any
import math

VALID_MISSING_MARKS_POLICIES = {"exclude", "zero"}


def validate_academic_policy(policy: dict[str, Any]) -> dict[str, Any]:
    """
    Validate a teacher-configured grading policy.

    Expected structure:
    {
        "course_id": "CS101",
        "assessment_weights": {
            "quiz": 20,
            "assignment": 30,
            "final_exam": 50
        },
        "assessment_max_marks": {
            "quiz": 10,
            "assignment": 20,
            "final_exam": 100
        },
        "pass_percentage": 40,
        "missing_marks_policy": "exclude"
    }

    Weight values are percentages and must total 100.
    Missing marks are never treated as zero unless explicitly configured.
    """

    if not isinstance(policy, dict):
        raise ValueError("Policy must be a dictionary.")

    course_id = policy.get("course_id")
    if not isinstance(course_id, str) or not course_id.strip():
        raise ValueError("course_id must be a non-empty string.")

    weights = policy.get("assessment_weights")
    maximums = policy.get("assessment_max_marks")
    pass_percentage = policy.get("pass_percentage")
    missing_policy = policy.get("missing_marks_policy")

    if not isinstance(weights, dict) or not weights:
        raise ValueError("assessment_weights must be a non-empty dictionary.")

    if not isinstance(maximums, dict) or not maximums:
        raise ValueError("assessment_max_marks must be a non-empty dictionary.")

    if set(weights) != set(maximums):
        raise ValueError(
            "Every weighted assessment must have a maximum mark, "
            "and both configurations must use the same assessment names."
        )

    for name, weight in weights.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Assessment names must be non-empty strings.")

        if (
            isinstance(weight, bool)
            or not isinstance(weight, (int, float))
            or not math.isfinite(weight)
        ):
            raise ValueError(f"Weight for '{name}' must be a finite number.")

        if not 0 < weight <= 100:
            raise ValueError(
                f"Weight for '{name}' must be greater than 0 and at most 100."
            )


    if not abs(sum(weights.values()) - 100.0) < 1e-8:
        raise ValueError("Assessment weights must total exactly 100%.")

    for name, maximum in maximums.items():
        if (
            isinstance(maximum, bool)
            or not isinstance(maximum, (int, float))
            or not math.isfinite(maximum)
        ):
            raise ValueError(
                f"Maximum marks for '{name}' must be a finite number."
            )

        if maximum <= 0:
            raise ValueError(
                f"Maximum marks for '{name}' must be greater than zero."
            )
        
    if (
        isinstance(pass_percentage, bool)
        or not isinstance(pass_percentage, (int, float))
        or not 0 <= pass_percentage <= 100
    ):
        raise ValueError("pass_percentage must be between 0 and 100.")

    if missing_policy not in VALID_MISSING_MARKS_POLICIES:
        raise ValueError(
            "missing_marks_policy must be 'exclude' or 'zero'."
        )

    return {
        "course_id": course_id.strip(),
        "assessment_weights": dict(weights),
        "assessment_max_marks": dict(maximums),
        "pass_percentage": float(pass_percentage),
        "missing_marks_policy": missing_policy,
    }


def calculate_weighted_result(
    marks: dict[str, float | int | None],
    policy: dict[str, Any],
) -> dict[str, Any]:
    """
    Calculate a student's weighted percentage using a validated policy.

    With 'exclude', missing assessments are omitted and the remaining
    assessment weights are normalized to calculate a provisional score.
    The result is marked incomplete.

    With 'zero', missing assessments count as zero only because the
    teacher explicitly configured that policy.
    """

    policy = validate_academic_policy(policy)

    if not isinstance(marks, dict):
        raise ValueError("marks must be a dictionary.")

    weights = policy["assessment_weights"]
    maximums = policy["assessment_max_marks"]
    missing_policy = policy["missing_marks_policy"]

    unknown = set(marks) - set(weights)
    if unknown:
        raise ValueError(f"Unknown assessments in marks: {sorted(unknown)}")

    percentages: dict[str, float] = {}
    missing_assessments: list[str] = []

    for assessment in weights:
        raw_mark = marks.get(assessment)

        if raw_mark is None:
            missing_assessments.append(assessment)
            continue

        if isinstance(raw_mark, bool) or not isinstance(raw_mark, (int, float)):
            raise ValueError(f"Mark for '{assessment}' must be numeric or None.")

        if not 0 <= raw_mark <= maximums[assessment]:
            raise ValueError(
                f"Mark for '{assessment}' must be between 0 and "
                f"{maximums[assessment]}."
            )

        percentages[assessment] = (
            float(raw_mark) / maximums[assessment]
        ) * 100.0

    if missing_assessments and missing_policy == "exclude":
        applicable = [
            assessment for assessment in weights
            if assessment in percentages
        ]

        if not applicable:
            return {
                "course_id": policy["course_id"],
                "weighted_percentage": None,
                "pass_status": "not_assessed",
                "is_complete": False,
                "missing_assessments": missing_assessments,
                "message": "No marks are available for evaluation.",
            }

        applicable_weight = sum(weights[name] for name in applicable)
        score = sum(
            percentages[name] * weights[name] for name in applicable
        ) / applicable_weight

        return {
            "course_id": policy["course_id"],
            "weighted_percentage": round(score, 2),
            "pass_status": "provisional",
            "is_complete": False,
            "missing_assessments": missing_assessments,
            "message": (
                "Provisional score: missing assessments were excluded "
                "and the available weights were normalized."
            ),
        }

    # If missing_policy == "zero", the teacher has explicitly authorized
    # missing assessments to count as zero.
    score = sum(
        percentages.get(assessment, 0.0) * weights[assessment]
        for assessment in weights
    ) / 100.0

    passed = score >= policy["pass_percentage"]

    return {
        "course_id": policy["course_id"],
        "weighted_percentage": round(score, 2),
        "pass_status": "pass" if passed else "fail",
        "is_complete": not missing_assessments,
        "missing_assessments": missing_assessments,
        "message": (
            "Missing assessments were counted as zero under the "
            "configured course policy."
            if missing_assessments
            else "All configured assessments have marks."
        ),
    }
