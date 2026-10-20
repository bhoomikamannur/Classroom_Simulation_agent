
from backend.app.agents.intervention_agent import InterventionAgent


agent = InterventionAgent()


# Simulated Performance Agent output:
# The student initially confused planning with memory,
# but their latest response shows partial understanding.

SAMPLE_PERFORMANCE_RESULT = {
    "student_id": "23bcs030",
    "subject_id": "agentic_ai",
    "diagnosis": {
        "concepts": [
            {
                "concept": "Planning",
                "understanding": "partial",
                "evidence": [
                    "Planning means remembering previous information.",
                    (
                        "Planning decides what steps to take, while "
                        "memory stores information from previous interactions."
                    ),
                ],
                "misconceptions": [
                    "The student initially confused planning with memory."
                ],
            }
        ],
        "strengths": [
            "The latest response distinguishes planning from memory."
        ],
        "weaknesses": [
            "The student may need further practice applying the distinction."
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
                "reason": "Planning is being confused with memory.",
            },
            {
                "student_statement": (
                    "Planning decides what steps to take, while memory "
                    "stores information from previous interactions."
                ),
                "central_claim": (
                    "The student distinguishes planning from memory."
                ),
                "classification": "aligned",
                "reason": (
                    "The latest response correctly distinguishes "
                    "the two concepts."
                ),
            },
        ]
    },
}


COURSE_CONTEXT = """
Planning determines the actions or sequence of steps needed to achieve a goal.
Memory retains information from previous interactions.
Planning and memory are separate components.
"""


def test_confused_but_improving():
    result = agent.analyze(
        performance_result=SAMPLE_PERFORMANCE_RESULT,
        course_context=COURSE_CONTEXT,
    )

    print("\n=== INTERVENTION FOR AN IMPROVING STUDENT ===")
    print("Student:", result["student_id"])
    print("Subject:", result["subject_id"])

    print("\nSTUDENT INTERVENTION")
    for key, value in result["intervention"].items():
        print(f"{key}: {value}")

    print("\nTEACHER INSIGHT")
    for key, value in result["teacher_insight"].items():
        print(f"{key}: {value}")

    # Structural validation
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

    print("\nTest passed: intervention generated for an improving student.")


if __name__ == "__main__":
    test_confused_but_improving()
