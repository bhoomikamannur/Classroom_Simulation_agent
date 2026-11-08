"""Course-level baseline lesson plans and student-specific topic progress."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo import ASCENDING

from backend.app.api.auth import require_role, get_current_user
from backend.app.database.mongodb import get_mongodb_database
from backend.app.services.course_access import get_accessible_course

router = APIRouter(prefix="/learning-plans", tags=["Adaptive Learning Plans"])


def _now():
    return datetime.now(timezone.utc)


def _db():
    return get_mongodb_database()


def _indexes():
    _db()["course_lesson_plans"].create_index([("course_id", ASCENDING)], unique=True)
    _db()["student_topic_progress"].create_index(
        [("course_id", ASCENDING), ("student_id", ASCENDING), ("topic_id", ASCENDING)],
        unique=True,
    )


class UnitInput(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    topics: list[str] = Field(min_length=1, max_length=30)


class GeneratePlanRequest(BaseModel):
    units: list[UnitInput] = Field(min_length=1, max_length=20)
    semester_weeks: int = Field(default=16, ge=2, le=30)
    start_date: datetime | None = None


class TopicProgressRequest(BaseModel):
    status: str = Field(pattern="^(not_started|in_progress|completed|needs_revision)$")


def _allocate_weeks(units: list[dict[str, Any]], total_weeks: int, previous: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Allocate contiguous week ranges, weighted by topic count, with >=1 week/unit."""
    if len(units) > total_weeks:
        raise HTTPException(status_code=422, detail="Semester weeks must be at least the number of syllabus units.")
    weights = [max(1, len(unit["topics"])) for unit in units]
    remaining = total_weeks - len(units)
    total_weight = sum(weights)
    raw = [remaining * weight / total_weight for weight in weights]
    extras = [int(value) for value in raw]
    leftover = remaining - sum(extras)
    order = sorted(range(len(raw)), key=lambda i: raw[i] - extras[i], reverse=True)
    for index in order[:leftover]:
        extras[index] += 1
    durations = [1 + value for value in extras]
    cursor = 1
    result = []
    previous_units = (previous or {}).get("units", [])
    for index, (unit, duration) in enumerate(zip(units, durations), start=1):
        old_unit = next((item for item in previous_units if item.get("title", "").strip().casefold() == unit["title"].strip().casefold()), None)
        old_topics = (old_unit or {}).get("topics", [])
        result.append({
            "unit_id": (old_unit or {}).get("unit_id", str(uuid4())), "unit_number": index,
            "title": unit["title"].strip(),
            "topics": [
                {"topic_id": next((old["topic_id"] for old in old_topics if old.get("title", "").strip().casefold() == topic.strip().casefold()), str(uuid4())),
                 "title": topic.strip(), "order": topic_index,
                 "estimated_effort_hours": 1.5, "prerequisites": []}
                for topic_index, topic in enumerate(unit["topics"], start=1) if topic.strip()
            ],
            "start_week": cursor, "end_week": cursor + duration - 1,
            "duration_weeks": duration,
        })
        cursor += duration
    return result



def _queue_plan_assessments(course_id: str, plan: dict[str, Any]) -> None:
    """Create durable per-unit preparation records; existing ready topic banks are reused."""
    jobs = _db()["assessment_generation_jobs"]
    banks = _db()["assessment_question_banks"]
    for unit in plan["units"]:
        bank = banks.find_one({"course_id": course_id, "unit_id": unit["unit_id"]}, {"_id": 0})
        topic_ids = {topic["topic_id"] for topic in unit["topics"]}
        counts: dict[str, int] = {}
        for question in (bank or {}).get("questions", []):
            counts[question.get("topic_id")] = counts.get(question.get("topic_id"), 0) + 1
        ready = bank and all(counts.get(topic_id, 0) >= 2 for topic_id in topic_ids)
        job_id = f"{course_id}:{unit['unit_id']}"
        if ready:
            jobs.update_one({"job_id": job_id}, {"$set": {
                "job_id": job_id, "course_id": course_id, "unit_id": unit["unit_id"],
                "unit_title": unit["title"], "plan_version": plan["version"],
                "total_topics": len(unit["topics"]), "completed_topics": len(unit["topics"]),
                "status": "ready", "updated_at": _now(),
            }}, upsert=True)
            continue
        jobs.update_one(
            {"job_id": job_id},
            {"$set": {"job_id": job_id, "course_id": course_id, "unit_id": unit["unit_id"],
                      "unit_title": unit["title"], "plan_version": plan["version"],
                      "total_topics": len(unit["topics"]), "status": "queued",
                      "updated_at": _now()},
             "$setOnInsert": {"created_at": _now(), "completed_topics": 0}},
            upsert=True,
        )


