
from backend.app.agents.performance_agent import PerformanceAgent
from backend.app.rag.course_context import build_course_context


def test_live_rag_retrieval_and_performance_diagnosis():
    query = (
        "Planning means breaking a high-level goal into "
        "smaller steps or subgoals."
    )

    # Verify actual retrieval from the existing ChromaDB collection.
    course_context = build_course_context(query)

    assert course_context, (
        "No course context was retrieved. Check the ChromaDB collection "
        "and relevance threshold."
    )

    print("\nRETRIEVED COURSE CONTEXT:")
    print(course_context[:1500])

    # Use the real Performance Agent and real Ollama generation.
    agent = PerformanceAgent()

    result = agent.analyze(
        student_id="23bcs030",
        subject_id="agentic_ai",
        interactions=[
            {
                "role": "user",
                "content": query,
            }
        ],
        course_context=course_context,
    )

    print("\nPERFORMANCE DIAGNOSIS:")
    print(result["diagnosis"])

    print("\nEVIDENCE INTERPRETATION:")
    print(result.get("evidence_interpretation"))

    assert result["student_id"] == "23bcs030"
    assert result["subject_id"] == "agentic_ai"
    assert isinstance(result["diagnosis"], dict)
    assert result["diagnosis"]["concepts"]
    assert result.get("evidence_interpretation", {}).get("evidence_analysis")
