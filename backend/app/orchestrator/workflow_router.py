from dataclasses import dataclass


@dataclass(frozen=True)
class WorkflowDefinition:
    steps: tuple[str, ...]
    allowed_roles: tuple[str, ...]


# The API endpoint chooses a fixed operation. Client input never chooses
# arbitrary agent names or workflow steps.
WORKFLOWS: dict[str, WorkflowDefinition] = {
    "tutor_chat": WorkflowDefinition(
        steps=("tutor",),
        allowed_roles=("student",),
    ),
    "content_answer": WorkflowDefinition(
        steps=("content",),
        allowed_roles=("student", "professor"),
    ),
    "performance_intervention": WorkflowDefinition(
        steps=("performance", "intervention"),
        allowed_roles=("professor",),
    ),
}


class UnknownWorkflowError(ValueError):
    pass


class WorkflowRoleError(PermissionError):
    pass


def resolve_workflow(operation: str, role: str) -> WorkflowDefinition:
    """Resolve a known workflow and enforce its role allow-list."""
    definition = WORKFLOWS.get(operation)
    if definition is None:
        raise UnknownWorkflowError(f"Unsupported workflow: {operation}")

    if role not in definition.allowed_roles:
        raise WorkflowRoleError(
            f"Role '{role}' cannot execute workflow '{operation}'."
        )

    return definition
