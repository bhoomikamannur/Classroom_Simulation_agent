from pathlib import Path

from fastapi import HTTPException

from backend.app.api import documents


class FakeDocuments:
    def __init__(self, record):
        self.record = record

    def find_one(self, query, projection=None):
        if self.record and self.record.get("document_id") == query.get("document_id"):
            return dict(self.record)
        return None


def _setup_file_access(monkeypatch, tmp_path):
    uploads = tmp_path / "backend" / "data" / "uploads"
    uploads.mkdir(parents=True)
    original = uploads / "demo.pdf"
    original.write_bytes(b"%PDF-1.4 demo")
    record = {
        "document_id": "doc-1",
        "course_id": "course-1",
        "professor_id": "test-professor-001",
        "filename": "lecture-notes.pdf",
        "file_type": "pdf",
        "file_path": original.relative_to(tmp_path / "backend").as_posix(),
    }
    monkeypatch.setattr(documents, "BACKEND_ROOT", tmp_path / "backend")
    monkeypatch.setattr(documents, "UPLOADS_DIR", uploads)
    monkeypatch.setattr(documents, "_documents", lambda: FakeDocuments(record))
    monkeypatch.setattr(
        documents, "get_accessible_course",
        lambda course_id, user: {"course_id": course_id, "professor_id": "test-professor-001"},
    )
    return original


def test_professor_can_view_original_pdf(professor_client, monkeypatch, tmp_path):
    _setup_file_access(monkeypatch, tmp_path)

    response = professor_client.get("/documents/doc-1/view")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.headers["content-disposition"].startswith("inline")
    assert response.content == b"%PDF-1.4 demo"


def test_student_can_download_enrolled_course_material(student_client, monkeypatch, tmp_path):
    _setup_file_access(monkeypatch, tmp_path)

    response = student_client.get("/documents/doc-1/download")

    assert response.status_code == 200
    assert response.headers["content-disposition"].startswith("attachment")
    assert "lecture-notes.pdf" in response.headers["content-disposition"]


def test_missing_original_file_returns_404(professor_client, monkeypatch, tmp_path):
    original = _setup_file_access(monkeypatch, tmp_path)
    original.unlink()

    response = professor_client.get("/documents/doc-1/view")

    assert response.status_code == 404


def test_document_path_outside_upload_directory_is_rejected(professor_client, monkeypatch, tmp_path):
    _setup_file_access(monkeypatch, tmp_path)
    record = {
        "document_id": "doc-1", "course_id": "course-1",
        "professor_id": "test-professor-001", "filename": "bad.pdf",
        "file_type": "pdf", "file_path": "../../secrets.txt",
    }
    monkeypatch.setattr(documents, "_documents", lambda: FakeDocuments(record))

    response = professor_client.get("/documents/doc-1/view")

    assert response.status_code == 404
