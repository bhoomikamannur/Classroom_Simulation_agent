from io import BytesIO


def _allow_course(monkeypatch):
    monkeypatch.setattr(
        "backend.app.api.academic_evaluation.get_accessible_course",
        lambda course_id, user: {"course_id": course_id},
    )


def test_upload_marks_merges_without_grading_policy(professor_client, monkeypatch):
    _allow_course(monkeypatch)
    def fake_merge(course_id, frame, uploaded_by, filename=None):
        assert course_id == "CS_TEST_101"
        assert list(frame.columns) == ["student_id", "quiz"]
        return {"course_id": course_id, "students_updated": 1, "message": "merged"}
    monkeypatch.setattr("backend.app.api.academic_evaluation.merge_marks", fake_merge)
    response = professor_client.post(
        "/academic-evaluation/upload",
        data={"course_id": "CS_TEST_101"},
        files={"file": ("marks.csv", BytesIO(b"student_id,quiz\nS001,8"), "text/csv")},
    )
    assert response.status_code == 200
    assert response.json()["students_updated"] == 1


def test_upload_marks_rejects_unsupported_file_type(professor_client):
    response = professor_client.post(
        "/academic-evaluation/upload",
        data={"course_id": "CS_TEST_101"},
        files={"file": ("marks.txt", BytesIO(b"sample"), "text/plain")},
    )
    assert response.status_code == 400
    assert "Only CSV and XLSX" in response.json()["detail"]


def test_upload_marks_rejects_empty_file(professor_client, monkeypatch):
    _allow_course(monkeypatch)
    response = professor_client.post(
        "/academic-evaluation/upload",
        data={"course_id": "CS_TEST_101"},
        files={"file": ("marks.csv", BytesIO(b""), "text/csv")},
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_register_returns_persisted_marks(professor_client, monkeypatch):
    _allow_course(monkeypatch)
    monkeypatch.setattr(
        "backend.app.api.academic_evaluation.get_marks_register",
        lambda course_id: {"course_id": course_id, "number_of_students": 1, "assessment_names": {"quiz": "Quiz"}, "students": [{"student_id": "S001", "assessments": {"quiz": 8}}]},
    )
    response = professor_client.get("/academic-evaluation/register/CS_TEST_101")
    assert response.status_code == 200
    assert response.json()["students"][0]["assessments"]["quiz"] == 8


def test_uploads_endpoint_lists_course_files(professor_client, monkeypatch):
    _allow_course(monkeypatch)
    monkeypatch.setattr(
        "backend.app.api.academic_evaluation.list_marks_uploads",
        lambda course_id: {"course_id": course_id, "uploads": [{"upload_id": "u1", "filename": "quiz.csv"}], "total_uploads": 1},
    )
    response = professor_client.get("/academic-evaluation/uploads/CS_TEST_101")
    assert response.status_code == 200
    assert response.json()["uploads"][0]["filename"] == "quiz.csv"


def test_delete_upload_endpoint(professor_client, monkeypatch):
    _allow_course(monkeypatch)
    monkeypatch.setattr(
        "backend.app.api.academic_evaluation.delete_marks_upload",
        lambda course_id, upload_id: {"upload_id": upload_id, "message": "deleted"},
    )
    response = professor_client.delete("/academic-evaluation/uploads/CS_TEST_101/u1")
    assert response.status_code == 200
    assert response.json()["upload_id"] == "u1"


def test_edit_mark_endpoint(professor_client, monkeypatch):
    _allow_course(monkeypatch)
    monkeypatch.setattr(
        "backend.app.api.academic_evaluation.edit_student_mark",
        lambda course_id, student_identifier, assessment, marks: {"student_id": student_identifier, "assessment": assessment, "marks": marks},
    )
    response = professor_client.patch(
        "/academic-evaluation/marks/CS_TEST_101",
        json={"student_identifier": "23bcs001", "assessment": "quiz", "marks": 9},
    )
    assert response.status_code == 200
    assert response.json()["marks"] == 9





def test_inline_evaluation_uses_register_and_saves_configuration(professor_client, monkeypatch):
    _allow_course(monkeypatch)
    monkeypatch.setattr(
        "backend.app.api.academic_evaluation.get_marks_register",
        lambda course_id: {
            "course_id": course_id,
            "assessment_names": {"quiz": "Quiz", "exam": "Exam"},
            "students": [
                {"student_id": "u1", "display_id": "S001", "assessments": {"quiz": 8, "exam": 70}},
                {"student_id": "u2", "display_id": "S002", "assessments": {"quiz": None, "exam": 60}},
            ],
        },
    )
    monkeypatch.setattr("backend.app.api.academic_evaluation.get_policy", lambda course_id: None)
    monkeypatch.setattr("backend.app.api.academic_evaluation.create_policy", lambda policy: policy)
    monkeypatch.setattr(
        "backend.app.api.academic_evaluation.persist_evaluation_and_update_alerts",
        lambda **kwargs: {"saved_results": 2, "alerts_opened": 0, "alerts_updated": 0, "alerts_resolved": 0},
    )
    response = professor_client.post(
        "/academic-evaluation/evaluate/CS_TEST_101",
        json={
            "assessment_weights": {"quiz": 20, "exam": 80},
            "assessment_max_marks": {"quiz": 10, "exam": 100},
            "pass_percentage": 40,
            "missing_marks_policy": "exclude",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["student_results"][0]["weighted_percentage"] == 72.0
    assert body["student_results"][1]["pass_status"] == "provisional"
    assert body["student_results"][1]["missing_assessments"] == ["quiz"]
    assert body["summary"]["student_count"] == 2
    assert body["summary"]["class_average_percentage"] == 66.0
    assert body["summary"]["complete_average_percentage"] == 72.0
    assert body["summary"]["pass_count"] == 1
    assert body["summary"]["provisional_count"] == 1
    assert body["summary"]["pass_rate"] == 100.0
    assert body["summary"]["assessment_summary"][0]["average_percentage"] == 80.0
    assert body["summary"]["assessment_summary"][1]["average_percentage"] == 65.0


def test_inline_evaluation_rejects_weights_not_totaling_100(professor_client, monkeypatch):
    _allow_course(monkeypatch)
    response = professor_client.post(
        "/academic-evaluation/evaluate/CS_TEST_101",
        json={
            "assessment_weights": {"quiz": 20},
            "assessment_max_marks": {"quiz": 10},
            "pass_percentage": 40,
            "missing_marks_policy": "exclude",
        },
    )
    assert response.status_code == 422
    assert "total exactly 100" in response.json()["detail"]
