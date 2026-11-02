from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkflowContext:
    """Shared, request-scoped data passed between workflow steps."""

    operation: str
    actor: dict[str, Any]
    payload: dict[str, Any]
    course: dict[str, Any] | None = None
    results: dict[str, Any] = field(default_factory=dict)
