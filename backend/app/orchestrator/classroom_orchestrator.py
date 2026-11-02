from typing import Any, Callable

from backend.app.orchestrator.workflow_context import WorkflowContext
from backend.app.orchestrator.workflow_router import resolve_workflow


class ClassroomOrchestrator:
    """Execute approved, deterministic multi-agent workflows.

    Authentication and course authorization remain the responsibility of
    the API/dependency layer. This class coordinates already-authorized
    requests and does not trust client-supplied agent names or workflow steps.
    """

    def __init__(
        self,
        tutor_agent: Any | None = None,
        content_agent: Any | None = None,
        performance_agent: Any | None = None,
        intervention_agent: Any | None = None,
        interaction_loader: Callable[..., list[dict[str, Any]]] | None = None,
    ) -> None:
        # Resolve agents lazily so each API only loads what it needs.
        self._agents: dict[str, Any | None] = {
            "tutor": tutor_agent,
            "content": content_agent,
            "performance": performance_agent,
            "intervention": intervention_agent,
        }
        self._interaction_loader = interaction_loader
        self._handlers: dict[str, Callable[[WorkflowContext], None]] = {
            "tutor": self._run_tutor,
            "content": self._run_content,
            "performance": self._run_performance,
            "intervention": self._run_intervention,
        }

    def _get_agent(self, name: str) -> Any:
        agent = self._agents.get(name)
        if agent is not None:
            return agent

        if name == "tutor":
            from backend.app.agents.tutor_agent import TutorAgent
            agent = TutorAgent()
        elif name == "content":
            from backend.app.agents.content_agent import ContentAgent
            agent = ContentAgent()
        elif name == "performance":
            from backend.app.agents.performance_agent import PerformanceAgent
            agent = PerformanceAgent()
        elif name == "intervention":
            from backend.app.agents.intervention_agent import InterventionAgent
            agent = InterventionAgent()
        else:
            raise ValueError(f"Unknown agent: {name}")

        self._agents[name] = agent
        return agent

    def execute(
        self,
        operation: str,
        actor: dict[str, Any],
        payload: dict[str, Any],
        course: dict[str, Any] | None = None,
    ) -> Any:
        """Run the registered workflow and return its public response."""
        definition = resolve_workflow(operation, actor.get("role", ""))

        context = WorkflowContext(
            operation=operation,
            actor=actor,
            payload=payload,
            course=course,
        )

        for step in definition.steps:
            handler = self._handlers.get(step)
            if handler is None:
                raise RuntimeError(
                    f"No handler registered for workflow step: {step}"
                )
            handler(context)

        if "response" not in context.results:
            raise RuntimeError(
                f"Workflow '{operation}' produced no response."
            )

        return context.results["response"]

    def _run_tutor(self, context: WorkflowContext) -> None:
        if context.course is None:
            raise ValueError("A validated course is required for tutoring.")

        payload = context.payload
        result = self._get_agent("tutor").answer(
            student_id=context.actor["user_id"],
            course_name=context.course.get("name", "Course"),
            session_id=payload["session_id"],
            message=payload["message"],
            top_k=payload.get("top_k", 5),
            course_id=context.course["course_id"],
            professor_id=context.course["professor_id"],
        )
        context.results["tutor"] = result
        context.results["response"] = result

    def _run_content(self, context: WorkflowContext) -> None:
        if context.course is None:
            raise ValueError(
                "A validated course is required for content generation."
            )

        payload = context.payload
        result = self._get_agent("content").answer(
            payload["query"],
            course_id=context.course["course_id"],
            top_k=payload.get("top_k", 5),
        )
        if isinstance(result, dict):
            result.setdefault("course_id", context.course["course_id"])
        context.results["content"] = result
        context.results["response"] = result

    def _run_performance(self, context: WorkflowContext) -> None:
        if context.course is None:
            raise ValueError(
                "A validated course is required for performance analysis."
            )

        payload = context.payload
        student_id = payload["student_id"]
        course_id = context.course["course_id"]

        # Learning evidence is loaded from MongoDB, never accepted from the
        # professor's request body. The API has already verified course
        # ownership and the student's active enrollment.
        loader = self._interaction_loader
        if loader is None:
            from backend.app.memory.learning_store import (
                get_student_course_interactions,
            )
            loader = get_student_course_interactions

        interactions = loader(
            student_id=student_id,
            course_id=course_id,
            limit=payload.get("interaction_limit", 500),
        )

        result = self._get_agent("performance").analyze(
            student_id=student_id,
            course_name=context.course.get("name", "Course"),
            interactions=interactions,
            course_context=payload.get("course_context"),
            course_id=course_id,
        )
        context.results["performance"] = result
        context.results["analysis_metadata"] = {
            "course_id": course_id,
            "student_id": student_id,
            "interactions_analyzed": len(interactions),
            "sessions_included": len({
                item.get("session_id")
                for item in interactions
                if item.get("session_id")
            }),
            "evidence_source": "mongodb_learning_interactions",
        }

    def _run_intervention(self, context: WorkflowContext) -> None:
        performance_result = context.results.get("performance")
        if performance_result is None:
            raise RuntimeError(
                "Intervention step requires a completed performance analysis."
            )

        diagnosis = performance_result.get("diagnosis", {})
        if (
            not diagnosis.get("concepts")
            and not diagnosis.get("strengths")
            and not diagnosis.get("weaknesses")
            and diagnosis.get("confidence") == "low"
        ):
            context.results["intervention"] = None
            context.results["response"] = {
                "performance": performance_result,
                "intervention": None,
                "analysis_metadata": {
                    **context.results.get("analysis_metadata", {}),
                    "status": "insufficient_evidence",
                },
            }
            return

        result = self._get_agent("intervention").analyze(
            performance_result=performance_result,
            course_context=context.payload.get("course_context"),
        )
        context.results["intervention"] = result
        context.results["response"] = {
            "performance": performance_result,
            "intervention": result,
            "analysis_metadata": context.results.get(
                "analysis_metadata", {}
            ),
        }