def _prepare_plan_assessments(course_id: str, plan: dict[str, Any]) -> None:
    """Prepare reusable topic questions after plan publication, outside the student request."""
    import json
    from backend.app.llm.ollama_client import generate
    from backend.app.rag.retriever import retrieve

    jobs = _db()["assessment_generation_jobs"]
    banks = _db()["assessment_question_banks"]
    for unit in plan["units"]:
        job_id = f"{course_id}:{unit['unit_id']}"
        job = jobs.find_one({"job_id": job_id}, {"_id": 0})
        if not job or job.get("status") == "ready":
            continue
        jobs.update_one({"job_id": job_id}, {"$set": {"status": "processing", "updated_at": _now()}})
        bank = banks.find_one({"course_id": course_id, "unit_id": unit["unit_id"]}, {"_id": 0}) or {
            "course_id": course_id, "unit_id": unit["unit_id"], "questions": [], "created_at": _now()
        }
        saved = list(bank.get("questions", []))
        saved_topics = {q.get("topic_id") for q in saved}
        try:
            for topic in unit["topics"]:
                if topic["topic_id"] in saved_topics:
                    continue
                docs = retrieve(f"{unit['title']}: {topic['title']}", course_id=course_id, top_k=2)
                context = "\n".join(str(doc.get("text", "")) for doc in docs if doc.get("text"))[:1600]
                prompt = (
                    "Create exactly TWO distinct MCQs for this topic: one conceptual and one application/reasoning. "
                    "Return ONLY compact JSON: "
                    '{"questions":[{"question":"...","options":["...","...","...","..."],"correct_index":0,"explanation":"..."}]}. '
                    "Use four distinct plausible options and one unambiguous correct answer. No markdown.\n"
                    f"UNIT: {unit['title']}\nTOPIC: {topic['title']}\n"
                    f"COURSE CONTEXT: {context or 'Use only established concepts implied by the topic.'}"
                )
                parsed = _parse_json_object(generate(prompt, num_predict=700))
                items = parsed.get("questions")
                if not isinstance(items, list) or len(items) != 2:
                    raise ValueError(f"Expected two questions for topic '{topic['title']}'.")
                topic_questions = []
                for item in items:
                    options, correct = item.get("options"), item.get("correct_index")
                    question_text = str(item.get("question", "")).strip()
                    if (not question_text or not isinstance(options, list) or len(options) != 4
                            or len({str(x).strip().casefold() for x in options}) != 4
                            or any(not str(x).strip() for x in options)
                            or isinstance(correct, bool) or not isinstance(correct, int) or correct not in range(4)):
                        raise ValueError(f"Invalid question structure for '{topic['title']}'.")
                    topic_questions.append({
                        "question_id": str(uuid4()), "topic_id": topic["topic_id"],
                        "topic_title": topic["title"], "question": question_text,
                        "options": [str(x).strip() for x in options], "correct_index": correct,
                        "explanation": str(item.get("explanation", "")).strip(),
                    })
                if topic_questions[0]["question"].casefold() == topic_questions[1]["question"].casefold():
                    raise ValueError(f"Duplicate questions for '{topic['title']}'.")
                saved.extend(topic_questions)
                saved_topics.add(topic["topic_id"])
                banks.update_one(
                    {"course_id": course_id, "unit_id": unit["unit_id"]},
                    {"$set": {"course_id": course_id, "unit_id": unit["unit_id"],
                              "questions": saved, "updated_at": _now()},
                     "$setOnInsert": {"created_at": _now()}}, upsert=True,
                )
                jobs.update_one({"job_id": job_id}, {"$set": {
                    "completed_topics": len(saved_topics), "total_topics": len(unit["topics"]),
                    "status": "processing", "updated_at": _now(),
                }})
            expected = {topic["topic_id"] for topic in unit["topics"]}
            if expected.issubset(saved_topics):
                jobs.update_one({"job_id": job_id}, {"$set": {"status": "ready", "completed_topics": len(expected), "updated_at": _now()}})
            else:
                raise ValueError("Question bank is missing one or more topics.")
        except Exception as exc:
            jobs.update_one({"job_id": job_id}, {"$set": {"status": "failed", "last_error": str(exc)[:300], "updated_at": _now()}})


