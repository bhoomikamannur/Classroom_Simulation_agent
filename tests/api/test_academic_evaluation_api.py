from io import BytesIO

from fastapi.testclient import TestClient

from backend.app.api.academic_evaluation import (
    evaluate_marks_file,
)
from backend.app.main import app


client = TestClient(app)


def test_upload_marks_returns_evaluation_results(monkeypatch):
    def fake_evaluate_marks_file(file_path, course_id, student_id_column=None):
        assert course_id == "CS_TEST_101"
        return {
            "course_id": course_id,
            "number_of_students": 1,
            "grading_policy": {"course_id": course_id},
            "student_results": [
                {
                    "student_id": "S001",
                    "weighted_percentage": 75.0,
                    "pass_status": "pass",
                }
            ],
        }

    monkeypatch.setattr(
        "backend.app.api.academic_evaluation.evaluate_marks_file",
        fake_evaluate_marks_file,
    )

    response = client.post(
        "/academic-evaluation/upload",
        data={"course_id": "CS_TEST_101"},
        files={
            "file": (
                "marks.csv",
                BytesIO(b"student_id,quiz\nS001,8"),
                "text/csv",
            )
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["course_id"] == "CS_TEST_101"
    assert result["number_of_students"] == 1
    assert result["student_results"][0]["weighted_percentage"] == 75.0


def test_upload_marks_rejects_missing_course_policy(monkeypatch):
    def fake_evaluate_marks_file(file_path, course_id, student_id_column=None):
        raise ValueError(
            f"No academic grading policy exists for course '{course_id}'."
        )

    monkeypatch.setattr(
        "backend.app.api.academic_evaluation.evaluate_marks_file",
        fake_evaluate_marks_file,
    )

    response = client.post(
        "/academic-evaluation/upload",
        data={"course_id": "UNKNOWN_COURSE"},
        files={
            "file": (
                "marks.csv",
                BytesIO(b"student_id,quiz\nS001,8"),
                "text/csv",
            )
        },
    )

    assert response.status_code == 404
    assert "No academic grading policy exists" in response.json()["detail"]


def test_upload_marks_rejects_unsupported_file_type():
    response = client.post(
        "/academic-evaluation/upload",
        data={"course_id": "CS_TEST_101"},
        files={
            "file": (
                "marks.txt",
                BytesIO(b"sample"),
                "text/plain",
            )
        },
    )

    assert response.status_code == 400
    assert "Only CSV and XLSX" in response.json()["detail"]


def test_upload_marks_rejects_empty_file():
    response = client.post(
        "/academic-evaluation/upload",
        data={"course_id": "CS_TEST_101"},
        files={
            "file": (
                "marks.csv",
                BytesIO(b""),
                "text/csv",
            )
        },
    )

    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()