
import json

from backend.app.agents import intervention_agent as intervention_module
from backend.app.agents.intervention_agent import InterventionAgent


def test_persistent_misconception_gets_targeted_intervention(monkeypatch):
    agent = InterventionAgent()
    captured_prompts = []

    performance_result = {
        "student_id": "23bcs030",
        "subject_id": "agentic_ai",
        "diagnosis": {
            "concepts": [
                {
                    "concept": "Planning",
                    "understanding": "confused",
                    "evidence": [
                        "Planning means remembering previous information.",
                        "Planning is just storing information for later.",
                        "Planning and memory do the same thing.",
                    ],
                    "misconceptions": [
                        "The student confuses planning with memory."
                    ],
                }
            ],
            "strengths": [],
            "weaknesses": [
                "The student repeatedly confuses planning with memory."
            ],
        },
        "evidence_interpretation": {
            "evidence_analysis": [
                {
                    "student_statement": (
                        "Planning means remembering previous information."
                    ),
                    "central_claim": (
                        "The student treats planning and memory as the same process."
                    ),
                    "classification": "conflict",
                    "reason": (
                        "The course distinguishes planning actions from retaining information."
                    ),
                },
                {
                    "student_statement": (
                        "Planning is just storing information for later."
                    ),
                    "central_claim": (
                        "The student continues to conflate planning and memory."
                    ),
                    "classification": "conflict",
                    "reason": (
                        "The misconception appears in multiple statements."
                    ),
                },
            ]
        },
    }

    mock_response = {
        "student_id": "23bcs030",
        "subject_id": "agentic_ai",
        "intervention": {
            "priority": "high",
            "objective": (
                "Help the student distinguish planning from memory."
            ),
            "explanation": (
                "Planning determines steps toward a goal, whereas memory "
                "retains information from previous interactions."
            ),
            "activity": (
                "Ask the student to demonstrate planning by listing the "
                "steps needed to achieve a simple goal. Then explain how "
                "planning differs from memory: planning selects steps "
                "toward a goal, while memory retains information from "
                "previous interactions."
            ),
            "follow_up_question": (
                "How is deciding the next step toward a goal different "
                "from remembering information from the past?"
            ),
            "success_criteria": (
                "The student explains the difference and provides one "
                "appropriate example of each concept."
            ),
        },
        "teacher_insight": {
            "observed_learning_state": (
                "Repeated confusion between planning and memory is present "
                "in the supplied diagnostic evidence."
            ),
            "evidence_summary": (
                "Multiple student statements equate planning with storing "
                "or remembering information."
            ),
            "recommended_teaching_action": (
                "Explicitly contrast planning and memory using a worked "
                "example, then ask the student to classify each process."
            ),
            "next_step": (
                "Review the student's explanation and update the diagnosis "
                "based on the follow-up evidence."
            ),
        },
    }

    def fake_generate(prompt):
        captured_prompts.append(prompt)
        return json.dumps(mock_response)

    monkeypatch.setattr(intervention_module, "generate", fake_generate)

    result = agent.analyze(
        performance_result=performance_result,
        course_context=(
            "Planning determines steps toward a goal. "
            "Memory retains information from previous interactions."
        ),
    )

    intervention = result["intervention"]
    teacher_insight = result["teacher_insight"]

    assert result["student_id"] == "23bcs030"
    assert result["subject_id"] == "agentic_ai"

    assert intervention["objective"].strip()
    assert intervention["activity"].strip()
    assert intervention["follow_up_question"].strip()
    assert intervention["success_criteria"].strip()

    # Recommendations should target the reported misconception.
    assert "planning" in intervention["objective"].lower()
    assert "memory" in intervention["objective"].lower()
    assert "planning" in intervention["activity"].lower()
    assert "memory" in intervention["activity"].lower()

    # Teacher insight should be evidence-based and actionable.
    assert "multiple student statements" in (
        teacher_insight["evidence_summary"].lower()
    )
    assert teacher_insight["recommended_teaching_action"].strip()
    assert teacher_insight["next_step"].strip()

    # Verify that the diagnosis and evidence reach the LLM prompt.
    assert len(captured_prompts) == 1
    assert "The student confuses planning with memory." in captured_prompts[0]
    assert "classification" in captured_prompts[0]

    print("PASS: Persistent misconception gets targeted intervention")


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
