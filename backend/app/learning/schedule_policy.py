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
