
from typing import Any

from pymongo import ASCENDING
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError

from backend.app.analytics.academic_policy import validate_academic_policy
from backend.app.database.mongodb import get_mongodb_database


def get_policy_collection() -> Collection:
    """Get the academic policy collection and enforce unique course IDs."""
    collection = get_mongodb_database()["academic_policies"]
    collection.create_index(
        [("course_id", ASCENDING)],
        unique=True,
    )
    return collection


def create_policy(policy: dict[str, Any]) -> dict[str, Any]:
    """Validate and persist a new course policy."""
    validated = validate_academic_policy(policy)
    collection = get_policy_collection()

    try:
        collection.insert_one(validated.copy())
    except DuplicateKeyError as exc:
        raise ValueError(
            f"A policy already exists for course '{validated['course_id']}'."
        ) from exc

    return validated


def get_policy(course_id: str) -> dict[str, Any] | None:
    """Retrieve a course policy, if one exists."""
    if not isinstance(course_id, str) or not course_id.strip():
        raise ValueError("course_id must be a non-empty string.")

    document = get_policy_collection().find_one(
        {"course_id": course_id.strip()},
        {"_id": 0},
    )
    return document


def update_policy(
    course_id: str,
    policy: dict[str, Any],
) -> dict[str, Any] | None:
    """Update an existing policy without creating a new course policy."""
    if not isinstance(course_id, str) or not course_id.strip():
        raise ValueError("course_id must be a non-empty string.")

    candidate = dict(policy)
    candidate["course_id"] = course_id.strip()
    validated = validate_academic_policy(candidate)

    result = get_policy_collection().replace_one(
        {"course_id": course_id.strip()},
        validated,
        upsert=False,
    )

    if result.matched_count == 0:
        return None

    return validated
