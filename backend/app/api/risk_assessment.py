"""Explainable cross-module student risk aggregation for professor dashboards.

Conceptual understanding combines Performance Agent diagnoses, persistent
misconception alerts, and formative unit-assessment mastery. Formal academic
marks remain isolated in the academic-performance dimension.
"""
from __future__ import annotations

from datetime import datetime, timezone, date
from typing import Any

from fastapi import APIRouter, Depends

from backend.app.analytics.academic_risk import analyse_assessment_risk

from backend.app.api.auth import require_role
from backend.app.database.mongodb import get_mongodb_database

router = APIRouter(prefix="/risk-assessment", tags=["Student Risk Assessment"])

WEIGHTS = {"conceptual": 0.30, "progress": 0.25, "academic": 0.30, "project": 0.15}


def _db():
    return get_mongodb_database()


def _safe_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except ValueError:
            return None
    return None


def _dimension(score: float, evidence: list[dict[str, Any]], available: bool = True) -> dict[str, Any]:
    return {"score": round(max(0, min(100, score)), 1), "available": available, "evidence": evidence}


def _student_risk(student_id: str, courses: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    db = _db()
    course_ids = [item["course_id"] for item in courses]
    course_names = {item["course_id"]: item.get("name", "Course") for item in courses}
    evidence: dict[str, list[dict[str, Any]]] = {key: [] for key in WEIGHTS}

    # 1) Conceptual understanding: structured Performance Agent profile.
    # Tutor conversations are inputs/context for Performance Agent diagnosis;
    # raw tutor messages are deliberately not counted as misconceptions.
    conceptual_risk_values: list[float] = []
    profile_concepts_seen: set[tuple[str, str]] = set()
    profiles = list(db["student_learning_profiles"].find(
        {"student_id": student_id, "course_id": {"$in": course_ids}},
        {"_id": 0, "course_id": 1, "concepts": 1},
    ))
    for profile in profiles:
        course_id = profile.get("course_id")
        concepts = profile.get("concepts", {})
        if not isinstance(concepts, dict):
            continue
        for concept_key, item in concepts.items():
            if not isinstance(item, dict):
                continue
            state = str(item.get("current_state", "")).lower()
            if state not in {"confused", "partial"}:
                continue
            identity = (str(course_id), str(concept_key))
            if identity in profile_concepts_seen:
                continue
            profile_concepts_seen.add(identity)
            severity_score = 35.0 if state == "confused" else 20.0
            conceptual_risk_values.append(severity_score)
            evidence["conceptual"].append({
                "course": course_names.get(course_id, "Course"),
                "issue": item.get("concept") or str(concept_key).replace("_", " "),
                "severity": "high" if state == "confused" else "medium",
                "source": "Performance Agent diagnosis",
                "details": (
                    "A misconception remains in the latest longitudinal concept profile."
                    if state == "confused"
                    else "Understanding is partial and may need reinforcement."
                ),
                "latest_evidence": item.get("latest_misconceptions") or item.get("latest_evidence") or [],
            })

    # Active misconception alerts provide lifecycle/severity evidence. Do not
    # count an alert twice when its concept is already represented in profile.
    alerts = list(db["teacher_alerts"].find({
        "student_id": student_id, "course_id": {"$in": course_ids},
        "status": "open", "alert_type": "persistent_misconception",
    }, {"_id": 0, "course_id": 1, "concept": 1, "concept_key": 1,
        "priority": 1, "message": 1, "latest_seen_at": 1}))
    for alert in alerts:
        identity = (str(alert.get("course_id")), str(alert.get("concept_key") or ""))
        if identity in profile_concepts_seen:
            # Profile state already contributes to the score; enrich its evidence.
            continue
        priority = str(alert.get("priority", "medium")).lower()
        conceptual_risk_values.append(35.0 if priority == "high" else 20.0)
        evidence["conceptual"].append({
            "course": course_names.get(alert.get("course_id"), "Course"),
            "issue": alert.get("concept", "Unresolved misconception"),
            "severity": priority,
            "source": "Persistent misconception alert",
            "details": alert.get("message", "Persistent misconception remains open."),
        })

    # Formative unit assessments belong to conceptual mastery, not formal
    # academic performance. Use the latest submitted attempt per unit.
    unit_results = list(db["unit_assessments"].find({
        "student_id": student_id, "course_id": {"$in": course_ids}, "status": "submitted",
    }, {"_id": 0, "course_id": 1, "unit_id": 1, "score": 1, "questions": 1,
        "answer_feedback": 1, "submitted_at": 1}).sort("submitted_at", -1))
    latest_by_unit: dict[tuple[str, str], dict[str, Any]] = {}
    for attempt in unit_results:
        key = (str(attempt.get("course_id")), str(attempt.get("unit_id")))
        latest_by_unit.setdefault(key, attempt)

    for attempt in latest_by_unit.values():
        questions = attempt.get("questions", [])
        feedback = {row.get("question_id"): row for row in attempt.get("answer_feedback", [])
                    if isinstance(row, dict)}
        per_topic: dict[str, dict[str, Any]] = {}
        for question in questions:
            if not isinstance(question, dict):
                continue
            topic_id = question.get("topic_id")
            if not topic_id:
                continue
            result = feedback.get(question.get("question_id"), {})
            bucket = per_topic.setdefault(str(topic_id), {
                "title": question.get("topic_title", "Unit topic"), "correct": 0, "total": 0,
            })
            bucket["total"] += 1
            bucket["correct"] += int(bool(result.get("correct")))
        weak_topic_scores = []
        for bucket in per_topic.values():
            if bucket["total"]:
                mastery = bucket["correct"] / bucket["total"] * 100
                if mastery < 60:
                    weak_topic_scores.append(mastery)
                    evidence["conceptual"].append({
                        "course": course_names.get(attempt.get("course_id"), "Course"),
                        "issue": f"Formative assessment: {bucket['title']}",
                        "severity": "high" if mastery < 40 else "medium",
                        "source": "Formative unit assessment",
                        "details": f"Latest topic mastery: {mastery:.1f}% (mastery threshold: 60%).",
                    })
        # If per-topic feedback is unavailable in an older record, use its
        # overall formative score as a single fallback signal.
        if not per_topic and isinstance(attempt.get("score"), (int, float)) and attempt["score"] < 60:
            weak_topic_scores.append(float(attempt["score"]))
            evidence["conceptual"].append({
                "course": course_names.get(attempt.get("course_id"), "Course"),
                "issue": "Formative unit assessment below mastery threshold",
                "severity": "high" if attempt["score"] < 40 else "medium",
                "source": "Formative unit assessment",
                "details": f"Latest formative unit assessment: {attempt['score']:.1f}%.",
            })
        conceptual_risk_values.extend(
            [max(0.0, min(100.0, (60.0 - score) * 1.5)) for score in weak_topic_scores]
        )

    # Weekly cross-course assessments also contribute to conceptual understanding.
    # Avoid double-counting topics already represented by the latest unit assessment.
    unit_topic_keys = set()
    for attempt in latest_by_unit.values():
        for question in attempt.get("questions", []):
            if question.get("topic_id"):
                unit_topic_keys.add((str(attempt.get("course_id")), str(question["topic_id"])))

    weekly_results = list(db["weekly_assessments"].find({
        "student_id": student_id, "status": "submitted",
    }, {"_id": 0, "topic_results": 1, "submitted_at": 1}).sort("submitted_at", -1))
    latest_weekly_topic: dict[tuple[str, str], dict[str, Any]] = {}
    for attempt in weekly_results:
        for result in attempt.get("topic_results", []):
            key = (str(result.get("course_id")), str(result.get("topic_id")))
            if key[0] in course_ids and key not in latest_weekly_topic and key not in unit_topic_keys:
                latest_weekly_topic[key] = result

    for (course_id, _topic_id), result in latest_weekly_topic.items():
        mastery = float(result.get("score", 0))
        if mastery < 60:
            conceptual_risk_values.append(max(0.0, min(100.0, (60.0 - mastery) * 1.5)))
            evidence["conceptual"].append({
                "course": course_names.get(course_id, "Course"),
                "issue": f"Weekly formative assessment: {result.get('topic_title', 'Topic')}",
                "severity": "high" if mastery < 40 else "medium",
                "source": "Weekly formative assessment",
                "details": f"Latest topic mastery: {mastery:.1f}% (mastery threshold: 60%).",
            })

    conceptual_score = min(100.0, sum(conceptual_risk_values))
    conceptual_available = bool(profiles or alerts or unit_results or weekly_results)

    # 2) Formal academic performance: assessment-by-assessment analysis.
    # Preserve the weighted final evaluation as one signal, but analyse each
    # assessment independently against the same-assessment cohort average.
    user_identity = db["users"].find_one(
        {"$or": [{"user_id": student_id}, {"roll_number": student_id}]},
        {"_id": 0, "user_id": 1, "roll_number": 1},
    ) or {}
    student_identifiers = list(dict.fromkeys(
        value for value in [student_id, user_identity.get("user_id"), user_identity.get("roll_number")]
        if value
    ))
    evaluations = list(db["academic_evaluation_results"].find({
        "student_id": {"$in": student_identifiers}, "course_id": {"$in": course_ids}, "is_complete": True,
    }, {"_id": 0, "course_id": 1, "weighted_percentage": 1,
        "pass_status": 1, "evaluated_at": 1}))
    academic_values = []
    academic_assessment_details = []
    assessment_risk_scores = []
    for item in evaluations:
        score = item.get("weighted_percentage")
        if isinstance(score, (int, float)):
            academic_values.append(float(score))
            if item.get("pass_status") == "fail" or score < 40:
                evidence["academic"].append({
                    "course": course_names.get(item.get("course_id"), "Course"),
                    "issue": "Below passing threshold", "severity": "high",
                    "source": "Formal academic evaluation",
                    "details": f"Latest complete weighted result: {score:.1f}%.",
                })
            elif score < 55:
                evidence["academic"].append({
                    "course": course_names.get(item.get("course_id"), "Course"),
                    "issue": "Low overall academic performance", "severity": "medium",
                    "source": "Formal academic evaluation",
                    "details": f"Latest complete weighted result: {score:.1f}%.",
                })

    for course_id in course_ids:
        enrolled_rows = list(db["course_enrollments"].find(
            {"course_id": course_id, "status": "active"},
            {"_id": 0, "student_id": 1},
        ))
        enrolled_ids = [str(row.get("student_id")) for row in enrolled_rows if row.get("student_id")]
        enrolled_users = list(db["users"].find(
            {"$or": [{"user_id": {"$in": enrolled_ids}}, {"roll_number": {"$in": enrolled_ids}}]},
            {"_id": 0, "user_id": 1, "roll_number": 1},
        )) if enrolled_ids else []
        cohort_ids = list(dict.fromkeys(
            value for row in enrolled_users for value in [row.get("user_id"), row.get("roll_number")]
            if value
        ))
        cohort_ids = list(dict.fromkeys([*enrolled_ids, *cohort_ids]))
        records = list(db["academic_marks"].find(
            {"course_id": course_id, "student_id": {"$in": cohort_ids}},
            {"_id": 0, "student_id": 1, "assessments": 1}
        )) if cohort_ids else []
        student_record = next((row for row in records if str(row.get("student_id")) in {str(v) for v in student_identifiers}), None)
        if not student_record:
            continue
        policy = db["academic_policies"].find_one({"course_id": course_id}, {"_id": 0}) or {}
        # Assessment history is stored with each marks-register component.
        history = []
        assessments_now = student_record.get("assessments", {}) or {}
        for key, component in assessments_now.items():
            component_history = component.get("history", []) if isinstance(component, dict) else []
            for event in component_history:
                history.append({
                    **event, "assessment_key": key,
                    "maximum_marks": event.get("maximum_marks") or component.get("maximum_marks"),
                })
        # Backfill trend context from older upload snapshots created before
        # per-assessment history was added to the marks register.
        if not history:
            uploads = list(db["academic_marks_uploads"].find(
                {"course_id": course_id, "status": "active"},
                {"_id": 0, "uploaded_at": 1, "rows": 1},
            ).sort("uploaded_at", 1))
            for upload in uploads:
                row = next((item for item in upload.get("rows", [])
                            if str(item.get("student_id")) in {str(v) for v in student_identifiers}), None)
                if not row:
                    continue
                for key, component in (row.get("assessments", {}) or {}).items():
                    if isinstance(component, dict) and component.get("marks") is not None:
                        history.append({
                            "assessment_key": key, "marks": component.get("marks"),
                            "maximum_marks": component.get("maximum_marks"),
                            "recorded_at": upload.get("uploaded_at"),
                        })
        analysis = analyse_assessment_risk(
            student_id=student_id,
            student_record=student_record,
            course_records=records,
            policy=policy,
            history=history,
        )
        if analysis.get("available"):
            assessment_risk_scores.append(float(analysis["score"]))
            academic_assessment_details.append({
                "course_id": course_id,
                "course": course_names.get(course_id, "Course"),
                "score": analysis["score"],
                "high_alert": analysis["high_alert"],
                "poor_assessment_count": analysis.get("poor_assessment_count", 0),
                "assessed_component_count": analysis.get("assessed_component_count", 0),
                "assessments": analysis.get("assessments", []),
            })
            for item_evidence in analysis.get("evidence", []):
                evidence["academic"].append({
                    "course": course_names.get(course_id, "Course"),
                    **item_evidence,
                })

    overall_score = max(0.0, min(100.0, (60 - min(academic_values)) * 2)) if academic_values else 0.0
    if assessment_risk_scores:
        overall_score = max(overall_score, max(assessment_risk_scores))
    academic_score = overall_score

    # 3) Learning progress against the published baseline schedule.
    progress_score = 0.0
    progress_available = False
    for course_id in course_ids:
        plan = db["course_lesson_plans"].find_one({"course_id": course_id, "status": "published"}, {"_id": 0})
        if not plan:
            continue
        topic_rows = [topic for unit in plan.get("units", []) for topic in unit.get("topics", [])]
        if not topic_rows:
            continue
        progress_available = True
        states = list(db["student_topic_progress"].find({
            "student_id": student_id, "course_id": course_id,
        }, {"_id": 0, "topic_id": 1, "status": 1}))
        # Topic coverage is evidence-based: checklist completion OR a weekly/unit
        # assessment attempt counts as covered. Mastery is evaluated separately.
        evidence_rows = list(db["student_topic_evidence"].find({
            "student_id": student_id, "course_id": course_id, "covered": True,
        }, {"_id": 0, "topic_id": 1}))
        covered_ids = {row["topic_id"] for row in states if row.get("status") == "completed"}
        covered_ids.update(row["topic_id"] for row in evidence_rows)
        start = _safe_date(plan.get("start_date"))
        total_weeks = max(1, int(plan.get("semester_weeks", 16)))
        current_week = min(total_weeks, max(1, int(max(0, (now.date() - start).days / 7)) + 1)) if start else 1
        # When a student semester plan exists, progress obligations come only
        # from its required activities. Optional early-study and revision
        # suggestions are never treated as missed syllabus work.
        semester_plan = db["student_semester_plans"].find_one(
            {"student_id": student_id}, {"_id": 0, "weeks": 1}
        )
        if semester_plan and semester_plan.get("weeks"):
            due_topic_ids = {
                activity.get("topic_id")
                for week_row in semester_plan.get("weeks", [])
                if int(week_row.get("week", 0)) <= current_week
                for activity in week_row.get("activities", [])
                if activity.get("course_id") == course_id
                and activity.get("schedule_type", "required") == "required"
            }
            due_topics = [topic for topic in topic_rows if topic.get("topic_id") in due_topic_ids]
        else:
            due_topics = [topic for unit in plan.get("units", [])
                          if int(unit.get("end_week", total_weeks)) <= current_week
                          for topic in unit.get("topics", [])]
        if due_topics:
            completion = sum(1 for topic in due_topics if topic["topic_id"] in covered_ids) / len(due_topics)
            course_risk = (1 - completion) * 100
            progress_score = max(progress_score, course_risk)
            if course_risk >= 25:
                evidence["progress"].append({
                    "course": course_names.get(course_id, "Course"),
                    "issue": "Scheduled topics not yet evidenced as covered",
                    "severity": "high" if course_risk >= 60 else "medium",
                    "details": f"{round(completion * 100)}% of topics scheduled through week {current_week} are supported by checklist or assessment evidence.",
                })

    # 4) Project submission compliance.
    projects = list(db["student_projects"].find({
        "student_id": student_id, "course_id": {"$in": course_ids}, "status": {"$ne": "archived"},
    }, {"_id": 0, "student_project_id": 1, "course_project_id": 1, "course_id": 1, "title": 1}))
    overdue_count = 0
    for project in projects:
        milestones = list(db["project_milestones"].find({
            "course_project_id": project["course_project_id"], "is_deleted": {"$ne": True},
        }, {"_id": 0, "milestone_id": 1, "title": 1, "due_date": 1}))
        for milestone in milestones:
            due = _safe_date(milestone.get("due_date"))
            if not due or due >= now.date():
                continue
            submitted = db["project_submissions"].find_one({
                "student_project_id": project["student_project_id"],
                "milestone_id": milestone["milestone_id"], "submission_type": "progress",
            }, {"_id": 1})
            if not submitted:
                overdue_count += 1
                evidence["project"].append({
                    "course": course_names.get(project.get("course_id"), "Course"),
                    "issue": f"Overdue milestone: {milestone.get('title', 'Project milestone')}",
                    "severity": "high",
                    "details": f"{project.get('title', 'Project')} deadline was {due.isoformat()}.",
                })
    project_score = min(100, overdue_count * 35)

    dimensions = {
        "conceptual": _dimension(conceptual_score, evidence["conceptual"], conceptual_available),
        "progress": _dimension(progress_score, evidence["progress"], progress_available),
        "academic": {
            **_dimension(academic_score, evidence["academic"], bool(evaluations or academic_assessment_details)),
            "assessment_analysis": academic_assessment_details,
        },
        "project": _dimension(project_score, evidence["project"], bool(projects)),
    }
    available_weight = sum(WEIGHTS[key] for key, value in dimensions.items() if value["available"])
    overall = (sum(WEIGHTS[key] * dimensions[key]["score"] for key in WEIGHTS if dimensions[key]["available"]) / available_weight) if available_weight else 0
    affected = [key for key, value in dimensions.items() if value["available"] and value["score"] >= 25]
    if len(affected) >= 3:
        overall = max(overall, 70)
    elif len(affected) >= 2:
        overall = max(overall, 50)
    overall = round(overall, 1)
    level = ("insufficient_data" if not available_weight else
             "critical" if overall >= 75 else "high" if overall >= 50 else "moderate" if overall >= 25 else "low")
    return {
        "student_id": student_id, "risk_score": overall, "risk_level": level,
        "affected_dimensions": len(affected), "affected_areas": affected,
        "dimensions": dimensions,
        "evidence_count": sum(len(value) for value in evidence.values()),
        "recommended_action": (
            "Collect more learning and academic evidence before assigning a risk level." if level == "insufficient_data"
            else "Arrange prompt individual review and agree on a support plan." if level in {"critical", "high"}
            else "Monitor progress and consider targeted support." if level == "moderate"
            else "Continue routine monitoring."
        ),
    }


@router.get("/dashboard")
def risk_dashboard(user: dict = Depends(require_role("professor"))):
    """Aggregate risk across every active course owned by the professor."""
    db = _db()
    courses = list(db["courses"].find(
        {"professor_id": user["user_id"], "status": "active"},
        {"_id": 0, "course_id": 1, "name": 1},
    ))
    course_ids = [course["course_id"] for course in courses]
    if not course_ids:
        return {"students": [], "summary": {"total": 0, "critical": 0, "high": 0, "moderate": 0, "low": 0, "insufficient_data": 0}}
    enrollments = list(db["course_enrollments"].find(
        {"course_id": {"$in": course_ids}, "status": "active"}, {"_id": 0, "student_id": 1}))
    student_ids = list(dict.fromkeys(str(row["student_id"]) for row in enrollments if row.get("student_id")))
    users = list(db["users"].find(
        {"user_id": {"$in": student_ids}, "role": "student"},
        {"_id": 0, "user_id": 1, "roll_number": 1, "email": 1, "display_name": 1, "full_name": 1, "name": 1},
    ))
    identity = {item["user_id"]: item for item in users}
    now = datetime.now(timezone.utc)
    results = []
    for student_id in student_ids:
        risk = _student_risk(student_id, courses, now)
        person = identity.get(student_id, {})
        risk.update({
            "student_name": person.get("display_name") or person.get("full_name") or person.get("name") or person.get("email") or "Student",
            "roll_number": person.get("roll_number"),
        })
        results.append(risk)
    rank = {"critical": 0, "high": 1, "moderate": 2, "low": 3, "insufficient_data": 4}
    results.sort(key=lambda item: (rank[item["risk_level"]], -item["risk_score"], -item["affected_dimensions"]))
    summary = {"total": len(results), **{level: sum(item["risk_level"] == level for item in results) for level in rank}}
    return {
        "students": results, "summary": summary, "courses_analysed": len(courses),
        "generated_at": now.isoformat(),
        "method": "Explainable weighted risk scoring. Conceptual understanding combines Performance Agent diagnoses, persistent misconception alerts and formative unit mastery; academic performance uses formal evaluated marks only. Unavailable dimensions are excluded.",
    }
