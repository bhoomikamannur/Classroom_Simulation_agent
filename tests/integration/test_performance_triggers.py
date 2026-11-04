"""Trigger contract tests: triggers differ, analysis implementation does not."""

from datetime import datetime, timedelta, timezone

from backend.app.services import incremental_performance as service
from backend.app.api import tutor


def _args():
    return {
        "student_id": "student-1",
        "course_id": "course-1",
        "course_name": "Agentic AI",
        "professor_id": "professor-1",
    }


def test_manual_drain_forces_below_threshold_and_uses_shared_batch_processor(monkeypatch):
    calls = []
    outcomes = iter([
        {"status": "completed", "processed_responses": 10, "pending_count": 2,
         "performance": {"batch": 1}, "intervention": None},
        {"status": "completed", "processed_responses": 2, "pending_count": 0,
         "performance": {"batch": 2}, "intervention": {"activity": "practice"}},
    ])

    def fake_process_pending_analysis(**kwargs):
        calls.append(kwargs)
        return next(outcomes)

    monkeypatch.setattr(service, "process_pending_analysis", fake_process_pending_analysis)

    result = service.process_all_pending_analysis(**_args(), force=True)

    assert len(calls) == 2
    assert all(call["force"] is True for call in calls)
    assert result["status"] == "completed"
    assert result["processed_responses"] == 12
    assert result["performance"] == {"batch": 2}
    assert result["intervention"] == {"activity": "practice"}
    assert len(result["batch_results"]) == 2


def test_manual_drain_stops_after_retryable_failure(monkeypatch):
    calls = []

    def fake_process_pending_analysis(**kwargs):
        calls.append(kwargs)
        return {"status": "failed_retry_pending", "pending_count": 10, "error": "temporary"}

    monkeypatch.setattr(service, "process_pending_analysis", fake_process_pending_analysis)

    result = service.process_all_pending_analysis(**_args(), force=True)

    assert len(calls) == 1
    assert result["status"] == "failed_retry_pending"
    assert result["error"] == "temporary"


def test_manual_drain_obeys_batch_safety_limit(monkeypatch):
    calls = []

    def fake_process_pending_analysis(**kwargs):
        calls.append(kwargs)
        return {"status": "completed", "processed_responses": 10, "pending_count": 10}

    monkeypatch.setattr(service, "process_pending_analysis", fake_process_pending_analysis)

    result = service.process_all_pending_analysis(**_args(), force=True, max_batches=2)

    assert len(calls) == 2
    assert result["status"] == "batch_limit_reached"
    assert result["processed_responses"] == 20


def test_automatic_trigger_uses_same_pending_batch_processor(monkeypatch):
    status_values = iter([
        {"pending_meaningful_responses": service.ANALYSIS_THRESHOLD},
        {"pending_meaningful_responses": 0},
    ])
    calls = []

    monkeypatch.setattr(service, "get_analysis_status", lambda *args: next(status_values))

    def fake_process_pending_analysis(**kwargs):
        calls.append(kwargs)
        return {"status": "completed", "pending_count": 0}

    monkeypatch.setattr(service, "process_pending_analysis", fake_process_pending_analysis)

    tutor._run_activity_trigger(**_args())

    assert len(calls) == 1
    assert calls[0] == _args()
    # The automatic trigger delegates to the same core function that the
    # manual drain wrapper calls; only its threshold/force policy differs.
    assert service.process_pending_analysis is fake_process_pending_analysis


def test_automatic_trigger_does_not_run_below_threshold(monkeypatch):
    calls = []
    monkeypatch.setattr(
        service,
        "get_analysis_status",
        lambda *args: {"pending_meaningful_responses": service.ANALYSIS_THRESHOLD - 1},
    )
    monkeypatch.setattr(service, "process_pending_analysis", lambda **kwargs: calls.append(kwargs))

    tutor._run_activity_trigger(**_args())

    assert calls == []


def test_automatic_trigger_is_bounded_to_three_batches(monkeypatch):
    calls = []
    monkeypatch.setattr(
        service,
        "get_analysis_status",
        lambda *args: {"pending_meaningful_responses": service.ANALYSIS_THRESHOLD},
    )

    def fake_process_pending_analysis(**kwargs):
        calls.append(kwargs)
        return {"status": "completed", "pending_count": service.ANALYSIS_THRESHOLD}

    monkeypatch.setattr(service, "process_pending_analysis", fake_process_pending_analysis)
    tutor._run_activity_trigger(**_args())

    assert len(calls) == 3


class _Cursor(list):
    def limit(self, count):
        return _Cursor(self[:count])


class _StateCollection:
    def __init__(self, states):
        self.states = states
        self.query = None

    def find(self, query, projection=None):
        self.query = query
        return _Cursor(self.states)


def test_periodic_sweep_delegates_due_queues_to_shared_manual_drain(monkeypatch):
    states = [
        {"student_id": "student-1", "course_id": "course-1", "professor_id": "professor-1"},
        {"student_id": "student-2", "course_id": "course-2", "professor_id": "professor-2",
         "retry_after": datetime.now(timezone.utc) + timedelta(hours=1)},
        {"student_id": "student-3", "course_id": "course-3"},
    ]
    state_collection = _StateCollection(states)
    monkeypatch.setattr(service, "_db", lambda: {"learning_analysis_state": state_collection})
    monkeypatch.setattr(service, "ensure_incremental_indexes", lambda: None)
    monkeypatch.setattr(service, "_now", lambda: datetime.now(timezone.utc))
    calls = []

    def fake_process_all_pending_analysis(**kwargs):
        calls.append(kwargs)
        return {"status": "completed"}

    monkeypatch.setattr(service, "process_all_pending_analysis", fake_process_all_pending_analysis)

    result = service.run_periodic_analysis_sweep(
        course_name_resolver=lambda course_id: f"Course {course_id}",
        limit=20,
    )

    assert result["checked"] == 3
    assert len(calls) == 1
    assert calls[0]["student_id"] == "student-1"
    assert calls[0]["course_name"] == "Course course-1"
    # Omitting force intentionally exercises process_all_pending_analysis'
    # default of False. Do not require the caller to pass the default explicitly.
    assert calls[0].get("force", False) is False
