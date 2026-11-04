"""Contract and scenario tests for the Project Analysis Agent.

These tests mock the LLM to verify extraction, prompt context, output validation and
safe fallback behaviour deterministically. Live Ollama reasoning is tested separately
when RUN_PROJECT_AGENT_LIVE=1.
"""
import json
from pathlib import Path

import pytest

from backend.app.agents import project_analysis_agent as agent


@pytest.fixture
def evidence_files(tmp_path: Path):
    proposal = tmp_path / "approved-proposal.txt"
    checkpoint = tmp_path / "checkpoint-report.txt"
    proposal.write_text(
        "Build an attendance system using face recognition. Objectives: authentication, "
        "face matching, attendance reports. Requirement: use PostgreSQL.",
        encoding="utf-8",
    )
    checkpoint.write_text(
        "Implemented login, face matching prototype, PostgreSQL attendance tables "
        "and a daily attendance report.",
        encoding="utf-8",
    )
    return proposal, checkpoint


def _payload(**overrides):
    result = {
        "summary": "The checkpoint appears consistent with the approved project.",
        "overall_status": "aligned",
        "aligned_work": ["Face matching prototype"],
        "additional_work": [],
        "deviations": [],
        "incomplete_objectives": [],
        "concerns": [],
        "feedback_addressed": [],
        "feedback_unresolved": [],
        "evidence_limitations": [],
        "recommendations": [],
        "recommendation": "Continue with the next checkpoint.",
        "confidence": "high",
    }
    result.update(overrides)
    return result


def _run(monkeypatch, evidence_files, response, *, milestone=None, reviews=None):
    proposal, checkpoint = evidence_files
    prompts = []
    monkeypatch.setattr(agent, "generate", lambda prompt: prompts.append(prompt) or json.dumps(response))
    result = agent.analyse_project_submission(
        project={
            "title": "AI attendance system",
            "description": "Build attendance with face recognition and reporting.",
            "objectives": ["Authentication", "Face matching", "Attendance reports"],
            "requirements": ["PostgreSQL"],
        },
        proposal_submission={"file": {"file_path": str(proposal)}},
        submission={
            "file": {"file_path": str(checkpoint)},
            "description": "Checkpoint implementation note",
        },
        milestone=milestone,
        previous_reviews=reviews or [],
    )
    return result, prompts[0]


def test_extract_text_file(tmp_path: Path):
    sample = tmp_path / "checkpoint.txt"
    sample.write_text("Implemented authentication and report generation.", encoding="utf-8")
    text, note = agent.extract_submission_text(str(sample))
    assert "Implemented authentication" in text
    assert "extracted" in note


def test_image_extraction_is_explicitly_limited(tmp_path: Path):
    sample = tmp_path / "screenshot.png"
    sample.write_bytes(b"not-a-real-image")
    text, note = agent.extract_submission_text(str(sample))
    assert text == ""
    assert "does not perform OCR" in note


@pytest.mark.parametrize(
    ("case_id", "response", "expected"),
    [
        ("TC01_aligned", _payload(), "aligned"),
        ("TC02_minor_addition", _payload(overall_status="minor_deviation", additional_work=["Added optional dashboard"]), "minor_deviation"),
        ("TC03_major_scope_change", _payload(overall_status="major_deviation", deviations=["Replaced face recognition with RFID"]), "major_deviation"),
        ("TC04_incomplete_objective", _payload(overall_status="needs_review", incomplete_objectives=["Attendance reports not evidenced"]), "needs_review"),
        ("TC05_feedback_addressed", _payload(feedback_addressed=["Added database indexes requested by professor"]), "aligned"),
        ("TC06_feedback_unresolved", _payload(overall_status="needs_review", feedback_unresolved=["Database normalization issue remains"]), "needs_review"),
        ("TC07_approved_scope_change", _payload(additional_work=["RFID fallback previously approved"], deviations=[]), "aligned"),
        ("TC08_unrelated_submission", _payload(overall_status="major_deviation", deviations=["Submitted unrelated weather application"]), "major_deviation"),
        ("TC09_insufficient_evidence", _payload(overall_status="needs_review", confidence="low", evidence_limitations=["Report contains no implementation evidence"]), "needs_review"),
        ("TC10_unreadable_image", _payload(overall_status="needs_review", confidence="low", evidence_limitations=["Image OCR is unavailable"]), "needs_review"),
        ("TC11_multiple_deliverables", _payload(aligned_work=["Report and source summary jointly evidence the checkpoint"]), "aligned"),
        ("TC12_missing_reference_context", _payload(overall_status="needs_review", confidence="low"), "needs_review"),
    ],
)
def test_analysis_scenario_contracts(monkeypatch, evidence_files, case_id, response, expected):
    result, _ = _run(monkeypatch, evidence_files, response)
    assert result["overall_status"] == expected, case_id
    assert isinstance(result["aligned_work"], list)
    assert isinstance(result["deviations"], list)
    assert result["confidence"] in {"low", "medium", "high"}


