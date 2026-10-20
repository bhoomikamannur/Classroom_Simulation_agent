
import json

import backend.app.agents.performance_agent as performance_module
import backend.app.agents.intervention_agent as intervention_module

from backend.app.agents.performance_agent import PerformanceAgent
from backend.app.agents.intervention_agent import InterventionAgent


COURSE_CONTEXT = """
Concept: Planning
Planning involves breaking a high-level goal into a sequence of
actions or subgoals.

Concept: Memory
Memory retains information from previous interactions.
Memory provides useful information, while planning determines
the actions needed to achieve a goal.
"""


def test_performance_to_intervention_integration(monkeypatch):
    """Verify that the Performance Agent's output reaches the
    Intervention Agent and produces an intervention."""

    performance_calls = []
    intervention_calls = []

    # Deterministic response from the Performance Agent's LLM.
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
                "reason": (
                    "The student's explanation matches the course context."
                ),
            }
        ],
    }

    def fake_performance_generate(*args, **kwargs):
        performance_calls.append((args, kwargs))
        return json.dumps(performance_response)

    # Deterministic response from the Intervention Agent's LLM.
    intervention_response = {
        "student_id": "23bcs030",
        "subject_id": "agentic_ai",
        "intervention": {
            "priority": "low",
            "objective": (
                "Strengthen the student's understanding of planning."
            ),
            "explanation": (
                "The student's statement aligns with the course definition."
            ),
            "activity": (
                "Ask the student to outline steps for achieving a simple goal."
            ),
            "follow_up_question": (
                "How would you break a large goal into smaller actions?"
            ),
            "success_criteria": (
                "The student identifies a sensible sequence of actions."
            ),
        },
        "teacher_insight": {
            "observed_learning_state": "understood",
            "evidence_summary": (
                "The student describes planning as breaking a goal into steps."
            ),
            "recommended_teaching_action": (
                "Provide an application activity rather than basic remediation."
            ),
            "next_step": (
                "Check whether the student can apply planning to a new example."
            ),
        },
    }

    def fake_intervention_generate(*args, **kwargs):
        intervention_calls.append((args, kwargs))
        return json.dumps(intervention_response)

    # Patch only the LLM calls; both agents' actual analyze() methods run.
    monkeypatch.setattr(
        performance_module, "generate", fake_performance_generate
    )
    monkeypatch.setattr(
        intervention_module, "generate", fake_intervention_generate
    )

    performance_agent = PerformanceAgent()
    intervention_agent = InterventionAgent()

    interactions = [
        {
            "role": "user",
            "content": (
                "Planning means breaking a high-level goal into "
                "smaller steps or actions."
            ),
        }
    ]

    # Stage 1: Analyze student evidence.
    performance_result = performance_agent.analyze(
        student_id="23bcs030",
        subject_id="agentic_ai",
        interactions=interactions,
        course_context=COURSE_CONTEXT,
    )

    assert performance_calls, "Performance Agent did not call its LLM."

    assert performance_result["student_id"] == "23bcs030"
    assert performance_result["subject_id"] == "agentic_ai"
    assert isinstance(performance_result["diagnosis"], dict)
    assert performance_result["diagnosis"]

    assert "evidence_interpretation" in performance_result
    assert isinstance(
        performance_result["evidence_interpretation"], dict
    )

    # Stage 2: Pass the complete result to the Intervention Agent.
    intervention_result = intervention_agent.analyze(
        performance_result=performance_result,
        course_context=COURSE_CONTEXT,
    )

    assert intervention_calls, "Intervention Agent did not call its LLM."

    # Verify identity is preserved across the pipeline.
    assert intervention_result["student_id"] == "23bcs030"
    assert intervention_result["subject_id"] == "agentic_ai"

    # Verify the intervention response structure.
    assert isinstance(intervention_result["intervention"], dict)
    assert isinstance(intervention_result["teacher_insight"], dict)

    for field in (
        "priority",
        "objective",
        "explanation",
        "activity",
        "follow_up_question",
        "success_criteria",
    ):
        assert intervention_result["intervention"].get(field)

    for field in (
        "observed_learning_state",
        "evidence_summary",
        "recommended_teaching_action",
        "next_step",
    ):
        assert intervention_result["teacher_insight"].get(field)

    # Verify the actual diagnosis and evidence were passed downstream.
    intervention_prompt = intervention_calls[0][0][0]

    assert "PERFORMANCE AGENT DIAGNOSIS" in intervention_prompt
    assert "EVIDENCE INTERPRETATION" in intervention_prompt
    assert "Planning" in intervention_prompt
    assert COURSE_CONTEXT in intervention_prompt
