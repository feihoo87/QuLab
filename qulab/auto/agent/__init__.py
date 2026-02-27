"""Agent system for auto experiment framework.

This module provides a three-layer agent architecture:
- PlannerAgent: High-level strategy and planning
- ExecutorAgent: Experiment skill execution
- AnalysisAgent: Data analysis execution
"""

from .analyzer import AnalysisAgent, AnalysisContext, AnalysisResult
from .executor import ExecutorAgent, ExecutionContext, ExecutionResult
from .loop import AgentConfig, AgentEvent, AgentLoop
from .memory import SessionMemory
from .planner import ExecutionPlan, PlanStatus, PlanStep, PlannerAgent

__all__ = [
    # Original classes
    "AgentLoop",
    "AgentConfig",
    "AgentEvent",
    "SessionMemory",
    # Planner Agent
    "PlannerAgent",
    "ExecutionPlan",
    "PlanStep",
    "PlanStatus",
    # Executor Agent
    "ExecutorAgent",
    "ExecutionContext",
    "ExecutionResult",
    # Analysis Agent
    "AnalysisAgent",
    "AnalysisContext",
    "AnalysisResult",
]
