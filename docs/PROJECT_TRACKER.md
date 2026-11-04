# Project Tracker

Project Tracker is an additive feature of the existing Classroom Simulation Agent. It reuses the existing authenticated users, course records, active `course_enrollments`, MongoDB connection, FastAPI application, React dashboard shell, and the existing Ollama LLM configuration.

## Course-level publishing and individual workspaces

A professor creates one `course_projects` record from a course workspace. Publishing snapshots the currently active class roster into individual `student_projects` records. The `GET /project-tracker/mine` and professor course-project listing endpoints also synchronize newly enrolled active students into already-published projects. Student IDs and course IDs are reused from the existing core records.

## Main workflows

- Professor: publish a course project, optionally upload a PDF brief, add/edit/soft-delete shared milestones, inspect each student's workspace, view submitted files, run AI analysis, and record a review decision.
- Student: open **My Projects** from the dashboard or a prominent course-page project widget, view all assigned projects, submit/revise a proposal, upload milestone progress and evidence, and read professor feedback and agent observations.
- Each student's proposal, submissions, reviews, analysis, and activity remain isolated by `student_project_id`. Repeated proposal uploads and repeated uploads for the same checkpoint receive incrementing version numbers; prior submission records are retained.

## Project Analysis Agent

`backend/app/agents/project_analysis_agent.py` compares the latest proposal submission with a progress submission using the existing `backend.app.llm.ollama_client.generate` client. It extracts text from PDF, PPTX, DOCX and text/code formats. Image evidence is recorded as an evidence limitation because OCR/vision is not configured; ZIP contents are not unpacked or executed. The agent now compares the professor-published course scope, the latest professor-approved student proposal, the selected checkpoint requirements, and the student's chronological prior professor review history. Previously approved scope changes are supplied as context so they are not repeatedly flagged as unapproved deviations. Structured JSON includes an overall status (aligned/minor deviation/major deviation/needs review), aligned work, additions, deviations, incomplete objectives, feedback addressed/unresolved, concerns, evidence limitations, recommendations and confidence. The result remains advisory; the professor makes the decision.

Professor-only API:

`POST /api/project-tracker/submissions/{submission_id}/analysis`

The report is persisted in `project_analyses` and attached to the corresponding submission. It is advisory and does not approve work or assign marks. The professor must make the final decision.

## Run

Use the existing backend setup and configure `MONGODB_URI` and the existing Ollama settings (`OLLAMA_URL`, `OLLAMA_MODEL_NAME`, and timeout values) in `backend/.env`. The analysis endpoint requires the configured Ollama service/model to be reachable. Existing file upload limits and authenticated file access apply.

## Important validation notes

- Run backend tests from the repository root with `PYTHONPATH=.` and installed `backend/requirements.txt` dependencies.
- Run frontend `npm install`, `npm run build`, and `npm run lint` in `frontend`.
- Live workflow validation requires the project's MongoDB database and configured Ollama model.


## Frontend structure and workspace navigation (v2 follow-up)

The frontend entry points are separated under `frontend/src/components/project-tracker/`:
- `professor/ProfessorProjectTracker.tsx`
- `student/StudentProjectTracker.tsx`
- `shared/ProjectTrackerCore.tsx`

Professor project management now uses a student selector rather than rendering the full roster as a long list. The selected student's individual workspace is shown directly below the selector, with submissions, analysis and review actions. Student My Projects is available from the student dashboard and from the student learning sidebar; the Project Tracker view retains that sidebar.


## Checkpoint management and current scope

Professors can create, edit and soft-delete class checkpoints. Soft deletion preserves the checkpoint identifier referenced by existing student submissions; deleted checkpoints are hidden from active student checkpoint lists. The professor's project workspace loads the active checkpoint list and each selected student's submission and review history. Editing/deleting checkpoints is recorded in project activity.

In-app/email notifications are intentionally deferred for this phase. Students see the current checkpoint details when their project workspace is refreshed/reloaded.

## Project Analysis Agent test strategy

- Deterministic contract/scenario tests: `tests/agents/test_project_analysis_agent.py` (mocked LLM; extraction, structured output, prior-feedback/checkpoint context and 12 scenario classifications).
- Optional configured-model tests: `tests/agents/test_project_analysis_agent_live.py`.
- Run deterministic tests from repository root: `python -m pytest tests/agents/test_project_analysis_agent.py -q`.
- Run live Ollama tests: set `RUN_PROJECT_AGENT_LIVE=1` and configure the existing Ollama environment variables, then run `python -m pytest tests/agents/test_project_analysis_agent_live.py -q`.

The deterministic tests validate prompt context and response contracts; only the optional live tests exercise the actual model's reasoning. Image OCR/vision is not configured, so image-only evidence is sent to professor review rather than being classified as aligned.
