import pandas as pd
import pytest
from backend.app.analytics import marks_store


class FakeCollection:
    def __init__(self):
        self.calls = []
        self.documents = []
    def create_index(self, *args, **kwargs):
        pass
    def update_one(self, query, update, upsert=False):
        self.calls.append((query, update, upsert))
    def find_one(self, query, projection=None):
        return None
    def insert_one(self, document):
        self.documents.append(document)


def setup(monkeypatch):
    marks = FakeCollection()
    uploads = FakeCollection()
    monkeypatch.setattr(marks_store, "get_marks_collection", lambda: marks)
    monkeypatch.setattr(marks_store, "_uploads", lambda: uploads)
    monkeypatch.setattr(marks_store, "_resolve_enrolled_students", lambda course_id: ({"S001": "S001"}, {"S001"}))
    return marks, uploads


def test_incremental_marks_upload_accepts_student_id_without_policy(monkeypatch):
    marks, uploads = setup(monkeypatch)
    first = pd.DataFrame({"student_id": ["S001"], "Assignment 1": [18]})
    second = pd.DataFrame({"roll_number": ["S001"], "Quiz_marks": [8]})
    result1 = marks_store.merge_marks_upload("COURSE1", first)
    result2 = marks_store.merge_marks_upload("COURSE1", second)
    assert result1["assessments_uploaded"] == ["assignment1"]
    assert result2["assessments_uploaded"] == ["quiz"]
    assert len(marks.calls) == 2
    assert len(uploads.documents) == 2


def test_marks_upload_accepts_maximum_column_and_rejects_invalid_marks(monkeypatch):
    setup(monkeypatch)
    frame = pd.DataFrame({"student_id": ["S001"], "Exam_marks": [45], "Exam_max": [50]})
    result = marks_store.merge_marks_upload("COURSE1", frame)
    assert result["assessments_uploaded"] == ["exam"]
    invalid = pd.DataFrame({"student_id": ["S001"], "Exam": [55], "Exam_max": [50]})
    with pytest.raises(ValueError, match="between 0 and 50"):
        marks_store.merge_marks_upload("COURSE1", invalid)


def test_upload_does_not_read_grading_policy_and_accepts_csv_maximum(monkeypatch):
    setup(monkeypatch)
    monkeypatch.setattr(marks_store, "get_policy", lambda *_: (_ for _ in ()).throw(AssertionError("policy must not be read")), raising=False)
    frame = pd.DataFrame({"roll_number": ["S001"], "Assignment1_marks": [17], "Assignment 1_max": [20]})
    result = marks_store.merge_marks("COURSE1", frame, "professor", "assignment_marks.csv")
    assert result["students_updated"] == 1


def test_enrollment_lookup_is_case_insensitive(monkeypatch):
    setup(monkeypatch)
    monkeypatch.setattr(marks_store, "_resolve_enrolled_students", lambda course_id: ({"S001": "S001"}, {"S001"}))
    frame = pd.DataFrame({"roll_number": ["s001"], "quiz": [8]})
    assert marks_store.merge_marks("COURSE1", frame)["students_updated"] == 1


def test_standalone_maximum_marks_column(monkeypatch):
    setup(monkeypatch)
    frame = pd.DataFrame({"roll_number": ["S001"], "exam_marks": [78], "maximum_marks": [100]})
    result = marks_store.merge_marks("COURSE1", frame, "professor", "exam_marks.csv")
    assert result["assessment_names"] == {"exam": "exam_marks"}
