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

agent = PerformanceAgent()


TEST_CASES = {

    "TEST 1 — Insufficient evidence": [
        {
            "role": "user",
            "content": "What is planning?"
        }
    ],

    "TEST 2 — Clear understanding": [
        {
            "role": "user",
            "content": (
                "Planning means breaking a high-level goal into smaller "
                "steps or actions that can be executed."
            )
        }
    ],

    "TEST 3 — Misconception": [
        {
            "role": "user",
            "content": (
                "Planning means remembering information from previous "
                "conversations so the agent knows what to do."
            )
        }
    ],

    "TEST 4 — Learning progression": [
        {
            "role": "user",
            "content": "I don't understand what planning means."
        },
        {
            "role": "assistant",
            "content": (
                "Planning means breaking a high-level goal into smaller "
                "steps that can be executed."
            )
        },
        {
            "role": "user",
            "content": "So planning is basically reasoning?"
        },
        {
            "role": "assistant",
            "content": (
                "Planning and reasoning are related, but planning focuses "
                "on deciding the sequence of actions needed to achieve a goal."
            )
        },
        {
            "role": "user",
            "content": (
                "Okay, so planning decides what steps to take, while "
                "reasoning helps evaluate them?"
            )
        }
    ],

    "TEST 5 — Repeated misconception": [
        {
            "role": "user",
            "content": (
                "Planning means remembering previous information."
            )
        },
        {
            "role": "assistant",
            "content": (
                "Planning is about deciding a sequence of actions to "
                "achieve a goal."
            )
        },
        {
            "role": "user",
            "content": (
                "So planning is basically the agent remembering what "
                "happened before?"
            )
        },
        {
            "role": "assistant",
            "content": (
                "Memory stores information from previous interactions, "
                "while planning determines what actions to take."
            )
        },
        {
            "role": "user",
            "content": (
                "Yes, planning means using previous information to decide "
                "what happened."
            )
        }
    ],
}


for test_name, interactions in TEST_CASES.items():

    print("\n" + "=" * 70)
    print(test_name)
    print("=" * 70)

    result = agent.analyze(
        student_id="23bcs030",
        subject_id="agentic_ai",
        interactions=interactions,
        course_context=COURSE_CONTEXT,
    )

    print("DIAGNOSIS:")
    print(result["diagnosis"])

    print("\nRAW EVIDENCE INTERPRETATION:")
    print(result.get("evidence_interpretation", "Not generated — insufficient evidence."))