@router.post("/courses/{course_id}/generate")
def generate_course_plan(
    course_id: str,
    request: GeneratePlanRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_role("professor")),
):
    _indexes()
    course = get_accessible_course(course_id, user)
    cleaned = []
    for unit in request.units:
        topics = [topic.strip() for topic in unit.topics if topic.strip()]
        if not unit.title.strip() or not topics:
            raise HTTPException(status_code=422, detail="Every unit must have a title and at least one topic.")
        cleaned.append({"title": unit.title.strip(), "topics": topics})
    previous_plan = _db()["course_lesson_plans"].find_one({"course_id": course_id}, {"_id": 0})
    units = _allocate_weeks(cleaned, request.semester_weeks, previous_plan)
    now = _now()
    plan = {
        "plan_id": str(uuid4()), "course_id": course_id,
        "course_name": course.get("name", "Course"), "professor_id": user["user_id"],
        "semester_weeks": request.semester_weeks,
        "start_date": request.start_date or now,
        "units": units, "version": 1, "status": "published",
        "created_at": now, "updated_at": now,
        "planning_method": "topic-weighted baseline allocation",
    }
    plan["version"] = int((previous_plan or {}).get("version", 0)) + 1
    _db()["course_lesson_plans"].replace_one({"course_id": course_id}, plan, upsert=True)
    enrollments = list(_db()["course_enrollments"].find({"course_id": course_id, "status": "active"}, {"_id": 0, "student_id": 1}))
    for enrollment in enrollments:
        for unit in units:
            for topic in unit["topics"]:
                _db()["student_topic_progress"].update_one(
                    {"course_id": course_id, "student_id": enrollment["student_id"], "topic_id": topic["topic_id"]},
                    {"$setOnInsert": {
                        "course_id": course_id, "student_id": enrollment["student_id"],
                        "unit_id": unit["unit_id"], "topic_id": topic["topic_id"],
                        "status": "not_started", "mastery_score": None,
                        "created_at": now, "updated_at": now,
                    }}, upsert=True,
                )
    _queue_plan_assessments(course_id, plan)
    background_tasks.add_task(_prepare_plan_assessments, course_id, plan)
    return {"message": "Baseline lesson plan published. Unit assessments are being prepared in the background.", "plan": plan, "enrolled_students_initialized": len(enrollments), "assessment_preparation": "queued"}


@router.get("/courses/{course_id}")
def get_course_plan(course_id: str, user: dict = Depends(require_role("professor"))):
    _indexes()
    get_accessible_course(course_id, user)
    plan = _db()["course_lesson_plans"].find_one({"course_id": course_id, "professor_id": user["user_id"]}, {"_id": 0})
    if not plan:
        raise HTTPException(status_code=404, detail="No lesson plan has been generated for this course.")
    return {"plan": plan}



