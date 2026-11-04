import pytest

from backend.app.orchestrator.classroom_orchestrator import ClassroomOrchestrator
from backend.app.orchestrator.workflow_router import (
    WorkflowRoleError,
    UnknownWorkflowError,
    resolve_workflow,
)


class FakeTutor:
    def answer(self, **kwargs):
        return {"answer": "tutor result", "received": kwargs}


class FakeContent:
    def answer(self, query, course_id, top_k=5):
        return {
            "answer": "content result",
            "query": query,
            "course_id": course_id,
            "top_k": top_k,
        }


class FakePerformance:
    def analyze(self, **kwargs):
        return {
            "student_id": kwargs["student_id"],
            "course_name": kwargs["course_name"],
            "diagnosis": {"overall_observation": "test diagnosis"},
        }


class FakeIntervention:
    def analyze(self, performance_result, course_context=None):
        return {
            "student_id": performance_result["student_id"],
            "intervention": {"objective": "test objective"},
        }


def make_orchestrator():
    return ClassroomOrchestrator(
        tutor_agent=FakeTutor(),
        content_agent=FakeContent(),
        performance_agent=FakePerformance(),
        intervention_agent=FakeIntervention(),
    )


def test_workflow_router_rejects_unknown_operation():
    with pytest.raises(UnknownWorkflowError):
        resolve_workflow("delete_everything", "professor")


def test_workflow_router_enforces_role():
    with pytest.raises(WorkflowRoleError):
        resolve_workflow("performance_intervention", "student")


def test_tutor_workflow_calls_tutor_with_verified_course():
    orchestrator = make_orchestrator()
    actor = {"user_id": "student-1", "role": "student"}
    course = {
        "course_id": "course-1",
        "professor_id": "professor-1",
    }

    result = orchestrator.execute(
        operation="tutor_chat",
        actor=actor,
        payload={
            "course_name": "agentic-ai",
            "session_id": "session-1",
            "message": "Explain RAG",
            "top_k": 4,
        },
        course=course,
    )

    assert result["answer"] == "tutor result"
    assert result["received"]["student_id"] == "student-1"
    assert result["received"]["course_id"] == "course-1"
    assert result["received"]["professor_id"] == "professor-1"


def test_content_workflow_calls_content_agent():
    orchestrator = make_orchestrator()
    result = orchestrator.execute(
        operation="content_answer",
        actor={"user_id": "student-1", "role": "student"},
        payload={"query": "Explain agents", "top_k": 3},
        course={"course_id": "course-1", "professor_id": "professor-1"},
    )

    assert result["answer"] == "content result"
    assert result["course_id"] == "course-1"
    assert result["top_k"] == 3


def test_performance_workflow_runs_performance_then_intervention():
    orchestrator = make_orchestrator()
    result = orchestrator.execute(
        operation="performance_intervention",
        actor={"user_id": "professor-1", "role": "professor"},
        payload={
            "student_id": "student-1",
            "course_name": "agentic-ai",
            "interactions": [{"role": "user", "content": "I think RAG is..."}],
            "course_context": "Course reference",
        },
        course={"course_id": "course-1", "professor_id": "professor-1"},
    )

    assert result["performance"]["diagnosis"]["overall_observation"] == "test diagnosis"
    assert result["intervention"]["intervention"]["objective"] == "test objective"


def test_workflow_requires_validated_course():
    orchestrator = make_orchestrator()
    with pytest.raises(ValueError, match="validated course"):
        orchestrator.execute(
            operation="tutor_chat",
            actor={"user_id": "student-1", "role": "student"},
            payload={
                "course_name": "agentic-ai",
                "session_id": "session-1",
                "message": "Explain RAG",
            },
            course=None,
        )
