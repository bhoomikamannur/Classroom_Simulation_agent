
from datetime import datetime, timezone
from typing import Any
import re

from pymongo import ASCENDING, DESCENDING, ReturnDocument
from pymongo.errors import DuplicateKeyError
from pymongo.collection import Collection

from backend.app.database.mongodb import get_mongodb_database


def _utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def _sessions() -> Collection:
    return get_mongodb_database()["learning_sessions"]


def _interactions() -> Collection:
    return get_mongodb_database()["learning_interactions"]


def _analysis_states() -> Collection:
    return get_mongodb_database()["learning_analysis_state"]


def is_meaningful_student_response(content: str) -> bool:
    """Conservative deterministic pre-filter; semantic correctness is not judged here."""
    text = re.sub(r"\s+", " ", (content or "").strip())
    if len(text) < 25 or len(text.split()) < 5:
        return False
    normalized = text.lower().strip(" .!?\t")
    noise = {
        "hi", "hello", "hey", "thanks", "thank you", "ok", "okay",
        "yes", "no", "got it", "understood", "good morning", "good afternoon",
    }
    if normalized in noise:
        return False
    uncertainty = (
        "i don't understand", "i do not understand", "i'm confused",
        "i am confused", "i don't get it", "i do not get it",
        "can you explain", "can you clarify", "what is", "what are",
        "how does this work",
    )
    if normalized.startswith(uncertainty) and normalized.count(" ") < 9:
        return False
    if text.endswith("?") and not any(
        marker in normalized for marker in (
            "so ", "does that mean", "is it correct that", "am i right that",
            "basically", "is that why",
        )
    ):
        return False
    return True


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
    _interactions().create_index(
        [("student_id", ASCENDING), ("course_id", ASCENDING), ("analysis_status", ASCENDING), ("meaningful_candidate", ASCENDING)],
        name="student_course_pending_evidence",
    )
    _analysis_states().create_index(
        [("student_id", ASCENDING), ("course_id", ASCENDING)],
        unique=True,
        name="unique_student_course_analysis_state",
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

    meaningful_candidate = role == "user" and is_meaningful_student_response(content)
    interaction = {
        **identity,
        "professor_id": session.get("professor_id"),
        "sequence": session["interaction_count"],
        "role": role,
        "content": content,
        "created_at": _utc_now(),
        "meaningful_candidate": meaningful_candidate,
        **({"analysis_status": "pending"} if meaningful_candidate else {}),
    }

    inserted = _interactions().insert_one(interaction)
    interaction["_id"] = inserted.inserted_id
    if meaningful_candidate:
        state_identity = {"student_id": student_id, "course_id": course_id}
        state_update = {
            "$setOnInsert": {
                **state_identity,
                "professor_id": session.get("professor_id"),
                "created_at": _utc_now(),
                "last_analyzed_at": None,
                "last_analysis_status": "not_yet_analyzed",
            },
            "$inc": {"pending_count": 1},
            "$set": {"updated_at": _utc_now()},
        }
        try:
            _analysis_states().update_one(state_identity, state_update, upsert=True)
        except DuplicateKeyError:
            # Concurrent first messages may race to create this student-course
            # state document; the unique index makes the retry safe.
            _analysis_states().update_one(state_identity, {
                "$inc": {"pending_count": 1},
                "$set": {"updated_at": _utc_now()},
            })

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


def get_student_course_interactions(
    student_id: str,
    course_id: str,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Return a student's persisted interactions for one course.

    Records are returned in chronological order across all sessions so the
    Performance Agent can evaluate the student's learning trajectory.
    """
    student_id = student_id.strip()
    course_id = course_id.strip()

    if not student_id or not course_id:
        raise ValueError("student_id and course_id must be non-empty.")

    if limit < 1 or limit > 5000:
        raise ValueError("limit must be between 1 and 5000.")

    ensure_learning_indexes()

    records = list(
        _interactions()
        .find(
            {
                "student_id": student_id,
                "course_id": course_id,
            },
            {"_id": 0},
        )
        .sort(
            [
                ("created_at", DESCENDING),
                ("session_id", DESCENDING),
                ("sequence", DESCENDING),
            ]
        )
        .limit(limit)
    )

    # Fetch the most recent records, then restore chronological order for
    # trajectory analysis by the Performance Agent.
    records.reverse()
    return records
