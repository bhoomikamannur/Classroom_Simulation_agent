# Semester-wide Adaptive Planner — Phase 1

## Decisions implemented
- Student declares total available study hours per week (1–80).
- Planner combines published baseline plans from all currently enrolled active courses.
- Professor course plans remain the source of syllabus scope and soft week windows.
- Student semester plan is stored separately in `student_semester_plans`.
- Topics carry estimated effort, difficulty, prerequisites, baseline window, coverage state and mastery evidence.
- Routine workload is scheduled automatically; this phase does not modify professor deadlines or course baseline plans.

## API
- `GET /semester-planner/mine` — retrieve the student's saved semester plan.
- `POST /semester-planner/generate` — build a cross-course plan using `weekly_available_hours`.
- `PATCH /semester-planner/availability` — update weekly hours and recalculate the plan.
- `POST /semester-planner/topics/{topic_id}/complete` — mark a topic complete from the semester planner.

## Evidence and risk semantics
`student_topic_evidence` stores coverage evidence separately from manual checklist state. Manual completion and submitted unit assessment attempts both establish coverage. A poor assessment score does not mean the topic was not covered; it sets a low mastery score and the topic is classified as requiring revision. The risk progress calculation now counts either completed checklist state or coverage evidence, while formative results remain in conceptual understanding.

## UI
A new Semester study plan entry appears on the student's course landing page. It allows the student to declare weekly hours, generate the combined plan, and inspect weekly activities across courses. Unit-level carry-forward/behind/ahead alert boxes were removed from the course learning-plan view; unit assessments themselves remain available.

## Current limitations / next phases
- This is the first working scheduling layer, not the final optimizer. Baseline week ranges are soft preferred windows; overload is surfaced rather than silently dropping topics.
- The current version does not yet collect external deadlines, calendar unavailability, daily time slots, or professor approval workflows. The agreed hybrid control model is the next scheduling enhancement.
- Weekly assessments and adaptive question selection (unseen variants, misconception-related questions, question exposure history) are not implemented in this phase. Existing unit assessments remain.
- Weekly assessment attempts must write `student_topic_evidence` with `coverage_source: weekly_assessment`; the risk and planner logic are ready to consume that evidence once the weekly assessment endpoint is added.
- Topic prerequisites are retained in schedule records but prerequisite-aware optimization is not yet enforced.
- No live MongoDB/Ollama integration test was performed in this environment.
