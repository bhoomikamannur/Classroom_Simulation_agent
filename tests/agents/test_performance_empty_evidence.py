from backend.app.agents.performance_agent import PerformanceAgent


def test_empty_or_unparseable_llm_response_does_not_create_unknown_concept():
    agent = PerformanceAgent()
    parsed = agent.parse_llm_response("this is not valid json")
    diagnosis = agent.build_diagnosis(parsed)

    assert parsed["parse_status"] == "invalid"
    assert diagnosis["concepts"] == []
    assert "No usable concept-specific" in diagnosis["overall_observation"]
    assert diagnosis["confidence"] == "low"


def test_unknown_concept_is_not_added_as_a_real_diagnosis():
    agent = PerformanceAgent()
    diagnosis = agent.build_diagnosis({
        "concept": "Unknown",
        "evidence_analysis": [
            {
                "concept": "Unknown",
                "student_statement": "Some student text",
                "central_claim": "Some claim",
                "classification": "uncertain",
                "reason": "No course reference.",
            }
        ],
    })

    assert diagnosis["concepts"] == []
    assert diagnosis["confidence"] == "low"


def test_valid_concept_evidence_is_still_diagnosed():
    agent = PerformanceAgent()
    diagnosis = agent.build_diagnosis({
        "concept": "Planning",
        "evidence_analysis": [
            {
                "concept": "Planning",
                "student_statement": "Planning breaks a goal into steps.",
                "central_claim": "Planning decomposes goals into actions.",
                "classification": "aligned",
                "reason": "Matches course reference.",
            }
        ],
    })

    assert diagnosis["concepts"][0]["concept"] == "Planning"
    assert diagnosis["concepts"][0]["understanding"] == "understood"
