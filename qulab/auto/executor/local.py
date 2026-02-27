"""Local code executor implementation.

Executes Python code in the local Python environment with
proper timeout control and context injection.
"""

from __future__ import annotations

import asyncio
import time
import traceback
from typing import Any

import numpy as np
from loguru import logger

from .base import CodeExecutor, ExecutionResult
from .context import ExecutionContext


class LocalCodeExecutor(CodeExecutor):
    """Local code executor for running skill code.

    This executor runs code in the local Python environment using
    exec() with a controlled namespace. It provides:

    - Timeout control via asyncio
    - Pre-configured namespace with common libraries
    - Access to world model and storage
    - Error handling and traceback capture

    Note: This executor does not provide sandboxing. It runs code
    with the same permissions as the host process.

    Example:
        ```python
        executor = LocalCodeExecutor(config)

        context = ExecutionContext(
            session_id="session_123",
            execution_id="exec_456",
            world_model=world_model,
            storage=storage
        )

        code = '''
import numpy as np
x = np.linspace(0, 10, 100)
y = np.sin(x)
result = {"x": x, "y": y}
'''

        result = await executor.execute(code, context, timeout=60.0)
        if result.success:
            print(result.data)  # {"x": array(...), "y": array(...)}
        ```
    """

    def __init__(self, config: Any = None):
        """Initialize the local executor.

        Args:
            config: Optional executor configuration
        """
        self.config = config
        self._execution_count = 0

        logger.info("LocalCodeExecutor initialized")

    async def execute(
        self,
        code: str,
        context: ExecutionContext,
        timeout: float = 600.0,
    ) -> ExecutionResult:
        """Execute Python code locally.

        Args:
            code: Python code to execute
            context: Execution context
            timeout: Maximum execution time in seconds

        Returns:
            ExecutionResult with success status and data/error
        """
        self._execution_count += 1
        start_time = time.time()

        logger.debug(f"Executing code (timeout: {timeout}s)")

        # Create execution namespace
        namespace = self.create_namespace(context)

        try:
            # Execute code with timeout
            result_data = await asyncio.wait_for(
                self._run_code(code, namespace),
                timeout=timeout,
            )

            execution_time = time.time() - start_time

            logger.debug(f"Code executed successfully in {execution_time:.2f}s")

            return ExecutionResult(
                success=True,
                data=result_data,
                namespace=namespace,
                execution_time=execution_time,
            )

        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            logger.error(f"Code execution timed out after {execution_time:.2f}s")

            return ExecutionResult(
                success=False,
                error=f"Execution timeout after {timeout}s",
                namespace=namespace,
                execution_time=execution_time,
            )

        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"{type(e).__name__}: {str(e)}"
            error_trace = traceback.format_exc()

            logger.error(f"Code execution failed: {error_msg}")
            logger.debug(f"Traceback:\n{error_trace}")

            return ExecutionResult(
                success=False,
                error=f"{error_msg}\n\nTraceback:\n{error_trace}",
                namespace=namespace,
                execution_time=execution_time,
            )

    async def _run_code(
        self,
        code: str,
        namespace: dict[str, Any],
    ) -> Any:
        """Run code in the given namespace.

        This method runs in a separate thread to avoid blocking
the event loop during execution.

        Args:
            code: Python code
            namespace: Execution namespace

        Returns:
            Result data (value of 'result' variable if set)
        """
        # Run exec in thread pool to not block event loop
        loop = asyncio.get_event_loop()

        def _exec():
            # Execute the code
            exec(code, namespace)

            # Return result if set
            return namespace.get("result", None)

        # Run in executor (thread pool)
        return await loop.run_in_executor(None, _exec)

    def create_namespace(self, context: ExecutionContext) -> dict[str, Any]:
        """Create execution namespace with injected dependencies.

        The namespace includes:
        - Standard libraries (numpy, matplotlib)
        - World model access
        - Storage access
        - Execution parameters

        Args:
            context: Execution context

        Returns:
            Namespace dictionary
        """
        namespace: dict[str, Any] = {}

        # Inject common libraries
        namespace["np"] = np

        try:
            import matplotlib.pyplot as plt

            namespace["plt"] = plt
        except ImportError:
            pass

        # Inject context access
        namespace["__context__"] = context
        namespace["get_parameter"] = context.get_parameter
        namespace["set_parameter"] = context.set_parameter

        # Inject storage access
        if context.storage:
            namespace["storage"] = context.storage
            namespace["load_dataset"] = context.load_dataset
            namespace["create_dataset"] = context.create_dataset

        # Inject world model
        if context.world_model:
            namespace["world_model"] = context.world_model

        # Inject parameters directly
        namespace.update(context.parameters)

        # Add standard library imports
        namespace["__builtins__"] = __builtins__

        return namespace

    def get_stats(self) -> dict[str, Any]:
        """Get execution statistics.

        Returns:
            Dictionary with execution statistics
        """
        return {
            "execution_count": self._execution_count,
        }
