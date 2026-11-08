"""Persistence helpers for the latest evaluated course report."""
from datetime import datetime, timezone
from typing import Any

from backend.app.database.mongodb import get_mongodb_database


def save_latest_evaluation_report(report: dict[str, Any]) -> dict[str, Any]:
    course_id = str(report.get("course_id", "")).strip()
    if not course_id:
        raise ValueError("course_id is required to save an evaluation report.")
    document = {
        **report,
        "course_id": course_id,
        "is_current": True,
        "evaluated_at": report.get("evaluated_at") or datetime.now(timezone.utc),
    }
    get_mongodb_database()["academic_evaluation_reports"].replace_one(
        {"course_id": course_id}, document, upsert=True
    )
    return document


def get_latest_evaluation_report(course_id: str) -> dict[str, Any] | None:
    return get_mongodb_database()["academic_evaluation_reports"].find_one(
        {"course_id": course_id, "is_current": True}, {"_id": 0}
    )


def invalidate_latest_evaluation_report(course_id: str) -> None:
    """Mark the calculated report stale when marks or grading rules change."""
    get_mongodb_database()["academic_evaluation_reports"].update_one(
        {"course_id": course_id},
        {"$set": {"is_current": False, "invalidated_at": datetime.now(timezone.utc)}},
    )
