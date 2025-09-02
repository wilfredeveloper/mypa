"""
Planning Tool for Personal Assistant - Task decomposition and planning.
"""

import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from enum import Enum
import logging

from app.agents.personal_assistant.tools.base import BaseTool

logger = logging.getLogger(__name__)


class TaskComplexity(str, Enum):
    """Task complexity levels."""
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


class TaskPriority(str, Enum):
    """Task priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TaskStatus(str, Enum):
    """Task status options."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class PlanningTool(BaseTool):
    """
    Tool for breaking down complex requests into actionable steps.

    This tool provides:
    - Task decomposition with dependency tracking
    - Priority assignment and scheduling
    - Progress tracking and status updates
    - Resource estimation and planning
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._session_plans = {}  # In-memory storage for session plans

    async def execute(self, parameters: Dict[str, Any]) -> Any:
        """
        Execute planning operations.

        Parameters:
            action (str): Action to perform - 'create', 'update', 'get', 'list'
            task (str): Task description for 'create' action
            complexity (str): Task complexity - 'simple', 'medium', 'complex'
            plan_id (str, optional): Plan ID for 'update', 'get' actions
            updates (dict, optional): Updates for 'update' action

        Returns:
            Planning result
        """
        if not self.validate_parameters(parameters):
            return await self.handle_error(
                ValueError("Invalid parameters"),
                "Parameter validation failed"
            )

        action = parameters.get("action", "create").lower()

        try:
            if action == "create":
                task = parameters.get("task")
                if not task:
                    return await self.handle_error(
                        ValueError("task is required for 'create' action"),
                        "Missing task description"
                    )
                complexity = parameters.get("complexity", "medium")
                return await self._create_plan(task, complexity)

            elif action == "update":
                plan_id = parameters.get("plan_id")
                updates = parameters.get("updates", {})
                if not plan_id:
                    return await self.handle_error(
                        ValueError("plan_id is required for 'update' action"),
                        "Missing plan ID"
                    )
                return await self._update_plan(plan_id, updates)

            elif action == "get":
                plan_id = parameters.get("plan_id")
                if not plan_id:
                    return await self.handle_error(
                        ValueError("plan_id is required for 'get' action"),
                        "Missing plan ID"
                    )
                return await self._get_plan(plan_id)

            elif action == "list":
                return await self._list_plans()

            else:
                return await self.handle_error(
                    ValueError(f"Unknown action: {action}"),
                    "Invalid action"
                )

        except Exception as e:
            return await self.handle_error(e, f"Action: {action}")

    async def _create_plan(self, task_description: str, complexity: str) -> Dict[str, Any]:
        """Create a new task plan with decomposition."""
        try:
            # Validate complexity
            if complexity not in [c.value for c in TaskComplexity]:
                complexity = TaskComplexity.MEDIUM.value

            # Generate plan ID
            plan_id = str(uuid.uuid4())

            # Decompose task based on complexity
            subtasks = await self._decompose_task(task_description, TaskComplexity(complexity))

            # Create plan structure
            plan = {
                "id": plan_id,
                "title": task_description,
                "description": f"Plan for: {task_description}",
                "complexity": complexity,
                "status": TaskStatus.PENDING.value,
                "priority": self._determine_priority(task_description, complexity),
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
                "estimated_duration_minutes": self._estimate_duration(subtasks),
                "subtasks": subtasks,
                "dependencies": self._identify_dependencies(subtasks),
                "resources_needed": self._identify_resources(task_description, subtasks),
                "progress": {
                    "completed_tasks": 0,
                    "total_tasks": len(subtasks),
                    "completion_percentage": 0
                }
            }

            # Store plan in session
            self._session_plans[plan_id] = plan

            return await self.create_success_response({
                "plan": plan,
                "message": f"Created plan with {len(subtasks)} subtasks",
                "next_steps": self._get_next_steps(plan)
            })

        except Exception as e:
            return await self.handle_error(e, "Creating plan")

    async def _decompose_task(self, task_description: str, complexity: TaskComplexity) -> List[Dict[str, Any]]:
        """Decompose a task into subtasks based on complexity."""
        subtasks = []

        # Basic task decomposition logic
        if complexity == TaskComplexity.SIMPLE:
            # Simple tasks get 1-3 subtasks
            subtasks = [
                {
                    "id": str(uuid.uuid4()),
                    "title": f"Complete: {task_description}",
                    "description": task_description,
                    "status": TaskStatus.PENDING.value,
                    "priority": TaskPriority.MEDIUM.value,
                    "estimated_minutes": 15,
                    "dependencies": [],
                    "order": 1
                }
            ]

        elif complexity == TaskComplexity.MEDIUM:
            # Medium tasks get 3-6 subtasks
            subtasks = [
                {
                    "id": str(uuid.uuid4()),
                    "title": f"Plan and prepare for: {task_description}",
                    "description": "Initial planning and preparation phase",
                    "status": TaskStatus.PENDING.value,
                    "priority": TaskPriority.HIGH.value,
                    "estimated_minutes": 20,
                    "dependencies": [],
                    "order": 1
                },
                {
                    "id": str(uuid.uuid4()),
                    "title": f"Execute main work for: {task_description}",
                    "description": "Main execution phase",
                    "status": TaskStatus.PENDING.value,
                    "priority": TaskPriority.HIGH.value,
                    "estimated_minutes": 45,
                    "dependencies": [],
                    "order": 2
                },
                {
                    "id": str(uuid.uuid4()),
                    "title": f"Review and finalize: {task_description}",
                    "description": "Review and completion phase",
                    "status": TaskStatus.PENDING.value,
                    "priority": TaskPriority.MEDIUM.value,
                    "estimated_minutes": 15,
                    "dependencies": [],
                    "order": 3
                }
            ]

        else:  # COMPLEX
            # Complex tasks get 6+ subtasks
            subtasks = [
                {
                    "id": str(uuid.uuid4()),
                    "title": f"Research and analysis for: {task_description}",
                    "description": "Initial research and requirement analysis",
                    "status": TaskStatus.PENDING.value,
                    "priority": TaskPriority.HIGH.value,
                    "estimated_minutes": 60,
                    "dependencies": [],
                    "order": 1
                },
                {
                    "id": str(uuid.uuid4()),
                    "title": f"Create detailed plan for: {task_description}",
                    "description": "Detailed planning and design phase",
                    "status": TaskStatus.PENDING.value,
                    "priority": TaskPriority.HIGH.value,
                    "estimated_minutes": 45,
                    "dependencies": [],
                    "order": 2
                },
                {
                    "id": str(uuid.uuid4()),
                    "title": f"Gather resources for: {task_description}",
                    "description": "Resource gathering and preparation",
                    "status": TaskStatus.PENDING.value,
                    "priority": TaskPriority.MEDIUM.value,
                    "estimated_minutes": 30,
                    "dependencies": [],
                    "order": 3
                },
                {
                    "id": str(uuid.uuid4()),
                    "title": f"Execute phase 1 of: {task_description}",
                    "description": "First execution phase",
                    "status": TaskStatus.PENDING.value,
                    "priority": TaskPriority.HIGH.value,
                    "estimated_minutes": 90,
                    "dependencies": [],
                    "order": 4
                },
                {
                    "id": str(uuid.uuid4()),
                    "title": f"Execute phase 2 of: {task_description}",
                    "description": "Second execution phase",
                    "status": TaskStatus.PENDING.value,
                    "priority": TaskPriority.HIGH.value,
                    "estimated_minutes": 90,
                    "dependencies": [],
                    "order": 5
                },
                {
                    "id": str(uuid.uuid4()),
                    "title": f"Test and validate: {task_description}",
                    "description": "Testing and validation phase",
                    "status": TaskStatus.PENDING.value,
                    "priority": TaskPriority.HIGH.value,
                    "estimated_minutes": 45,
                    "dependencies": [],
                    "order": 6
                },
                {
                    "id": str(uuid.uuid4()),
                    "title": f"Finalize and document: {task_description}",
                    "description": "Final review and documentation",
                    "status": TaskStatus.PENDING.value,
                    "priority": TaskPriority.MEDIUM.value,
                    "estimated_minutes": 30,
                    "dependencies": [],
                    "order": 7
                }
            ]

        return subtasks

    def _determine_priority(self, task_description: str, complexity: str) -> str:
        """Determine task priority based on description and complexity."""
        task_lower = task_description.lower()

        # Check for urgent keywords
        urgent_keywords = ["urgent", "asap", "immediately", "emergency", "critical"]
        if any(keyword in task_lower for keyword in urgent_keywords):
            return TaskPriority.URGENT.value

        # Check for high priority keywords
        high_keywords = ["important", "priority", "deadline", "due", "meeting"]
        if any(keyword in task_lower for keyword in high_keywords):
            return TaskPriority.HIGH.value

        # Complex tasks default to high priority
        if complexity == TaskComplexity.COMPLEX.value:
            return TaskPriority.HIGH.value

        return TaskPriority.MEDIUM.value

    def _estimate_duration(self, subtasks: List[Dict[str, Any]]) -> int:
        """Estimate total duration in minutes."""
        return sum(task.get("estimated_minutes", 30) for task in subtasks)

    def _identify_dependencies(self, subtasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify dependencies between subtasks."""
        dependencies = []

        # For now, create simple sequential dependencies
        for i, task in enumerate(subtasks):
            if i > 0:
                dependencies.append({
                    "task_id": task["id"],
                    "depends_on": [subtasks[i-1]["id"]],
                    "dependency_type": "sequential"
                })

        return dependencies

    def _identify_resources(self, task_description: str, subtasks: List[Dict[str, Any]]) -> List[str]:
        """Identify resources needed for the task."""
        resources = ["time", "attention"]

        task_lower = task_description.lower()

        # Add resources based on task content
        if any(word in task_lower for word in ["email", "message", "contact"]):
            resources.append("email_access")

        if any(word in task_lower for word in ["calendar", "schedule", "meeting", "appointment"]):
            resources.append("calendar_access")

        if any(word in task_lower for word in ["research", "information", "data"]):
            resources.append("internet_access")

        if any(word in task_lower for word in ["document", "file", "report", "write"]):
            resources.append("document_editor")

        return list(set(resources))

    def _get_next_steps(self, plan: Dict[str, Any]) -> List[str]:
        """Get immediate next steps for the plan."""
        next_steps = []

        # Find first pending task
        pending_tasks = [task for task in plan["subtasks"] if task["status"] == TaskStatus.PENDING.value]

        if pending_tasks:
            # Sort by order
            pending_tasks.sort(key=lambda x: x.get("order", 0))
            first_task = pending_tasks[0]

            next_steps.append(f"Start with: {first_task['title']}")
            next_steps.append(f"Estimated time: {first_task['estimated_minutes']} minutes")

            if len(pending_tasks) > 1:
                next_steps.append(f"Then proceed to: {pending_tasks[1]['title']}")

        return next_steps

    async def _update_plan(self, plan_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing plan."""
        try:
            if plan_id not in self._session_plans:
                return await self.handle_error(
                    ValueError(f"Plan not found: {plan_id}"),
                    "Plan not found"
                )

            plan = self._session_plans[plan_id]

            # Update plan fields
            for key, value in updates.items():
                if key in ["status", "priority", "description"]:
                    plan[key] = value
                elif key == "subtask_updates":
                    # Update specific subtasks
                    for subtask_update in value:
                        subtask_id = subtask_update.get("id")
                        for subtask in plan["subtasks"]:
                            if subtask["id"] == subtask_id:
                                subtask.update(subtask_update)
                                break

            # Update progress
            completed_tasks = sum(1 for task in plan["subtasks"] if task["status"] == TaskStatus.COMPLETED.value)
            plan["progress"] = {
                "completed_tasks": completed_tasks,
                "total_tasks": len(plan["subtasks"]),
                "completion_percentage": int((completed_tasks / len(plan["subtasks"])) * 100)
            }

            plan["updated_at"] = datetime.utcnow().isoformat()

            return await self.create_success_response({
                "plan": plan,
                "message": "Plan updated successfully",
                "next_steps": self._get_next_steps(plan)
            })

        except Exception as e:
            return await self.handle_error(e, "Updating plan")

    async def _get_plan(self, plan_id: str) -> Dict[str, Any]:
        """Get a specific plan."""
        try:
            if plan_id not in self._session_plans:
                return await self.handle_error(
                    ValueError(f"Plan not found: {plan_id}"),
                    "Plan not found"
                )

            plan = self._session_plans[plan_id]

            return await self.create_success_response({
                "plan": plan,
                "next_steps": self._get_next_steps(plan)
            })

        except Exception as e:
            return await self.handle_error(e, "Getting plan")

    async def _list_plans(self) -> Dict[str, Any]:
        """List all plans for the session."""
        try:
            plans_summary = []

            for plan_id, plan in self._session_plans.items():
                plans_summary.append({
                    "id": plan["id"],
                    "title": plan["title"],
                    "status": plan["status"],
                    "priority": plan["priority"],
                    "complexity": plan["complexity"],
                    "progress": plan["progress"],
                    "created_at": plan["created_at"],
                    "estimated_duration_minutes": plan["estimated_duration_minutes"]
                })

            # Sort by creation date (newest first)
            plans_summary.sort(key=lambda x: x["created_at"], reverse=True)

            return await self.create_success_response({
                "plans": plans_summary,
                "total_count": len(plans_summary),
                "active_plans": len([p for p in plans_summary if p["status"] != TaskStatus.COMPLETED.value])
            })

        except Exception as e:
            return await self.handle_error(e, "Listing plans")