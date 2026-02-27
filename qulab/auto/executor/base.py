"""Base code executor interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExecutionResult:
    """Result of code execution.

    Attributes:
        success: Whether execution succeeded
        data: Output data from execution
        error: Error message if failed
        namespace: Execution namespace after completion
        execution_time: Time taken to execute
    """

    success: bool
    data: Any = None
    error: str | None = None
    namespace: dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0


class CodeExecutor(ABC):
    """Abstract base class for code executors.

    Code executors are responsible for running generated Python code
    in a controlled environment with proper timeout and context management.
    """

    @abstractmethod
    async def execute(
        self,
        code: str,
        context: Any,
        timeout: float = 600.0,
    ) -> ExecutionResult:
        """Execute Python code.

        Args:
            code: Python code to execute
            context: Execution context
            timeout: Maximum execution time in seconds

        Returns:
            ExecutionResult
        """
        ...

    @abstractmethod
    def create_namespace(self, context: Any) -> dict[str, Any]:
        """Create execution namespace with injected dependencies.

        Args:
            context: Execution context

        Returns:
            Namespace dictionary
        """
        ...
