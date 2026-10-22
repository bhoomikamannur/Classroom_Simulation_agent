
import json

from fastapi.testclient import TestClient

import backend.app.agents.performance_agent as performance_module
import backend.app.agents.intervention_agent as intervention_module

from backend.app.main import app


client = TestClient(app)


def test_performance_intervention_endpoint(monkeypatch):
    performance_response = {
        "concept": "Planning",
        "evidence_analysis": [
            {
                "student_statement": (
                    "Planning means breaking a goal into smaller steps."
                ),
                "central_claim": (
                    "Planning determines the steps needed to achieve a goal."
                ),
                "classification": "aligned",
                "reason": "Matches the course definition.",
            }
        ],
    }

    intervention_response = {
        "student_id": "S001",
        "subject_id": "agentic_ai",
        "intervention": {
            "priority": "low",
            "objective": "Strengthen understanding of planning.",
            "explanation": "The student's statement aligns with the course.",
            "activity": "Break a goal into smaller actions.",
            "follow_up_question": "How would you plan a new task?",
            "success_criteria": "Identifies a sensible sequence of actions.",
        },
        "teacher_insight": {
            "observed_learning_state": "understood",
            "evidence_summary": "The student describes planning correctly.",
            "recommended_teaching_action": "Provide an application activity.",
            "next_step": "Check application to a new example.",
        },
    }

    def fake_performance_generate(*args, **kwargs):
        return json.dumps(performance_response)

    def fake_intervention_generate(*args, **kwargs):
        return json.dumps(intervention_response)

    monkeypatch.setattr(
        performance_module, "generate", fake_performance_generate
    )
    monkeypatch.setattr(
        intervention_module, "generate", fake_intervention_generate
    )

    response = client.post(
        "/performance/intervene",
        json={
            "student_id": "S001",
            "subject_id": "agentic_ai",
            "interactions": [
                {
                    "role": "user",
                    "content": (
                        "Planning means breaking a high-level goal "
                        "into smaller steps."
                    ),
                }
            ],
            "course_context": (
                "Planning involves breaking a high-level goal "
                "into a sequence of actions or subgoals."
            ),
        },
    )

    assert response.status_code == 200

    result = response.json()
    assert result["performance"]["student_id"] == "S001"
    assert result["intervention"]["student_id"] == "S001"
    assert result["intervention"]["subject_id"] == "agentic_ai"
    assert result["intervention"]["intervention"]["activity"]
    assert result["intervention"]["teacher_insight"]["next_step"]


def test_performance_intervention_rejects_missing_student_id():
    response = client.post(
        "/performance/intervene",
        json={
            "subject_id": "agentic_ai",
            "interactions": [
                {"role": "user", "content": "Planning breaks goals into steps."}
            ],
        },
    )

    assert response.status_code == 422
