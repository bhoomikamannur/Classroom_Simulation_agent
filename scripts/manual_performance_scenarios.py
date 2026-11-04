"""Manual live scenarios for exploratory Performance Agent evaluation.

Run explicitly with: python -m scripts.manual_performance_scenarios
This is not a pytest module.
"""

from backend.app.agents.performance_agent import PerformanceAgent

COURSE_CONTEXT = """
Concept: Planning

Planning involves breaking a high-level goal into a sequence of
actions or subgoals. Candidate plans can be evaluated based on
factors such as efficiency, tool availability, cost, risk, and
alignment with the goal.

Planning is concerned with deciding what actions or steps should
be taken to achieve a goal.

Concept: Memory

Memory allows an agent to retain information from previous
interactions or relevant past information.

Planning and memory are separate components. Memory provides
information that may be useful, while planning determines the
actions or sequence of steps needed to achieve a goal.

Concept: Reasoning

Reasoning is used during planning and execution to evaluate
information, alternatives, and decisions.
"""

def run_manual_scenarios():
    agent = PerformanceAgent()
    for test_name, interactions in TEST_CASES.items():


        print("\n" + "=" * 70)
        print(test_name)
        print("=" * 70)

        result = agent.analyze(
            student_id="23bcs030",
            course_name="agentic_ai",
            interactions=interactions,
            course_context=COURSE_CONTEXT,
        )

        print("DIAGNOSIS:")
        print(result["diagnosis"])

        print("\nRAW EVIDENCE INTERPRETATION:")
        print(result.get("evidence_interpretation", "Not generated — insufficient evidence."))

if __name__ == "__main__":
    run_manual_scenarios()
