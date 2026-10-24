
from datetime import datetime, timezone
from typing import Any

from pymongo import ASCENDING, DESCENDING, ReturnDocument
from pymongo.collection import Collection

from backend.app.database.mongodb import get_mongodb_database


def _utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def _sessions() -> Collection:
    return get_mongodb_database()["learning_sessions"]


def _interactions() -> Collection:
    return get_mongodb_database()["learning_interactions"]


def ensure_learning_indexes() -> None:
    """Create indexes used to isolate and retrieve learning records."""

    _sessions().create_index(
        [
            ("student_id", ASCENDING),
            ("course_id", ASCENDING),
            ("session_id", ASCENDING),
        ],
        unique=True,
        name="unique_student_course_session",
    )

    _sessions().create_index(
        [("course_id", ASCENDING), ("updated_at", DESCENDING)],
        name="course_recent_sessions",
    )

    _interactions().create_index(
        [
            ("student_id", ASCENDING),
            ("course_id", ASCENDING),
            ("session_id", ASCENDING),
            ("sequence", ASCENDING),
        ],
        unique=True,
        name="unique_session_interaction_sequence",
    )

    _interactions().create_index(
        [
            ("student_id", ASCENDING),
            ("course_id", ASCENDING),
            ("created_at", DESCENDING),
        ],
        name="student_course_recent_interactions",
    )


def get_or_create_session(
    student_id: str,
    course_id: str,
    session_id: str,
    professor_id: str | None = None,
) -> dict[str, Any]:
    """Create a session or return the existing matching session."""

    student_id = student_id.strip()
    course_id = course_id.strip()
    session_id = session_id.strip()

    if not student_id or not course_id or not session_id:
        raise ValueError(
            "student_id, course_id and session_id must be non-empty."
        )

    if professor_id is not None:
        professor_id = professor_id.strip()
        if not professor_id:
            raise ValueError("professor_id must be non-empty when provided.")

    ensure_learning_indexes()

    sessions = _sessions()
    now = _utc_now()

    identity = {
        "student_id": student_id,
        "course_id": course_id,
        "session_id": session_id,
    }

    # Existing session ownership and course association are immutable here.
    # A repeated request must not silently reassign the session.
    sessions.update_one(
        identity,
        {
            "$setOnInsert": {
                **identity,
                "professor_id": professor_id,
                "status": "active",
                "created_at": now,
                "updated_at": now,
                "interaction_count": 0,
            }
        },
        upsert=True,
    )

    session = sessions.find_one(identity, {"_id": 0})

    if session is None:
        raise RuntimeError("Could not create or retrieve the learning session.")

    return session


def save_interaction(
    student_id: str,
    course_id: str,
    session_id: str,
    role: str,
    content: str,
) -> dict[str, Any]:
    """Persist one student or tutor message in an existing session."""

    student_id = student_id.strip()
    course_id = course_id.strip()
    session_id = session_id.strip()
    content = content.strip()
    role = role.strip().lower()

    if not student_id or not course_id or not session_id:
        raise ValueError(
            "student_id, course_id and session_id must be non-empty."
        )

    if role not in {"user", "assistant"}:
        raise ValueError("role must be 'user' or 'assistant'.")

    if not content:
        raise ValueError("content must not be empty.")

    ensure_learning_indexes()

    identity = {
        "student_id": student_id,
        "course_id": course_id,
        "session_id": session_id,
    }

    # Only an already-created session can receive interactions.
    # This prevents accidental creation of orphaned messages.
    session = _sessions().find_one_and_update(
        {**identity, "status": "active"},
        {
            "$inc": {"interaction_count": 1},
            "$set": {"updated_at": _utc_now()},
        },
        return_document=ReturnDocument.AFTER,
    )

    if session is None:
        raise ValueError(
            "No active session exists for this student, course and session ID."
        )

    interaction = {
        **identity,
        "professor_id": session.get("professor_id"),
        "sequence": session["interaction_count"],
        "role": role,
        "content": content,
        "created_at": _utc_now(),
    }

    _interactions().insert_one(interaction)

    return {**interaction}


def get_recent_interactions(
    student_id: str,
    course_id: str,
    session_id: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Return the latest interactions in chronological order."""

    student_id = student_id.strip()
    course_id = course_id.strip()
    session_id = session_id.strip()

    if not student_id or not course_id or not session_id:
        raise ValueError(
            "student_id, course_id and session_id must be non-empty."
        )

    if limit < 1 or limit > 500:
        raise ValueError("limit must be between 1 and 500.")

    ensure_learning_indexes()

    identity = {
        "student_id": student_id,
        "course_id": course_id,
        "session_id": session_id,
    }

    records = list(
        _interactions()
        .find(identity, {"_id": 0})
        .sort("sequence", DESCENDING)
        .limit(limit)
    )

    records.reverse()
    return records
