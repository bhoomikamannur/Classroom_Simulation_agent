from fastapi import HTTPException
from backend.app.database.mongodb import get_mongodb_database


def get_accessible_course(course_id: str, user: dict) -> dict:
    """Return an active course only when the caller owns or is enrolled in it."""
    course = get_mongodb_database()["courses"].find_one(
        {"course_id": course_id, "status": "active"},
        {"_id": 0},
    )
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found.")

    role = user.get("role")
    if role == "professor":
        if course.get("professor_id") != user.get("user_id"):
            raise HTTPException(status_code=403, detail="You do not own this course.")
        return course

    if role == "student":
        enrollment = get_mongodb_database()["course_enrollments"].find_one(
            {
                "course_id": course_id,
                "student_id": user.get("user_id"),
                "status": "active",
            },
            {"_id": 1},
        )
        if enrollment is None:
            # Avoid disclosing the existence of courses to non-enrolled students.
            raise HTTPException(status_code=404, detail="Course not found.")
        return course

    raise HTTPException(status_code=403, detail="This account cannot access courses.")

