"""Run the periodic Performance Analysis sweep.

Schedule with Windows Task Scheduler or cron, e.g. every 5 minutes:
    python -m backend.scripts.run_periodic_performance
"""
from backend.app.database.mongodb import get_mongodb_database
from backend.app.services.incremental_performance import run_periodic_analysis_sweep


def _course_name(course_id: str) -> str:
    course = get_mongodb_database()["courses"].find_one(
        {"course_id": course_id}, {"_id": 0, "name": 1}
    ) or {}
    return course.get("name", "Course")


if __name__ == "__main__":
    print(run_periodic_analysis_sweep(course_name_resolver=_course_name))
