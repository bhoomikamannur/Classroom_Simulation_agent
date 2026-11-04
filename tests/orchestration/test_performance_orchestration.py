from backend.app.orchestrator.classroom_orchestrator import (
    ClassroomOrchestrator,
)


class FakePerformanceAgent:
    def __init__(self):
        self.received = None

    def analyze(self, **kwargs):
        self.received = kwargs
        return {
            "student_id": kwargs["student_id"],
            "course_id": kwargs["course_id"],
            "course_name": kwargs["course_name"],
            "diagnosis": {"overall_observation": "Evidence reviewed."},
        }


class FakeInterventionAgent:
    def __init__(self):
        self.received = None

    def analyze(self, **kwargs):
        self.received = kwargs
        return {"intervention": {"priority": "medium"}}


def test_performance_workflow_loads_interactions_from_repository():
    persisted = [
        {
            "student_id": "student-1",
            "course_id": "course-1",
            "session_id": "session-1",
            "role": "user",
            "content": "Planning means choosing actions.",
        },
        {
            "student_id": "student-1",
            "course_id": "course-1",
            "session_id": "session-1",
            "role": "assistant",
            "content": "Correct. Planning selects actions toward a goal.",
        },
    ]
    loaded = {}
    performance = FakePerformanceAgent()
    intervention = FakeInterventionAgent()

    def interaction_loader(**kwargs):
        loaded.update(kwargs)
        return persisted

    orchestrator = ClassroomOrchestrator(
        performance_agent=performance,
        intervention_agent=intervention,
        interaction_loader=interaction_loader,
    )

    result = orchestrator.execute(
        operation="performance_intervention",
        actor={"user_id": "professor-1", "role": "professor"},
        payload={
            "student_id": "student-1",
            "course_name": "Agentic AI",
            "interaction_limit": 250,
        },
        course={
            "course_id": "course-1",
            "professor_id": "professor-1",
            "name": "Agentic AI",
        },
    )

    assert loaded == {
        "student_id": "student-1",
        "course_id": "course-1",
        "limit": 250,
    }
    assert performance.received["interactions"] == persisted
    assert performance.received["course_id"] == "course-1"
    assert intervention.received["performance_result"] == result["performance"]
    assert result["analysis_metadata"]["interactions_analyzed"] == 2
    assert result["analysis_metadata"]["sessions_included"] == 1
    assert result["analysis_metadata"]["evidence_source"] == (
        "mongodb_learning_interactions"
    )

