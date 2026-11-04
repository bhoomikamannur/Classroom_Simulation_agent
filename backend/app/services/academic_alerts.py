"""Persist evaluated academic outcomes and combine them with learning alerts.

Academic outcomes are contextual signals only: they never create a conceptual
misconception diagnosis. Only complete, explicitly evaluated results can be
classified as pass/fail.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.app.database.mongodb import get_mongodb_database
from backend.app.agents.teacher_alert_rules import determine_teacher_alert


def persist_evaluation_and_update_alerts(
    course_id: str,
    professor_id: str,
    student_results: list[dict[str, Any]],
    pass_percentage: float,
) -> dict[str, int]:
    db = get_mongodb_database()
    now = datetime.now(timezone.utc)
    saved = 0
    opened = 0
    updated = 0
    resolved = 0

    for result in student_results:
        student_id = str(result.get("student_id", "")).strip()
        if not student_id:
            continue

        status = result.get("pass_status")
        complete = bool(result.get("is_complete")) and status in {"pass", "fail"}
        academic_condition = (status == "fail") if complete else None
        percentage = result.get("weighted_percentage")
        academic_evidence = []
        if complete:
            academic_evidence.append(
                f"Latest complete evaluated result is {percentage}% "
                f"against the course pass threshold of {pass_percentage}%."
            )

        evaluation = {
            "student_id": student_id,
            "course_id": course_id,
            "professor_id": professor_id,
            "weighted_percentage": percentage,
            "pass_status": status,
            "is_complete": bool(result.get("is_complete")),
            "missing_assessments": result.get("missing_assessments", []),
            "pass_percentage": pass_percentage,
            "evaluated_at": now,
            "academic_evidence": academic_evidence,
        }
        db["academic_evaluation_results"].update_one(
            {"student_id": student_id, "course_id": course_id},
            {"$set": evaluation, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
        saved += 1

        misconception_query = {
            "student_id": student_id,
            "course_id": course_id,
            "alert_type": "persistent_misconception",
            "status": "open",
        }
        learning_alerts = list(db["teacher_alerts"].find(misconception_query))
        # A persistent learning condition is established upstream by the
        # cross-session misconception lifecycle, not by academic marks.
        learning_condition = bool(learning_alerts) if learning_alerts else False
        decision = determine_teacher_alert(
            learning_condition,
            academic_condition,
            learning_evidence=[
                str(item.get("message", "Persistent conceptual difficulty detected."))
                for item in learning_alerts
            ],
            academic_evidence=academic_evidence,
        )

        if learning_alerts:
            for alert in learning_alerts:
                db["teacher_alerts"].update_one(
                    {"_id": alert["_id"]},
                    {"$set": {
                        "priority": decision["priority"],
                        "academic_context": {
                            "pass_status": status,
                            "weighted_percentage": percentage,
                            "is_complete": bool(result.get("is_complete")),
                            "evaluated_at": now,
                        },
                        "priority_reasons": decision["reasons"],
                        "updated_at": now,
                    }},
                )
                updated += 1

        academic_identity = {
            "student_id": student_id,
            "course_id": course_id,
            "concept_key": "__academic_performance__",
            "alert_type": "academic_review",
        }
        existing = db["teacher_alerts"].find_one(academic_identity)
        if academic_condition is True:
            doc = {
                **academic_identity,
                "professor_id": professor_id,
                "concept": "Academic performance",
                "status": "open",
                "priority": "medium",
                "message": (
                    f"Latest complete academic result is {percentage}% "
                    f"against the {pass_percentage}% pass threshold."
                ),
                "academic_context": evaluation,
                "priority_reasons": decision["reasons"],
                "latest_seen_at": now,
                "updated_at": now,
            }
            if existing:
                db["teacher_alerts"].update_one(
                    academic_identity,
                    {"$set": doc, "$unset": {
                        "resolved_at": "", "resolution_reason": "",
                        "closed_at": "", "closed_by": "",
                        "acknowledged_at": "", "acknowledged_by": "",
                    }},
                )
                updated += 1
            else:
                doc["created_at"] = now
                db["teacher_alerts"].insert_one(doc)
                opened += 1
        elif academic_condition is False and existing and existing.get("status") == "open":
            db["teacher_alerts"].update_one(
                academic_identity,
                {"$set": {
                    "status": "resolved",
                    "resolved_at": now,
                    "resolution_reason": "A later complete evaluation met the course pass threshold.",
                    "latest_seen_at": now,
                    "academic_context": evaluation,
                    "updated_at": now,
                }},
            )
            resolved += 1

    return {"saved_results": saved, "alerts_opened": opened,
            "alerts_updated": updated, "alerts_resolved": resolved}
