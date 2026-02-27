"""Planner Agent for high-level experiment strategy.

The Planner Agent is responsible for:
- Understanding experimental goals from natural language
- Selecting appropriate Skills from the registry
- Creating execution plans with dependency resolution
- Detecting oscillations and adjusting strategy
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from loguru import logger

from ..bus import Event, EventType, MessageBus
from ..skills import Skill


class PlanStatus(Enum):
    """Status of an execution plan."""

    PENDING = auto()
    IN_PROGRESS = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


@dataclass
class PlanStep:
    """A single step in an execution plan.

    Attributes:
        step_id: Unique step identifier
        skill_id: ID of the skill to execute
        skill_type: Type of skill (experiment/analysis)
        parameters: Parameters for the skill
        depends_on: List of step IDs this step depends on
        description: Human-readable description
        fallback_step: Step ID to execute if this step fails
    """

    step_id: str
    skill_id: str
    skill_type: str  # "experiment" or "analysis"
    parameters: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    description: str = ""
    fallback_step: str | None = None
    status: PlanStatus = PlanStatus.PENDING
    result: Any = None


@dataclass
class ExecutionPlan:
    """An execution plan for achieving an experimental goal.

    Attributes:
        plan_id: Unique plan identifier
        goal: Original goal description
        steps: List of plan steps
        status: Overall plan status
        created_at: Creation timestamp
        completed_at: Completion timestamp
        metadata: Additional metadata
    """

    plan_id: str
    goal: str
    steps: list[PlanStep] = field(default_factory=list)
    status: PlanStatus = PlanStatus.PENDING
    created_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert plan to dictionary."""
        return {
            "plan_id": self.plan_id,
            "goal": self.goal,
            "steps": [
                {
                    "step_id": s.step_id,
                    "skill_id": s.skill_id,
                    "skill_type": s.skill_type,
                    "parameters": s.parameters,
                    "depends_on": s.depends_on,
                    "description": s.description,
                    "status": s.status.name,
                }
                for s in self.steps
            ],
            "status": self.status.name,
            "created_at": self.created_at,
        }