@router.get("/courses/{course_id}/assessment-preparation")
def get_assessment_preparation(course_id: str, user: dict = Depends(require_role("professor"))):
    get_accessible_course(course_id, user)
    plan = _db()["course_lesson_plans"].find_one({"course_id": course_id, "professor_id": user["user_id"]}, {"_id": 0, "units": 1})
    if not plan:
        raise HTTPException(status_code=404, detail="No lesson plan has been generated.")
    jobs = list(_db()["assessment_generation_jobs"].find(
        {"course_id": course_id, "unit_id": {"$in": [unit["unit_id"] for unit in plan["units"]]}},
        {"_id": 0, "job_id": 0, "course_id": 0},
    ))
    by_unit = {job["unit_id"]: job for job in jobs}
    return {"units": [{"unit_id": unit["unit_id"], "title": unit["title"],
                       "status": by_unit.get(unit["unit_id"], {}).get("status", "ready"),
                       "completed_topics": by_unit.get(unit["unit_id"], {}).get("completed_topics", len(unit["topics"])),
                       "total_topics": len(unit["topics"]),
                       "error": by_unit.get(unit["unit_id"], {}).get("last_error")}
                      for unit in plan["units"]]}


@router.get("/courses/{course_id}/mine")
def get_my_course_plan(course_id: str, user: dict = Depends(require_role("student"))):
    _indexes()
    get_accessible_course(course_id, user)
    plan = _db()["course_lesson_plans"].find_one({"course_id": course_id, "status": "published"}, {"_id": 0})
    if not plan:
        raise HTTPException(status_code=404, detail="Your professor has not published a lesson plan yet.")
    progress = list(_db()["student_topic_progress"].find(
        {"course_id": course_id, "student_id": user["user_id"]}, {"_id": 0}
    ))
    preparation_jobs = {job["unit_id"]: job for job in _db()["assessment_generation_jobs"].find(
        {"course_id": course_id}, {"_id": 0, "unit_id": 1, "status": 1, "completed_topics": 1, "total_topics": 1}
    )}
    by_topic = {item["topic_id"]: item for item in progress}
    student_units = []
    carryover_by_unit: dict[str, list[dict[str, Any]]] = {}
    events = list(_db()["student_learning_events"].find(
        {"student_id": user["user_id"], "course_id": course_id, "event_type": "unit_assessment"},
        {"_id": 0, "unit_id": 1, "weak_topics": 1, "score": 1},
    ).sort("created_at", -1))
    unit_positions = {unit["unit_id"]: index for index, unit in enumerate(plan["units"])}
    for event in events:
        source_index = unit_positions.get(event.get("unit_id"), -1)
        if source_index < 0 or source_index + 1 >= len(plan["units"]):
            continue
        next_unit_id = plan["units"][source_index + 1]["unit_id"]
        existing = {item.get("topic_id") for item in carryover_by_unit.get(next_unit_id, [])}
        for weak in event.get("weak_topics", []):
            if weak.get("topic_id") not in existing:
                carryover_by_unit.setdefault(next_unit_id, []).append(weak)
    start_value = plan.get("start_date")
    if isinstance(start_value, str):
        try:
            start_value = datetime.fromisoformat(start_value.replace("Z", "+00:00"))
        except ValueError:
            start_value = None
    if isinstance(start_value, datetime):
        current_week = max(1, min(int(plan.get("semester_weeks", 16)), ((_now().date() - start_value.date()).days // 7) + 1))
    else:
        current_week = 1
    adaptive = _db()["student_adaptive_plans"].find_one(
        {"student_id": user["user_id"], "course_id": course_id}, {"_id": 0}
    ) or {}
    revision_unit_id = None
    if adaptive.get("revision_required") and adaptive.get("last_assessed_unit_id") in unit_positions:
        source_index = unit_positions[adaptive["last_assessed_unit_id"]]
        if source_index + 1 < len(plan["units"]):
            revision_unit_id = plan["units"][source_index + 1]["unit_id"]
    for unit in plan["units"]:
        topics = []
        for topic in unit["topics"]:
            record = by_topic.get(topic["topic_id"], {})
            topics.append({**topic, "status": record.get("status", "not_started"), "mastery_score": record.get("mastery_score")})
        completed_count = sum(1 for topic in topics if topic["status"] == "completed")
        incomplete_due = [topic["title"] for topic in topics if int(unit["end_week"]) < current_week and topic["status"] != "completed"]
        early = completed_count == len(topics) and current_week < int(unit["end_week"])
        adjusted_start, adjusted_end = int(unit["start_week"]), int(unit["end_week"])
        revision_week = None
        if revision_unit_id:
            next_index = unit_positions[revision_unit_id]
            if unit["unit_id"] == revision_unit_id:
                revision_week = adjusted_start
                adjusted_start += 1
                adjusted_end += 1
            elif unit_positions[unit["unit_id"]] > next_index:
                adjusted_start += 1
                adjusted_end += 1
        job = preparation_jobs.get(unit["unit_id"], {})
        student_units.append({**unit, "start_week": adjusted_start, "end_week": adjusted_end,
                              "revision_week": revision_week,
                              "assessment_status": job.get("status", "ready"),
                              "assessment_topics_ready": job.get("completed_topics", len(unit["topics"])),
                              "assessment_topics_total": job.get("total_topics", len(unit["topics"])),
                              "topics": topics,
                              "revision_topics": carryover_by_unit.get(unit["unit_id"], []),
                              "early_completion": early, "behind_schedule_topics": incomplete_due})
    return {"plan": {**plan, "units": student_units, "current_week": current_week,
                      "adaptation_summary": "Unmastered topics are surfaced for revision in the next learning slot; early completion creates room for revision or early progression, while overdue topics are highlighted."}}


@router.patch("/courses/{course_id}/topics/{topic_id}")
def update_topic_progress(
    course_id: str, topic_id: str, request: TopicProgressRequest,
    user: dict = Depends(require_role("student")),
):
    _indexes()
    get_accessible_course(course_id, user)
    plan = _db()["course_lesson_plans"].find_one({"course_id": course_id, "status": "published"}, {"_id": 0, "units": 1})
    topic = next((topic for unit in (plan or {}).get("units", []) for topic in unit["topics"] if topic["topic_id"] == topic_id), None)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found in this course plan.")
    now = _now()
    _db()["student_topic_progress"].update_one(
        {"course_id": course_id, "student_id": user["user_id"], "topic_id": topic_id},
        {"$set": {"status": request.status, "updated_at": now}, "$setOnInsert": {
            "course_id": course_id, "student_id": user["user_id"], "topic_id": topic_id,
            "created_at": now,
        }}, upsert=True,
    )
    if request.status == "completed":
        _db()["student_topic_evidence"].update_one(
            {"student_id": user["user_id"], "course_id": course_id, "topic_id": topic_id},
            {"$set": {"covered": True, "coverage_source": "manual_checklist", "covered_at": now, "updated_at": now},
             "$setOnInsert": {"student_id": user["user_id"], "course_id": course_id, "topic_id": topic_id}},
            upsert=True,
        )
    return {"message": "Topic progress updated.", "topic_id": topic_id, "status": request.status}

class AssessmentSubmission(BaseModel):
    answers: dict[str, int]


def _parse_json_object(raw: str) -> dict[str, Any]:
    import json
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
    result = json.loads(text)
    if not isinstance(result, dict):
        raise ValueError("Expected a JSON object.")
    return result


@router.post("/courses/{course_id}/units/{unit_id}/assessment")
def get_prepared_unit_assessment(
    course_id: str, unit_id: str, user: dict = Depends(require_role("student")),
):
    """Instantly create a student attempt from the pre-generated shared question bank."""
    _indexes()
    get_accessible_course(course_id, user)
    plan = _db()["course_lesson_plans"].find_one({"course_id": course_id, "status": "published"}, {"_id": 0})
    unit = next((item for item in (plan or {}).get("units", []) if item["unit_id"] == unit_id), None)
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found.")
    progress = list(_db()["student_topic_progress"].find(
        {"course_id": course_id, "student_id": user["user_id"], "unit_id": unit_id}, {"_id": 0}
    ))
    completed = {item["topic_id"] for item in progress if item.get("status") == "completed"}
    if len(completed) < len(unit["topics"]):
        raise HTTPException(status_code=409, detail="Complete every topic in this unit before taking its assessment.")
    assessments = _db()["unit_assessments"]
    existing = assessments.find_one({
        "course_id": course_id, "unit_id": unit_id, "student_id": user["user_id"],
        "plan_version": plan.get("version", 1), "status": "open",
    }, {"_id": 0})
    if existing:
        questions = existing["questions"]
        return {"assessment_id": existing["assessment_id"], "unit_title": unit["title"],
                "questions": [{k: v for k, v in q.items() if k not in {"correct_index", "explanation"}} for q in questions]}
    bank = _db()["assessment_question_banks"].find_one({"course_id": course_id, "unit_id": unit_id}, {"_id": 0})
    if not bank:
        raise HTTPException(status_code=409, detail="This unit's assessment is still being prepared. Please try again shortly.")
    questions = []
    for topic in unit["topics"]:
        topic_bank = [q for q in bank.get("questions", []) if q.get("topic_id") == topic["topic_id"]]
        if len(topic_bank) < 2:
            raise HTTPException(status_code=409, detail=f"Assessment preparation is incomplete for '{topic['title']}'. Please try again later.")
        questions.extend(topic_bank[:2])
    assessment_id = str(uuid4())
    record = {"assessment_id": assessment_id, "course_id": course_id, "unit_id": unit_id,
              "student_id": user["user_id"], "plan_version": plan.get("version", 1),
              "questions": questions, "status": "open", "created_at": _now(),
              "source": "pre_generated_question_bank"}
    assessments.insert_one(record)
    return {"assessment_id": assessment_id, "unit_title": unit["title"],
            "questions": [{k: v for k, v in q.items() if k not in {"correct_index", "explanation"}} for q in questions]}


@router.post("/courses/{course_id}/assessments/{assessment_id}/submit")
def submit_unit_assessment(
    course_id: str, assessment_id: str, request: AssessmentSubmission,
    user: dict = Depends(require_role("student")),
):
    _indexes()
    get_accessible_course(course_id, user)
    assessment = _db()["unit_assessments"].find_one({
        "assessment_id": assessment_id, "course_id": course_id,
        "student_id": user["user_id"], "status": "open",
    }, {"_id": 0})
    if not assessment:
        raise HTTPException(status_code=404, detail="Open assessment not found.")
    questions = assessment["questions"]
    correct_count = 0
    per_topic: dict[str, dict[str, Any]] = {}
    answer_feedback = []
    for question in questions:
        selected = request.answers.get(question["question_id"])
        correct = selected == question["correct_index"]
        correct_count += int(correct)
        topic_id = question["topic_id"]
        item = per_topic.setdefault(topic_id, {"correct": 0, "total": 0, "topic_title": question["topic_title"]})
        item["correct"] += int(correct)
        item["total"] += 1
        answer_feedback.append({"question_id": question["question_id"], "correct": correct,
                                "correct_index": question["correct_index"], "explanation": question.get("explanation", "")})
    percentage = round(correct_count / max(1, len(questions)) * 100, 2)
    now = _now()
    weak_topics = []
    for topic_id, result in per_topic.items():
        topic_score = round(result["correct"] / result["total"] * 100, 2)
        status = "completed" if topic_score >= 60 else "needs_revision"
        _db()["student_topic_progress"].update_one(
            {"course_id": course_id, "student_id": user["user_id"], "topic_id": topic_id},
            {"$set": {"mastery_score": topic_score, "status": status, "assessed_at": now, "updated_at": now}},
        )
        _db()["student_topic_evidence"].update_one(
            {"student_id": user["user_id"], "course_id": course_id, "topic_id": topic_id},
            {"$set": {"covered": True, "coverage_source": "unit_assessment", "mastery_score": topic_score,
                      "last_assessed_at": now, "assessment_count": 1, "updated_at": now},
             "$setOnInsert": {"student_id": user["user_id"], "course_id": course_id, "topic_id": topic_id}},
            upsert=True,
        )
        if status == "needs_revision":
            weak_topics.append({"topic_id": topic_id, "title": result["topic_title"], "mastery_score": topic_score})
    _db()["unit_assessments"].update_one({"assessment_id": assessment_id}, {"$set": {
        "status": "submitted", "score": percentage, "submitted_at": now,
        "answer_feedback": answer_feedback,
    }})
    result = {
        "assessment_id": assessment_id, "score": percentage,
        "correct_answers": correct_count, "total_questions": len(questions),
        "topic_results": [{"topic_id": key, "topic_title": value["topic_title"],
                           "score": round(value["correct"] / value["total"] * 100, 2)} for key, value in per_topic.items()],
        "topics_to_revisit": weak_topics,
        "unit_mastered": not weak_topics,
        "message": "Unit mastered. Continue to the next unit." if not weak_topics else "Some topics need targeted revision. Your topic mastery results have been recorded.",
    }
    _db()["student_learning_events"].insert_one({
        "student_id": user["user_id"], "course_id": course_id,
        "unit_id": assessment["unit_id"], "event_type": "unit_assessment",
        "score": percentage, "weak_topics": weak_topics, "created_at": now,
    })
    # Student-specific adaptation signal; the professor's baseline plan remains unchanged.
    _db()["student_adaptive_plans"].update_one(
        {"student_id": user["user_id"], "course_id": course_id},
        {"$set": {"student_id": user["user_id"], "course_id": course_id,
                  "last_assessed_unit_id": assessment["unit_id"],
                  "revision_topics": weak_topics,
                  "revision_required": bool(weak_topics),
                  "revision_weeks": 1 if weak_topics else 0,
                  "last_assessment_score": percentage, "updated_at": now}},
        upsert=True,
    )
    return result

class SyllabusExtractRequest(BaseModel):
    document_id: str = Field(min_length=1)


@router.post("/courses/{course_id}/extract-syllabus")
def extract_syllabus_structure(
    course_id: str, request: SyllabusExtractRequest,
    user: dict = Depends(require_role("professor")),
):
    """Extract a reviewable unit/topic outline from an already-uploaded PDF/PPTX."""
    from pathlib import Path
    import json
    from backend.app.llm.ollama_client import generate
    from backend.app.rag.loaders.pdf_loader import load_pdf
    from backend.app.rag.loaders.pptx_loader import load_pptx

    course = get_accessible_course(course_id, user)
    document = _db()["documents"].find_one({
        "document_id": request.document_id, "course_id": course_id,
        "professor_id": user["user_id"], "status": "processed",
    }, {"_id": 0})
    if not document or not document.get("file_path"):
        raise HTTPException(status_code=404, detail="Processed syllabus document not found in this course.")
    backend_root = Path(__file__).resolve().parents[2]
    uploads_root = (backend_root / "data" / "uploads").resolve()
    path = (backend_root / document["file_path"]).resolve()
    if uploads_root not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="Original syllabus file is unavailable.")
    try:
        pages = load_pdf(path) if document.get("file_type") == "pdf" else load_pptx(path)
        text = "\n\n".join(str(page.get("text", "")) for page in pages)
        if not text.strip():
            raise ValueError("No readable text was extracted.")
        prompt = f'''Extract the formal syllabus hierarchy from this document. Return ONLY JSON in this shape: {{"units":[{{"title":"Unit 1: ...","topics":["topic 1","topic 2"]}}]}}. Preserve the source's unit names and topic wording. Do not invent topics. Ignore course outcomes, references, schedules and assessment policy unless they are explicitly listed as syllabus topics. If the hierarchy is unclear, return only clearly supported units and topics.\nCOURSE: {course.get("name", "Course")}\nSYLLABUS TEXT:\n{text[:24000]}'''
        result = _parse_json_object(generate(prompt))
        raw_units = result.get("units", [])
        units = []
        for item in raw_units:
            title = str(item.get("title", "")).strip()
            topics = [str(topic).strip() for topic in item.get("topics", []) if str(topic).strip()]
            if title and topics:
                units.append({"title": title, "topics": topics})
        if not units:
            raise ValueError("The model did not identify any units with topics.")
        return {"document_id": request.document_id, "filename": document.get("filename"), "units": units,
                "message": "Review the extracted unit/topic structure before publishing the lesson plan."}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Syllabus extraction failed. Check the configured Ollama model and document text. ({str(exc)[:180]})") from exc
