
import json

from backend.app.agents import intervention_agent as intervention_module
from backend.app.agents.intervention_agent import InterventionAgent


def test_insufficient_evidence_recommends_more_evidence(monkeypatch):
    agent = InterventionAgent()
    captured_prompts = []

    performance_result = {
        "student_id": "23bcs030",
        "subject_id": "agentic_ai",
        "diagnosis": {
            "concepts": [
                {
                    "concept": "Planning",
                    "understanding": "insufficient_evidence",
                    "evidence": [],
                    "misconceptions": [],
                }
            ],
            "strengths": [],
            "weaknesses": [],
        },
        "evidence_interpretation": {
            "evidence_analysis": [
                {
                    "student_statement": "",
                    "central_claim": "",
                    "classification": "uncertain",
                    "reason": "Insufficient student evidence to assess understanding.",
                }
            ]
        },
    }

    mock_response = {
        "student_id": "23bcs030",
        "subject_id": "agentic_ai",
        "intervention": {
            "priority": "low",
            "objective": "Gather enough evidence to assess understanding of planning.",
            "explanation": "There is not enough evidence to determine the student's understanding.",
            "activity": "Ask the student to explain how they would plan steps to achieve a simple goal.",
            "follow_up_question": "How would you decide which steps are needed to achieve a goal?",
            "success_criteria": "The student provides an explanation that can be assessed against the course material.",
        },
        "teacher_insight": {
            "observed_learning_state": "Insufficient evidence to determine understanding.",
            "evidence_summary": "No substantive student response is available for this concept.",
            "recommended_teaching_action": "Ask a targeted question before deciding whether remediation is needed.",
            "next_step": "Review the student's response and update the diagnosis.",
        },
    }

    def fake_generate(prompt):
        captured_prompts.append(prompt)
        return json.dumps(mock_response)

    monkeypatch.setattr(intervention_module, "generate", fake_generate)

    result = agent.analyze(performance_result)

    # The agent must preserve the input identity.
    assert result["student_id"] == "23bcs030"
    assert result["subject_id"] == "agentic_ai"

    intervention = result["intervention"]
    teacher_insight = result["teacher_insight"]

    # Recommendations must contain actionable content.
    assert intervention["objective"].strip()
    assert intervention["activity"].strip()
    assert intervention["follow_up_question"].strip()
    assert intervention["success_criteria"].strip()

    # The intended action is to gather evidence, not assume a misconception.
    assert "gather" in intervention["objective"].lower()
    assert "not enough evidence" in intervention["explanation"].lower()
    assert "ask" in teacher_insight["recommended_teaching_action"].lower()

    # Confirm that the actual diagnosis reached the LLM prompt.
    assert len(captured_prompts) == 1
    assert "insufficient_evidence" in captured_prompts[0]
    assert "Do not independently diagnose the student" in captured_prompts[0]
    assert "If evidence is insufficient" in captured_prompts[0]

    print("PASS: Insufficient-evidence scenario")


if __name__ == "__main__":
    test_insufficient_evidence_recommends_more_evidence(
        __import__("pytest").MonkeyPatch()
    )
