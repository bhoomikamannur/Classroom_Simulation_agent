from datetime import datetime, timezone
from secrets import token_urlsafe
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError

from backend.app.api.auth import get_current_user, require_role
from backend.app.database.mongodb import get_mongodb_database


router = APIRouter(prefix="/courses", tags=["Courses"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _courses():
    return get_mongodb_database()["courses"]


def _enrollments():
    return get_mongodb_database()["course_enrollments"]


def _ensure_indexes() -> None:
    """Create indexes that enforce course and enrollment identity."""
    _courses().create_index(
        [("course_id", ASCENDING)], unique=True, name="unique_course_id"
    )
    _courses().create_index(
        [("enrollment_code", ASCENDING)],
        unique=True,
        name="unique_course_enrollment_code",
    )
    _courses().create_index(
        [("professor_id", ASCENDING), ("created_at", DESCENDING)],
        name="professor_courses_recent",
    )
    _enrollments().create_index(
        [("student_id", ASCENDING), ("course_id", ASCENDING)],
        unique=True,
        name="unique_student_course_enrollment",
    )
    _enrollments().create_index(
        [("course_id", ASCENDING), ("enrolled_at", DESCENDING)],
        name="course_enrollments_recent",
    )


class CourseCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)


class CourseUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    status: str | None = Field(default=None, pattern="^(active|archived)$")


class CourseEnrollmentRequest(BaseModel):
    enrollment_code: str = Field(min_length=4, max_length=40)


def _public_course(course: dict, *, include_code: bool = False) -> dict:
    result = {
        "course_id": course["course_id"],
        "name": course["name"],
        "description": course.get("description", ""),
        "professor_id": course["professor_id"],
        "status": course["status"],
        "created_at": course["created_at"],
        "updated_at": course["updated_at"],
    }
    if include_code:
        result["enrollment_code"] = course["enrollment_code"]
    return result


def _get_course_or_404(course_id: str) -> dict:
    course = _courses().find_one({"course_id": course_id}, {"_id": 0})
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found.")
    return course


def _require_course_owner(course: dict, professor: dict) -> None:
    if course.get("professor_id") != professor.get("user_id"):
        raise HTTPException(
            status_code=403,
            detail="You do not own this course.",
        )


def _require_course_access(course: dict, user: dict) -> None:
    if user.get("role") == "professor":
        _require_course_owner(course, user)
        return

    enrollment = _enrollments().find_one(
        {
            "course_id": course["course_id"],
            "student_id": user["user_id"],
        },
        {"_id": 0, "course_id": 1},
    )
    if enrollment is None:
        # Do not reveal course details to a student who is not enrolled.
        raise HTTPException(status_code=404, detail="Course not found.")


@router.post("", status_code=status.HTTP_201_CREATED)
def create_course(
    request: CourseCreateRequest,
    current_user: dict = Depends(require_role("professor")),
):
    _ensure_indexes()
    name = request.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Course name cannot be blank.")

    now = _now()
    course = {
        "course_id": str(uuid4()),
        "name": name,
        "description": request.description.strip(),
        "professor_id": current_user["user_id"],
        "enrollment_code": token_urlsafe(9).replace("-", "").replace("_", "")[:12].upper(),
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }

    try:
        _courses().insert_one(course)
    except DuplicateKeyError as exc:
        # A highly unlikely enrollment-code collision; ask the client to retry.
        raise HTTPException(
            status_code=503,
            detail="Could not allocate a unique course enrollment code. Please retry.",
        ) from exc

    return {
        "message": "Course created successfully.",
        "course": _public_course(course, include_code=True),
    }


@router.get("")
def list_professor_courses(
    current_user: dict = Depends(require_role("professor")),
):
    _ensure_indexes()
    courses = list(
        _courses()
        .find({"professor_id": current_user["user_id"]}, {"_id": 0})
        .sort("created_at", DESCENDING)
    )
    return {"courses": [_public_course(course, include_code=True) for course in courses]}


@router.get("/mine")
def list_student_courses(
    current_user: dict = Depends(require_role("student")),
):
    _ensure_indexes()
    enrollments = list(
        _enrollments().find(
            {"student_id": current_user["user_id"]},
            {"_id": 0, "course_id": 1, "enrolled_at": 1},
        ).sort("enrolled_at", DESCENDING)
    )
    course_ids = [item["course_id"] for item in enrollments]
    courses_by_id = {
        course["course_id"]: course
        for course in _courses().find(
            {"course_id": {"$in": course_ids}, "status": "active"},
            {"_id": 0},
        )
    }
    result = []
    for enrollment in enrollments:
        course = courses_by_id.get(enrollment["course_id"])
        if course:
            result.append({
                **_public_course(course),
                "enrolled_at": enrollment["enrolled_at"],
            })
    return {"courses": result}


@router.post("/enroll", status_code=status.HTTP_201_CREATED)
def enroll_in_course(
    request: CourseEnrollmentRequest,
    current_user: dict = Depends(require_role("student")),
):
    _ensure_indexes()
    code = request.enrollment_code.strip().upper()
    course = _courses().find_one(
        {"enrollment_code": code, "status": "active"},
        {"_id": 0},
    )
    if course is None:
        raise HTTPException(status_code=404, detail="Active course not found for this enrollment code.")

    enrollment = {
        "enrollment_id": str(uuid4()),
        "course_id": course["course_id"],
        "student_id": current_user["user_id"],
        "professor_id": course["professor_id"],
        "enrolled_at": _now(),
        "status": "active",
    }
    try:
        _enrollments().insert_one(enrollment)
    except DuplicateKeyError:
        raise HTTPException(
            status_code=409,
            detail="You are already enrolled in this course.",
        )

    return {
        "message": "Successfully enrolled in course.",
        "course": _public_course(course),
        "enrolled_at": enrollment["enrolled_at"],
    }


@router.get("/{course_id}")
def get_course(
    course_id: str,
    current_user: dict = Depends(get_current_user),
):
    _ensure_indexes()
    course = _get_course_or_404(course_id)
    _require_course_access(course, current_user)
    return {"course": _public_course(course)}


@router.patch("/{course_id}")
def update_course(
    course_id: str,
    request: CourseUpdateRequest,
    current_user: dict = Depends(require_role("professor")),
):
    _ensure_indexes()
    course = _get_course_or_404(course_id)
    _require_course_owner(course, current_user)

    updates = request.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="Provide at least one field to update.")
    if "name" in updates:
        updates["name"] = updates["name"].strip()
        if not updates["name"]:
            raise HTTPException(status_code=422, detail="Course name cannot be blank.")
    if "description" in updates and updates["description"] is not None:
        updates["description"] = updates["description"].strip()
    updates["updated_at"] = _now()

    _courses().update_one(
        {"course_id": course_id, "professor_id": current_user["user_id"]},
        {"$set": updates},
    )
    updated = _get_course_or_404(course_id)
    return {"message": "Course updated successfully.", "course": _public_course(updated)}


@router.get("/{course_id}/students")
def list_course_students(
    course_id: str,
    current_user: dict = Depends(require_role("professor")),
):
    _ensure_indexes()
    course = _get_course_or_404(course_id)
    _require_course_owner(course, current_user)

    records = list(
        _enrollments()
        .find(
            {"course_id": course_id, "status": "active"},
            {"_id": 0, "student_id": 1, "enrolled_at": 1},
        )
        .sort("enrolled_at", DESCENDING)
    )
    student_ids = [record["student_id"] for record in records]
    users = get_mongodb_database()["users"]
    users_by_id = {
        user["user_id"]: user
        for user in users.find(
            {"user_id": {"$in": student_ids}},
            {"_id": 0, "user_id": 1, "email": 1, "roll_number": 1},
        )
    }
    return {
        "course_id": course_id,
        "students": [
            {
                "student_id": record["student_id"],
                "email": users_by_id.get(record["student_id"], {}).get("email"),
                "roll_number": users_by_id.get(record["student_id"], {}).get("roll_number"),
                "enrolled_at": record["enrolled_at"],
            }
            for record in records
        ],
        "total_students": len(records),
    }
