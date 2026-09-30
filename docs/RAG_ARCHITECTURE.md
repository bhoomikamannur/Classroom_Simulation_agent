# RAG Architecture — Milestone 1

## Goal

Build a grounded course-material retrieval layer for the Classroom Simulation System.

## Sources

- PDF: primary course-material source
- PPTX: first-class source because faculty commonly share lecture slides

Faculty do not have to manually specify units. A single file may contain one or multiple units. The first milestone preserves document/page/slide metadata. Automatic unit detection can be added after basic retrieval is evaluated.

## Pipeline

```text
Faculty PDF/PPTX
      |
      v
Document Loader
  |          |
PDF loader  PPTX loader
  |          |
  +----+-----+
       |
       v
Normalized page/slide text
       |
       v
Chunking
       |
       v
Embedding model
BAAI/bge-small-en-v1.5
       |
       v
ChromaDB
       |
       v
Semantic retrieval
       |
       v
Content Agent
```

## Embeddings

Embeddings convert text into numerical vectors that capture semantic meaning. A student's question can therefore be compared with course-material chunks even when the wording differs.

## Chroma

Local persistent Chroma is used for development. The vector-store implementation is isolated in `vector_store.py`, allowing a future hosted/server deployment without changing the agent interface.

## Current agent

Only one agent is being implemented now: **Content Agent**.

Its current responsibility is to retrieve relevant course context. An LLM will be connected after the team selects a provider.

## Evaluation

1. Select one real course.
2. Load representative PDF/PPTX material.
3. Create about 20–30 questions with known source pages/slides.
4. Measure whether the correct source appears in top-k results.
5. Tune chunking and embedding choice if necessary.
