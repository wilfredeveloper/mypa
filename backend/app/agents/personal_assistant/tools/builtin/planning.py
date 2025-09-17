"""
Planning Tool for Personal Assistant - Task decomposition and planning.
"""

import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from enum import Enum
import logging
import json
import re

from app.agents.personal_assistant.tools.base import BaseTool
from utils.baml_utils import BAMLGeminiLLM

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
    Enhanced tool for strategic planning and execution tracking.

    This tool provides:
    - Task decomposition with dependency tracking
    - Priority assignment and scheduling
    - Progress tracking and status updates
    - Resource estimation and planning
    - Integration with VFS plan.txt for comprehensive tracking
    - Step-by-step execution monitoring
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._plans_by_session = {}  # Session-scoped storage: {session_id: {plan_id: plan_data}}
        self._current_session_id = None  # Track current session
        self._vfs_tool = None  # VFS tool reference for plan.txt updates
        self._baml_llm = BAMLGeminiLLM()  # Initialize BAML LLM for intelligent planning

    def set_session_context(self, session_id: str) -> None:
        """Set the current session context for plan operations."""
        self._current_session_id = session_id

    def set_memory(self, memory) -> None:
        """Set the conversation memory reference for plan persistence."""
        self.memory = memory

    def set_vfs_tool(self, vfs_tool) -> None:
        """Set the VFS tool reference for plan.txt updates."""
        self._vfs_tool = vfs_tool

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
                from app.agents.personal_assistant.tool_entity_store import EntityContext, EntityType
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
                logger.debug(f"Stored plan {plan['id']} in entity store")
            else:
                logger.debug("No entity store reference available for plan storage")
        except Exception as e:
            logger.warning(f"Failed to store plan in entity store: {str(e)}")

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

            # Update plan.txt with comprehensive structure
            await self._update_plan_file(plan, "create")

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
        """Decompose a task into specific, actionable subtasks using LLM-powered analysis."""
        try:
            # Use BAML function for intelligent task decomposition
            logger.info(f"🧠 Using LLM-powered task decomposition for: {task_description}")

            baml_result = await self._baml_llm.call_function(
                "PersonalAssistantPlanning",
                task_description=task_description,
                complexity=complexity.value,
                user_context=f"Personal assistant helping with: {task_description}"
            )

            logger.info(f"🧠 BAML planning result: {baml_result}")

            # Parse the BAML result and convert to subtasks
            subtasks = self._parse_baml_planning_result(baml_result, task_description)

            if subtasks:
                logger.info(f"✅ Generated {len(subtasks)} intelligent subtasks from LLM")
                return subtasks
            else:
                logger.warning("⚠️ LLM planning failed, falling back to deterministic logic")

        except Exception as e:
            logger.error(f"❌ Error in LLM-powered task decomposition: {str(e)}")
            logger.warning("⚠️ Falling back to deterministic task decomposition")

        # Fallback to deterministic decomposition if LLM fails
        return self._fallback_task_decomposition(task_description, complexity)

    def _parse_baml_planning_result(self, baml_result: Dict[str, Any], task_description: str) -> List[Dict[str, Any]]:
        """Parse BAML planning result into structured subtasks."""
        try:
            subtasks = []

            # The BAML function returns a map<string, string>, so we need to parse it
            if not isinstance(baml_result, dict):
                logger.warning(f"Unexpected BAML result type: {type(baml_result)}")
                return []

            # Extract steps from the BAML result
            # The result should contain step information
            step_counter = 1

            for key, value in baml_result.items():
                if key.lower().startswith('step') or 'title' in key.lower():
                    # This looks like a step title
                    title = value.strip()

                    # Look for corresponding description
                    desc_key = key.replace('title', 'description').replace('step', 'description')
                    description = baml_result.get(desc_key, title)

                    # Look for time estimate
                    time_key = key.replace('title', 'time').replace('step', 'time')
                    time_str = baml_result.get(time_key, "15")

                    try:
                        estimated_minutes = int(re.findall(r'\d+', str(time_str))[0]) if re.findall(r'\d+', str(time_str)) else 15
                    except:
                        estimated_minutes = 15

                    # Determine priority based on content
                    priority = self._determine_subtask_priority(title, description)

                    subtask = {
                        "id": str(uuid.uuid4()),
                        "title": title,
                        "description": description,
                        "status": TaskStatus.PENDING.value,
                        "priority": priority,
                        "estimated_minutes": estimated_minutes,
                        "dependencies": [],
                        "order": step_counter
                    }

                    subtasks.append(subtask)
                    step_counter += 1

            # If we didn't find structured steps, try to parse as a single text response
            if not subtasks and baml_result:
                # Look for any text that might contain step information
                full_text = " ".join(str(v) for v in baml_result.values())
                subtasks = self._extract_steps_from_text(full_text, task_description)

            return subtasks

        except Exception as e:
            logger.error(f"Error parsing BAML planning result: {str(e)}")
            return []

    def _extract_steps_from_text(self, text: str, task_description: str) -> List[Dict[str, Any]]:
        """Extract steps from unstructured text response."""
        try:
            subtasks = []

            # Look for numbered steps or bullet points
            lines = text.split('\n')
            step_counter = 1

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Check if this looks like a step
                if (re.match(r'^\d+\.', line) or
                    re.match(r'^-', line) or
                    re.match(r'^\*', line) or
                    'step' in line.lower()):

                    # Clean up the line
                    title = re.sub(r'^\d+\.|\*|-|step\s*\d*:?\s*', '', line, flags=re.IGNORECASE).strip()

                    if len(title) > 5:  # Only include meaningful steps
                        priority = self._determine_subtask_priority(title, title)

                        subtask = {
                            "id": str(uuid.uuid4()),
                            "title": title,
                            "description": title,
                            "status": TaskStatus.PENDING.value,
                            "priority": priority,
                            "estimated_minutes": 15,
                            "dependencies": [],
                            "order": step_counter
                        }

                        subtasks.append(subtask)
                        step_counter += 1

            return subtasks

        except Exception as e:
            logger.error(f"Error extracting steps from text: {str(e)}")
            return []

    def _determine_subtask_priority(self, title: str, description: str) -> str:
        """Determine priority for a subtask based on its content."""
        title_lower = title.lower()
        desc_lower = description.lower()

        # High priority keywords
        high_priority_keywords = ['urgent', 'critical', 'important', 'deadline', 'asap', 'immediately']
        if any(keyword in title_lower or keyword in desc_lower for keyword in high_priority_keywords):
            return TaskPriority.HIGH.value

        # Calendar/email tasks are typically high priority for user requests
        if any(keyword in title_lower for keyword in ['calendar', 'schedule', 'meeting', 'email', 'send', 'invite']):
            return TaskPriority.HIGH.value

        # Medium priority for most other tasks
        return TaskPriority.MEDIUM.value

    def _fallback_task_decomposition(self, task_description: str, complexity: TaskComplexity) -> List[Dict[str, Any]]:
        """Fallback deterministic task decomposition when LLM fails."""
        subtasks = []

        if complexity == TaskComplexity.SIMPLE:
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
            # Try to create more specific subtasks based on content analysis
            specific_subtasks = self._analyze_and_extract_specific_actions(task_description)
            if specific_subtasks:
                subtasks = specific_subtasks
            else:
                # Generic fallback
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
                    }
                ]
        else:  # COMPLEX
            # For complex tasks, try content analysis first
            specific_subtasks = self._analyze_and_extract_specific_actions(task_description)
            if specific_subtasks:
                subtasks = specific_subtasks
            else:
                # Generic complex task breakdown
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
                        "title": f"Planning and design for: {task_description}",
                        "description": "Detailed planning and design phase",
                        "status": TaskStatus.PENDING.value,
                        "priority": TaskPriority.HIGH.value,
                        "estimated_minutes": 90,
                        "dependencies": [],
                        "order": 2
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "title": f"Implementation for: {task_description}",
                        "description": "Main implementation phase",
                        "status": TaskStatus.PENDING.value,
                        "priority": TaskPriority.HIGH.value,
                        "estimated_minutes": 120,
                        "dependencies": [],
                        "order": 3
                    }
                ]

        return subtasks

    def _analyze_and_extract_specific_actions(self, task_description: str) -> List[Dict[str, Any]]:
        """Analyze task description and extract specific actionable subtasks."""
        subtasks = []
        task_lower = task_description.lower()

        # Calendar/scheduling related actions
        if any(keyword in task_lower for keyword in ['lunch', 'meeting', 'appointment', 'schedule', 'calendar', 'event']):
            # Extract time information
            time_info = self._extract_time_info(task_description)
            event_title = self._extract_event_title(task_description)

            subtasks.append({
                "id": str(uuid.uuid4()),
                "title": f"Create calendar event for {event_title}",
                "description": f"Schedule {event_title} with appropriate reminders and details",
                "status": TaskStatus.PENDING.value,
                "priority": TaskPriority.HIGH.value,
                "estimated_minutes": 5,
                "dependencies": [],
                "order": len(subtasks) + 1
            })

        # Email/invitation related actions
        if any(keyword in task_lower for keyword in ['email', 'invite', 'send', 'message']):
            # Extract recipient information
            recipient_info = self._extract_recipient_info(task_description)

            subtasks.append({
                "id": str(uuid.uuid4()),
                "title": f"Send email invitation to {recipient_info}",
                "description": f"Send invitation email with relevant details and context",
                "status": TaskStatus.PENDING.value,
                "priority": TaskPriority.HIGH.value,
                "estimated_minutes": 10,
                "dependencies": [],
                "order": len(subtasks) + 1
            })

        # Document/file related actions
        if any(keyword in task_lower for keyword in ['document', 'file', 'nda', 'contract', 'report']):
            doc_type = self._extract_document_type(task_description)

            subtasks.append({
                "id": str(uuid.uuid4()),
                "title": f"Prepare and send {doc_type} document",
                "description": f"Handle {doc_type} document preparation and delivery",
                "status": TaskStatus.PENDING.value,
                "priority": TaskPriority.MEDIUM.value,
                "estimated_minutes": 15,
                "dependencies": [],
                "order": len(subtasks) + 1
            })

        return subtasks

    def _extract_time_info(self, text: str) -> str:
        """Extract time information from text."""
        # Look for time patterns like "at 12", "12 PM", etc.
        time_patterns = [
            r'at (\d{1,2}(?::\d{2})?(?:\s*(?:am|pm))?)',
            r'(\d{1,2}(?::\d{2})?(?:\s*(?:am|pm))?)',
        ]

        for pattern in time_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)

        return "12:00 PM"  # Default time

    def _extract_event_title(self, text: str) -> str:
        """Extract event title from text."""
        text_lower = text.lower()

        if 'lunch' in text_lower:
            return "lunch"
        elif 'meeting' in text_lower:
            return "meeting"
        elif 'appointment' in text_lower:
            return "appointment"
        else:
            return "event"

    def _extract_recipient_info(self, text: str) -> str:
        """Extract recipient information from text."""
        # Look for email addresses
        email_pattern = r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
        email_match = re.search(email_pattern, text)

        if email_match:
            return email_match.group(1)

        # Look for names
        name_patterns = [
            r'invite (?:my )?(?:friend )?(\w+)',
            r'send (?:to )?(\w+)',
        ]

        for pattern in name_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)

        return "recipient"

    def _extract_document_type(self, text: str) -> str:
        """Extract document type from text."""
        text_lower = text.lower()

        if 'nda' in text_lower:
            return "NDA"
        elif 'contract' in text_lower:
            return "contract"
        elif 'report' in text_lower:
            return "report"
        else:
            return "document"

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

            # Update plan.txt with changes
            await self._update_plan_file(plan, "update")

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

    async def _update_plan_file(self, plan: Dict[str, Any], operation: str) -> None:
        """Update plan.txt with comprehensive plan structure."""
        try:
            if not self._vfs_tool:
                logger.warning("VFS tool not available for plan.txt update")
                return

            # Generate comprehensive plan content
            plan_content = self._generate_plan_file_content(plan, operation)

            # Write to plan.txt (overwrite with complete plan)
            await self._vfs_tool.execute({
                "action": "write",
                "file_path": "plan.txt",
                "content": plan_content
            })

            logger.debug(f"Updated plan.txt for plan: {plan.get('title', 'Unknown')}")

        except Exception as e:
            logger.error(f"Failed to update plan.txt: {str(e)}")

    def _generate_plan_file_content(self, plan: Dict[str, Any], operation: str) -> str:
        """Generate comprehensive plan.txt content."""
        try:
            session_id = self._current_session_id or "unknown"
            timestamp = datetime.utcnow().isoformat()

            # Determine planning type
            planning_type = self._determine_planning_type(plan)

            # Generate execution steps section
            steps_content = ""
            subtasks = plan.get("subtasks", [])
            for i, subtask in enumerate(subtasks, 1):
                steps_content += f"""
STEP {i}: {subtask.get('title', 'Untitled Step')}
DESCRIPTION: {subtask.get('description', 'No description')}
STATUS: {subtask.get('status', 'Pending')}
TOOL_REQUIRED: {self._identify_tool_for_step(subtask)}
PARAMETERS: {self._format_step_parameters(subtask)}
DEPENDENCIES: {self._format_dependencies(subtask, subtasks)}
STARTED_AT: {subtask.get('started_at', '')}
COMPLETED_AT: {subtask.get('completed_at', '')}
EXECUTION_TIME: {subtask.get('execution_time', '')}
RESULT_SUMMARY: {subtask.get('result_summary', '')}
DETAILED_RESULT: {subtask.get('detailed_result', '')}
EVALUATION: {subtask.get('evaluation', '')}
NOTES: {subtask.get('notes', '')}
"""

            # Calculate metrics
            progress = plan.get("progress", {})
            total_steps = progress.get("total_tasks", len(subtasks))
            completed_steps = progress.get("completed_tasks", 0)
            failed_steps = sum(1 for task in subtasks if task.get("status") == "failed")
            completion_rate = f"{progress.get('completion_percentage', 0)}%"
            current_step = self._get_current_step_number(subtasks)

            content = f"""SESSION: {session_id}
PLAN_TYPE: {planning_type}
CREATED: {plan.get('created_at', timestamp)}
LAST_UPDATED: {plan.get('updated_at', timestamp)}
OVERALL_STATUS: {plan.get('status', 'Planning')}

=== PLAN OVERVIEW ===
PRIMARY_GOAL: {plan.get('title', 'Unknown Goal')}
SUCCESS_DEFINITION: {self._define_success_criteria(plan)}
ESTIMATED_DURATION: {plan.get('estimated_duration_minutes', 0)} minutes
TOOLS_REQUIRED: {', '.join(plan.get('resources_needed', []))}
CRITICAL_DEPENDENCIES: {self._format_critical_dependencies(plan)}

=== EXECUTION STEPS ==={steps_content}

=== PLAN METRICS ===
TOTAL_STEPS: {total_steps}
COMPLETED_STEPS: {completed_steps}
FAILED_STEPS: {failed_steps}
COMPLETION_RATE: {completion_rate}
CURRENT_STEP: {current_step}

=== FINAL EVALUATION ===
OVERALL_SUCCESS: {self._evaluate_overall_success(plan)}
USER_GOAL_ACHIEVED: {self._evaluate_goal_achievement(plan)}
ISSUES_ENCOUNTERED: {self._list_issues_encountered(plan)}
LESSONS_LEARNED: {self._extract_lessons_learned(plan)}
USER_FEEDBACK: [To be filled when user provides feedback]
"""
            return content

        except Exception as e:
            logger.error(f"Error generating plan file content: {str(e)}")
            return f"Error generating plan content: {str(e)}"

    def _determine_planning_type(self, plan: Dict[str, Any]) -> str:
        """Determine the planning type based on plan characteristics."""
        title = plan.get("title", "").lower()

        if "create a plan" in title or "strategy" in title:
            return "Domain"
        elif len(plan.get("subtasks", [])) > 3:
            return "Hybrid"
        else:
            return "Procedural"

    def _identify_tool_for_step(self, subtask: Dict[str, Any]) -> str:
        """Identify the most appropriate tool for a subtask."""
        title = subtask.get("title", "").lower()
        description = subtask.get("description", "").lower()

        if "email" in title or "send" in title:
            return "gmail"
        elif "calendar" in title or "schedule" in title:
            return "google_calendar"
        elif "search" in title or "research" in title:
            return "tavily_search"
        elif "plan" in title:
            return "planning"
        elif "file" in title or "document" in title:
            return "virtual_fs"
        else:
            return "system_prompt"

    def _format_step_parameters(self, subtask: Dict[str, Any]) -> str:
        """Format parameters for a step."""
        # This would be enhanced based on the specific tool requirements
        return "To be determined during execution"

    def _format_dependencies(self, subtask: Dict[str, Any], all_subtasks: List[Dict[str, Any]]) -> str:
        """Format dependencies for a subtask."""
        order = subtask.get("order", 0)
        if order <= 1:
            return "None (starting step)"
        else:
            prev_step = next((task for task in all_subtasks if task.get("order") == order - 1), None)
            if prev_step:
                return f"Step {order - 1}: {prev_step.get('title', 'Previous step')}"
            return "Previous step completion"

    def _format_critical_dependencies(self, plan: Dict[str, Any]) -> str:
        """Format critical dependencies for the plan."""
        dependencies = plan.get("dependencies", [])
        if not dependencies:
            return "None identified"

        critical = [dep for dep in dependencies if dep.get("dependency_type") == "critical"]
        if critical:
            return f"{len(critical)} critical dependencies identified"
        return "Sequential execution required"

    def _get_current_step_number(self, subtasks: List[Dict[str, Any]]) -> str:
        """Get the current step number being executed."""
        for i, task in enumerate(subtasks, 1):
            if task.get("status") == "in_progress":
                return str(i)
            elif task.get("status") == "pending":
                return str(i)
        return str(len(subtasks)) if subtasks else "1"

    def _define_success_criteria(self, plan: Dict[str, Any]) -> str:
        """Define success criteria for the plan."""
        title = plan.get("title", "").lower()

        if "create" in title:
            return "All items successfully created and delivered"
        elif "schedule" in title:
            return "All events successfully scheduled and confirmed"
        elif "send" in title:
            return "All messages successfully sent and delivered"
        else:
            return "All subtasks completed successfully"

    def _evaluate_overall_success(self, plan: Dict[str, Any]) -> str:
        """Evaluate overall success of the plan."""
        progress = plan.get("progress", {})
        completion_rate = progress.get("completion_percentage", 0)

        if completion_rate >= 100:
            return "Yes"
        elif completion_rate >= 80:
            return "Partial"
        else:
            return "No"

    def _evaluate_goal_achievement(self, plan: Dict[str, Any]) -> str:
        """Evaluate if the user's goal was achieved."""
        status = plan.get("status", "pending")

        if status == "completed":
            return "Yes"
        elif status == "in_progress":
            return "Partially"
        else:
            return "No"

    def _list_issues_encountered(self, plan: Dict[str, Any]) -> str:
        """List issues encountered during plan execution."""
        subtasks = plan.get("subtasks", [])
        failed_tasks = [task for task in subtasks if task.get("status") == "failed"]

        if not failed_tasks:
            return "None reported"

        issues = []
        for task in failed_tasks:
            issue = f"Step failed: {task.get('title', 'Unknown step')}"
            if task.get("notes"):
                issue += f" - {task['notes']}"
            issues.append(issue)

        return "; ".join(issues)

    def _extract_lessons_learned(self, plan: Dict[str, Any]) -> str:
        """Extract lessons learned from plan execution."""
        # This could be enhanced with more sophisticated analysis
        progress = plan.get("progress", {})
        completion_rate = progress.get("completion_percentage", 0)

        if completion_rate >= 90:
            return "Plan executed successfully with good task decomposition"
        elif completion_rate >= 50:
            return "Some steps succeeded, may need better dependency management"
        else:
            return "Plan needs revision, consider simpler task breakdown"