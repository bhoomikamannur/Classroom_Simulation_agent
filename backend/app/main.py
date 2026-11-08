from fastapi import FastAPI

from backend.app.api.documents import router as documents_router
from backend.app.api.retrieval import router as retrieval_router
from backend.app.api.content import router as content_router
from backend.app.api.tutor import router as tutor_router
from backend.app.api.academic_evaluation import (
    router as academic_evaluation_router,
)
from backend.app.api.academic_policy import router as academic_policy_router
from backend.app.api.performance_intervention import (
    router as performance_intervention_router,
)
from backend.app.api.auth import router as auth_router
from backend.app.api.courses import router as courses_router
from backend.app.api.project_tracker import router as project_tracker_router
from backend.app.api.learning_plans import router as learning_plans_router
from backend.app.api.risk_assessment import router as risk_assessment_router
from backend.app.api.semester_planner import router as semester_planner_router

app = FastAPI(
    title="Agentic AI Classroom Simulation System",
    version="0.1.0",
    description="RAG foundation and Content Agent scaffold.",
)

app.include_router(documents_router)
app.include_router(retrieval_router)
app.include_router(content_router)
app.include_router(tutor_router)
app.include_router(academic_evaluation_router)
app.include_router(academic_policy_router)
app.include_router(performance_intervention_router)
app.include_router(auth_router)
app.include_router(courses_router)
app.include_router(project_tracker_router)
app.include_router(learning_plans_router)
app.include_router(risk_assessment_router)
app.include_router(semester_planner_router)

@app.get("/")
def root():
    return {
        "message": "Classroom Simulation Agent API is running",
        "milestone": "RAG Foundation + Content Agent scaffold",
    }