class PlannerAgent:
    """Strategy layer Agent for experiment planning.

    The Planner Agent understands experimental goals, selects appropriate
    Skills from the registry, and creates execution plans. It works with
    the World Model to get current state and maintains an audit log of
    its decisions.

    Example:
        ```python
        planner = PlannerAgent(
            llm=llm_provider,
            skill_registry=skill_registry,
            world_model=world_model,
            bus=message_bus
        )

        # Create a plan
        plan = await planner.plan(
            goal="Measure T1 relaxation time for qubit 1",
            context={"session_id": "session_123"}
        )

        # Get next step to execute
        step = planner.get_next_step(plan)
        ```
    """

    def __init__(
        self,
        llm,
        skill_registry,
        world_model,
        bus: MessageBus | None = None,
        memory=None,
    ):
        """Initialize the Planner Agent.

        Args:
            llm: LLM provider for reasoning
            skill_registry: Registry of available skills
            world_model: World Model for state access
            bus: Optional MessageBus for event publishing
            memory: Optional memory system for lessons
        """
        self.llm = llm
        self.skills = skill_registry
        self.world_model = world_model
        self.bus = bus
        self.memory = memory

        logger.info("Planner Agent initialized")

    async def plan(
        self,
        goal: str,
        context: dict[str, Any],
        max_steps: int = 10,
    ) -> ExecutionPlan:
        """Create an execution plan for the given goal.

        Args:
            goal: Natural language goal description
            context: Execution context (session_id, etc.)
            max_steps: Maximum number of steps in the plan

        Returns:
            ExecutionPlan instance
        """
        import uuid

        plan_id = str(uuid.uuid4())

        logger.info(f"Creating plan for goal: {goal}")

        # 1. Get current state from World Model
        state = self.world_model.get_experiment_state()
        parameters = self.world_model.query_parameters()

        # 2. Query relevant lessons from memory
        lessons = []
        if self.memory:
            lessons = await self._query_lessons(goal)

        # 3. Find relevant skills
        available_skills = self._find_relevant_skills(goal)

        # 4. Build planning prompt
        prompt = self._build_planning_prompt(
            goal=goal,
            state=state,
            parameters=parameters,
            lessons=lessons,
            skills=available_skills,
            max_steps=max_steps,
        )

        # 5. Call LLM for planning
        try:
            response = await self.llm.chat(
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert quantum experiment planner. "
                        "Create detailed execution plans using available skills.",
                    },
                    {"role": "user", "content": prompt},
                ]
            )

            # 6. Parse the plan
            plan = self._parse_plan_response(
                response.content, plan_id, goal, available_skills
            )

        except Exception as e:
            logger.error(f"Planning failed: {e}")
            # Create a minimal fallback plan
            plan = self._create_fallback_plan(plan_id, goal, available_skills)

        # 7. Publish plan created event
        if self.bus:
            await self.bus.publish(
                Event(
                    type=EventType.AGENT_PLAN_CREATED,
                    payload={
                        "plan_id": plan_id,
                        "goal": goal,
                        "step_count": len(plan.steps),
                    },
                    session_id=context.get("session_id", "default"),
                    source="planner_agent",
                )
            )

        return plan

    def get_next_step(self, plan: ExecutionPlan) -> PlanStep | None:
        """Get the next executable step in the plan.

        A step is executable if:
        - It hasn't been executed yet (PENDING status)
        - All its dependencies are completed

        Args:
            plan: The execution plan

        Returns:
            Next executable step or None
        """
        # Build set of completed step IDs
        completed = {
            s.step_id for s in plan.steps if s.status == PlanStatus.COMPLETED
        }

        for step in plan.steps:
            if step.status != PlanStatus.PENDING:
                continue

            # Check if all dependencies are met
            if all(dep in completed for dep in step.depends_on):
                return step

        return None

    def update_step_status(
        self,
        plan: ExecutionPlan,
        step_id: str,
        status: PlanStatus,
        result: Any = None,
    ) -> None:
        """Update the status of a plan step.

        Args:
            plan: The execution plan
            step_id: ID of the step to update
            status: New status
            result: Optional result data
        """
        for step in plan.steps:
            if step.step_id == step_id:
                step.status = status
                step.result = result
                logger.debug(f"Step {step_id} status updated to {status.name}")
                break

        # Update overall plan status
        self._update_plan_status(plan)

    def _update_plan_status(self, plan: ExecutionPlan) -> None:
        """Update the overall plan status based on step statuses.

        Args:
            plan: The execution plan
        """
        if not plan.steps:
            plan.status = PlanStatus.COMPLETED
            return

        statuses = [s.status for s in plan.steps]

        if all(s == PlanStatus.COMPLETED for s in statuses):
            plan.status = PlanStatus.COMPLETED
            plan.completed_at = time.time()
        elif any(s == PlanStatus.FAILED for s in statuses):
            plan.status = PlanStatus.FAILED
            plan.completed_at = time.time()
        elif any(s == PlanStatus.IN_PROGRESS for s in statuses):
            plan.status = PlanStatus.IN_PROGRESS
        else:
            plan.status = PlanStatus.PENDING

    async def replan(
        self,
        plan: ExecutionPlan,
        reason: str,
        context: dict[str, Any],
    ) -> ExecutionPlan:
        """Create a revised plan based on execution feedback.

        Args:
            plan: The original plan
            reason: Reason for replanning
            context: Execution context

        Returns:
            Revised ExecutionPlan
        """
        logger.info(f"Replanning due to: {reason}")

        # Build replanning prompt with history
        prompt = self._build_replanning_prompt(plan, reason)

        try:
            response = await self.llm.chat(
                messages=[
                    {
                        "role": "system",
                        "content": "Revise the execution plan based on feedback.",
                    },
                    {"role": "user", "content": prompt},
                ]
            )

            # Parse new plan
            available_skills = self._find_relevant_skills(plan.goal)
            new_plan = self._parse_plan_response(
                response.content,
                plan.plan_id,
                plan.goal,
                available_skills,
            )

            return new_plan

        except Exception as e:
            logger.error(f"Replanning failed: {e}")
            return plan  # Return original plan on failure

    def _find_relevant_skills(self, goal: str) -> list[Skill]:
        """Find skills relevant to the goal.

        Args:
            goal: Goal description

        Returns:
            List of relevant skills
        """
        if not self.skills:
            return []

        # Try to match by querying the registry
        try:
            return self.skills.query_for_goal(goal)
        except Exception as e:
            logger.warning(f"Skill query failed: {e}")
            # Fallback: return all skills
            try:
                return list(self.skills._skills.values())
            except AttributeError:
                return []

    async def _query_lessons(self, goal: str) -> list[dict]:
        """Query relevant lessons from memory.

        Args:
            goal: Goal description

        Returns:
            List of relevant lessons
        """
        if not self.memory:
            return []

        try:
            return await self.memory.query_lessons(goal)
        except Exception as e:
            logger.warning(f"Lesson query failed: {e}")
            return []

    def _build_planning_prompt(
        self,
        goal: str,
        state: Any,
        parameters: dict[str, Any],
        lessons: list[dict],
        skills: list[Skill],
        max_steps: int,
    ) -> str:
        """Build the planning prompt for the LLM.

        Args:
            goal: User's goal
            state: Current experiment state
            parameters: Current parameters
            lessons: Relevant lessons
            skills: Available skills
            max_steps: Maximum steps

        Returns:
            Planning prompt
        """
        lines = [
            "# Experiment Planning Request",
            "",
            f"## Goal\n{goal}",
            "",
            "## Current State",
            f"- Status: {state.status.name if hasattr(state, 'status') else 'unknown'}",
            "",
            "## Available Parameters",
        ]

        # Add parameters
        if parameters:
            for path, param in list(parameters.items())[:10]:  # Limit to first 10
                expired = " (EXPIRED)" if param.is_expired() else ""
                lines.append(f"- {path}: {param.value} (conf: {param.confidence:.2f}){expired}")
        else:
            lines.append("(no parameters available)")

        # Add relevant lessons
        if lessons:
            lines.extend(["", "## Relevant Lessons"])
            for lesson in lessons[:5]:
                lines.append(f"- {lesson.get('content', '')}")

        # Add available skills
        lines.extend(["", "## Available Skills"])
        for skill in skills:
            lines.append(f"- {skill.id}: {skill.description[:100]}...")

        # Add instructions
        lines.extend([
            "",
            "## Instructions",
            f"Create an execution plan with at most {max_steps} steps.",
            "For each step, specify:",
            "1. The skill to use",
            "2. Required parameters",
            "3. Dependencies on previous steps",
            "4. A brief description",
            "",
            "Respond with a structured plan in this format:",
            "```",
            "Step 1: <skill_id>",
            "  Description: <what this step does>",
            "  Parameters: <key=value pairs>",
            "  Depends on: <step numbers>",
            "",
            "Step 2: <skill_id>",
            "  ...",
            "```",
        ])

        return "\n".join(lines)

    def _build_replanning_prompt(self, plan: ExecutionPlan, reason: str) -> str:
        """Build a prompt for replanning.

        Args:
            plan: Original plan
            reason: Reason for replanning

        Returns:
            Replanning prompt
        """
        lines = [
            "# Replanning Request",
            "",
            f"## Original Goal\n{plan.goal}",
            "",
            f"## Reason for Replanning\n{reason}",
            "",
            "## Executed Steps",
        ]

        for step in plan.steps:
            if step.status == PlanStatus.COMPLETED:
                lines.append(f"- Step {step.step_id}: {step.skill_id} (COMPLETED)")
            elif step.status == PlanStatus.FAILED:
                lines.append(f"- Step {step.step_id}: {step.skill_id} (FAILED)")

        lines.extend([
            "",
            "## Remaining Steps",
        ])

        for step in plan.steps:
            if step.status == PlanStatus.PENDING:
                lines.append(f"- Step {step.step_id}: {step.skill_id}")

        lines.extend([
            "",
            "Please revise the plan to address the issue.",
            "Consider:",
            "- Using alternative skills",
            "- Adding verification steps",
            "- Adjusting parameters",
        ])

        return "\n".join(lines)

    def _parse_plan_response(
        self,
        content: str,
        plan_id: str,
        goal: str,
        available_skills: list[Skill],
    ) -> ExecutionPlan:
        """Parse the LLM's plan response.

        Args:
            content: LLM response content
            plan_id: Plan ID
            goal: Original goal
            available_skills: Available skills for lookup

        Returns:
            ExecutionPlan
        """
        steps = []
        skill_map = {s.id: s for s in available_skills}

        # Simple parsing - look for Step patterns
        import re

        step_pattern = r"Step\s+(\d+)\s*[:\.]\s*(\S+)"
        current_step = None

        lines = content.split("\n")

        for line in lines:
            line = line.strip()

            # Check for step header
            match = re.match(step_pattern, line, re.IGNORECASE)
            if match:
                if current_step:
                    steps.append(current_step)

                step_num = match.group(1)
                skill_id = match.group(2)

                # Determine skill type
                skill = skill_map.get(skill_id)
                skill_type = skill.type if skill else "unknown"

                current_step = PlanStep(
                    step_id=f"step_{step_num}",
                    skill_id=skill_id,
                    skill_type=skill_type,
                )

            elif current_step:
                # Parse step details
                if line.lower().startswith("description:"):
                    current_step.description = line.split(":", 1)[1].strip()
                elif line.lower().startswith("parameters:"):
                    params_str = line.split(":", 1)[1].strip()
                    current_step.parameters = self._parse_parameters(params_str)
                elif line.lower().startswith("depends on:"):
                    deps_str = line.split(":", 1)[1].strip()
                    current_step.depends_on = self._parse_dependencies(
                        deps_str, len(steps)
                    )

        # Add last step
        if current_step:
            steps.append(current_step)

        return ExecutionPlan(
            plan_id=plan_id,
            goal=goal,
            steps=steps,
        )

    def _parse_parameters(self, params_str: str) -> dict[str, Any]:
        """Parse parameter string into dictionary.

        Args:
            params_str: Parameter string

        Returns:
            Parameter dictionary
        """
        params = {}
        # Simple parsing: key=value, key=value
        for pair in params_str.split(","):
            if "=" in pair:
                key, value = pair.split("=", 1)
                params[key.strip()] = value.strip()
        return params

    def _parse_dependencies(self, deps_str: str, current_count: int) -> list[str]:
        """Parse dependency string into list of step IDs.

        Args:
            deps_str: Dependency string
            current_count: Current number of steps

        Returns:
            List of step IDs
        """
        if not deps_str or deps_str.lower() in ("none", ""):
            return []

        deps = []
        for part in deps_str.split(","):
            part = part.strip()
            if part.isdigit():
                deps.append(f"step_{part}")
        return deps

    def _create_fallback_plan(
        self,
        plan_id: str,
        goal: str,
        available_skills: list[Skill],
    ) -> ExecutionPlan:
        """Create a minimal fallback plan when planning fails.

        Args:
            plan_id: Plan ID
            goal: Original goal
            available_skills: Available skills

        Returns:
            Basic execution plan
        """
        steps = []

        # Try to find a matching skill
        for skill in available_skills:
            if skill.type == "experiment":
                steps.append(
                    PlanStep(
                        step_id="step_1",
                        skill_id=skill.id,
                        skill_type=skill.type,
                        description=f"Execute {skill.name} based on goal",
                    )
                )
                break

        return ExecutionPlan(
            plan_id=plan_id,
            goal=goal,
            steps=steps,
            status=PlanStatus.PENDING if steps else PlanStatus.FAILED,
        )
