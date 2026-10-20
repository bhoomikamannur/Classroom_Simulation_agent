
import json

from backend.app.agents import intervention_agent as intervention_module
from backend.app.agents.intervention_agent import InterventionAgent


def test_student_understands_concept_gets_extension_activity(monkeypatch):
    agent = InterventionAgent()
    captured_prompts = []

    performance_result = {
        "student_id": "23bcs030",
        "subject_id": "agentic_ai",
        "diagnosis": {
            "concepts": [
                {
                    "concept": "Planning",
                    "understanding": "clear",
                    "evidence": [
                        "Planning determines the steps needed to achieve a goal.",
                        "Planning helps an agent decide what to do next.",
                    ],
                    "misconceptions": [],
                }
            ],
            "strengths": [
                "The student accurately explains planning."
            ],
            "weaknesses": [],
        },
        "evidence_interpretation": {
            "evidence_analysis": [
                {
                    "student_statement": (
                        "Planning helps an agent choose steps to achieve its goal."
                    ),
                    "central_claim": (
                        "The student understands the purpose of planning."
                    ),
                    "classification": "aligned",
                    "reason": (
                        "The statement is consistent with the supplied course context."
                    ),
                }
            ]
        },
    }

    mock_response = {
        "student_id": "23bcs030",
        "subject_id": "agentic_ai",
        "intervention": {
            "priority": "low",
            "objective": (
                "Extend the student's understanding by applying planning "
                "to a more complex goal."
            ),
            "explanation": (
                "The student demonstrates understanding, so extension "
                "rather than remedial teaching is appropriate."
            ),
            "activity": (
                "Ask the student to design a multi-step plan for an agent "
                "with a goal and limited resources, and explain how the "
                "plan would change if a constraint changed."
            ),
            "follow_up_question": (
                "If one action in your plan became unavailable, how would "
                "you revise the remaining steps to reach the goal?"
            ),
            "success_criteria": (
                "The student proposes a coherent plan and explains how "
                "the changed constraint affects the selected steps."
            ),
        },
        "teacher_insight": {
            "observed_learning_state": (
                "The supplied evidence indicates clear understanding of planning."
            ),
            "evidence_summary": (
                "The student accurately describes planning as selecting "
                "steps toward a goal."
            ),
            "recommended_teaching_action": (
                "Provide a more challenging application task instead of "
                "repeating introductory explanations."
            ),
            "next_step": (
                "Review the student's solution to the extension task."
            ),
        },
    }

    def fake_generate(prompt):
        captured_prompts.append(prompt)
        return json.dumps(mock_response)

    monkeypatch.setattr(intervention_module, "generate", fake_generate)

    result = agent.analyze(performance_result)

    intervention = result["intervention"]
    teacher_insight = result["teacher_insight"]

    assert result["student_id"] == "23bcs030"
    assert result["subject_id"] == "agentic_ai"

    assert intervention["priority"] == "low"
    assert intervention["objective"].strip()
    assert intervention["activity"].strip()
    assert intervention["follow_up_question"].strip()
    assert intervention["success_criteria"].strip()

    # The activity should extend understanding, not remediate a nonexistent weakness.
    assert "extend" in intervention["objective"].lower()
    assert "more challenging" in teacher_insight["recommended_teaching_action"].lower()

    # Teacher insight should reflect the supplied evidence.
    assert "clear understanding" in (
        teacher_insight["observed_learning_state"].lower()
    )
    assert teacher_insight["next_step"].strip()

    # Confirm that the actual diagnosis reaches the generation prompt.
    assert len(captured_prompts) == 1
    assert '"understanding": "clear"' in captured_prompts[0]
    assert "extension or application activity" in captured_prompts[0]

    print("PASS: Student understanding leads to an extension activity")


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
