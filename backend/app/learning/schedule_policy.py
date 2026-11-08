"""Pure scheduling policy helpers, kept independent for fast synthetic tests."""
from typing import Any


def select_balanced_week(candidates: list[int], weeks: dict[int, dict[str, Any]],
                         capacity: float, effort: float, start_week: int,
                         end_week: int) -> int:
    """Choose the least-loaded feasible week, preferring the baseline window."""
    feasible = [w for w in candidates if weeks[w]["planned_hours"] + effort <= capacity + 1e-6]
    pool = feasible if feasible else candidates
    midpoint = (start_week + end_week) / 2
    return min(pool, key=lambda w: (
        weeks[w]["planned_hours"] / max(capacity, 0.1),
        sum(1 for a in weeks[w]["activities"] if a.get("schedule_type") == "required"),
        abs(w - midpoint) if start_week <= w <= end_week else 10_000,
        w,
    ))


def calculate_current_week(start_date, today, total_weeks: int) -> int:
    """Resolve a semester-relative week from the shared semester start date."""
    days = (today - start_date).days
    return min(max(1, total_weeks), max(1, days // 7 + 1))


def is_carry_forward(previous_required_week: int | None,
                     baseline_end_week: int,
                     current_week: int) -> bool:
    """An incomplete required topic from a past week is due in the current week."""
    return bool(
        (previous_required_week is not None and previous_required_week < current_week)
        or baseline_end_week < current_week
    )


def adaptive_course_allocations(topics: list[dict[str, Any]], capacity: float) -> list[dict[str, Any]]:
    """Allocate weekly hours by remaining syllabus effort and assessed mastery."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for topic in topics:
        grouped.setdefault(topic["course_id"], []).append(topic)
    weights: dict[str, float] = {}
    metadata: dict[str, dict[str, Any]] = {}
    for course_id, rows in grouped.items():
        pending = [t for t in rows if t["coverage_status"] in {"not_covered", "revision_required"}]
        remaining_effort = sum(t["estimated_effort_hours"] for t in pending)
        scored = [t["mastery_score"] for t in rows if t.get("mastery_score") is not None]
        average = sum(scored) / len(scored) if scored else None
        low_ratio = sum(1 for score in scored if score < 60) / len(scored) if scored else 0.0
        if remaining_effort <= 0:
            multiplier, reason = 0.0, "Syllabus topics are covered; spare capacity can support enrichment or revision."
        elif low_ratio >= 0.30:
            multiplier = 1.0 + min(0.50, low_ratio * 0.75)
            reason = "More time allocated because several assessed topics show weak mastery."
        elif average is not None and average >= 80 and low_ratio < 0.15:
            multiplier, reason = 0.80, "Less time allocated because recent topic mastery is strong."
        else:
            multiplier, reason = 1.0, "Maintains the baseline pace from the professor's lesson plan."
        weights[course_id] = remaining_effort * multiplier
        metadata[course_id] = {
            "course_id": course_id, "course_name": rows[0]["course_name"],
            "remaining_effort_hours": round(remaining_effort, 1),
            "average_mastery": round(average, 1) if average is not None else None,
            "weak_topic_ratio": round(low_ratio, 2), "allocation_reason": reason,
            "performance_band": "needs_support" if low_ratio >= 0.30 else (
                "strong" if average is not None and average >= 80 else "developing"
            ),
        }
    total_weight = sum(weights.values())
    if total_weight <= 0:
        # When every syllabus topic is already covered, reserve the student's
        # available capacity for enrichment/reinforcement rather than showing
        # a misleading zero-hour allocation.
        eligible = [course_id for course_id, rows in grouped.items()
                    if any(t["coverage_status"] in {"covered", "mastered"} for t in rows)]
        for course_id in eligible:
            weights[course_id] = 1.0
        total_weight = sum(weights.values())
    allocations = []
    for course_id, data in metadata.items():
        allocated = capacity * weights[course_id] / total_weight if total_weight > 0 else 0.0
        allocations.append({**data, "weekly_hours": round(allocated, 1),
                            "weekly_share_percent": round(allocated / capacity * 100, 1) if capacity else 0})
    if allocations and total_weight > 0:
        drift = round(capacity - sum(row["weekly_hours"] for row in allocations), 1)
        target = max(allocations, key=lambda row: row["weekly_hours"])
        target["weekly_hours"] = round(target["weekly_hours"] + drift, 1)
        target["weekly_share_percent"] = round(target["weekly_hours"] / capacity * 100, 1) if capacity else 0
    return sorted(allocations, key=lambda row: row["course_name"].lower())


def revision_week_after_assessment(assessed_week: int | None,
                                   current_week: int,
                                   total_weeks: int) -> int | None:
    """Place weak-assessment revision in the following week, never in the past."""
    if assessed_week is None:
        return None
    return min(total_weeks, max(current_week, assessed_week + 1))
