
import json

from backend.app.agents.intervention_agent import InterventionAgent


agent = InterventionAgent()


SAMPLE_PERFORMANCE_RESULT = {
    "student_id": "23bcs030",
    "subject_id": "agentic_ai",
    "diagnosis": {
        "concepts": [
            {
                "concept": "Planning",
                "understanding": "confused",
                "evidence": [
                    "Planning means remembering previous information."
                ],
                "misconceptions": [
                    "The student confuses planning with memory."
                ],
            }
        ],
        "strengths": [],
        "weaknesses": [
            "The student confuses planning with memory."
        ],
    },
    "evidence_interpretation": {
        "evidence_analysis": [
            {
                "student_statement": (
                    "Planning means remembering previous information."
                ),
                "central_claim": (
                    "The student believes planning means remembering "
                    "previous information."
                ),
                "classification": "conflict",
                "reason": (
                    "Planning and memory are distinct concepts."
                ),
            }
        ]
    },
}


COURSE_CONTEXT = """
Planning determines the actions or steps needed to achieve a goal.
Memory retains information from previous interactions.
"""


def test_intervention_output():
    result = agent.analyze(
        performance_result=SAMPLE_PERFORMANCE_RESULT,
        course_context=COURSE_CONTEXT,
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))

    assert result["student_id"] == "23bcs030"
    assert result["subject_id"] == "agentic_ai"

    intervention = result["intervention"]
    teacher_insight = result["teacher_insight"]

    assert intervention["objective"].strip()
    assert intervention["activity"].strip()
    assert intervention["follow_up_question"].strip()
    assert intervention["success_criteria"].strip()

    assert teacher_insight["evidence_summary"].strip()
    assert teacher_insight["recommended_teaching_action"].strip()

    print("\nIntervention Agent test passed.")


if __name__ == "__main__":
    test_intervention_output()
