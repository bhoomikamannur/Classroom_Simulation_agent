from fastapi.testclient import TestClient
from backend.app.main import app
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
    monkeypatch.setattr(api.orchestrator, "execute", lambda **kwargs: {
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
