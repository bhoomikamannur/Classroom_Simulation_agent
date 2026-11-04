
import os
import pytest

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.getenv("RUN_PERFORMANCE_LIVE") != "1",
        reason="Set RUN_PERFORMANCE_LIVE=1 to run live Ollama/RAG tests.",
    ),
]

from backend.app.agents.performance_agent import PerformanceAgent
from backend.app.rag.course_context import build_course_context


def test_live_rag_retrieval_and_performance_diagnosis():
    query = (
        "Planning means breaking a high-level goal into "
        "smaller steps or subgoals."
    )

    # Verify actual retrieval from the existing ChromaDB collection.
    course_context = build_course_context(query, course_id=os.getenv("PERFORMANCE_LIVE_COURSE_ID", "3ce7921b-cb0f-476f-b7d4-de62fc55dd12"))

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
        course_name="Introduction to Agentic AI",
        course_id=os.getenv("PERFORMANCE_LIVE_COURSE_ID", "3ce7921b-cb0f-476f-b7d4-de62fc55dd12"),
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
    assert result["course_name"] == "Introduction to Agentic AI"
    assert isinstance(result["diagnosis"], dict)
    assert result["diagnosis"]["concepts"]
    assert result.get("evidence_interpretation", {}).get("evidence_analysis")
