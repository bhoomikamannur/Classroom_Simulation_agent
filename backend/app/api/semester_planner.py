"""Semester-wide adaptive planner across all courses enrolled by a student."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.api.auth import require_role
from backend.app.database.mongodb import get_mongodb_database
from backend.app.learning.schedule_policy import (
    adaptive_course_allocations, calculate_current_week, is_carry_forward,
    revision_week_after_assessment,
)

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


def _parse_plan_date(value: Any):
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _build_schedule(student_id: str, courses: list[dict[str, Any]], hours: float,
                    weeks_override: int | None, previous: dict[str, Any] | None) -> dict[str, Any]:
    """Build a time-aware, cross-course adaptive plan with explicit required/optional work."""
    total_weeks = weeks_override or max(
        [int(item["plan"].get("semester_weeks", 16)) for item in courses] or [16]
    )
    capacity = float(hours)
    db = _db()
    progress_docs = list(db["student_topic_progress"].find({"student_id": student_id}, {"_id": 0}))
    progress = {item["topic_id"]: item for item in progress_docs}
    evidence_docs = list(db["student_topic_evidence"].find({"student_id": student_id}, {"_id": 0}))
    evidence = {item["topic_id"]: item for item in evidence_docs}

    starts = [_parse_plan_date(item["plan"].get("start_date")) for item in courses]
    starts = [value for value in starts if value is not None]
    semester_start = min(starts) if starts else _now()
    if semester_start.tzinfo is None:
        semester_start = semester_start.replace(tzinfo=timezone.utc)
    current_week = calculate_current_week(semester_start.date(), _now().date(), total_weeks)

    weeks: dict[int, dict[str, Any]] = {
        week: {"week": week, "planned_hours": 0.0, "activities": [],
               "assessment_topics": [], "course_planned_hours": {}}
        for week in range(current_week, total_weeks + 1)
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
                assessed_at = _parse_plan_date(e.get("last_assessed_at") or p.get("assessed_at"))
                assessed_week = (
                    calculate_current_week(semester_start.date(), assessed_at.date(), total_weeks)
                    if assessed_at else None
                )
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
                    "last_assessed_at": assessed_at, "assessed_week": assessed_week,
                    "checklist_status": p.get("status", "not_started"),
                    "revision_required": state == "revision_required",
                })

    allocations = adaptive_course_allocations(topics, capacity)
    course_caps = {row["course_id"]: row["weekly_hours"] for row in allocations}
    previous_required_week: dict[str, int] = {}
    if previous:
        for old_week in previous.get("weeks", []):
            for activity in old_week.get("activities", []):
                if activity.get("topic_id") and activity.get("schedule_type", "required") == "required":
                    previous_required_week[activity["topic_id"]] = int(old_week.get("week", activity.get("week", 1)))

    pending = [t for t in topics if t["coverage_status"] in {"not_covered", "revision_required"}]
    pending.sort(key=lambda t: (
        0 if (t["topic_id"] in previous_required_week and previous_required_week[t["topic_id"]] < current_week) else 1,
        t["baseline_end_week"], 0 if t["revision_required"] else 1,
        -t["difficulty"], -t["estimated_effort_hours"], t["course_name"], t["title"],
    ))
    assigned: set[str] = set()
    required_week_by_topic: dict[str, int] = {}
    for topic in pending:
        start_week = topic["baseline_start_week"]
        end_week = max(start_week, topic["baseline_end_week"])
        old_week = previous_required_week.get(topic["topic_id"])
        overdue = is_carry_forward(old_week, end_week, current_week)
        weak_result = (
            topic["revision_required"] and topic.get("assessed_week") is not None
            and topic["assessed_week"] >= current_week
        )
        if weak_result:
            revision_week = revision_week_after_assessment(
                topic["assessed_week"], current_week, total_weeks
            )
            candidates = list(range(revision_week or current_week, total_weeks + 1))
        elif overdue:
            candidates = list(range(current_week, total_weeks + 1))
        else:
            candidates = [w for w in range(max(current_week, start_week), end_week + 1)]
            candidates += list(range(end_week + 1, total_weeks + 1))
        if not candidates:
            candidates = [current_week]
        course_cap = course_caps.get(topic["course_id"], 0.0)
        effort = topic["estimated_effort_hours"]

        def load_score(w: int):
            global_load = weeks[w]["planned_hours"]
            course_load = weeks[w]["course_planned_hours"].get(topic["course_id"], 0.0)
            return (
                global_load / max(capacity, 0.1),
                course_load / max(course_cap, 0.1),
                sum(1 for a in weeks[w]["activities"] if a.get("schedule_type") == "required"),
                abs(w - ((max(current_week, start_week) + max(current_week, end_week)) / 2)),
                w,
            )

        feasible = [
            w for w in candidates
            if weeks[w]["planned_hours"] + effort <= capacity + 1e-6
            and weeks[w]["course_planned_hours"].get(topic["course_id"], 0.0) + effort <= course_cap + 1e-6
        ]
        pool = feasible or candidates
        chosen = min(pool, key=load_score)
        reason = (
            "Carried forward from an earlier week because required work was not completed."
            if overdue else
            "Required targeted revision scheduled for the week after a poor assessment result."
            if weak_result else
            "Required targeted revision based on weak assessment evidence."
            if topic["revision_required"] else
            "Required syllabus topic, scheduled within the professor's baseline window and adaptive course-hour allocation."
        )
        weeks[chosen]["activities"].append({
            **topic, "week": chosen,
            "status": "revision" if topic["revision_required"] else "planned",
            "schedule_type": "required", "carried_forward": overdue, "revision_scheduled_next_week": weak_result,
            "schedule_reason": reason,
        })
        weeks[chosen]["planned_hours"] += effort
        weeks[chosen]["course_planned_hours"][topic["course_id"]] = (
            weeks[chosen]["course_planned_hours"].get(topic["course_id"], 0.0) + effort
        )
        weeks[chosen]["assessment_topics"].append({
            "topic_id": topic["topic_id"], "course_id": topic["course_id"],
            "course_name": topic["course_name"], "title": topic["title"],
        })
        assigned.add(topic["topic_id"])
        required_week_by_topic[topic["topic_id"]] = chosen

    # Maintain cumulative syllabus obligations for progress-risk analysis even though
    # historical weeks are removed from the active calendar shown to the student.
    due_topic_map: dict[str, dict[str, str]] = {}
    for row in (previous or {}).get("progress_due_topics", []):
        if row.get("topic_id") and row.get("course_id"):
            due_topic_map[row["topic_id"]] = {
                "topic_id": row["topic_id"], "course_id": row["course_id"]
            }
    for topic in topics:
        scheduled_week = required_week_by_topic.get(topic["topic_id"])
        if topic["baseline_end_week"] < current_week or (
            scheduled_week is not None and scheduled_week <= current_week
        ):
            due_topic_map[topic["topic_id"]] = {
                "topic_id": topic["topic_id"], "course_id": topic["course_id"]
            }

    # The active response intentionally contains current/future weeks only.
    # Cumulative due-topic evidence above preserves the risk engine's semester context.

    # Optional early-study suggestions consume spare course/global capacity but never count as required.
    for week_number, week_data in weeks.items():
        spare_global = max(0.0, capacity - week_data["planned_hours"])
        if spare_global < 0.5:
            continue
        candidates = [
            t for t in topics if t["topic_id"] in required_week_by_topic
            and required_week_by_topic[t["topic_id"]] > week_number
            and t["coverage_status"] == "not_covered"
        ]
        candidates.sort(key=lambda t: (t["baseline_start_week"], -t["difficulty"], t["course_name"]))
        for topic in candidates:
            course_spare = course_caps.get(topic["course_id"], 0.0) - week_data["course_planned_hours"].get(topic["course_id"], 0.0)
            if topic["estimated_effort_hours"] <= min(spare_global, max(0.0, course_spare)) + 1e-6:
                week_data["activities"].append({
                    **topic, "week": week_number, "status": "optional",
                    "schedule_type": "optional",
                    "schedule_reason": "Optional early-study opportunity. Skipping this does not make you behind; the topic remains required in its original future window.",
                })
                spare_global -= topic["estimated_effort_hours"]
                if spare_global < 0.5:
                    break

    # Optional reinforcement and extension rotate across topics rather than
    # repeating the same suggestion in every future week.
    revision_suggested: set[str] = set()
    extension_suggested: set[str] = set()
    for week_number, week_data in weeks.items():
        suggested = {a.get("topic_id") for a in week_data["activities"]}
        revision_candidates = [
            t for t in topics if t["coverage_status"] == "covered"
            and t["topic_id"] not in suggested and t["topic_id"] not in revision_suggested
            and (t.get("mastery_score") is None or 60 <= t["mastery_score"] < 80)
        ]
        if revision_candidates and week_data["planned_hours"] < capacity:
            topic = revision_candidates[0]
            week_data["activities"].append({
                **topic, "week": week_number, "status": "revision_suggestion",
                "schedule_type": "revision",
                "schedule_reason": "Optional reinforcement assessment to strengthen partially secure or unverified understanding.",
            })
            revision_suggested.add(topic["topic_id"])
        mastered = [t for t in topics if t["coverage_status"] == "mastered"
                    and t["topic_id"] not in suggested and t["topic_id"] not in extension_suggested]
        if mastered and week_data["planned_hours"] < capacity and not revision_candidates:
            topic = mastered[0]
            week_data["activities"].append({
                **topic, "week": week_number, "status": "extended_practice",
                "schedule_type": "extended_assessment",
                "schedule_reason": "Optional extension challenge because demonstrated mastery is strong.",
            })
            extension_suggested.add(topic["topic_id"])

    for week_data in weeks.values():
        week_data["planned_hours"] = round(week_data["planned_hours"], 1)
        week_data["capacity_hours"] = capacity
        week_data["over_capacity"] = week_data["planned_hours"] > capacity
        week_data["required_hours"] = week_data["planned_hours"]
        week_data["required_topic_count"] = sum(1 for a in week_data["activities"] if a.get("schedule_type") == "required")
        week_data.pop("course_planned_hours", None)

    now = _now()
    return {
        "plan_id": (previous or {}).get("plan_id", str(uuid4())),
        "student_id": student_id, "weekly_available_hours": capacity,
        "semester_weeks": total_weeks, "current_week": current_week,
        "semester_start_date": semester_start, "weeks": list(weeks.values()),
        "progress_due_topics": list(due_topic_map.values()),
        "course_hour_allocations": allocations,
        "course_count": len(courses), "topic_count": len(topics),
        "generated_at": now, "updated_at": now,
        "version": int((previous or {}).get("version", 0)) + 1,
        "planning_method": "time-aware adaptive allocation with required carry-forward, optional early study, revision and extension activities",
    }


def _refresh_student_semester_plan(student_id: str) -> dict[str, Any] | None:
    collection = _db()["student_semester_plans"]
    plan = collection.find_one({"student_id": student_id}, {"_id": 0})
    if not plan:
        return None
    courses = _student_courses(student_id)
    if not courses:
        return plan
    start = _parse_plan_date(plan.get("semester_start_date"))
    if start is None:
        dates = [_parse_plan_date(item["plan"].get("start_date")) for item in courses]
        dates = [value for value in dates if value is not None]
        start = min(dates) if dates else None
    live_week = None
    if start:
        live_week = calculate_current_week(start.date(), _now().date(),
                                           int(plan.get("semester_weeks", 16)))
    needs_upgrade = (
        not plan.get("current_week")
        or "course_hour_allocations" not in plan
        or "progress_due_topics" not in plan
    )
    week_advanced = live_week is not None and live_week > int(plan.get("current_week", 1))
    if needs_upgrade or week_advanced:
        plan = _build_schedule(
            student_id, courses, float(plan["weekly_available_hours"]),
            int(plan["semester_weeks"]), plan,
        )
        collection.replace_one({"student_id": student_id}, plan, upsert=True)
    return plan


@router.get("/mine")
def get_my_semester_plan(user: dict = Depends(require_role("student"))):
    return {"plan": _refresh_student_semester_plan(user["user_id"])}


@router.post("/generate")
def generate_my_semester_plan(request: GenerateSemesterPlanRequest,
                              user: dict = Depends(require_role("student"))):
    courses = _student_courses(user["user_id"])
    if not courses:
        raise HTTPException(status_code=409, detail="No enrolled courses with published lesson plans were found.")
    db = _db()
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
def create_weekly_assessment(week_number: int, mode: str = "regular",
                             user: dict = Depends(require_role("student"))):
    """Assemble a regular, targeted-revision, or extension assessment from unseen bank questions."""
    if mode not in {"regular", "revision", "extended"}:
        raise HTTPException(status_code=422, detail="Assessment mode must be regular, revision, or extended.")
    db = _db()
    plan = db["student_semester_plans"].find_one(
        {"student_id": user["user_id"]}, {"_id": 0}
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Generate your semester plan first.")
    week = next((item for item in plan.get("weeks", []) if item.get("week") == week_number), None)
    if not week:
        raise HTTPException(status_code=404, detail="Week not found in your semester plan.")
    mode_filter = ({"$or": [{"assessment_mode": "regular"}, {"assessment_mode": {"$exists": False}}]}
                   if mode == "regular" else {"assessment_mode": mode})
    existing = db["weekly_assessments"].find_one({
        "student_id": user["user_id"], "plan_id": plan["plan_id"],
        "week": week_number, **mode_filter, "status": "open",
    }, {"_id": 0})
    if existing:
        return {"assessment": _public_weekly_assessment(existing), "reused": True}
    submitted = db["weekly_assessments"].find_one({
        "student_id": user["user_id"], "plan_id": plan["plan_id"],
        "week": week_number, **mode_filter, "status": "submitted",
    }, {"_id": 0, "score": 1})
    if submitted:
        raise HTTPException(status_code=409, detail="You have already submitted this week's assessment.")

    # Assessment mode determines which activities are sampled. Optional activities
    # never become compulsory syllabus work or progress-risk obligations.
    if mode == "regular":
        activities = [a for a in week.get("activities", [])
                      if a.get("schedule_type", "required") == "required"
                      and a.get("coverage_status") != "mastered"
                      and not a.get("revision_required")]
    elif mode == "revision":
        activities = [a for a in week.get("activities", [])
                      if a.get("schedule_type") == "revision"
                      or (a.get("schedule_type") == "required" and a.get("revision_required"))]
    else:
        activities = [a for a in week.get("activities", [])
                      if a.get("schedule_type") == "extended_assessment"]
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
        "week": week_number, "assessment_mode": mode,
        "questions": questions, "status": "open", "created_at": _now(),
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
        "mode": assessment.get("assessment_mode", "regular"), "status": assessment["status"],
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
