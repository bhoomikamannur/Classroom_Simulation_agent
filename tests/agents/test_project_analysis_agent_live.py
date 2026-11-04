"""Optional real-model tests. Run with RUN_PROJECT_AGENT_LIVE=1 and Ollama available."""
import os
from pathlib import Path

import pytest

from backend.app.agents.project_analysis_agent import analyse_project_submission

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_PROJECT_AGENT_LIVE") != "1",
    reason="Set RUN_PROJECT_AGENT_LIVE=1 to exercise the configured Ollama model.",
)


@pytest.mark.parametrize(
    ("submission_text", "expected_status"),
    [
        (
            "Implemented authentication, face matching prototype, PostgreSQL attendance tables, "
            "and daily attendance report generation.",
            "aligned",
        ),
        (
            "We abandoned face recognition and PostgreSQL. The entire solution is now an RFID "
            "attendance application using a spreadsheet as its only data store.",
            "major_deviation",
        ),
    ],
)
def test_live_model_classifies_project_alignment(tmp_path: Path, submission_text: str, expected_status: str):
    proposal = tmp_path / "approved_proposal.txt"
    submission = tmp_path / "checkpoint.txt"
    proposal.write_text(
        "Build an attendance system using face recognition and PostgreSQL. "
        "Objectives: authentication, face matching and attendance reports.",
        encoding="utf-8",
    )
    submission.write_text(submission_text, encoding="utf-8")
    report = analyse_project_submission(
        project={
            "title": "Face recognition attendance system",
            "description": "Build an attendance system using face recognition and PostgreSQL.",
            "objectives": ["Authentication", "Face matching", "Attendance reports"],
            "requirements": ["PostgreSQL"],
        },
        proposal_submission={"file": {"file_path": str(proposal)}},
        submission={"file": {"file_path": str(submission)}, "description": "Checkpoint implementation report"},
        milestone={
            "title": "Working prototype",
            "description": "Demonstrate face matching and PostgreSQL attendance storage.",
            "is_mandatory": True,
        },
        previous_reviews=[],
    )
    
    assert report["overall_status"] == expected_status

    assert report["summary"]
