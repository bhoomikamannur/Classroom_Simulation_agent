from backend.app.rag import vector_store


class FakeCollection:
    def __init__(self):
        self.query_kwargs = None
        self.deleted = None
        self.upsert_kwargs = None

    def query(self, **kwargs):
        self.query_kwargs = kwargs
        return {
            "documents": [["chunk text"]],
            "metadatas": [[{"course_id": "course-a"}]],
            "distances": [[0.2]],
        }

    def get(self, **kwargs):
        return {"ids": ["doc-1-0", "doc-1-1"]}

    def delete(self, **kwargs):
        self.deleted = kwargs

    def upsert(self, **kwargs):
        self.upsert_kwargs = kwargs


def test_search_filters_by_course(monkeypatch):
    collection = FakeCollection()
    monkeypatch.setattr(vector_store, "_collection", collection)
    monkeypatch.setattr(vector_store, "embed_query", lambda query: [0.1, 0.2])

    results = vector_store.search("question", course_id="course-a", top_k=3)

    assert results[0]["text"] == "chunk text"
    assert collection.query_kwargs["where"] == {"course_id": "course-a"}
    assert collection.query_kwargs["n_results"] == 3


def test_add_chunks_requires_course_ownership_metadata():
    try:
        vector_store.add_chunks([{
            "text": "a chunk",
            "metadata": {"source_name": "lecture.pdf"},
        }])
    except ValueError as exc:
        assert "document_id, course_id and professor_id" in str(exc)
    else:
        raise AssertionError("Expected missing course metadata to be rejected.")


def test_delete_document_chunks(monkeypatch):
    collection = FakeCollection()
    monkeypatch.setattr(vector_store, "_collection", collection)

    deleted = vector_store.delete_document_chunks("doc-1")

    assert deleted == 2
    assert collection.deleted == {"ids": ["doc-1-0", "doc-1-1"]}
