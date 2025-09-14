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
        self._plans_by_session = {}  # Session-scoped storage: {session_id: {plan_id: plan_data}}
        self._current_session_id = None  # Track current session

    def set_session_context(self, session_id: str) -> None:
        """Set the current session context for plan operations."""
        self._current_session_id = session_id

    def set_memory(self, memory) -> None:
        """Set the conversation memory reference for plan persistence."""
        self.memory = memory

    def _get_session_plans(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Get plans for a specific session."""
        session_id = session_id or self._current_session_id
        if not session_id:
            return {}

        if session_id not in self._plans_by_session:
            self._plans_by_session[session_id] = {}
        return self._plans_by_session[session_id]

    def _store_plan_in_memory(self, plan: Dict[str, Any], session_id: Optional[str] = None) -> None:
        """Store plan in conversation memory if available."""
        try:
            # Try to get memory from the tool instance
            memory = getattr(self, 'memory', None)

            if memory:
                from app.agents.personal_assistant.memory import EntityContext, EntityType
                from datetime import datetime

                plan_entity = EntityContext(
                    entity_id=plan['id'],
                    entity_type=EntityType.PLAN,
                    display_name=plan['title'],
                    data=plan,
                    created_at=datetime.utcnow(),
                    last_accessed=datetime.utcnow(),
                    source_tool="planning"
                )
                memory.store_entity(plan_entity)
                logger.debug(f"Stored plan {plan['id']} in conversation memory")
            else:
                logger.debug("No memory reference available for plan storage")
        except Exception as e:
            logger.warning(f"Failed to store plan in memory: {str(e)}")

    async def execute(self, parameters: Dict[str, Any]) -> Any:
        """
        Execute planning operations.

        Parameters:
            action (str): Action to perform - 'create', 'update', 'get', 'list'
            task (str): Task description for 'create' action
            complexity (str): Task complexity - 'simple', 'medium', 'complex'
            plan_id (str, optional): Plan ID for 'update', 'get' actions
            updates (dict, optional): Updates for 'update' action
            session_id (str, optional): Session ID for session-scoped operations

        Returns:
            Planning result
        """
        if not self.validate_parameters(parameters):
            return await self.handle_error(
                ValueError("Invalid parameters"),
                "Parameter validation failed"
            )

        action = parameters.get("action", "create").lower()
        session_id = parameters.get("session_id")

        # Set session context if provided
        if session_id:
            self.set_session_context(session_id)

        try:
            if action == "create":
                task = parameters.get("task")
                if not task:
                    return await self.handle_error(
                        ValueError("task is required for 'create' action"),
                        "Missing task description"
                    )
                complexity = parameters.get("complexity", "medium")
                return await self._create_plan(task, complexity, session_id)

            elif action == "update":
                plan_id = parameters.get("plan_id")
                updates = parameters.get("updates", {})
                if not plan_id:
                    return await self.handle_error(
                        ValueError("plan_id is required for 'update' action"),
                        "Missing plan ID"
                    )
                return await self._update_plan(plan_id, updates, session_id)

            elif action == "get":
                plan_id = parameters.get("plan_id")
                if not plan_id:
                    return await self.handle_error(
                        ValueError("plan_id is required for 'get' action"),
                        "Missing plan ID"
                    )
                return await self._get_plan(plan_id, session_id)

            elif action == "list":
                return await self._list_plans(session_id)

            else:
                return await self.handle_error(
                    ValueError(f"Unknown action: {action}"),
                    "Invalid action"
                )

        except Exception as e:
            return await self.handle_error(e, f"Action: {action}")

    async def _create_plan(self, task_description: str, complexity: str, session_id: Optional[str] = None) -> Dict[str, Any]:
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

            # Store plan in session-scoped storage
            session_plans = self._get_session_plans(session_id)
            session_plans[plan_id] = plan

            # Store plan in conversation memory for persistence
            self._store_plan_in_memory(plan, session_id)

            return await self.create_success_response({
                "plan": plan,  # Return full plan content
                "plan_id": plan_id,
                "message": f"Created plan '{plan['title']}' with {len(subtasks)} subtasks",
                "next_steps": self._get_next_steps(plan),
                "usage_tip": f"To retrieve this plan later, use plan_id: {plan_id} or search by title: '{plan['title']}'"
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

    async def _update_plan(self, plan_id: str, updates: Dict[str, Any], session_id: Optional[str] = None) -> Dict[str, Any]:
        """Update an existing plan."""
        try:
            session_plans = self._get_session_plans(session_id)

            if plan_id not in session_plans:
                return await self.handle_error(
                    ValueError(f"Plan not found: {plan_id}"),
                    "Plan not found"
                )

            plan = session_plans[plan_id]

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

    async def _get_plan(self, plan_id: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Get a specific plan by ID or search by description."""
        try:
            session_plans = self._get_session_plans(session_id)

            # First try exact UUID match
            if plan_id in session_plans:
                plan = session_plans[plan_id]
                return await self.create_success_response({
                    "plan": plan,
                    "next_steps": self._get_next_steps(plan)
                })

            # If not found by UUID, try to find by title/description match
            plan_id_lower = plan_id.lower()
            matching_plans = []

            for stored_plan_id, plan in session_plans.items():
                title_lower = plan.get("title", "").lower()
                description_lower = plan.get("description", "").lower()

                # Check if the search term appears in title or description
                if (plan_id_lower in title_lower or
                    plan_id_lower in description_lower or
                    any(word in title_lower for word in plan_id_lower.split()) or
                    any(word in description_lower for word in plan_id_lower.split())):
                    matching_plans.append((stored_plan_id, plan))

            if len(matching_plans) == 1:
                # Found exactly one match
                plan_id, plan = matching_plans[0]
                return await self.create_success_response({
                    "plan": plan,
                    "next_steps": self._get_next_steps(plan),
                    "message": f"Found plan: {plan['title']}"
                })
            elif len(matching_plans) > 1:
                # Multiple matches - return list of options
                plan_summaries = [
                    {
                        "id": pid,
                        "title": p["title"],
                        "description": p["description"],
                        "status": p["status"]
                    }
                    for pid, p in matching_plans
                ]
                return await self.create_success_response({
                    "message": f"Found {len(matching_plans)} matching plans",
                    "matching_plans": plan_summaries,
                    "suggestion": "Please specify which plan you want by using its exact title or ID"
                })
            else:
                # No matches found
                if session_plans:
                    available_plans = [
                        {
                            "id": pid,
                            "title": p["title"],
                            "status": p["status"]
                        }
                        for pid, p in session_plans.items()
                    ]
                    return await self.create_success_response({
                        "message": f"No plan found matching '{plan_id}'",
                        "available_plans": available_plans,
                        "suggestion": "Use the 'list' action to see all available plans"
                    })
                else:
                    return await self.handle_error(
                        ValueError("No plans have been created yet"),
                        "No plans available"
                    )

        except Exception as e:
            return await self.handle_error(e, "Getting plan")

    async def _list_plans(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """List all plans for the session."""
        try:
            session_plans = self._get_session_plans(session_id)
            plans_summary = []

            for plan_id, plan in session_plans.items():
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