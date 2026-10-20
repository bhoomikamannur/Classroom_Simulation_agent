
import backend.app.rag.course_context as context_module


def test_build_course_context_formats_retrieved_chunks(monkeypatch):
    def fake_retrieve(query, top_k=5, relevance_threshold=0.85):
        assert query == "Explain planning"
        assert top_k == 5
        assert relevance_threshold == 0.85

        return [
            {
                "text": "Planning breaks a goal into smaller actions.",
                "metadata": {
                    "source_name": "agentic_ai.pdf",
                    "page": 3,
                },
                "distance": 0.2,
            }
        ]

    monkeypatch.setattr(context_module, "retrieve", fake_retrieve)

    result = context_module.build_course_context("Explain planning")

    assert result is not None
    assert "Planning breaks a goal into smaller actions." in result
    assert "agentic_ai.pdf" in result
    assert "page 3" in result


def test_build_course_context_returns_none_when_no_results(monkeypatch):
    monkeypatch.setattr(context_module, "retrieve", lambda **kwargs: [])

    result = context_module.build_course_context("Explain planning")

    assert result is None


def test_build_course_context_skips_empty_text(monkeypatch):
    monkeypatch.setattr(
        context_module,
        "retrieve",
        lambda **kwargs: [
            {
                "text": "   ",
                "metadata": {"source_name": "empty.pdf"},
                "distance": 0.2,
            }
        ],
    )

    result = context_module.build_course_context("Explain planning")

    assert result is None


def test_build_course_context_returns_none_for_empty_query():
    assert context_module.build_course_context("   ") is None
