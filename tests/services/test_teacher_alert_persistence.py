"""Persistence contract tests for misconception alert lifecycle."""

from backend.app.services import incremental_performance as service


class FakeCollection:
    def __init__(self, document=None):
        self.document = document
        self.updates = []

    def find_one(self, query, projection=None):
        if self.document is None:
            return None
        return dict(self.document)

    def update_one(self, query, update, upsert=False):
        self.updates.append((query, update, upsert))
        if "$set" in update:
            self.document = {**(self.document or {}), **update["$set"]}
        if "$unset" in update and self.document:
            for key in update["$unset"]:
                self.document.pop(key, None)
        return None


class FakeDatabase(dict):
    def __getitem__(self, name):
        return dict.__getitem__(self, name)


def _performance(state):
    return {
        "diagnosis": {
            "confidence": "high",
            "concepts": [{
                "concept": "Planning",
                "understanding": state,
                "proposed_understanding": state,
                "evidence": ["The student explains planning accurately and applies it to a new example."],
                "misconceptions": [],
            }],
        }
    }


def _persist(monkeypatch, alert_document, state):
    alerts = FakeCollection(alert_document)
    evidence = FakeCollection()
    profiles = FakeCollection()
    db = FakeDatabase(
        teacher_alerts=alerts,
        interaction_evidence=evidence,
        student_learning_profiles=profiles,
    )
    monkeypatch.setattr(service, "_db", lambda: db)
    service._persist_success(
        student_id="student-1",
        course_id="course-1",
        professor_id="professor-1",
        batch_id="batch-1",
        interactions=[{"_id": "interaction-1", "session_id": "session-2"}],
        performance=_performance(state),
        intervention=None,
        previous_profile={"concepts": {"planning": {"current_state": "confused"}}},
    )
    return alerts


def test_persisting_understanding_resolves_existing_alert_and_keeps_evidence(monkeypatch):
    alerts = _persist(
        monkeypatch,
        {
            "student_id": "student-1",
            "course_id": "course-1",
            "concept_key": "planning",
            "alert_type": "persistent_misconception",
            "status": "open",
        },
        "understood",
    )

    alert_updates = [update for _, update, _ in alerts.updates]
    resolution = next(update["$set"] for update in alert_updates if update.get("$set", {}).get("status") == "resolved")

    assert resolution["status"] == "resolved"
    assert resolution["resolution_evidence"]
    assert resolution["resolved_at"] is not None
    assert "resolution_reason" in resolution


def test_persisting_returning_misconception_reopens_resolved_alert(monkeypatch):
    alerts = _persist(
        monkeypatch,
        {
            "student_id": "student-1",
            "course_id": "course-1",
            "concept_key": "planning",
            "alert_type": "persistent_misconception",
            "status": "resolved",
            "resolved_at": "previous-resolution",
            "resolution_evidence": ["Earlier correct explanation."],
        },
        "confused",
    )

    alert_updates = [update for _, update, _ in alerts.updates]
    reopening = next(update for update in alert_updates if update.get("$set", {}).get("status") == "open")

    assert reopening["$set"]["status"] == "open"
    assert reopening["$unset"] == {
        "resolved_at": "",
        "resolution_evidence": "",
        "resolution_reason": "",
    }
