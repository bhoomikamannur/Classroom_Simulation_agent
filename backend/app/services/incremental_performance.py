"""Activity-triggered, incremental learning analysis.

Only new, deterministic candidate student responses are sent to the
Performance Agent. Pending records are acknowledged only after a valid
analysis and persistent profile/evidence updates have completed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4
import re
import hashlib

from pymongo import ASCENDING, ReturnDocument

from backend.app.database.mongodb import get_mongodb_database
from backend.app.memory.learning_store import ensure_learning_indexes

ANALYSIS_THRESHOLD = 10
BATCH_SIZE = 10
LOCK_MINUTES = 15


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _db():
    return get_mongodb_database()


def ensure_incremental_indexes() -> None:
    ensure_learning_indexes()
    _db()["interaction_evidence"].create_index(
        [("student_id", ASCENDING), ("course_id", ASCENDING), ("created_at", ASCENDING)],
        name="student_course_evidence_timeline",
    )
    _db()["interaction_evidence"].create_index(
        [("batch_id", ASCENDING), ("concept_key", ASCENDING)],
        unique=True,
        name="unique_batch_concept_evidence",
    )
    _db()["student_learning_profiles"].create_index(
        [("student_id", ASCENDING), ("course_id", ASCENDING)],
        unique=True,
        name="unique_student_course_learning_profile",
    )
    _db()["teacher_alerts"].create_index(
        [("student_id", ASCENDING), ("course_id", ASCENDING), ("concept_key", ASCENDING), ("alert_type", ASCENDING)],
        unique=True,
        name="unique_student_course_concept_alert",
    )


def get_analysis_status(student_id: str, course_id: str) -> dict[str, Any]:
    ensure_incremental_indexes()
    state = _db()["learning_analysis_state"].find_one(
        {"student_id": student_id, "course_id": course_id}, {"_id": 0}
    ) or {}
    pending = _db()["learning_interactions"].count_documents({
        "student_id": student_id,
        "course_id": course_id,
        "role": "user",
        "meaningful_candidate": True,
        "analysis_status": "pending",
    })
    profile = _db()["student_learning_profiles"].find_one(
        {"student_id": student_id, "course_id": course_id},
        {"_id": 0, "concepts": 1, "updated_at": 1, "latest_diagnosis": 1, "latest_intervention": 1},
    ) or {}
    concept_map = profile.get("concepts", {})
    concept_list = list(concept_map.values()) if isinstance(concept_map, dict) else concept_map
    alerts = list(_db()["teacher_alerts"].find(
        {"student_id": student_id, "course_id": course_id, "status": "open"},
        {"_id": 0, "alert_type": 1, "concept": 1, "priority": 1, "message": 1, "created_at": 1},
    ).sort("created_at", -1).limit(20))
    return {
        "student_id": student_id,
        "course_id": course_id,
        "pending_meaningful_responses": pending,
        "analysis_threshold": ANALYSIS_THRESHOLD,
        "threshold_reached": pending >= ANALYSIS_THRESHOLD,
        "analysis_in_progress": bool(state.get("analysis_lock")),
        "last_analyzed_at": state.get("last_analyzed_at"),
        "last_analysis_status": state.get("last_analysis_status", "not_yet_analyzed"),
        "last_analysis_error": state.get("last_analysis_error"),
        "retry_after": state.get("retry_after"),
        "concepts": concept_list,
        "latest_diagnosis": profile.get("latest_diagnosis"),
        "latest_intervention": profile.get("latest_intervention"),
        "profile_updated_at": profile.get("updated_at"),
        "open_teacher_alerts": alerts,
    }


def _claim(student_id: str, course_id: str) -> str | None:
    now = _now()
    lock_id = str(uuid4())
    state = _db()["learning_analysis_state"].find_one_and_update(
        {
            "student_id": student_id,
            "course_id": course_id,
            "$or": [
                {"analysis_lock": {"$exists": False}},
                {"lock_expires_at": {"$lt": now}},
            ],
        },
        {
            "$set": {
                "analysis_lock": lock_id,
                "lock_expires_at": now + timedelta(minutes=LOCK_MINUTES),
                "analysis_started_at": now,
                "updated_at": now,
            },
        },
        return_document=ReturnDocument.AFTER,
    )
    if state:
        return lock_id

    # A state record may not exist yet if no meaningful response has been
    # persisted; do not create a lock for an empty queue.
    return None


def _release(student_id: str, course_id: str, lock_id: str, **updates: Any) -> None:
    _db()["learning_analysis_state"].update_one(
        {"student_id": student_id, "course_id": course_id, "analysis_lock": lock_id},
        {"$set": {**updates, "updated_at": _now()}, "$unset": {"analysis_lock": "", "lock_expires_at": ""}},
    )


def _concept_key(name: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return key[:80] or "unclassified_concept"


def _persist_success(
    student_id: str,
    course_id: str,
    professor_id: str,
    batch_id: str,
    interactions: list[dict[str, Any]],
    performance: dict[str, Any],
    intervention: dict[str, Any] | None,
) -> None:
    now = _now()
    diagnosis = performance.get("diagnosis", {})
    concepts = diagnosis.get("concepts", []) if isinstance(diagnosis, dict) else []
    evidence_collection = _db()["interaction_evidence"]
    profile_collection = _db()["student_learning_profiles"]
    profile_set: dict[str, Any] = {"updated_at": now}
    profile_inc: dict[str, int] = {}

    for item in concepts:
        concept = str(item.get("concept", "")).strip()
        if not concept or concept.lower() == "unknown":
            continue
        key = _concept_key(concept)
        state = str(item.get("understanding", "unclear")).lower()
        evidence = [str(value) for value in item.get("evidence", []) if str(value).strip()]
        misconceptions = [str(value) for value in item.get("misconceptions", []) if str(value).strip()]
        current_session_ids = sorted({row["session_id"] for row in interactions})
        if state == "confused":
            prior_separate_session = evidence_collection.find_one({
                "student_id": student_id,
                "course_id": course_id,
                "concept_key": key,
                "understanding": "confused",
                "session_ids": {"$nin": current_session_ids},
            }, {"_id": 1, "session_ids": 1})
            if prior_separate_session:
                _db()["teacher_alerts"].update_one(
                    {"student_id": student_id, "course_id": course_id, "concept_key": key, "alert_type": "persistent_misconception"},
                    {"$setOnInsert": {
                        "student_id": student_id,
                        "course_id": course_id,
                        "professor_id": professor_id,
                        "concept": concept,
                        "concept_key": key,
                        "alert_type": "persistent_misconception",
                        "priority": "medium",
                        "status": "open",
                        "message": f"A misconception about {concept} has appeared in separate learning sessions.",
                        "first_evidence_session_ids": prior_separate_session.get("session_ids", []),
                        "created_at": now,
                    }, "$set": {"latest_seen_at": now, "latest_evidence": misconceptions or evidence}},
                    upsert=True,
                )

        evidence_collection.update_one(
            {"batch_id": batch_id, "concept_key": key},
            {"$setOnInsert": {
                "batch_id": batch_id,
                "student_id": student_id,
                "course_id": course_id,
                "professor_id": professor_id,
                "concept": concept,
                "concept_key": key,
                "understanding": state,
                "evidence": evidence,
                "misconceptions": misconceptions,
                "interaction_ids": [str(row["_id"]) for row in interactions],
                "session_ids": sorted({row["session_id"] for row in interactions}),
                "created_at": now,
            }},
            upsert=True,
        )
        profile_set.update({
            f"concepts.{key}.concept": concept,
            f"concepts.{key}.current_state": state,
            f"concepts.{key}.latest_evidence": evidence,
            f"concepts.{key}.latest_misconceptions": misconceptions,
            f"concepts.{key}.last_observed_at": now,
        })
        profile_inc[f"concepts.{key}.analysis_count"] = 1
        if state == "understood":
            profile_inc[f"concepts.{key}.understood_count"] = 1
        elif state == "partial":
            profile_inc[f"concepts.{key}.partial_count"] = 1
        elif state == "confused":
            profile_inc[f"concepts.{key}.misconception_count"] = 1

    profile_collection.update_one(
        {"student_id": student_id, "course_id": course_id},
        {"$setOnInsert": {
            "student_id": student_id,
            "course_id": course_id,
            "professor_id": professor_id,
            "created_at": now,
        }},
        upsert=True,
    )
    # Apply all concept counters as one idempotent batch update.
    profile_collection.update_one(
        {"student_id": student_id, "course_id": course_id, "applied_batch_ids": {"$ne": batch_id}},
        {
            "$set": profile_set,
            "$inc": profile_inc,
            "$addToSet": {"applied_batch_ids": batch_id},
        },
    )
    profile_collection.update_one(
        {"student_id": student_id, "course_id": course_id},
        {"$set": {
            "latest_diagnosis": diagnosis,
            "latest_intervention": intervention,
            "latest_batch_id": batch_id,
            "updated_at": now,
        }},
    )


def process_pending_analysis(
    student_id: str,
    course_id: str,
    course_name: str,
    professor_id: str,
    force: bool = False,
) -> dict[str, Any]:
    """Analyze one new batch; failed batches remain pending for retry."""
    ensure_incremental_indexes()
    pending_query = {
        "student_id": student_id,
        "course_id": course_id,
        "role": "user",
        "meaningful_candidate": True,
        "analysis_status": "pending",
    }
    pending_count = _db()["learning_interactions"].count_documents(pending_query)
    state = _db()["learning_analysis_state"].find_one(
        {"student_id": student_id, "course_id": course_id},
        {"_id": 0, "retry_after": 1},
    ) or {}
    if not force and state.get("retry_after") and state["retry_after"] > _now():
        return {"status": "retry_scheduled", "pending_count": pending_count, "threshold": ANALYSIS_THRESHOLD}
    if pending_count < ANALYSIS_THRESHOLD and not force:
        return {"status": "waiting_for_activity", "pending_count": pending_count, "threshold": ANALYSIS_THRESHOLD}
    if pending_count == 0:
        return {"status": "no_pending_evidence", "pending_count": 0, "threshold": ANALYSIS_THRESHOLD}

    lock_id = _claim(student_id, course_id)
    if not lock_id:
        return {"status": "already_running", "pending_count": pending_count, "threshold": ANALYSIS_THRESHOLD}

    try:
        rows = list(_db()["learning_interactions"].find(pending_query).sort(
            [("created_at", ASCENDING), ("session_id", ASCENDING), ("sequence", ASCENDING)]
        ).limit(BATCH_SIZE))
        if not rows:
            _release(student_id, course_id, lock_id, last_analysis_status="no_pending_evidence")
            return {"status": "no_pending_evidence", "pending_count": 0, "threshold": ANALYSIS_THRESHOLD}

        from backend.app.agents.performance_agent import PerformanceAgent
        from backend.app.agents.intervention_agent import InterventionAgent

        performance = PerformanceAgent().analyze(
            student_id=student_id,
            course_name=course_name,
            interactions=[{
                "role": row.get("role", "user"),
                "content": row.get("content", ""),
                "session_id": row.get("session_id"),
                "sequence": row.get("sequence"),
            } for row in rows],
            course_id=course_id,
        )
        interpretation = performance.get("evidence_interpretation", {})
        parse_status = interpretation.get("parse_status") if isinstance(interpretation, dict) else None
        diagnosis = performance.get("diagnosis", {})
        concepts = diagnosis.get("concepts", []) if isinstance(diagnosis, dict) else []

        # The Performance Agent's deterministic gate may reject a candidate
        # batch as questions/uncertainty rather than substantive evidence.
        # Such a batch is safely acknowledged as non-evidence; parser failures
        # and empty/truncated model output remain pending for retry.
        if parse_status is None and not concepts and isinstance(diagnosis, dict) and diagnosis.get("confidence") == "low":
            ids = [row["_id"] for row in rows]
            _db()["learning_interactions"].update_many(
                {"_id": {"$in": ids}, "analysis_status": "pending"},
                {"$set": {"analysis_status": "processed_no_evidence", "analyzed_at": _now()}},
            )
            remaining = _db()["learning_interactions"].count_documents(pending_query)
            _release(
                student_id, course_id, lock_id,
                pending_count=remaining,
                last_analyzed_at=_now(),
                last_analysis_status="insufficient_evidence",
                last_analysis_error=None,
                retry_after=None,
            )
            return {
                "status": "insufficient_evidence",
                "processed_responses": len(rows),
                "pending_count": remaining,
                "threshold": ANALYSIS_THRESHOLD,
                "performance": performance,
                "intervention": None,
            }

        if parse_status != "valid" or not concepts:
            raise RuntimeError(
                f"Performance Agent did not return usable concept evidence (parse_status={parse_status or 'missing'})."
            )

        intervention = None
        needs_support = any(
            item.get("understanding") in {"confused", "partial"}
            for item in concepts if isinstance(item, dict)
        )
        if needs_support:
            intervention = InterventionAgent().generate_recommendations(
                student_id=student_id,
                course_name=course_name,
                diagnosis=diagnosis,
                course_id=course_id,
                evidence_interpretation=interpretation,
            )

        # Stable identity for this exact pending batch: if the process stops
        # after persistence but before acknowledgement, retrying the same rows
        # reuses the same batch ID and cannot double-count profile metrics.
        batch_material = "|".join(str(row["_id"]) for row in rows)
        batch_id = hashlib.sha256(batch_material.encode("utf-8")).hexdigest()[:32]
        _persist_success(
            student_id, course_id, professor_id, batch_id, rows, performance, intervention
        )
        ids = [row["_id"] for row in rows]
        _db()["learning_interactions"].update_many(
            {"_id": {"$in": ids}, "analysis_status": "pending"},
            {"$set": {"analysis_status": "processed", "analysis_batch_id": batch_id, "analyzed_at": _now()}},
        )
        remaining = _db()["learning_interactions"].count_documents(pending_query)
        _release(
            student_id, course_id, lock_id,
            pending_count=remaining,
            last_analyzed_at=_now(),
            last_analysis_status="completed",
            last_analysis_error=None,
            retry_after=None,
            latest_batch_id=batch_id,
        )
        return {
            "status": "completed",
            "batch_id": batch_id,
            "processed_responses": len(rows),
            "pending_count": remaining,
            "threshold": ANALYSIS_THRESHOLD,
            "performance": performance,
            "intervention": intervention,
        }
    except Exception as exc:
        # Do not update interaction analysis_status: all evidence remains pending.
        _release(
            student_id, course_id, lock_id,
            last_analysis_status="failed_retry_pending",
            last_analysis_error=str(exc)[:1000],
            retry_after=_now() + timedelta(minutes=5),
        )
        return {
            "status": "failed_retry_pending",
            "pending_count": _db()["learning_interactions"].count_documents(pending_query),
            "threshold": ANALYSIS_THRESHOLD,
            "error": str(exc)[:1000],
        }
