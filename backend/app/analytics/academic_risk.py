"""Assessment-level academic risk signals with explainable evidence."""
from __future__ import annotations

from typing import Any


def _percentage(marks: Any, maximum: Any) -> float | None:
    try:
        score, total = float(marks), float(maximum)
        if total <= 0 or score < 0:
            return None
        return max(0.0, min(100.0, score / total * 100.0))
    except (TypeError, ValueError):
        return None


def analyse_assessment_risk(
    student_id: str,
    student_record: dict[str, Any] | None,
    course_records: list[dict[str, Any]],
    policy: dict[str, Any] | None = None,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compare each current assessment with its cohort and prior recorded score.

    Risk is based on normalized percentages, never raw marks with different
    maximums. Repeated poor performance is required for a high alert.
    """
    student_record = student_record or {}
    policy = policy or {}
    history = history or []
    assessments = student_record.get("assessments", {}) or {}
    weights = policy.get("assessment_weights", {}) or {}
    maximums = policy.get("assessment_max_marks", {}) or {}
    histories: dict[str, list[float]] = {}
    for event in sorted(history, key=lambda x: str(x.get("recorded_at", ""))):
        key = event.get("assessment_key")
        pct = _percentage(event.get("marks"), event.get("maximum_marks"))
        if key and pct is not None:
            values = histories.setdefault(str(key), [])
            if not values or abs(values[-1] - pct) >= 0.01:
                values.append(pct)

    breakdown = []
    poor_keys = []
    total_weight = 0.0
    weighted_risk = 0.0
    for key, item in assessments.items():
        if not isinstance(item, dict) or item.get("marks") is None:
            continue
        maximum = maximums.get(key) or item.get("maximum_marks")
        student_pct = _percentage(item.get("marks"), maximum)
        if student_pct is None:
            continue
        cohort = []
        for record in course_records:
            value = (record.get("assessments", {}) or {}).get(key, {})
            if isinstance(value, dict):
                pct = _percentage(value.get("marks"), maximums.get(key) or value.get("maximum_marks") or maximum)
            else:
                pct = _percentage(value, maximum)
            if pct is not None:
                cohort.append(pct)
        class_avg = sum(cohort) / len(cohort) if cohort else None
        gap = class_avg - student_pct if class_avg is not None else None

        absolute_risk = 0.0
        if student_pct < 40:
            absolute_risk = 80.0
        elif student_pct < 50:
            absolute_risk = 65.0
        elif student_pct < 60:
            absolute_risk = 35.0
        elif student_pct < 65:
            absolute_risk = 15.0
        relative_risk = 0.0
        if gap is not None:
            if gap >= 25:
                relative_risk = 25.0
            elif gap >= 15:
                relative_risk = 18.0
            elif gap >= 10:
                relative_risk = 10.0
            elif gap >= 5:
                relative_risk = 5.0
        assessment_risk = min(100.0, absolute_risk + relative_risk)
        poor = student_pct < 50 or (gap is not None and gap >= 15 and student_pct < 60)
        if poor:
            poor_keys.append(key)

        previous_values = histories.get(str(key), [])
        previous_pct = previous_values[-1] if previous_values else None
        # The latest upload snapshot commonly duplicates the current register value.
        if previous_pct is not None and abs(previous_pct - student_pct) < 0.01 and len(previous_values) > 1:
            previous_pct = previous_values[-2]
        change = student_pct - previous_pct if previous_pct is not None else None
        weight = float(weights.get(key, 1.0) or 1.0)
        total_weight += weight
        weighted_risk += assessment_risk * weight
        breakdown.append({
            "assessment_key": key,
            "assessment_name": item.get("name", key),
            "student_percentage": round(student_pct, 1),
            "class_average_percentage": round(class_avg, 1) if class_avg is not None else None,
            "gap_from_class_average": round(gap, 1) if gap is not None else None,
            "previous_percentage": round(previous_pct, 1) if previous_pct is not None else None,
            "change_from_previous": round(change, 1) if change is not None else None,
            "weight": weight,
            "risk_score": round(assessment_risk, 1),
            "poor_performance": poor,
            "cohort_size": len(cohort),
        })

    if not breakdown:
        return {"score": 0.0, "available": False, "evidence": [], "assessments": [], "high_alert": False}

    consistency = len(poor_keys)
    poor_ratio = consistency / len(breakdown) if breakdown else 0.0
    # Avoid calling a student consistently poor when only a small minority of
    # their assessments are low. Two of two/three is a pattern; isolated lows
    # among many assessments remain monitoring evidence.
    consistent_low_pattern = consistency >= 2 and (
        poor_ratio >= 0.5 or (consistency >= 3 and poor_ratio >= 0.4)
    )
    consistency_risk = 90.0 if consistent_low_pattern and consistency >= 3 else (
        75.0 if consistent_low_pattern else 0.0
    )
    base_score = weighted_risk / total_weight if total_weight else 0.0
    score = max(base_score, consistency_risk)
    # A high alert requires a repeated pattern, not one isolated quiz.
    high_alert = consistent_low_pattern and score >= 65
    evidence = []
    for item in breakdown:
        if item["poor_performance"]:
            detail = (
                f"{item['assessment_name']}: {item['student_percentage']:.1f}%"
                + (f", class average {item['class_average_percentage']:.1f}%"
                   f" (gap {item['gap_from_class_average']:.1f} percentage points)"
                   if item["class_average_percentage"] is not None else "")
                + (f", previous recorded score {item['previous_percentage']:.1f}%"
                   if item["previous_percentage"] is not None else "")
            )
            evidence.append({
                "issue": "Poor performance in assessment",
                "severity": "high" if high_alert else "medium",
                "source": "Assessment-wise academic analysis",
                "details": detail,
            })
    if consistent_low_pattern:
        evidence.append({
            "issue": "Consistently low assessment performance",
            "severity": "high" if high_alert else "medium",
            "source": "Assessment-wise academic analysis",
            "details": f"Poor performance detected in {consistency} of {len(breakdown)} assessed components.",
        })
    declining = [item for item in breakdown if item["change_from_previous"] is not None and item["change_from_previous"] <= -10]
    if declining:
        evidence.append({
            "issue": "Declining performance compared with previous recorded scores",
            "severity": "medium",
            "source": "Assessment history",
            "details": f"Performance declined by at least 10 percentage points in {len(declining)} assessment(s) compared with the previous recorded score.",
        })
    return {
        "score": round(max(0.0, min(100.0, score)), 1),
        "available": True,
        "evidence": evidence,
        "assessments": breakdown,
        "poor_assessment_count": consistency,
        "poor_assessment_ratio": round(poor_ratio, 2),
        "consistent_low_pattern": consistent_low_pattern,
        "assessed_component_count": len(breakdown),
        "high_alert": high_alert,
    }
