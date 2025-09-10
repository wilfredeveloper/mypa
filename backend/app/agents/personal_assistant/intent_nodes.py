"""
Intent-Driven Personal Assistant Nodes
New architecture focused on efficient execution through intent classification and structured planning.
"""

import json
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from pocketflow import AsyncNode
from app.agents.personal_assistant.nodes import PAToolCallNode, PAResponseNode, PAEndNode

logger = logging.getLogger(__name__)


class PAIntentClassificationNode(AsyncNode):
    """Node that classifies user intent and determines execution complexity."""

    async def prep_async(self, shared):
        """Prepare intent classification data."""
        user_message = shared.get("user_message", "")
        session = shared.get("session", {})
        tool_registry = shared.get("tool_registry")

        # Get conversation context (last 3 messages for context)
        messages = session.get("messages", [])
        conversation_context = []
        for msg in messages[-3:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            conversation_context.append(f"{role}: {content}")

        # Get available tools summary
        available_tools = []
        if tool_registry:
            for tool_name, tool_instance in tool_registry._tool_instances.items():
                tool_info = {
                    "name": tool_name,
                    "description": getattr(tool_instance.registry, 'description', 'No description')
                }
                available_tools.append(f"- {tool_name}: {tool_info['description']}")

        return {
            "user_message": user_message,
            "available_tools": "\n".join(available_tools),
            "conversation_context": "\n".join(conversation_context),
            "baml_client": shared.get("baml_client")
        }

    async def exec_async(self, prep_res):
        """Execute intent classification."""
        baml_client = prep_res.get("baml_client")
        
        if not baml_client:
            # Fallback classification without BAML
            return self._fallback_classification(prep_res["user_message"])

        try:
            # Call BAML function for intent classification
            classification = await baml_client.call_function(
                "ClassifyUserIntent",
                user_message=prep_res["user_message"],
                available_tools=prep_res["available_tools"],
                conversation_context=prep_res["conversation_context"]
            )

            # Convert BAML result to dict format
            return {
                "complexity_level": classification.complexity_level,
                "task_category": classification.task_category,
                "user_intent": classification.user_intent,
                "requires_tools": classification.requires_tools,
                "estimated_steps": classification.estimated_steps,
                "reasoning": classification.reasoning
            }

        except Exception as e:
            logger.error(f"Error in intent classification: {str(e)}", exc_info=True)
            return self._fallback_classification(prep_res["user_message"])

    def _fallback_classification(self, user_message: str) -> Dict[str, Any]:
        """Fallback classification when BAML is not available."""
        message_lower = user_message.lower()
        
        # Simple heuristics for classification
        if any(word in message_lower for word in ["hi", "hello", "hey", "thanks", "thank you"]):
            return {
                "complexity_level": "simple",
                "task_category": "greeting",
                "user_intent": "User is greeting or expressing gratitude",
                "requires_tools": False,
                "estimated_steps": 1,
                "reasoning": "Detected greeting or social interaction"
            }
        elif any(word in message_lower for word in ["research", "analyze", "comprehensive", "detailed", "business plan"]):
            return {
                "complexity_level": "complex",
                "task_category": "research",
                "user_intent": "User wants comprehensive research or analysis",
                "requires_tools": True,
                "estimated_steps": 6,
                "reasoning": "Detected complex research or analysis request"
            }
        else:
            return {
                "complexity_level": "focused",
                "task_category": "question",
                "user_intent": "User has a specific question or request",
                "requires_tools": True,
                "estimated_steps": 3,
                "reasoning": "Default focused classification for specific requests"
            }

    async def post_async(self, shared, prep_res, exec_res):
        """Save classification results and decide next step."""
        # Save classification to shared state
        shared["intent_classification"] = exec_res
        shared["complexity_level"] = exec_res["complexity_level"]
        shared["task_category"] = exec_res["task_category"]
        shared["user_intent"] = exec_res["user_intent"]
        shared["estimated_steps"] = exec_res["estimated_steps"]

        print(f"🎯 Intent Classification: {exec_res['complexity_level'].upper()} - {exec_res['task_category']}")
        print(f"📋 User Intent: {exec_res['user_intent']}")
        print(f"⏱️ Estimated Steps: {exec_res['estimated_steps']}")

        # Route based on complexity and tool requirements
        if exec_res["complexity_level"] == "simple" and not exec_res["requires_tools"]:
            # Simple greetings or basic responses - skip planning
            shared["skip_planning"] = True
            return "respond"
        elif exec_res["requires_tools"]:
            # Needs planning for tool execution
            return "plan"
        else:
            # Simple but might need basic response
            return "respond"


class PAStructuredPlanningNode(AsyncNode):
    """Node that creates structured, executable plans based on intent classification."""

    async def prep_async(self, shared):
        """Prepare planning data."""
        classification = shared.get("intent_classification", {})
        tool_registry = shared.get("tool_registry")
        
        # Get available tools with detailed info
        available_tools = []
        if tool_registry:
            for tool_name, tool_instance in tool_registry._tool_instances.items():
                tool_info = {
                    "name": tool_name,
                    "description": getattr(tool_instance.registry, 'description', 'No description'),
                    "schema": getattr(tool_instance.registry, 'schema_data', {})
                }
                available_tools.append(f"**{tool_name}**: {tool_info['description']}")

        return {
            "user_intent": classification.get("user_intent", ""),
            "complexity_level": classification.get("complexity_level", "focused"),
            "task_category": classification.get("task_category", "question"),
            "estimated_steps": classification.get("estimated_steps", 3),
            "available_tools": "\n".join(available_tools),
            "baml_client": shared.get("baml_client")
        }

    async def exec_async(self, prep_res):
        """Execute structured planning."""
        baml_client = prep_res.get("baml_client")
        
        if not baml_client:
            return self._fallback_planning(prep_res)

        try:
            # Call BAML function for structured planning
            plan = await baml_client.call_function(
                "CreateStructuredPlan",
                user_intent=prep_res["user_intent"],
                complexity_level=prep_res["complexity_level"],
                task_category=prep_res["task_category"],
                available_tools=prep_res["available_tools"],
                estimated_steps=prep_res["estimated_steps"]
            )

            # Convert BAML result to dict format
            todos = []
            for todo in plan.todos:
                todos.append({
                    "id": todo.id,
                    "title": todo.title,
                    "description": todo.description,
                    "tool_required": getattr(todo, 'tool_required', None),
                    "tool_parameters": getattr(todo, 'tool_parameters', {}),
                    "estimated_minutes": todo.estimated_minutes,
                    "dependencies": getattr(todo, 'dependencies', []),
                    "status": "pending"
                })

            return {
                "plan_summary": plan.plan_summary,
                "total_estimated_minutes": plan.total_estimated_minutes,
                "todos": todos,
                "success_criteria": plan.success_criteria,
                "workspace_files": getattr(plan, 'workspace_files', [])
            }

        except Exception as e:
            logger.error(f"Error in structured planning: {str(e)}", exc_info=True)
            return self._fallback_planning(prep_res)

    def _fallback_planning(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback planning when BAML is not available."""
        complexity = prep_res["complexity_level"]
        task_category = prep_res["task_category"]
        
        if complexity == "simple":
            todos = [{
                "id": "todo_1",
                "title": "Complete simple request",
                "description": "Handle the user's simple request directly",
                "tool_required": None,
                "tool_parameters": {},
                "estimated_minutes": 2,
                "dependencies": [],
                "status": "pending"
            }]
        elif complexity == "focused":
            todos = [
                {
                    "id": "todo_1",
                    "title": "Research information",
                    "description": "Gather relevant information for the request",
                    "tool_required": "tavily_search",
                    "tool_parameters": {"query": "relevant search terms"},
                    "estimated_minutes": 5,
                    "dependencies": [],
                    "status": "pending"
                },
                {
                    "id": "todo_2",
                    "title": "Create response",
                    "description": "Compile findings into a helpful response",
                    "tool_required": "virtual_fs",
                    "tool_parameters": {"action": "create", "filename": "response.md"},
                    "estimated_minutes": 3,
                    "dependencies": ["todo_1"],
                    "status": "pending"
                }
            ]
        else:  # complex
            todos = [
                {
                    "id": "todo_1",
                    "title": "Initial research",
                    "description": "Conduct comprehensive research on the topic",
                    "tool_required": "tavily_search",
                    "tool_parameters": {"query": "comprehensive research terms"},
                    "estimated_minutes": 10,
                    "dependencies": [],
                    "status": "pending"
                },
                {
                    "id": "todo_2",
                    "title": "Create workspace",
                    "description": "Set up organized workspace for the project",
                    "tool_required": "virtual_fs",
                    "tool_parameters": {"action": "create", "filename": "project_workspace.md"},
                    "estimated_minutes": 3,
                    "dependencies": [],
                    "status": "pending"
                },
                {
                    "id": "todo_3",
                    "title": "Analyze findings",
                    "description": "Analyze and synthesize research findings",
                    "tool_required": None,
                    "tool_parameters": {},
                    "estimated_minutes": 8,
                    "dependencies": ["todo_1", "todo_2"],
                    "status": "pending"
                },
                {
                    "id": "todo_4",
                    "title": "Create final deliverable",
                    "description": "Create comprehensive final output",
                    "tool_required": "virtual_fs",
                    "tool_parameters": {"action": "create", "filename": "final_report.md"},
                    "estimated_minutes": 10,
                    "dependencies": ["todo_3"],
                    "status": "pending"
                }
            ]

        return {
            "plan_summary": f"Structured plan for {task_category} task",
            "total_estimated_minutes": sum(todo["estimated_minutes"] for todo in todos),
            "todos": todos,
            "success_criteria": "All todos completed successfully",
            "workspace_files": ["task_plan.md"]
        }

    async def post_async(self, shared, prep_res, exec_res):
        """Save plan and initialize execution."""
        # Save plan to shared state
        shared["structured_plan"] = exec_res
        shared["current_todo_index"] = 0
        shared["completed_todos"] = []
        shared["plan_start_time"] = datetime.utcnow().isoformat()

        # Create initial workspace with plan
        await self._create_plan_workspace(shared, exec_res)

        print(f"📋 Created Plan: {exec_res['plan_summary']}")
        print(f"⏱️ Estimated Time: {exec_res['total_estimated_minutes']} minutes")
        print(f"📝 Total Todos: {len(exec_res['todos'])}")

        # Start executing the first todo
        return "execute"

    async def _create_plan_workspace(self, shared, plan):
        """Create workspace file with the structured plan."""
        tool_registry = shared.get("tool_registry")
        if not tool_registry or "virtual_fs" not in tool_registry._tool_instances:
            return

        try:
            virtual_fs_tool = tool_registry._tool_instances["virtual_fs"]
            task_id = str(uuid.uuid4())[:8]
            
            # Create plan content
            plan_content = f"""# Task Plan: {task_id}

## Plan Summary
{plan['plan_summary']}

## Success Criteria
{plan['success_criteria']}

## Estimated Time
{plan['total_estimated_minutes']} minutes

## Todo List
"""
            
            for i, todo in enumerate(plan['todos'], 1):
                status_icon = "⏳" if todo['status'] == "pending" else "✅" if todo['status'] == "completed" else "🔄"
                plan_content += f"""
### {i}. {status_icon} {todo['title']} (ID: {todo['id']})
- **Description**: {todo['description']}
- **Estimated Time**: {todo['estimated_minutes']} minutes
- **Tool Required**: {todo['tool_required'] or 'None'}
- **Status**: {todo['status']}
- **Dependencies**: {', '.join(todo['dependencies']) if todo['dependencies'] else 'None'}
"""

            plan_content += f"""

## Execution Log
- Plan created: {datetime.utcnow().isoformat()}

---
*This plan is managed by the Intent-Driven Personal Assistant*
"""

            # Create the workspace file
            workspace_filename = f"task_plan_{task_id}.md"
            result = await virtual_fs_tool.execute({
                "action": "create",
                "filename": workspace_filename,
                "content": plan_content
            })

            if result.get("success", False):
                shared["workspace_filename"] = workspace_filename
                shared["task_id"] = task_id
                logger.info(f"Created plan workspace: {workspace_filename}")

        except Exception as e:
            logger.warning(f"Failed to create plan workspace: {str(e)}")


class PAPlanExecutionNode(AsyncNode):
    """Node that executes todos from the structured plan sequentially."""

    async def prep_async(self, shared):
        """Prepare plan execution data."""
        plan = shared.get("structured_plan", {})
        current_index = shared.get("current_todo_index", 0)
        todos = plan.get("todos", [])

        if current_index >= len(todos):
            return {"error": "No more todos to execute", "plan_complete": True}

        current_todo = todos[current_index]

        # Check if dependencies are met
        dependencies = current_todo.get("dependencies", [])
        completed_todos = shared.get("completed_todos", [])

        unmet_dependencies = [dep for dep in dependencies if dep not in completed_todos]
        if unmet_dependencies:
            return {"error": f"Dependencies not met: {unmet_dependencies}", "plan_complete": False}

        return {
            "current_todo": current_todo,
            "current_index": current_index,
            "plan": plan,
            "tool_registry": shared.get("tool_registry"),
            "baml_client": shared.get("baml_client"),
            "workspace_filename": shared.get("workspace_filename")
        }

    async def exec_async(self, prep_res):
        """Execute the current todo step with intelligent validation."""
        if prep_res.get("error"):
            logger.error(f"PAPlanExecutionNode received error: {prep_res.get('error')}")
            return prep_res

        current_todo = prep_res["current_todo"]
        tool_required = current_todo.get("tool_required")
        plan = prep_res.get("plan", {})
        baml_client = prep_res.get("baml_client")

        # Add detailed debugging
        print(f"🔄 Executing todo: {current_todo['title']}")
        logger.info(f"Starting execution of todo {current_todo['id']}: {current_todo['title']}")
        logger.debug(f"Todo details: tool_required={tool_required}, description={current_todo.get('description', 'No description')}")

        # Mark todo as in progress
        current_todo["status"] = "in_progress"

        execution_result = {
            "todo_id": current_todo["id"],
            "todo_title": current_todo["title"],
            "tool_results": [],
            "execution_summary": "",
            "todo_completed": False,
            "baml_evaluation": None
        }

        # Execute tool if required
        if tool_required and prep_res.get("tool_registry"):
            try:
                tool_registry = prep_res["tool_registry"]
                tool_parameters = current_todo.get("tool_parameters", {})

                print(f"🔧 Executing tool: {tool_required} for todo: {current_todo['title']}")

                # Execute the tool
                result = await tool_registry.execute_tool(tool_required, tool_parameters)

                execution_result["tool_results"] = [{
                    "tool": tool_required,
                    "parameters": tool_parameters,
                    "result": result,
                    "success": True,
                    "timestamp": datetime.utcnow().isoformat()
                }]

                print(f"🧠 Evaluating tool results with LLM reasoning...")

            except Exception as e:
                logger.error(f"Error executing tool {tool_required}: {str(e)}")
                execution_result["tool_results"] = [{
                    "tool": tool_required,
                    "parameters": tool_parameters,
                    "result": f"Error: {str(e)}",
                    "success": False,
                    "timestamp": datetime.utcnow().isoformat()
                }]
                print(f"❌ Tool execution failed: {str(e)}")

        # Now use BAML to intelligently evaluate the execution
        if baml_client:
            try:
                # Prepare context for BAML evaluation
                current_todo_str = json.dumps(current_todo, indent=2)
                plan_context = json.dumps({
                    "plan_summary": plan.get("plan_summary", ""),
                    "success_criteria": plan.get("success_criteria", ""),
                    "total_todos": len(plan.get("todos", [])),
                    "current_todo_index": prep_res.get("current_index", 0)
                }, indent=2)
                tool_results_str = json.dumps(execution_result["tool_results"], indent=2)
                workspace_state = await self._get_workspace_state(prep_res.get("workspace_filename"), prep_res.get("tool_registry"))

                # Call BAML function for intelligent evaluation
                baml_result = await baml_client.call_function(
                    "ExecutePlanStep",
                    current_todo=current_todo_str,
                    plan_context=plan_context,
                    tool_results=tool_results_str,
                    workspace_state=workspace_state
                )

                # Use BAML evaluation results
                execution_result["todo_completed"] = baml_result.todo_completed
                execution_result["execution_summary"] = baml_result.execution_summary
                execution_result["baml_evaluation"] = {
                    "next_todo_id": getattr(baml_result, 'next_todo_id', None),
                    "workspace_updates": getattr(baml_result, 'workspace_updates', []),
                    "plan_complete": getattr(baml_result, 'plan_complete', False),
                    "final_output": getattr(baml_result, 'final_output', None)
                }

                if execution_result["todo_completed"]:
                    print(f"✅ LLM validated todo completion: {current_todo['title']}")
                    print(f"📝 Reasoning: {baml_result.execution_summary}")
                else:
                    print(f"⚠️ LLM determined todo needs more work: {current_todo['title']}")
                    print(f"📝 Reasoning: {baml_result.execution_summary}")

            except Exception as e:
                logger.error(f"Error in BAML evaluation: {str(e)}")
                # Fallback to simple completion logic
                if tool_required:
                    execution_result["todo_completed"] = len(execution_result["tool_results"]) > 0 and execution_result["tool_results"][0].get("success", False)
                    execution_result["execution_summary"] = f"Tool executed, but LLM evaluation failed: {str(e)}"
                else:
                    execution_result["todo_completed"] = True
                    execution_result["execution_summary"] = f"No tool required - completed without LLM validation"
                print(f"⚠️ Fallback completion logic used due to LLM evaluation error")
        else:
            # Fallback when BAML is not available
            if tool_required:
                execution_result["todo_completed"] = len(execution_result["tool_results"]) > 0 and execution_result["tool_results"][0].get("success", False)
                execution_result["execution_summary"] = f"Tool executed - no LLM validation available"
            else:
                execution_result["todo_completed"] = True
                execution_result["execution_summary"] = f"No tool required - completed without validation"
            print(f"⚠️ No LLM validation - using basic completion logic")

        return execution_result

    async def _get_workspace_state(self, workspace_filename: str, tool_registry) -> str:
        """Get current workspace state for BAML evaluation."""
        if not workspace_filename or not tool_registry or "virtual_fs" not in tool_registry._tool_instances:
            return "No workspace available"

        try:
            virtual_fs_tool = tool_registry._tool_instances["virtual_fs"]

            # Read current workspace content
            read_result = await virtual_fs_tool.execute({
                "action": "read",
                "filename": workspace_filename
            })

            if read_result.get("success", False):
                content = read_result.get("result", {}).get("content", "")
                return f"Workspace file '{workspace_filename}':\n{content}"
            else:
                return f"Failed to read workspace file '{workspace_filename}'"

        except Exception as e:
            logger.warning(f"Error reading workspace state: {str(e)}")
            return f"Error accessing workspace: {str(e)}"

    async def post_async(self, shared, prep_res, exec_res):
        """Process execution results and determine next step."""
        if prep_res.get("error"):
            logger.error(f"PAPlanExecutionNode post_async received error: {prep_res.get('error')}")
            if prep_res.get("plan_complete"):
                return "respond"  # Plan is complete
            else:
                # Handle dependency errors by finding next executable todo
                if "Dependencies not met" in prep_res.get("error", ""):
                    return await self._handle_dependency_error(shared, prep_res)
                else:
                    return "execute"  # Try again for other errors

        plan = shared.get("structured_plan", {})
        current_index = shared.get("current_todo_index", 0)
        todos = plan.get("todos", [])
        baml_evaluation = exec_res.get("baml_evaluation", {})

        # Get current todo - needed in both completion and retry logic
        current_todo = todos[current_index] if current_index < len(todos) else None
        if not current_todo:
            logger.error(f"No todo found at index {current_index}, total todos: {len(todos)}")
            return "respond"

        # Add detailed debugging for decision logic
        logger.info(f"Processing execution results for todo {current_index + 1}/{len(todos)}")
        logger.debug(f"Todo completed: {exec_res.get('todo_completed', False)}")
        logger.debug(f"BAML evaluation: {baml_evaluation}")
        logger.debug(f"Current todo index: {current_index}, Total todos: {len(todos)}")

        # Check if BAML determined the plan is complete early
        if baml_evaluation.get("plan_complete", False):
            shared["plan_completed"] = True
            shared["plan_end_time"] = datetime.utcnow().isoformat()
            shared["final_output"] = baml_evaluation.get("final_output")
            print(f"🎉 LLM determined plan is complete early! Success criteria met.")
            print(f"📝 Final output: {baml_evaluation.get('final_output', 'Plan completed successfully')}")
            return "respond"

        if exec_res.get("todo_completed"):
            # Mark current todo as completed
            current_todo["status"] = "completed"
            current_todo["completed_at"] = datetime.utcnow().isoformat()
            current_todo["llm_evaluation"] = exec_res.get("execution_summary", "")

            # Add to completed todos list
            completed_todos = shared.get("completed_todos", [])
            completed_todos.append(current_todo["id"])
            shared["completed_todos"] = completed_todos

            # Update workspace with progress and any LLM-suggested updates
            await self._update_workspace_progress(shared, current_todo, exec_res)
            await self._process_workspace_updates(shared, baml_evaluation.get("workspace_updates", []))

            print(f"✅ Completed todo {current_index + 1}/{len(todos)}: {current_todo['title']}")

            # Use BAML's next step recommendation if available
            next_todo_id = baml_evaluation.get("next_todo_id")
            if next_todo_id:
                # Find the next todo by ID (allows for non-linear progression)
                next_index = None
                for i, todo in enumerate(todos):
                    if todo["id"] == next_todo_id:
                        next_index = i
                        break

                if next_index is not None:
                    shared["current_todo_index"] = next_index
                    print(f"🧠 LLM recommended jumping to todo: {todos[next_index]['title']}")
                    return "execute"
                else:
                    logger.warning(f"LLM recommended next_todo_id '{next_todo_id}' not found, using linear progression")

            # Default linear progression
            shared["current_todo_index"] = current_index + 1

            # Check if plan is complete
            if current_index + 1 >= len(todos):
                shared["plan_completed"] = True
                shared["plan_end_time"] = datetime.utcnow().isoformat()
                print(f"🎉 Plan completed! All {len(todos)} todos finished.")
                return "respond"
            else:
                # Continue with next todo
                next_todo = todos[current_index + 1]
                print(f"➡️ Moving to next todo: {next_todo['title']}")
                return "execute"
        else:
            # Todo not completed - LLM determined more work needed
            print(f"🔄 Todo requires more work: {exec_res.get('execution_summary')}")

            # Implement retry logic to prevent infinite loops
            retry_count = shared.get("todo_retry_counts", {}).get(current_todo["id"], 0)
            max_retries = 2  # Allow up to 2 retries per todo

            logger.info(f"Todo {current_todo['id']} not completed. Retry count: {retry_count}/{max_retries}")
            logger.debug(f"Execution summary: {exec_res.get('execution_summary', 'No summary')}")

            if retry_count < max_retries:
                # Increment retry count and try again
                if "todo_retry_counts" not in shared:
                    shared["todo_retry_counts"] = {}
                shared["todo_retry_counts"][current_todo["id"]] = retry_count + 1

                print(f"🔄 Retrying todo (attempt {retry_count + 2}/{max_retries + 1}): {current_todo['title']}")
                logger.info(f"Retrying todo {current_todo['id']} - attempt {retry_count + 2}")
                return "execute"
            else:
                # Max retries reached - mark as failed and move on
                print(f"❌ Todo failed after {max_retries + 1} attempts: {current_todo['title']}")
                logger.warning(f"Todo {current_todo['id']} failed after max retries: {exec_res.get('execution_summary')}")

                # Mark todo as failed in shared state
                if "failed_todos" not in shared:
                    shared["failed_todos"] = []
                shared["failed_todos"].append({
                    "todo": current_todo,
                    "reason": exec_res.get('execution_summary', 'LLM evaluation failed'),
                    "retry_count": retry_count + 1
                })

                # Move to next todo
                shared["current_todo_index"] = current_index + 1

                if current_index + 1 >= len(todos):
                    return "respond"
                else:
                    return "execute"

    async def _process_workspace_updates(self, shared, workspace_updates: list):
        """Process LLM-suggested workspace file updates."""
        if not workspace_updates:
            return

        tool_registry = shared.get("tool_registry")
        if not tool_registry or "virtual_fs" not in tool_registry._tool_instances:
            return

        virtual_fs_tool = tool_registry._tool_instances["virtual_fs"]

        for filename in workspace_updates:
            try:
                # For now, we just log that the LLM suggested updating these files
                # In the future, we could implement more sophisticated workspace management
                logger.info(f"LLM suggested updating workspace file: {filename}")
                print(f"📝 LLM recommended updating: {filename}")

            except Exception as e:
                logger.warning(f"Error processing workspace update for {filename}: {str(e)}")

    async def _update_workspace_progress(self, shared, completed_todo, exec_res):
        """Update workspace file with todo completion progress."""
        workspace_filename = shared.get("workspace_filename")
        tool_registry = shared.get("tool_registry")

        if not workspace_filename or not tool_registry or "virtual_fs" not in tool_registry._tool_instances:
            return

        try:
            virtual_fs_tool = tool_registry._tool_instances["virtual_fs"]

            # Read current workspace content
            read_result = await virtual_fs_tool.execute({
                "action": "read",
                "filename": workspace_filename
            })

            if not read_result.get("success", False):
                return

            # Fix: Access content through the correct structure
            current_content = read_result.get("result", {}).get("file", {}).get("content", "")

            # Update the todo status in the content
            todo_id = completed_todo["id"]
            todo_title = completed_todo["title"]

            # Replace the todo status line
            updated_content = current_content.replace(
                f"### {shared.get('current_todo_index', 0) + 1}. ⏳ {todo_title} (ID: {todo_id})",
                f"### {shared.get('current_todo_index', 0) + 1}. ✅ {todo_title} (ID: {todo_id})"
            )

            # Add execution log entry with LLM reasoning
            llm_reasoning = exec_res.get('execution_summary', 'No LLM evaluation available')
            tool_results = exec_res.get('tool_results', [])

            log_entry = f"\n- {datetime.utcnow().isoformat()}: ✅ Completed '{todo_title}'"
            log_entry += f"\n  🧠 LLM Evaluation: {llm_reasoning}"

            if tool_results:
                for tool_result in tool_results:
                    tool_name = tool_result.get('tool', 'unknown')
                    success = tool_result.get('success', False)
                    status_icon = "✅" if success else "❌"
                    log_entry += f"\n  🔧 {status_icon} Tool: {tool_name}"

            if "## Execution Log" in updated_content:
                updated_content = updated_content.replace(
                    "## Execution Log",
                    f"## Execution Log{log_entry}"
                )

            # Update the workspace file
            await virtual_fs_tool.execute({
                "action": "update",
                "filename": workspace_filename,
                "content": updated_content
            })

            logger.info(f"Updated workspace progress for todo: {todo_title}")

        except Exception as e:
            logger.warning(f"Failed to update workspace progress: {str(e)}")

    async def _handle_dependency_error(self, shared, prep_res):
        """Handle dependency errors by finding next executable todo or marking plan as blocked."""
        plan = shared.get("structured_plan", {})
        current_index = shared.get("current_todo_index", 0)
        todos = plan.get("todos", [])
        completed_todos = shared.get("completed_todos", [])

        logger.info(f"Handling dependency error for todo {current_index + 1}/{len(todos)}")

        # Try to find the next executable todo (one whose dependencies are met)
        for i in range(current_index + 1, len(todos)):
            todo = todos[i]
            dependencies = todo.get("dependencies", [])
            unmet_dependencies = [dep for dep in dependencies if dep not in completed_todos]

            if not unmet_dependencies:
                # Found an executable todo, jump to it
                shared["current_todo_index"] = i
                logger.info(f"Found executable todo at index {i}: {todo['title']}")
                print(f"⏭️ Skipping blocked todo, jumping to: {todo['title']}")
                return "execute"

        # No executable todos found - check if any todos can be completed
        # This might happen if there are circular dependencies or missing todos
        blocked_todos = []
        for i in range(current_index, len(todos)):
            todo = todos[i]
            if todo["id"] not in completed_todos:
                dependencies = todo.get("dependencies", [])
                unmet_dependencies = [dep for dep in dependencies if dep not in completed_todos]
                if unmet_dependencies:
                    blocked_todos.append({
                        "id": todo["id"],
                        "title": todo["title"],
                        "unmet_dependencies": unmet_dependencies
                    })

        if blocked_todos:
            logger.error(f"Plan is blocked - no executable todos found. Blocked todos: {blocked_todos}")
            print(f"🚫 Plan execution blocked - no todos can be executed due to unmet dependencies")
            for blocked in blocked_todos:
                print(f"   - {blocked['title']} (waiting for: {blocked['unmet_dependencies']})")

            # Mark plan as failed due to dependency issues
            shared["plan_completed"] = True
            shared["plan_failed"] = True
            shared["failure_reason"] = f"Dependency deadlock - blocked todos: {[b['title'] for b in blocked_todos]}"
            return "respond"
        else:
            # All remaining todos are completed, plan is done
            shared["plan_completed"] = True
            shared["plan_end_time"] = datetime.utcnow().isoformat()
            print(f"🎉 Plan completed! All executable todos finished.")
            return "respond"
