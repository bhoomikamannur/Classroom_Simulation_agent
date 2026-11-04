from backend.app.api import performance_intervention as api

class FakeCollection:
    def find_one(self, query, projection=None):
        return {"_id": "enrollment-1"}

class FakeDatabase(dict):
    def __getitem__(self, key):
        return FakeCollection()

def test_performance_intervention_endpoint(professor_client, monkeypatch):
    course = {"course_id": "course-1", "name": "Agentic AI", "professor_id": "test-professor-001"}
    monkeypatch.setattr(api, "get_accessible_course", lambda course_id, user: course)
    monkeypatch.setattr(api, "get_mongodb_database", lambda: FakeDatabase())
    from backend.app.services import incremental_performance
    monkeypatch.setattr(incremental_performance, "process_all_pending_analysis", lambda **kwargs: {
        "status": "completed",
        "performance": {"student_id": "S001", "course_name": "Agentic AI", "diagnosis": {"overall_observation": "Evidence reviewed"}},
        "intervention": {"student_id": "S001", "course_name": "Agentic AI", "intervention": {"activity": "Apply planning"}, "teacher_insight": {"next_step": "Review"}},
    })
    response = professor_client.post("/performance/intervene", json={"student_id": "S001", "course_id": "course-1"})
    assert response.status_code == 200
    result = response.json()
    assert result["performance"]["student_id"] == "S001"
    assert result["intervention"]["course_name"] == "Agentic AI"

def test_performance_intervention_rejects_missing_student_id(professor_client):
    response = professor_client.post("/performance/intervene", json={"course_id": "course-1"})
    assert response.status_code == 422

def test_performance_intervention_rejects_legacy_subject_fields(professor_client):
    response = professor_client.post("/performance/intervene", json={"student_id": "S001", "course_id": "course-1", "subject_id": "agentic_ai"})
    assert response.status_code == 422


def test_student_role_cannot_call_professor_performance_analysis(student_client):
    response = student_client.post(
        "/performance/intervene",
        json={"student_id": "S001", "course_id": "course-1"},
    )
    assert response.status_code == 403


def test_professor_cannot_analyze_course_they_do_not_own(professor_client, monkeypatch):
    from fastapi import HTTPException

    def deny_course_access(course_id, user):
        raise HTTPException(status_code=403, detail="Course access denied.")

    monkeypatch.setattr(api, "get_accessible_course", deny_course_access)
    response = professor_client.post(
        "/performance/intervene",
        json={"student_id": "S001", "course_id": "other-course"},
    )
    assert response.status_code == 403


class _Cursor(list):
    def sort(self, keys):
        rows = list(self)
        for field, direction in reversed(keys):
            rows = sorted(rows, key=lambda item: item.get(field) or "", reverse=direction < 0)
        self[:] = rows
        return self


class _AlertCollection:
    def __init__(self, docs):
        self.docs = docs
        self.updates = []

    def find(self, query, projection=None):
        rows = [dict(doc) for doc in self.docs if all(
            (doc.get(key) in value.get("$in", [])) if isinstance(value, dict) and "$in" in value
            else doc.get(key) == value
            for key, value in query.items()
        )]
        return _Cursor(rows)

    def update_one(self, query, update):
        self.updates.append((query, update))
        doc = next((item for item in self.docs if all(item.get(k) == v for k, v in query.items())), None)
        if doc is None:
            return type("Result", (), {"matched_count": 0})()
        doc.update(update.get("$set", {}))
        return type("Result", (), {"matched_count": 1})()


class _UsersCollection:
    def find(self, query, projection=None):
        ids = query["user_id"]["$in"]
        return [
            {"user_id": "student-1", "roll_number": "23bcs001", "email": "student1@example.com", "display_name": "Student One"}
            for _ in [0] if "student-1" in ids
        ]


class _AlertsDB(dict):
    def __init__(self, alerts):
        super().__init__()
        self["teacher_alerts"] = _AlertCollection(alerts)
        self["users"] = _UsersCollection()


def test_course_alerts_list_includes_student_identity_and_only_open_alerts(professor_client, monkeypatch):
    from bson import ObjectId
    open_id = ObjectId()
    alerts = [
        {"_id": open_id, "student_id": "student-1", "course_id": "course-1",
         "professor_id": "test-professor-001", "status": "open", "priority": "high",
         "alert_type": "persistent_misconception", "concept": "Planning", "message": "Needs support."},
        {"_id": ObjectId(), "student_id": "student-1", "course_id": "course-1",
         "professor_id": "test-professor-001", "status": "closed", "priority": "medium"},
    ]
    monkeypatch.setattr(api, "get_accessible_course", lambda course_id, user: {"course_id": course_id})
    monkeypatch.setattr(api, "get_mongodb_database", lambda: _AlertsDB(alerts))
    response = professor_client.get("/performance/alerts?course_id=course-1")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["alerts"][0]["student_name"] == "Student One"
    assert body["alerts"][0]["roll_number"] == "23bcs001"
    assert body["alerts"][0]["priority"] == "high"


def test_professor_can_acknowledge_without_resolving_alert(professor_client, monkeypatch):
    from bson import ObjectId
    alert_id = ObjectId()
    alert = {"_id": alert_id, "course_id": "course-1", "professor_id": "test-professor-001", "status": "open"}
    db = _AlertsDB([alert])
    monkeypatch.setattr(api, "get_accessible_course", lambda course_id, user: {"course_id": course_id})
    monkeypatch.setattr(api, "get_mongodb_database", lambda: db)
    response = professor_client.post(f"/performance/alerts/{alert_id}/acknowledge?course_id=course-1")
    assert response.status_code == 200
    assert alert["status"] == "open"
    assert alert["acknowledged_by"] == "test-professor-001"
    assert alert["acknowledged_at"] is not None


def test_professor_can_close_alert_without_deleting_history(professor_client, monkeypatch):
    from bson import ObjectId
    alert_id = ObjectId()
    alert = {"_id": alert_id, "course_id": "course-1", "professor_id": "test-professor-001", "status": "open"}
    db = _AlertsDB([alert])
    monkeypatch.setattr(api, "get_accessible_course", lambda course_id, user: {"course_id": course_id})
    monkeypatch.setattr(api, "get_mongodb_database", lambda: db)
    response = professor_client.post(f"/performance/alerts/{alert_id}/close?course_id=course-1")
    assert response.status_code == 200
    assert alert["status"] == "closed"
    assert alert["closed_by"] == "test-professor-001"
    assert alert["closed_at"] is not None
    assert len(db["teacher_alerts"].docs) == 1


def test_student_cannot_list_professor_course_alerts(student_client):
    response = student_client.get("/performance/alerts?course_id=course-1")
    assert response.status_code == 403
