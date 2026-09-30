# Agentic AI Classroom Simulation System

## Current milestone: RAG Foundation + Content Agent scaffold

Current workflow:

Faculty PDF/PPTX -> extraction -> chunking -> embeddings -> Chroma -> retrieval -> Content Agent

### Not included yet
- Tutor Agent
- Performance & Diagnostic Agent
- Intervention & Teacher Insight Agent
- Project Tracking Agent
- LangGraph orchestration
- MongoDB
- React frontend
- Production deployment

## Requirements
- Python 3.12
- Internet connection on first run to download the embedding model

## Setup (Windows)

```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload
```

Open http://127.0.0.1:8000/docs

## API

### Upload course material
`POST /documents/upload`

Accepts PDF and PPTX. The file is extracted, chunked, embedded, and stored in Chroma.

### Search course material
`POST /retrieve`

```json
{"query": "What are the necessary conditions for deadlock?", "top_k": 5}
```

### Content Agent
`POST /content/answer`

The current agent retrieves grounded course context. The LLM provider is intentionally not hard-coded yet.

## Structure

```text
classroom-simulation-agent/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   ├── rag/
│   │   │   └── loaders/
│   │   └── agents/
│   ├── data/
│   │   ├── raw/
│   │   └── chroma/
│   ├── tests/
│   └── requirements.txt
├── docs/
└── README.md
```

## Design notes

PDF is the primary source and PPTX is a first-class source because faculty commonly share slides. Faculty do not have to manually specify units in this milestone; a file may contain one or multiple units. Page/slide metadata is preserved.

Chroma is persistent locally for development. The vector-store interface is isolated so it can later be moved to a hosted/server deployment.

Before adding more agents, evaluate retrieval on real faculty material using a small set of known questions and source pages/slides.
