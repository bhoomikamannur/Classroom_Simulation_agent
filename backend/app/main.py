from fastapi import FastAPI

from backend.app.api.documents import router as documents_router
from backend.app.api.retrieval import router as retrieval_router
from backend.app.api.content import router as content_router
from backend.app.api.tutor import router as tutor_router

app = FastAPI(
    title="Agentic AI Classroom Simulation System",
    version="0.1.0",
    description="RAG foundation and Content Agent scaffold.",
)

app.include_router(documents_router)
app.include_router(retrieval_router)
app.include_router(content_router)
app.include_router(tutor_router)


@app.get("/")
def root():
    return {
        "message": "Classroom Simulation Agent API is running",
        "milestone": "RAG Foundation + Content Agent scaffold",
    }
