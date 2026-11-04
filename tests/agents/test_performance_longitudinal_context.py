"""The prior profile is context for interpretation, never fresh student evidence."""

import json

from backend.app.agents import performance_agent as performance_module
from backend.app.agents.performance_agent import PerformanceAgent


def test_previous_profile_is_passed_as_longitudinal_context_not_new_evidence(monkeypatch):
    captured = {}

    response = {
        "concept": "Planning",
        "evidence_analysis": [{
            "concept": "Planning",
            "student_statement": "Planning determines actions to reach a goal.",
            "central_claim": "Planning selects actions to reach a goal.",
            "classification": "aligned",
            "reason": "This matches the course reference.",
        }],
    }

    def fake_generate(prompt):
        captured["prompt"] = prompt
        return json.dumps(response)

    monkeypatch.setattr(performance_module, "generate", fake_generate)
    agent = PerformanceAgent()
    prior_profile = {
        "planning": {
            "current_state": "confused",
            "latest_misconceptions": ["Planning is the same as memory."],
        }
    }

    result = agent.analyze(
        student_id="student-1",
        course_name="Agentic AI",
        course_id="course-1",
        interactions=[{
            "role": "user",
            "content": "Planning determines actions to reach a goal.",
        }],
        course_context="Planning selects actions; memory stores information.",
        previous_profile=prior_profile,
    )

    assert result["diagnosis"]["concepts"]
    assert "PREVIOUS CONCEPT PROFILE (LONGITUDINAL CONTEXT ONLY — NOT NEW EVIDENCE)" in captured["prompt"]
    assert '"current_state": "confused"' in captured["prompt"]
    assert "STUDENT EVIDENCE:" in captured["prompt"]
    assert "Planning determines actions to reach a goal." in captured["prompt"]
