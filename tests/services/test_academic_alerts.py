from backend.app.services import academic_alerts


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = list(docs or [])
        self.updates = []

    def update_one(self, query, update, upsert=False):
        self.updates.append((query, update, upsert))
        doc = next((d for d in self.docs if all(d.get(k) == v for k, v in query.items())), None)
        if doc is None and upsert:
            doc = dict(query)
            self.docs.append(doc)
        if doc is not None:
            doc.update(update.get("$set", {}))
            for key in update.get("$unset", {}):
                doc.pop(key, None)

    def find(self, query):
        return [d for d in self.docs if all(d.get(k) == v for k, v in query.items())]

    def find_one(self, query):
        return next((d for d in self.docs if all(d.get(k) == v for k, v in query.items())), None)

    def insert_one(self, doc):
        self.docs.append(dict(doc))


class FakeDB(dict):
    pass


def _db(monkeypatch, alerts=None):
    db = FakeDB(
        academic_evaluation_results=FakeCollection(),
        teacher_alerts=FakeCollection(alerts),
    )
    monkeypatch.setattr(academic_alerts, "get_mongodb_database", lambda: db)
    return db


def test_complete_failing_result_opens_academic_review_alert(monkeypatch):
    db = _db(monkeypatch)
    result = academic_alerts.persist_evaluation_and_update_alerts(
        "course-1", "prof-1",
        [{"student_id": "student-1", "weighted_percentage": 32,
          "pass_status": "fail", "is_complete": True, "missing_assessments": []}],
        40,
    )
    alert = db["teacher_alerts"].docs[0]
    assert result["saved_results"] == 1
    assert alert["alert_type"] == "academic_review"
    assert alert["priority"] == "medium"
    assert alert["status"] == "open"


def test_poor_academics_raise_persistent_learning_alert_to_high(monkeypatch):
    db = _db(monkeypatch, [{
        "_id": "alert-1", "student_id": "student-1", "course_id": "course-1",
        "alert_type": "persistent_misconception", "status": "open",
        "message": "Persistent difficulty with planning.",
    }])
    academic_alerts.persist_evaluation_and_update_alerts(
        "course-1", "prof-1",
        [{"student_id": "student-1", "weighted_percentage": 30,
          "pass_status": "fail", "is_complete": True, "missing_assessments": []}],
        40,
    )
    assert db["teacher_alerts"].docs[0]["priority"] == "high"


def test_provisional_result_does_not_open_academic_failure_alert(monkeypatch):
    db = _db(monkeypatch)
    academic_alerts.persist_evaluation_and_update_alerts(
        "course-1", "prof-1",
        [{"student_id": "student-1", "weighted_percentage": 80,
          "pass_status": "provisional", "is_complete": False,
          "missing_assessments": ["exam"]}],
        40,
    )
    assert db["teacher_alerts"].docs == []
    saved = db["academic_evaluation_results"].docs[0]
    assert saved["pass_status"] == "provisional"
    assert saved["is_complete"] is False


def test_later_complete_pass_resolves_academic_review_alert(monkeypatch):
    db = _db(monkeypatch, [{
        "student_id": "student-1", "course_id": "course-1",
        "concept_key": "__academic_performance__",
        "alert_type": "academic_review", "status": "open",
    }])
    result = academic_alerts.persist_evaluation_and_update_alerts(
        "course-1", "prof-1",
        [{"student_id": "student-1", "weighted_percentage": 65,
          "pass_status": "pass", "is_complete": True, "missing_assessments": []}],
        40,
    )
    assert result["alerts_resolved"] == 1
    assert db["teacher_alerts"].docs[0]["status"] == "resolved"