def test_prompt_contains_checkpoint_and_previous_professor_feedback(monkeypatch, evidence_files):
    reviews = [
        {"decision": "revision_requested", "feedback": "Add database normalization and explain the schema."},
        {"decision": "approved", "feedback": "RFID fallback is approved as an optional addition."},
    ]
    milestone = {
        "title": "Database design",
        "description": "Submit ER diagram and normalized schema.",
        "due_date": "2026-11-10T23:59:00Z",
        "is_mandatory": True,
    }
    result, prompt = _run(monkeypatch, evidence_files, _payload(), milestone=milestone, reviews=reviews)
    assert "Database design" in prompt
    assert "ER diagram and normalized schema" in prompt
    assert "Add database normalization" in prompt
    assert "RFID fallback is approved" in prompt
    assert "must NOT be flagged again" in prompt
    assert result["overall_status"] == "aligned"




def test_explicit_abandonment_of_core_scope_is_promoted_to_major_deviation(monkeypatch, evidence_files):
    proposal, checkpoint = evidence_files
    checkpoint.write_text(
        "We abandoned face recognition and PostgreSQL. The solution now uses RFID and spreadsheets.",
        encoding="utf-8",
    )
    response = _payload(
        overall_status="needs_review",
        confidence="low",
        deviations=["Abandonment of face recognition and PostgreSQL"],
        incomplete_objectives=["Face recognition and PostgreSQL objectives abandoned"],
    )
    result, _ = _run(monkeypatch, evidence_files, response)
    assert result["overall_status"] == "major_deviation"
    assert result["confidence"] == "low"
    assert any("face recognition" in item.lower() for item in result["deviations"])
    assert any("postgresql" in item.lower() for item in result["deviations"])


def test_explicitly_approved_replacement_is_not_promoted(monkeypatch, evidence_files):
    proposal, checkpoint = evidence_files
    checkpoint.write_text(
        "We replaced face recognition with RFID and PostgreSQL with a spreadsheet.",
        encoding="utf-8",
    )
    response = _payload(overall_status="aligned", deviations=[])
    reviews = [
        {
            "decision": "approved",
            "feedback": "Replace face recognition with RFID and PostgreSQL with a spreadsheet; this scope change is approved.",
        }
    ]
    result, _ = _run(monkeypatch, evidence_files, response, reviews=reviews)
    assert result["overall_status"] == "aligned"
    assert result["deviations"] == []


def test_optional_addition_is_not_promoted_to_deviation(monkeypatch, evidence_files):
    proposal, checkpoint = evidence_files
    checkpoint.write_text(
        "Implemented face recognition and PostgreSQL. Added an optional RFID fallback.",
        encoding="utf-8",
    )
    result, _ = _run(monkeypatch, evidence_files, _payload(additional_work=["Optional RFID fallback"]))
    assert result["overall_status"] == "aligned"
    assert result["deviations"] == []


def test_negated_abandonment_statement_is_not_promoted(monkeypatch, evidence_files):
    proposal, checkpoint = evidence_files
    checkpoint.write_text(
        "We will not abandon face recognition or PostgreSQL; both remain in the implementation.",
        encoding="utf-8",
    )
    result, _ = _run(monkeypatch, evidence_files, _payload())
    assert result["overall_status"] == "aligned"

def test_invalid_model_status_falls_back_to_needs_review(monkeypatch, evidence_files):
    result, _ = _run(monkeypatch, evidence_files, _payload(overall_status="looks-good"))
    assert result["overall_status"] == "needs_review"
    assert result["confidence"] == "high"


def test_model_output_with_json_fence_is_parsed(monkeypatch, evidence_files):
    proposal, checkpoint = evidence_files
    payload = _payload()
    monkeypatch.setattr(agent, "generate", lambda prompt: "```json\n" + json.dumps(payload) + "\n```")
    result = agent.analyse_project_submission(
        project={"title": "Attendance", "objectives": [], "requirements": []},
        proposal_submission={"file": {"file_path": str(proposal)}},
        submission={"file": {"file_path": str(checkpoint)}},
    )
    assert result["overall_status"] == "aligned"


def test_missing_file_fails_with_clear_error(tmp_path: Path):
    with pytest.raises(ValueError, match="no longer available"):
        agent.extract_submission_text(str(tmp_path / "missing.txt"))


def test_professor_uploaded_brief_is_included_in_baseline(monkeypatch, evidence_files, tmp_path):
    proposal, checkpoint = evidence_files
    brief = tmp_path / "professor-brief.txt"
    brief.write_text("The professor requires a face recognition attendance system.", encoding="utf-8")
    prompts = []
    monkeypatch.setattr(agent, "generate", lambda prompt: prompts.append(prompt) or json.dumps(_payload()))
    agent.analyse_project_submission(
        project={
            "title": "AI attendance system",
            "description": "Build attendance.",
            "objectives": ["Face matching"],
            "requirements": ["PostgreSQL"],
            "brief_file": {"file_path": str(brief)},
        },
        proposal_submission={"file": {"file_path": str(proposal)}},
        submission={"file": {"file_path": str(checkpoint)}},
    )
    assert "The professor requires a face recognition attendance system." in prompts[0]
    assert "PROFESSOR PROJECT BRIEF TEXT" in prompts[0]
