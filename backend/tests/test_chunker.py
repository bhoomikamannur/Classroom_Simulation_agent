from backend.app.rag.chunker import chunk_text


def test_chunk_text_preserves_metadata():
    documents = [{
        "text": "This is a short piece of course material.",
        "metadata": {
            "source_name": "sample.pdf",
            "source_type": "pdf",
            "page": 2,
        },
    }]

    chunks = chunk_text(documents, chunk_size=20, overlap=5)

    assert chunks
    assert chunks[0]["metadata"]["source_name"] == "sample.pdf"
    assert chunks[0]["metadata"]["page"] == 2
