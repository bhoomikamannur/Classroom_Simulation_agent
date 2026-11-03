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


