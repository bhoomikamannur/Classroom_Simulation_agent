"""Semester-wide adaptive planner across all courses enrolled by a student."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.api.auth import require_role
from backend.app.database.mongodb import get_mongodb_database
from backend.app.learning.schedule_policy import select_balanced_week

router = APIRouter(prefix="/semester-planner", tags=["Semester-wide Adaptive Planner"])


def _now():
    return datetime.now(timezone.utc)


def _db():
    return get_mongodb_database()


class GenerateSemesterPlanRequest(BaseModel):
    weekly_available_hours: float = Field(ge=1, le=80)
    semester_weeks: int | None = Field(default=None, ge=2, le=30)


class AvailabilityRequest(BaseModel):
    weekly_available_hours: float = Field(ge=1, le=80)


def _student_courses(student_id: str) -> list[dict[str, Any]]:
    db = _db()
    enrollments = list(db["course_enrollments"].find(
        {"student_id": student_id}, {"_id": 0, "course_id": 1}
    ))
    course_ids = list(dict.fromkeys(item["course_id"] for item in enrollments))
    if not course_ids:
        return []
    courses = {item["course_id"]: item for item in db["courses"].find(
        {"course_id": {"$in": course_ids}, "status": "active"}, {"_id": 0}
    )}
    plans = list(db["course_lesson_plans"].find(
        {"course_id": {"$in": course_ids}, "status": "published"}, {"_id": 0}
    ))
    result = []
    for plan in plans:
        course = courses.get(plan["course_id"])
        if course:
            result.append({"course_id": plan["course_id"],
                           "course_name": course.get("name", plan.get("course_name", "Course")),
                           "plan": plan})
    return result


def _build_schedule(student_id: str, courses: list[dict[str, Any]], hours: float,
                    weeks_override: int | None, previous: dict[str, Any] | None) -> dict[str, Any]:
    """Build a balanced required schedule plus clearly non-obligatory suggestions."""
    total_weeks = weeks_override or max(
        [int(item["plan"].get("semester_weeks", 16)) for item in courses] or [16]
    )
    capacity = float(hours)
    db = _db()
    progress_docs = list(db["student_topic_progress"].find(
        {"student_id": student_id}, {"_id": 0}
    ))
    progress = {item["topic_id"]: item for item in progress_docs}
    evidence_docs = list(db["student_topic_evidence"].find(
        {"student_id": student_id}, {"_id": 0}
    ))
    evidence = {item["topic_id"]: item for item in evidence_docs}
    weeks: dict[int, dict[str, Any]] = {
        week: {"week": week, "planned_hours": 0.0, "activities": [], "assessment_topics": []}
        for week in range(1, total_weeks + 1)
    }
    topics: list[dict[str, Any]] = []
    for item in courses:
        plan = item["plan"]
        for unit in plan.get("units", []):
            for topic in unit.get("topics", []):
                tid = topic["topic_id"]
                p, e = progress.get(tid, {}), evidence.get(tid, {})
                covered = bool(p.get("status") == "completed" or e.get("covered"))
                mastery = e.get("mastery_score", p.get("mastery_score"))
                try:
                    mastery = float(mastery) if mastery is not None else None
                except (TypeError, ValueError):
                    mastery = None
                if covered and mastery is not None and mastery >= 80:
                    state = "mastered"
                elif covered and mastery is not None and mastery < 60:
                    state = "revision_required"
                elif covered:
                    state = "covered"
                else:
                    state = "not_covered"
                topics.append({
                    "topic_id": tid, "course_id": item["course_id"],
                    "course_name": item["course_name"], "unit_id": unit["unit_id"],
                    "unit_title": unit["title"], "title": topic["title"],
                    "estimated_effort_hours": max(0.5, float(topic.get("estimated_effort_hours", 1.5))),
                    "difficulty": max(1, min(5, int(topic.get("difficulty", 3)))),
                    "prerequisites": topic.get("prerequisites", []),
                    "baseline_start_week": max(1, min(total_weeks, int(unit.get("start_week", 1)))),
                    "baseline_end_week": max(1, min(total_weeks, int(unit.get("end_week", total_weeks)))),
                    "coverage_status": state, "mastery_score": mastery,
                    "checklist_status": p.get("status", "not_started"),
                    "revision_required": state == "revision_required",
                })

    previous_activities: dict[str, dict[str, Any]] = {}
    if previous:
        for old_week in previous.get("weeks", []):
            for activity in old_week.get("activities", []):
                if activity.get("topic_id"):
                    previous_activities[activity["topic_id"]] = activity

    # Keep completed work in its historical week; it never consumes future capacity.
    for topic in topics:
        if topic["coverage_status"] in {"covered", "mastered"}:
            old = previous_activities.get(topic["topic_id"])
            if old:
                old_week = int(old.get("week", topic["baseline_start_week"]))
                if old_week in weeks:
                    weeks[old_week]["activities"].append({
                        **topic, "week": old_week, "status": "completed",
                        "schedule_type": "completed",
                        "schedule_reason": "Completed learning retained as history.",
                    })

    pending = [t for t in topics if t["coverage_status"] in {"not_covered", "revision_required"}]
    # Stable, deadline-aware order. Global weekly load balancing below prevents
    # individual courses/units from monopolising the earliest available week.
    pending.sort(key=lambda t: (
        t["baseline_end_week"],
        0 if t["revision_required"] else 1,
        -t["difficulty"], -t["estimated_effort_hours"],
        t["baseline_start_week"], t["course_name"], t["title"],
    ))

    assigned: set[str] = set()
    required_week_by_topic: dict[str, int] = {}
    for topic in pending:
        start_week = topic["baseline_start_week"]
        end_week = max(start_week, topic["baseline_end_week"])
        preferred = list(range(start_week, end_week + 1))
        overflow = list(range(end_week + 1, total_weeks + 1))
        earlier = list(range(1, start_week))
        candidates = preferred + overflow + earlier
        effort = topic["estimated_effort_hours"]

        # Prefer the least-loaded week in the professor's soft window. Capacity
        # is respected where possible; if impossible, retain the topic and flag it.
        chosen = select_balanced_week(candidates, weeks, capacity, effort, start_week, end_week)
        activity = {
            **topic, "week": chosen,
            "status": "revision" if topic["revision_required"] else "planned",
            "schedule_type": "required",
            "schedule_reason": (
                "Required targeted revision based on demonstrated learning difficulty."
                if topic["revision_required"] else
                "Required syllabus topic, balanced across the professor's baseline window."
            ),
        }
        weeks[chosen]["activities"].append(activity)
        weeks[chosen]["planned_hours"] += effort
        weeks[chosen]["assessment_topics"].append({
            "topic_id": topic["topic_id"], "course_id": topic["course_id"],
            "course_name": topic["course_name"], "title": topic["title"],
        })
        assigned.add(topic["topic_id"])
        required_week_by_topic[topic["topic_id"]] = chosen

    # Optional early-study suggestions: these are deliberately not part of the
    # required workload, weekly assessment, or progress-risk denominator.
    for week_number, week_data in weeks.items():
        spare = max(0.0, capacity - week_data["planned_hours"])
        if spare < 0.5:
            continue
        candidates = [
            t for t in topics
            if t["topic_id"] in required_week_by_topic
            and required_week_by_topic[t["topic_id"]] > week_number
            and t["coverage_status"] == "not_covered"
            and t["estimated_effort_hours"] <= spare + 1e-6
        ]
        candidates.sort(key=lambda t: (
            t["baseline_start_week"], -t["difficulty"], t["course_name"], t["title"]
        ))
        for topic in candidates[:2]:
            week_data["activities"].append({
                **topic, "week": week_number, "status": "optional",
                "schedule_type": "optional",
                "schedule_reason": (
                    "Optional early-study opportunity. Skipping this does not make you behind; "
                    "the topic remains required in its original future window."
                ),
            })
            spare -= topic["estimated_effort_hours"]

    # Suggest revision of already-covered but not-yet-mastered topics in spare weeks.
    for week_number, week_data in weeks.items():
        if week_data["planned_hours"] >= capacity:
            continue
        already_suggested = {a.get("topic_id") for a in week_data["activities"]}
        revision_candidates = [
            t for t in topics
            if t["coverage_status"] == "covered"
            and t["topic_id"] not in already_suggested
            and t.get("mastery_score") is not None
            and 60 <= t["mastery_score"] < 80
        ]
        for topic in revision_candidates[:1]:
            week_data["activities"].append({
                **topic, "week": week_number, "status": "revision_suggestion",
                "schedule_type": "revision",
                "schedule_reason": "Optional reinforcement to make partially secure understanding stronger.",
            })

    for week_data in weeks.values():
        week_data["planned_hours"] = round(week_data["planned_hours"], 1)
        week_data["capacity_hours"] = capacity
        week_data["over_capacity"] = week_data["planned_hours"] > capacity
        week_data["required_hours"] = week_data["planned_hours"]
        week_data["required_topic_count"] = sum(
            1 for a in week_data["activities"] if a.get("schedule_type") == "required"
        )

    now = _now()
    return {
        "plan_id": (previous or {}).get("plan_id", str(uuid4())),
        "student_id": student_id, "weekly_available_hours": capacity,
        "semester_weeks": total_weeks, "weeks": list(weeks.values()),
        "course_count": len(courses), "topic_count": len(topics),
        "generated_at": now, "updated_at": now,
        "version": int((previous or {}).get("version", 0)) + 1,
        "planning_method": "balanced cross-course allocation with required, optional early-study, and revision activities",
    }


@router.get("/mine")
def get_my_semester_plan(user: dict = Depends(require_role("student"))):
    plan = _db()["student_semester_plans"].find_one(
        {"student_id": user["user_id"]}, {"_id": 0}
    )
    return {"plan": plan}


@router.post("/generate")
def generate_my_semester_plan(request: GenerateSemesterPlanRequest,
                              user: dict = Depends(require_role("student"))):
    courses = _student_courses(user["user_id"])
    if not courses:
        raise HTTPException(status_code=409, detail="No enrolled courses with published lesson plans were found.")
    collection = db["student_semester_plans"]
    previous = collection.find_one({"student_id": user["user_id"]}, {"_id": 0})
    plan = _build_schedule(user["user_id"], courses, request.weekly_available_hours,
                           request.semester_weeks, previous)
    collection.update_one({"student_id": user["user_id"]},
                          {"$set": plan}, upsert=True)
    return {"message": "Your semester-wide study plan has been generated.", "plan": plan}


@router.patch("/availability")
def update_availability(request: AvailabilityRequest,
                        user: dict = Depends(require_role("student"))):
    existing = _db()["student_semester_plans"].find_one(
        {"student_id": user["user_id"]}, {"_id": 0}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Generate your semester plan first.")
    courses = _student_courses(user["user_id"])
    plan = _build_schedule(user["user_id"], courses, request.weekly_available_hours,
                           existing.get("semester_weeks"), existing)
    _db()["student_semester_plans"].replace_one(
        {"student_id": user["user_id"]}, plan, upsert=True
    )
    return {"message": "Availability updated and your remaining plan rescheduled.", "plan": plan}



class WeeklyAssessmentSubmission(BaseModel):
    answers: dict[str, int]


@router.post("/weeks/{week_number}/assessment")
def create_weekly_assessment(week_number: int, user: dict = Depends(require_role("student"))):
    """Assemble a weekly assessment from pre-generated, previously unseen topic questions."""
    db = _db()
    plan = db["student_semester_plans"].find_one(
        {"student_id": user["user_id"]}, {"_id": 0}
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Generate your semester plan first.")
    week = next((item for item in plan.get("weeks", []) if item.get("week") == week_number), None)
    if not week:
        raise HTTPException(status_code=404, detail="Week not found in your semester plan.")
    existing = db["weekly_assessments"].find_one({
        "student_id": user["user_id"], "plan_id": plan["plan_id"],
        "week": week_number, "status": "open",
    }, {"_id": 0})
    if existing:
        return {"assessment": _public_weekly_assessment(existing), "reused": True}
    submitted = db["weekly_assessments"].find_one({
        "student_id": user["user_id"], "plan_id": plan["plan_id"],
        "week": week_number, "status": "submitted",
    }, {"_id": 0, "score": 1})
    if submitted:
        raise HTTPException(status_code=409, detail="You have already submitted this week's assessment.")

    # Only required work is assessed. Optional early-study and revision suggestions
    # never become hidden weekly obligations.
    activities = [a for a in week.get("activities", [])
                  if a.get("schedule_type", "required") == "required"
                  and a.get("coverage_status") != "mastered"]
    if not activities:
        raise HTTPException(status_code=409, detail="There are no outstanding learning topics scheduled for this week.")
    history = db["student_question_history"]
    questions = []
    missing = []
    for activity in activities:
        bank = db["assessment_question_banks"].find_one({
            "course_id": activity["course_id"], "unit_id": activity["unit_id"]
        }, {"_id": 0, "questions": 1})
        candidates = [q for q in (bank or {}).get("questions", [])
                      if q.get("topic_id") == activity["topic_id"]]
        seen_ids = {row["question_id"] for row in history.find(
            {"student_id": user["user_id"], "question_id": {"$in": [q["question_id"] for q in candidates]}},
            {"_id": 0, "question_id": 1}
        )}
        unseen = [q for q in candidates if q["question_id"] not in seen_ids]
        if not unseen:
            missing.append(activity["title"])
            continue
        # Use multiple unseen variants when the prepared bank has them. This
        # produces a more meaningful topic score than a single binary question.
        for chosen in unseen[:3]:
            questions.append({
                "question_id": chosen["question_id"], "course_id": activity["course_id"],
                "course_name": activity["course_name"], "topic_id": activity["topic_id"],
                "topic_title": activity["title"], "question": chosen["question"],
                "options": chosen["options"], "correct_index": chosen["correct_index"],
                "explanation": chosen.get("explanation", ""),
            })
    if missing:
        raise HTTPException(
            status_code=409,
            detail="More unseen questions need to be prepared for: " + ", ".join(missing[:5]) +
                   ". The current prepared question bank is exhausted for these topics.",
        )
    assessment = {
        "assessment_id": str(uuid4()), "student_id": user["user_id"],
        "plan_id": plan["plan_id"], "plan_version": plan.get("version", 1),
        "week": week_number, "questions": questions, "status": "open",
        "created_at": _now(),
    }
    db["weekly_assessments"].insert_one(assessment)
    for question in questions:
        history.update_one(
            {"student_id": user["user_id"], "question_id": question["question_id"]},
            {"$setOnInsert": {"student_id": user["user_id"],
                              "question_id": question["question_id"],
                              "first_seen_at": _now(), "source": "weekly_assessment"}},
            upsert=True,
        )
    return {"assessment": _public_weekly_assessment(assessment), "reused": False}


def _public_weekly_assessment(assessment: dict[str, Any]) -> dict[str, Any]:
    return {
        "assessment_id": assessment["assessment_id"], "week": assessment["week"],
        "status": assessment["status"],
        "questions": [{k: q[k] for k in (
            "question_id", "course_id", "course_name", "topic_id", "topic_title",
            "question", "options"
        )} for q in assessment["questions"]],
    }


@router.post("/assessments/{assessment_id}/submit")
def submit_weekly_assessment(assessment_id: str, request: WeeklyAssessmentSubmission,
                             user: dict = Depends(require_role("student"))):
    db = _db()
    assessment = db["weekly_assessments"].find_one({
        "assessment_id": assessment_id, "student_id": user["user_id"], "status": "open"
    }, {"_id": 0})
    if not assessment:
        raise HTTPException(status_code=404, detail="Open weekly assessment not found.")
    questions = assessment["questions"]
    if set(request.answers) != {q["question_id"] for q in questions}:
        raise HTTPException(status_code=422, detail="Answer every question before submitting.")
    by_topic: dict[tuple[str, str], dict[str, Any]] = {}
    feedback = []
    correct_count = 0
    for q in questions:
        selected = request.answers[q["question_id"]]
        correct = selected == q["correct_index"]
        correct_count += int(correct)
        key = (q["course_id"], q["topic_id"])
        item = by_topic.setdefault(key, {"correct": 0, "total": 0, "title": q["topic_title"]})
        item["correct"] += int(correct)
        item["total"] += 1
        feedback.append({"question_id": q["question_id"], "correct": correct,
                         "correct_index": q["correct_index"], "explanation": q.get("explanation", "")})
    now = _now()
    topic_results = []
    for (course_id, topic_id), item in by_topic.items():
        score = round(item["correct"] / item["total"] * 100, 2)
        topic_results.append({"course_id": course_id, "topic_id": topic_id,
                              "topic_title": item["title"], "score": score})
        db["student_topic_evidence"].update_one(
            {"student_id": user["user_id"], "course_id": course_id, "topic_id": topic_id},
            {"$set": {"student_id": user["user_id"], "course_id": course_id,
                      "topic_id": topic_id, "covered": True,
                      "coverage_source": "weekly_assessment", "mastery_score": score,
                      "last_assessed_at": now, "updated_at": now},
             "$inc": {"assessment_count": 1}},
            upsert=True,
        )
        db["student_topic_progress"].update_one(
            {"student_id": user["user_id"], "course_id": course_id, "topic_id": topic_id},
            {"$set": {"student_id": user["user_id"], "course_id": course_id,
                      "topic_id": topic_id, "mastery_score": score,
                      "status": "needs_revision" if score < 60 else "completed",
                      "assessed_at": now, "updated_at": now}},
            upsert=True,
        )
        db["student_learning_events"].insert_one({
            "student_id": user["user_id"], "course_id": course_id,
            "topic_id": topic_id, "event_type": "weekly_assessment",
            "score": score, "created_at": now,
        })
    total_score = round(correct_count / max(1, len(questions)) * 100, 2)
    db["weekly_assessments"].update_one({"assessment_id": assessment_id}, {"$set": {
        "status": "submitted", "score": total_score, "topic_results": topic_results,
        "answer_feedback": feedback, "submitted_at": now,
    }})
    # Recalculate only this student's remaining semester plan using the new evidence.
    current_plan = db["student_semester_plans"].find_one(
        {"student_id": user["user_id"]}, {"_id": 0}
    )
    if current_plan:
        refreshed = _build_schedule(
            user["user_id"], _student_courses(user["user_id"]),
            float(current_plan["weekly_available_hours"]),
            int(current_plan["semester_weeks"]), current_plan,
        )
        db["student_semester_plans"].replace_one(
            {"student_id": user["user_id"]}, refreshed, upsert=True
        )
    return {"assessment_id": assessment_id, "score": total_score,
            "correct_answers": correct_count, "total_questions": len(questions),
            "topic_results": topic_results,
            "message": "Weekly assessment submitted. Topic mastery was updated and your remaining semester plan was recalculated."}


@router.post("/topics/{topic_id}/complete")
def complete_semester_topic(topic_id: str, user: dict = Depends(require_role("student"))):
    db = _db()
    progress = db["student_topic_progress"].find_one(
        {"student_id": user["user_id"], "topic_id": topic_id}, {"_id": 0}
    )
    if not progress:
        # A topic can exist in the published plan before a progress row has
        # been created. Resolve it from the student's enrolled course plans.
        for course in _student_courses(user["user_id"]):
            for unit in course["plan"].get("units", []):
                if any(t.get("topic_id") == topic_id for t in unit.get("topics", [])):
                    progress = {"course_id": course["course_id"], "topic_id": topic_id}
                    break
            if progress:
                break
    if not progress:
        raise HTTPException(status_code=404, detail="Topic not found in your enrolled course plans.")
    now = _now()
    db["student_topic_progress"].update_one(
        {"student_id": user["user_id"], "course_id": progress["course_id"], "topic_id": topic_id},
        {"$set": {"student_id": user["user_id"], "course_id": progress["course_id"],
                  "topic_id": topic_id, "status": "completed", "updated_at": now}},
        upsert=True,
    )
    db["student_topic_evidence"].update_one(
        {"student_id": user["user_id"], "course_id": progress["course_id"], "topic_id": topic_id},
        {"$set": {"covered": True, "coverage_source": "manual_checklist",
                  "covered_at": now, "updated_at": now},
         "$setOnInsert": {"student_id": user["user_id"], "course_id": progress["course_id"],
                          "topic_id": topic_id}},
        upsert=True,
    )
    collection = db["student_semester_plans"]
    existing = collection.find_one({"student_id": user["user_id"]}, {"_id": 0})
    if existing:
        courses = _student_courses(user["user_id"])
        refreshed = _build_schedule(user["user_id"], courses,
                                    float(existing["weekly_available_hours"]),
                                    int(existing["semester_weeks"]), existing)
        collection.replace_one({"student_id": user["user_id"]}, refreshed, upsert=True)
    updated_plan = collection.find_one({"student_id": user["user_id"]}, {"_id": 0}) if existing else None
    return {"message": "Topic marked as completed and your remaining semester plan was updated.",
            "plan": updated_plan}
