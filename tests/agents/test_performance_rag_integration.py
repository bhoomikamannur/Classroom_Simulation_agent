
import backend.app.agents.performance_agent as performance_module
from backend.app.agents.performance_agent import PerformanceAgent


def test_performance_agent_uses_retrieved_course_context(monkeypatch):
    retrieved_context = (
        "Concept: Planning\n"
        "Planning means breaking a high-level goal into "
        "a sequence of actions or subgoals."
    )

    retrieval_calls = []
    llm_prompts = []

    def fake_build_course_context(query):
        retrieval_calls.append(query)
        return retrieved_context

    def fake_generate(prompt):
        llm_prompts.append(prompt)

        return """
        {
            "concept": "Planning",
            "evidence_analysis": [
                {
                    "student_statement": "Planning breaks a goal into steps.",
                    "central_claim": "Planning determines steps to achieve a goal.",
                    "classification": "aligned",
                    "reason": "The claim matches the supplied course reference."
                }
            ]
        }
        """

    monkeypatch.setattr(
        performance_module,
        "build_course_context",
        fake_build_course_context,
    )
    monkeypatch.setattr(
        performance_module,
        "generate",
        fake_generate,
    )

    agent = PerformanceAgent()

    result = agent.analyze(
        student_id="23bcs030",
        subject_id="agentic_ai",
        interactions=[
            {
                "role": "user",
                "content": "Planning breaks a goal into smaller steps.",
            }
        ],
        # Intentionally omit course_context to trigger retrieval.
    )

    # Retrieval must be called with the student's message.
    assert retrieval_calls == [
        "Planning breaks a goal into smaller steps."
    ]

    # The retrieved context must reach the LLM prompt.
    assert len(llm_prompts) == 1
    assert retrieved_context in llm_prompts[0]

    # The Performance Agent must produce its normal result structure.
    assert result["student_id"] == "23bcs030"
    assert result["subject_id"] == "agentic_ai"
    assert result["diagnosis"]["concepts"][0]["understanding"] == "understood"
    assert result["evidence_interpretation"]["concept"] == "Planning"


def test_explicit_course_context_skips_retrieval(monkeypatch):
    def unexpected_retrieval(query):
        raise AssertionError(
            "RAG should not run when course_context is explicitly supplied."
        )

    def fake_generate(prompt):
        assert "Planning is a sequence of actions." in prompt

        return """
        {
            "concept": "Planning",
            "evidence_analysis": [
                {
                    "student_statement": "Planning is a sequence of actions.",
                    "central_claim": "Planning determines a sequence of actions.",
                    "classification": "aligned",
                    "reason": "The claim matches the supplied course reference."
                }
            ]
        }
        """

    monkeypatch.setattr(
        performance_module,
        "build_course_context",
        unexpected_retrieval,
    )
    monkeypatch.setattr(
        performance_module,
        "generate",
        fake_generate,
    )

    result = PerformanceAgent().analyze(
        student_id="23bcs030",
        subject_id="agentic_ai",
        interactions=[
            {
                "role": "user",
                "content": "Planning is a sequence of actions.",
            }
        ],
        course_context="Planning is a sequence of actions.",
    )

    assert result["diagnosis"]["concepts"][0]["understanding"] == "understood"
