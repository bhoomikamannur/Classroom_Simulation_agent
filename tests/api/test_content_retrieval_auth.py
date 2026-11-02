from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.api.auth import get_current_user
from backend.app.api import content, retrieval

COURSE = {"course_id": "course-1", "name": "Agentic AI", "professor_id": "test-professor-001"}

def test_content_agent_allows_student(student_client, monkeypatch):
    monkeypatch.setattr(content, "get_accessible_course", lambda course_id, user: COURSE)
    monkeypatch.setattr(content.orchestrator, "execute", lambda **kwargs: {"answer": "Mock content answer"})
    response = student_client.post("/content/answer", json={"query": "What is an AI agent?", "course_id": "course-1"})
    assert response.status_code == 200
    assert response.json()["answer"] == "Mock content answer"

def test_content_agent_allows_professor(professor_client, monkeypatch):
    monkeypatch.setattr(content, "get_accessible_course", lambda course_id, user: COURSE)
    monkeypatch.setattr(content.orchestrator, "execute", lambda **kwargs: {"answer": "Mock content answer"})
    response = professor_client.post("/content/answer", json={"query": "Explain agent architecture", "course_id": "course-1"})
    assert response.status_code == 200

def test_content_agent_rejects_unauthenticated_user():
    with TestClient(app) as client:
        response = client.post("/content/answer", json={"query": "What is an AI agent?", "course_id": "course-1"})
    assert response.status_code == 401

def test_retrieval_allows_student(student_client, monkeypatch):
    monkeypatch.setattr(retrieval, "get_accessible_course", lambda course_id, user: COURSE)
    monkeypatch.setattr(retrieval, "retrieve", lambda query, course_id, top_k=5: [{"text": "Mock retrieved content"}])
    response = student_client.post("/retrieve", json={"query": "Explain machine learning", "course_id": "course-1"})
    assert response.status_code == 200
    assert len(response.json()["results"]) == 1

def test_retrieval_allows_professor(professor_client, monkeypatch):
    monkeypatch.setattr(retrieval, "get_accessible_course", lambda course_id, user: COURSE)
    monkeypatch.setattr(retrieval, "retrieve", lambda query, course_id, top_k=5: [{"text": "Mock retrieved content"}])
    response = professor_client.post("/retrieve", json={"query": "Explain machine learning", "course_id": "course-1"})
    assert response.status_code == 200

def test_retrieval_rejects_unauthenticated_user():
    with TestClient(app) as client:
        response = client.post("/retrieve", json={"query": "Explain machine learning", "course_id": "course-1"})
    assert response.status_code == 401
