"""
Personal Assistant AsyncNodes following chatbot_core patterns.
"""

import asyncio
import json
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import logging
import re


from pocketflow import AsyncNode
from utils.baml_utils import RateLimitedBAMLGeminiLLM
from app.services.parameter_processor import ParameterProcessor, ParameterProcessingError
from app.agents.personal_assistant.context_resolver import create_context_resolver

logger = logging.getLogger(__name__)





class PAThinkNode(AsyncNode):
    """
    Enhanced node that implements Phase 1: Meta-Cognitive Thinking.

    This node analyzes user requests, classifies planning types, and updates
    the structured thoughts.txt file with comprehensive analysis.
    """

    def __init__(self):
        super().__init__()
        self.parameter_processor = ParameterProcessor()

    async def prep_async(self, shared):
        """Prepare thinking data with VFS context integration."""
        user_message = shared.get("user_message", "")
        session = shared.get("session", {})
        config = shared.get("config")
        tool_registry = shared.get("tool_registry")
        baml_client = shared.get("baml_client")
        ctx = shared.get("context", {}) or {}
        entity_store = shared.get("entity_store")

        # Get session ID for VFS operations
        session_id = session.get("id") if session else None

        # Get conversation history
        messages = session.get("messages", [])
        conversation_history = []
        for msg in messages[-10:]:  # Last 10 messages for context
            conversation_history.append(f"{msg['role']}: {msg['content']}")

        # Compute time context (timezone -> now)
        tz_from_ctx = ctx.get("timezone") or ctx.get("user_timezone") or ctx.get("tz")
        tz_from_cfg = None
        try:
            cfg = getattr(config, "config_data", None) or {}
            prefs = cfg.get("preferences", {}) if isinstance(cfg, dict) else {}
            tz_from_cfg = prefs.get("timezone")
        except Exception:
            pass
        tz_name = (tz_from_ctx or tz_from_cfg or "UTC").strip() or "UTC"
        try:
            tzinfo = ZoneInfo(tz_name)
        except Exception:
            tzinfo = ZoneInfo("UTC")
            tz_name = "UTC"
        now_utc = datetime.now(timezone.utc)
        now_local = now_utc.astimezone(tzinfo)
        time_context_prompt = (
            "\n\nTime awareness (runtime-provided):\n"
            f"- CURRENT_DATETIME_UTC: {now_utc.isoformat()}\n"
            f"- USER_TIMEZONE: {tz_name}\n"
            f"- CURRENT_DATETIME_LOCAL: {now_local.isoformat()}\n"
            "Guidance: Interpret relative dates/times in USER_TIMEZONE. When calling tools, "
            "always include explicit timezone offsets (RFC3339). If user omits a date range for "
            "calendar queries, choose a sensible range based on their request and this time context."
        )

        # Get available tools
        available_tools = []
        if tool_registry:
            tools = await tool_registry.get_available_tools()
            available_tools = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "schema": tool.schema
                }
                for tool in tools
            ]

        # Add entity store context information
        entity_context_prompt = ""
        if entity_store:
            try:
                # Cleanup expired entities
                entity_store.cleanup_expired_entities()

                # Get recent entities for context
                recent_entities = entity_store.get_recent_entities(limit=5)
                recent_executions = entity_store.get_recent_tool_executions(limit=5)

                if recent_entities or recent_executions:
                    entity_context_prompt = "\n\nTool Entity Store:\n"

                    # Add recent entities
                    if recent_entities:
                        entity_context_prompt += "\nRecently discussed entities:\n"
                        for entity in recent_entities:
                            entity_info = f"- {entity.entity_type.value}: {entity.display_name}"
                            if entity.entity_type.name == "CALENDAR_EVENT":
                                start_time = entity.data.get('start', '')
                                if start_time:
                                    entity_info += f" (on {start_time})"
                            elif entity.entity_type.name == "PLAN":
                                # Include full plan details for plans
                                plan_data = entity.data
                                if isinstance(plan_data, dict):
                                    entity_info += f"\n  Plan Details:"
                                    entity_info += f"\n  - Status: {plan_data.get('status', 'unknown')}"
                                    entity_info += f"\n  - Priority: {plan_data.get('priority', 'unknown')}"
                                    entity_info += f"\n  - Complexity: {plan_data.get('complexity', 'unknown')}"

                                    subtasks = plan_data.get('subtasks', [])
                                    if subtasks:
                                        entity_info += f"\n  - Subtasks ({len(subtasks)}):"
                                        for i, subtask in enumerate(subtasks[:5], 1):  # Show first 5 subtasks
                                            entity_info += f"\n    {i}. {subtask.get('title', 'Untitled')} ({subtask.get('status', 'pending')})"
                                        if len(subtasks) > 5:
                                            entity_info += f"\n    ... and {len(subtasks) - 5} more subtasks"

                                    progress = plan_data.get('progress', {})
                                    if progress:
                                        completion = progress.get('completion_percentage', 0)
                                        entity_info += f"\n  - Progress: {completion}% complete"

                            entity_info += f" [ID: {entity.entity_id}]"
                            entity_context_prompt += entity_info + "\n"

                    # Add recent tool executions
                    if recent_executions:
                        entity_context_prompt += "\nRecent tool executions:\n"
                        for execution in recent_executions:
                            exec_info = f"- {execution.get_summary()}"
                            if execution.user_request:
                                exec_info += f" (for: '{execution.user_request[:50]}...')"

                            # Include result details for planning tool executions
                            if execution.tool_name == "planning" and execution.raw_output:
                                result = execution.raw_output
                                if isinstance(result, dict) and result.get('success'):
                                    data = result.get('data', {})
                                    if 'plan' in data:
                                        plan = data['plan']
                                        exec_info += f"\n    → Created plan: {plan.get('title', 'Untitled')}"
                                        exec_info += f" (ID: {plan.get('id', 'unknown')})"
                                        if 'subtasks' in plan:
                                            exec_info += f" with {len(plan['subtasks'])} subtasks"

                            entity_context_prompt += exec_info + "\n"

                    entity_context_prompt += (
                        "\nGuidance: When users refer to entities ambiguously (e.g., 'delete the event', "
                        "'call John', 'execute the plan'), check if they match any recently discussed entities above. "
                        "Use the entity ID for operations when you can identify the correct entity. "
                        "For plans: If a user asks to execute, show, or work with a plan, use the plan details shown above. "
                        "You can see the full plan structure including all subtasks and their status. "
                        "You can also reference previous tool executions to provide context-aware responses."
                    )
            except Exception as e:
                logger.warning(f"Failed to build entity context: {str(e)}")

        # Add VFS context for session continuity
        vfs_context_prompt = ""
        if tool_registry and session_id:
            try:
                # Get VFS tool instance
                vfs_tool = tool_registry.get_tool_instance("virtual_fs")
                if vfs_tool:
                    # Set session context
                    user_timezone = ctx.get("timezone") or ctx.get("user_timezone") or tz_name
                    user_id = ctx.get("user_id") or session.get("user_id")
                    vfs_tool.set_session_context(session_id, user_timezone, user_id)

                    # Read mandatory files for context
                    vfs_context_prompt = "\n\nVirtual File System Context:\n"

                    # Read thoughts.txt
                    thoughts_result = await vfs_tool.execute({"action": "read", "file_path": "thoughts.txt"})
                    if thoughts_result.get("success") and thoughts_result.get("data", {}).get("file", {}).get("content"):
                        thoughts_content = thoughts_result["data"]["file"]["content"]
                        vfs_context_prompt += f"\nCURRENT THOUGHTS FILE:\n{thoughts_content}\n"

                    # Read plan.txt
                    plan_result = await vfs_tool.execute({"action": "read", "file_path": "plan.txt"})
                    if plan_result.get("success") and plan_result.get("data", {}).get("file", {}).get("content"):
                        plan_content = plan_result["data"]["file"]["content"]
                        vfs_context_prompt += f"\nCURRENT PLAN FILE:\n{plan_content}\n"

                    # Read web_search_results.txt
                    search_result = await vfs_tool.execute({"action": "read", "file_path": "web_search_results.txt"})
                    if search_result.get("success") and search_result.get("data", {}).get("file", {}).get("content"):
                        search_content = search_result["data"]["file"]["content"]
                        vfs_context_prompt += f"\nWEB SEARCH RESULTS:\n{search_content}\n"

                    vfs_context_prompt += (
                        "\nGuidance: Use the VFS context above to maintain session continuity. "
                        "Update thoughts.txt with new analysis, plan.txt with execution progress, "
                        "and web_search_results.txt with search findings."
                    )

                    # Store VFS tool reference for later use
                    shared["vfs_tool"] = vfs_tool

            except Exception as e:
                logger.warning(f"Failed to build VFS context: {str(e)}")

        base_system_prompt = config.system_prompt if config else ""
        system_prompt = base_system_prompt + time_context_prompt + entity_context_prompt + vfs_context_prompt

        return {
            "user_message": user_message,
            "conversation_history": "\n".join(conversation_history),
            "available_tools": available_tools,
            "system_prompt": system_prompt,
            "current_thought_number": len(shared.get("thoughts", [])) + 1,
            "baml_client": baml_client,
            "session_id": session_id,
            "time_context": {
                "timezone": tz_name,
                "now_utc": now_utc.isoformat(),
                "now_local": now_local.isoformat(),
            }
        }

    async def exec_async(self, prep_res):
        """Execute the thinking process."""
        user_message = prep_res["user_message"]
        conversation_history = prep_res["conversation_history"]
        available_tools = prep_res["available_tools"]
        system_prompt = prep_res["system_prompt"]
        baml_client = prep_res.get("baml_client")
        if not baml_client:
            logger.error("BAML client not available")
            return {
                "thinking": "I need to process your request, but I'm having technical difficulties.",
                "action": "respond",
                "action_input": "I apologize, but I'm experiencing technical issues. Please try again.",
                "is_final": True,
                "needs_tools": False
            }

        try:
            # Call BAML function for thinking
            thinking_result = await baml_client.call_function(
                "PersonalAssistantThinking",
                user_query=user_message,
                conversation_history=conversation_history,
                available_tools=json.dumps(available_tools),
                system_prompt=system_prompt
            )

            # Convert BAML result to dict format
            if hasattr(thinking_result, 'thinking'):
                thought_data = {
                    "thinking": thinking_result.thinking,
                    "action": thinking_result.action,
                    "action_input": thinking_result.action_input,
                    "is_final": thinking_result.is_final,
                    "needs_tools": getattr(thinking_result, 'needs_tools', False),
                    "tools_to_use": getattr(thinking_result, 'tools_to_use', [])
                }
            else:
                # Fallback if BAML function not available
                thought_data = {
                    "thinking": f"I need to help the user with: {user_message}",
                    "action": "respond" if not available_tools else "use_tools",
                    "action_input": user_message,
                    "is_final": False,
                    "needs_tools": len(available_tools) > 0,
                    "tools_to_use": []
                }

            return thought_data

        except Exception as e:
            logger.error(f"Error in thinking process: {str(e)}")

            # Enhanced error handling with recovery strategies
            error_context = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "user_message": user_message,
                "timestamp": datetime.now().isoformat()
            }

            # Log error to VFS if available
            await self._log_error_to_vfs(shared, error_context)

            # Attempt graceful recovery
            recovery_response = self._attempt_error_recovery(e, user_message)

            return {
                "thinking": f"I encountered an issue while processing your request: {recovery_response['thinking']}",
                "action": "respond",
                "action_input": recovery_response['response'],
                "is_final": True,
                "needs_tools": False,
                "error_context": error_context
            }

    async def post_async(self, shared, prep_res, exec_res):
        """Save thinking result, update thoughts.txt, and decide next step."""
        # Save thinking result
        if "thoughts" not in shared:
            shared["thoughts"] = []
        shared["thoughts"].append(exec_res)

        # Update thoughts.txt with structured analysis
        await self._update_thoughts_file(shared, prep_res, exec_res)

        # Process tools_to_use with centralized parameter processor
        try:
            tools = exec_res.get("tools_to_use") or []
            processed_tools: List[Dict[str, Any]] = []
            tool_registry = prep_res.get("tool_registry")

            for tool_call in tools:
                tool_name = "unknown"  # Initialize with default value
                try:
                    # Extract tool name and parameters
                    if hasattr(tool_call, 'name'):
                        tool_name = tool_call.name
                        raw_params = getattr(tool_call, 'parameters', {}) or {}
                    elif isinstance(tool_call, dict):
                        tool_name = tool_call.get('name') or tool_call.get('tool')
                        raw_params = tool_call.get('parameters', {})
                    else:
                        logger.warning(f"Invalid tool call format: {tool_call}")
                        continue

                    if not tool_name or tool_name == "unknown":
                        logger.warning("Tool call missing name")
                        continue

                    # Get tool schema for validation
                    tool_schema = None
                    if tool_registry:
                        tool_schema = tool_registry.get_tool_schema(tool_name)

                    if not tool_schema:
                        logger.warning(f"No schema found for tool: {tool_name}")
                        # Still process without schema validation
                        processed_tools.append({
                            'name': tool_name,
                            'parameters': raw_params if isinstance(raw_params, dict) else {}
                        })
                        continue

                    # Process parameters using centralized processor
                    processed_params = await self.parameter_processor.process_baml_parameters(
                        raw_params, tool_schema, tool_name
                    )

                    processed_tools.append({
                        'name': tool_name,
                        'parameters': processed_params
                    })

                    logger.debug(f"Successfully processed parameters for {tool_name}")

                except ParameterProcessingError as e:
                    logger.error(f"Parameter processing failed for tool {tool_name}: {e}")
                    # Add error information for user feedback
                    processed_tools.append({
                        'name': tool_name,
                        'parameters': {},
                        'error': str(e)
                    })
                except Exception as e:
                    logger.error(f"Unexpected error processing tool {tool_name}: {e}")
                    continue

            exec_res['tools_to_use'] = processed_tools
        except Exception as _e:
            logger.warning(f"Failed to normalize BAML tools_to_use: {_e}")

        # Persist time context for downstream nodes
        if prep_res.get("time_context"):
            shared["time_context"] = prep_res["time_context"]

        # Save current action information
        shared["current_action"] = exec_res["action"]
        shared["current_action_input"] = exec_res["action_input"]
        shared["needs_tools"] = exec_res.get("needs_tools", False)
        shared["tools_to_use"] = exec_res.get("tools_to_use", [])

        print(f"🤔 PA Thinking: {exec_res['thinking'][:100]}...")

        # Decide next step - prioritize tools over final response
        if exec_res.get("needs_tools", False) and exec_res.get("tools_to_use"):
            # Check if we're using the planning tool - if so, execute it first
            tools_to_use = exec_res.get("tools_to_use", [])
            has_planning_tool = any(
                (hasattr(tool, 'name') and tool.name == "planning") or
                (isinstance(tool, dict) and tool.get('name') == "planning")
                for tool in tools_to_use
            )

            if has_planning_tool:
                # Filter to only execute the planning tool first
                planning_tools = [
                    tool for tool in tools_to_use
                    if ((hasattr(tool, 'name') and tool.name == "planning") or
                        (isinstance(tool, dict) and tool.get('name') == "planning"))
                ]
                shared["tools_to_use"] = planning_tools
                print(f"📋 Executing planning tool first, will auto-extract execution steps")

            return "tools"
        elif exec_res.get("is_final", False):
            shared["final_response"] = exec_res["action_input"]
            return "end"
        else:
            return "respond"

    async def _update_thoughts_file(self, shared, prep_res, exec_res):
        """Update thoughts.txt with structured meta-cognitive analysis."""
        try:
            vfs_tool = shared.get("vfs_tool")
            if not vfs_tool:
                logger.warning("VFS tool not available for thoughts update")
                return

            user_message = prep_res.get("user_message", "")
            thinking = exec_res.get("thinking", "")
            action = exec_res.get("action", "")
            needs_tools = exec_res.get("needs_tools", False)
            tools_to_use = exec_res.get("tools_to_use", [])
            time_context = prep_res.get("time_context", {})

            # Classify planning type and complexity
            planning_type = self._classify_planning_type(user_message, thinking, tools_to_use)
            complexity_level = self._assess_complexity(user_message, tools_to_use)

            # Create structured analysis entry
            timestamp = time_context.get("now_local", datetime.now().isoformat())

            analysis_entry = f"""
[{timestamp}] NEW_USER_REQUEST: {user_message}
[{timestamp}] THINKING_ANALYSIS: {thinking}
[{timestamp}] PRIMARY_GOAL: {self._extract_primary_goal(user_message, thinking)}
[{timestamp}] COMPLEXITY_LEVEL: {complexity_level}
[{timestamp}] PLANNING_TYPE: {planning_type}
[{timestamp}] REQUIRED_TOOLS: {[tool.get('name') if isinstance(tool, dict) else getattr(tool, 'name', 'unknown') for tool in tools_to_use]}
[{timestamp}] ESTIMATED_STEPS: {len(tools_to_use) if tools_to_use else 1}
[{timestamp}] ACTION_DECISION: {action}
[{timestamp}] NEEDS_TOOLS: {needs_tools}
[{timestamp}] GOAL_DECOMPOSITION: {self._decompose_goals(user_message, thinking)}
[{timestamp}] DEPENDENCIES_IDENTIFIED: {self._identify_dependencies(tools_to_use)}
[{timestamp}] SUCCESS_CRITERIA: {self._define_success_criteria(user_message, thinking)}
"""

            # Append to thoughts.txt
            await vfs_tool.execute({
                "action": "append",
                "file_path": "thoughts.txt",
                "content": analysis_entry
            })

            logger.debug(f"Updated thoughts.txt with analysis for: {user_message[:50]}...")

        except Exception as e:
            logger.error(f"Failed to update thoughts.txt: {str(e)}")

    def _classify_planning_type(self, user_message: str, thinking: str, tools_to_use: list) -> str:
        """Classify the type of planning needed."""
        message_lower = user_message.lower()

        # Domain planning indicators
        domain_keywords = ["create a plan", "make a plan", "plan for", "strategy", "approach", "method"]
        if any(keyword in message_lower for keyword in domain_keywords):
            return "Domain"

        # Procedural planning indicators
        procedural_keywords = ["schedule", "send", "create", "delete", "update", "search", "find"]
        if any(keyword in message_lower for keyword in procedural_keywords):
            return "Procedural"

        # Hybrid indicators
        if len(tools_to_use) > 2:
            return "Hybrid"

        return "Procedural"  # Default

    def _assess_complexity(self, user_message: str, tools_to_use: list) -> str:
        """Assess the complexity level of the request."""
        tool_count = len(tools_to_use) if tools_to_use else 0

        if tool_count == 0:
            return "Single Tool"
        elif tool_count <= 2:
            return "Multi-Tool"
        else:
            return "Complex Multi-Tool"

    def _extract_primary_goal(self, user_message: str, thinking: str) -> str:
        """Extract the primary goal from user message and thinking."""
        # Simple extraction - could be enhanced with NLP
        if "help me" in user_message.lower():
            return user_message.replace("help me", "").strip()
        return user_message[:100] + "..." if len(user_message) > 100 else user_message

    def _decompose_goals(self, user_message: str, thinking: str) -> str:
        """Decompose the request into sub-goals."""
        # Simple decomposition based on conjunctions
        if " and " in user_message:
            parts = user_message.split(" and ")
            return f"Sub-goals: {', '.join(parts)}"
        return f"Single goal: {user_message}"

    def _identify_dependencies(self, tools_to_use: list) -> str:
        """Identify dependencies between tools."""
        if not tools_to_use or len(tools_to_use) <= 1:
            return "No dependencies"

        tool_names = []
        for tool in tools_to_use:
            if isinstance(tool, dict):
                name = tool.get('name', 'unknown')
            else:
                name = getattr(tool, 'name', 'unknown')
            tool_names.append(str(name) if name else 'unknown')

        return f"Sequential execution required: {' -> '.join(tool_names)}"

    def _define_success_criteria(self, user_message: str, thinking: str) -> str:
        """Define success criteria for the request."""
        if "create" in user_message.lower():
            return "Successfully create requested item"
        elif "send" in user_message.lower():
            return "Successfully send message/email"
        elif "schedule" in user_message.lower():
            return "Successfully schedule event"
        elif "find" in user_message.lower() or "search" in user_message.lower():
            return "Successfully find and return relevant information"
        else:
            return "Successfully complete user request"

    async def _log_error_to_vfs(self, shared, error_context: Dict[str, Any]) -> None:
        """Log error information to VFS for debugging and recovery."""
        try:
            vfs_tool = shared.get("vfs_tool")
            if not vfs_tool:
                return

            error_log = f"""
[{error_context['timestamp']}] ERROR_ENCOUNTERED
ERROR_TYPE: {error_context['error_type']}
ERROR_MESSAGE: {error_context['error_message']}
USER_REQUEST: {error_context['user_message']}
RECOVERY_ATTEMPTED: Yes
"""

            await vfs_tool.execute({
                "action": "append",
                "file_path": "thoughts.txt",
                "content": error_log
            })

        except Exception as e:
            logger.warning(f"Failed to log error to VFS: {str(e)}")

    def _attempt_error_recovery(self, error: Exception, user_message: str) -> Dict[str, str]:
        """Attempt to provide helpful recovery suggestions based on error type."""
        error_type = type(error).__name__
        error_message = str(error).lower()

        # API/Network errors
        if "connection" in error_message or "timeout" in error_message or "network" in error_message:
            return {
                "thinking": "I encountered a network connectivity issue while processing your request.",
                "response": "I'm experiencing connectivity issues at the moment. Please try your request again in a few moments. If the problem persists, the service may be temporarily unavailable."
            }

        # Authentication errors
        if "auth" in error_message or "unauthorized" in error_message or "permission" in error_message:
            return {
                "thinking": "I encountered an authentication issue with one of the required services.",
                "response": "It looks like I need to re-authenticate with one of the services to complete your request. Please check the authorization status in the app and re-authorize if needed, then try your request again."
            }

        # Tool-specific errors
        if "gmail" in error_message:
            return {
                "thinking": "I encountered an issue with the Gmail service.",
                "response": "I'm having trouble accessing Gmail at the moment. Please ensure Gmail is authorized in the app settings and try again. If you continue to have issues, the Gmail service may be temporarily unavailable."
            }

        if "calendar" in error_message:
            return {
                "thinking": "I encountered an issue with the Google Calendar service.",
                "response": "I'm having trouble accessing Google Calendar. Please ensure Calendar is authorized in the app settings and try again. If the issue persists, please check your calendar permissions."
            }

        # Parameter/validation errors
        if "parameter" in error_message or "validation" in error_message or "invalid" in error_message:
            return {
                "thinking": "I encountered an issue with the parameters for your request.",
                "response": "I had trouble understanding some details of your request. Could you please provide more specific information or rephrase your request? For example, if you're scheduling an event, please include the date, time, and participants."
            }

        # Rate limiting errors
        if "rate" in error_message or "limit" in error_message or "quota" in error_message:
            return {
                "thinking": "I encountered a rate limiting issue with one of the services.",
                "response": "I've hit a temporary usage limit with one of the services. Please wait a few minutes and try your request again. The service should be available shortly."
            }

        # Generic fallback
        return {
            "thinking": "I encountered an unexpected issue while processing your request.",
            "response": "I apologize, but I encountered an unexpected error while processing your request. Please try rephrasing your request or breaking it down into smaller steps. If the problem continues, please let me know and I'll do my best to help in a different way."
        }


class PAToolCallNode(AsyncNode):
    """
    Enhanced node that implements Phase 3: Systematic Execution.

    This node executes tools step-by-step with continuous evaluation,
    plan updates, and multi-tool orchestration capabilities.
    """

    async def prep_async(self, shared):
        """Prepare tool call data with VFS and planning context."""
        tools_to_use = shared.get("tools_to_use", [])
        tool_registry = shared.get("tool_registry")
        user_message = shared.get("user_message", "")
        entity_store = shared.get("entity_store")
        session_id = shared.get("session_id")
        vfs_tool = shared.get("vfs_tool")
        time_context = shared.get("time_context", {})

        return {
            "tools_to_use": tools_to_use,
            "tool_registry": tool_registry,
            "user_message": user_message,
            "entity_store": entity_store,
            "session_id": session_id,
            "vfs_tool": vfs_tool,
            "time_context": time_context
        }

    async def exec_async(self, prep_res):
        """Execute tool calls with systematic evaluation and plan updates."""
        tools_to_use = prep_res["tools_to_use"]
        tool_registry = prep_res["tool_registry"]
        user_message = prep_res["user_message"]
        entity_store = prep_res.get("entity_store")
        session_id = prep_res.get("session_id")
        vfs_tool = prep_res.get("vfs_tool")
        time_context = prep_res.get("time_context", {})

        if not tool_registry:
            return {"error": "Tool registry not available"}

        # Create context resolver if entity store is available
        context_resolver = None
        if entity_store:
            context_resolver = create_context_resolver(entity_store)

        tool_results = []

        # Initialize execution tracking
        execution_start_time = datetime.now(timezone.utc)
        total_steps = len(tools_to_use)
        current_step = 0

        for tool_call in tools_to_use:
            current_step += 1
            tool_name = "unknown"
            parameters = {}
            start_time = datetime.now(timezone.utc)

            try:
                # Handle both dict and Pydantic object formats
                if hasattr(tool_call, 'name'):
                    # Pydantic object
                    tool_name = tool_call.name
                    parameters = tool_call.parameters if hasattr(tool_call, 'parameters') else {}
                else:
                    # Dictionary format
                    tool_name = tool_call.get("name") or tool_call.get("tool")
                    parameters = tool_call.get("parameters", {})

                if not tool_name or tool_name == "unknown":
                    continue

                # Log step execution start
                print(f"🔄 Executing step {current_step}/{total_steps}: {tool_name}")

                # Update plan.txt with step start if VFS is available
                if vfs_tool and tool_name != "virtual_fs":
                    await self._update_step_status(vfs_tool, current_step, tool_name, "in_progress", start_time)

                # Parameters are already processed by centralized processor
                # Check for processing errors
                if isinstance(tool_call, dict) and 'error' in tool_call:
                    logger.warning(f"Tool {tool_name} has processing error: {tool_call['error']}")
                    # Still try to execute with available parameters

                # Set context on tool if it supports it and we have context
                if context_resolver and hasattr(tool_registry, '_tool_instances'):
                    tool_instance = tool_registry._tool_instances.get(tool_name)
                    if tool_instance and hasattr(tool_instance, 'set_context'):
                        try:
                            tool_instance.set_context(context_resolver, user_message)
                            logger.debug(f"Set context on tool: {tool_name}")
                        except Exception as e:
                            logger.warning(f"Failed to set context on tool {tool_name}: {str(e)}")

                # Set entity store and session context for planning tool
                if tool_name == "planning" and hasattr(tool_registry, '_tool_instances'):
                    tool_instance = tool_registry._tool_instances.get(tool_name)
                    if tool_instance:
                        # Set entity store reference
                        if entity_store and hasattr(tool_instance, 'set_memory'):
                            tool_instance.set_memory(entity_store)
                            logger.debug(f"Set entity store reference on planning tool")

                        # Set session context
                        if session_id and hasattr(tool_instance, 'set_session_context'):
                            tool_instance.set_session_context(session_id)
                            logger.debug(f"Set session context {session_id} on planning tool")

                # Set session context for virtual_fs tool
                if tool_name == "virtual_fs" and session_id and hasattr(tool_registry, '_tool_instances'):
                    tool_instance = tool_registry._tool_instances.get(tool_name)
                    if tool_instance and hasattr(tool_instance, 'set_session_context'):
                        tool_instance.set_session_context(session_id)
                        logger.debug(f"Set session context {session_id} on virtual_fs tool")

                # Add session_id to parameters for session-aware tools
                if tool_name in ["planning", "virtual_fs"] and session_id and "session_id" not in parameters:
                    parameters["session_id"] = session_id
                    logger.debug(f"Added session_id {session_id} to {tool_name} tool parameters")

                # Execute the tool
                result = await tool_registry.execute_tool(tool_name, parameters)

                # Calculate execution time
                end_time = datetime.now(timezone.utc)
                execution_time_ms = (end_time - start_time).total_seconds() * 1000

                # Evaluate step success
                step_success = self._evaluate_step_success(result)
                step_evaluation = self._generate_step_evaluation(tool_name, result, step_success)

                tool_result = {
                    "tool": tool_name,
                    "parameters": parameters,
                    "result": result,
                    "success": True,
                    "timestamp": end_time.isoformat(),
                    "execution_time_ms": execution_time_ms,
                    "step_number": current_step,
                    "step_evaluation": step_evaluation,
                    "step_success": step_success
                }

                tool_results.append(tool_result)

                # Update plan.txt with step completion if VFS is available
                if vfs_tool and tool_name != "virtual_fs":
                    await self._update_step_status(vfs_tool, current_step, tool_name, "completed", end_time, result, step_evaluation)

                print(f"✅ Completed step {current_step}/{total_steps}: {tool_name} ({'Success' if step_success else 'Partial'})")

            except Exception as e:
                # Calculate execution time even for errors
                end_time = datetime.now(timezone.utc)
                execution_time_ms = (end_time - start_time).total_seconds() * 1000

                logger.error(f"Error executing tool {tool_name}: {str(e)}")

                # Enhanced error handling with recovery strategies
                error_analysis = self._analyze_tool_error(tool_name, e, parameters)
                recovery_suggestion = self._get_tool_recovery_suggestion(tool_name, e)

                tool_result = {
                    "tool": tool_name,
                    "parameters": parameters,
                    "result": f"Error: {str(e)}",
                    "success": False,
                    "timestamp": end_time.isoformat(),
                    "execution_time_ms": execution_time_ms,
                    "step_number": current_step,
                    "error_message": str(e),
                    "error_type": type(e).__name__,
                    "error_analysis": error_analysis,
                    "recovery_suggestion": recovery_suggestion,
                    "step_success": False
                }

                tool_results.append(tool_result)

                # Update plan.txt with error status if VFS is available
                if vfs_tool and tool_name != "virtual_fs":
                    await self._update_step_status(vfs_tool, current_step, tool_name, "failed", end_time,
                                                 f"Error: {str(e)}", error_analysis)

                # Log detailed error for debugging
                await self._log_tool_error(vfs_tool, tool_name, current_step, e, parameters)

                print(f"❌ Failed step {current_step}/{total_steps}: {tool_name} - {error_analysis}")

        return {"tool_results": tool_results}

    async def post_async(self, shared, prep_res, exec_res):
        """Save tool results and continue to response."""
        tool_results = exec_res.get("tool_results", [])

        # Save tool results
        if "tools_used" not in shared:
            shared["tools_used"] = []
        shared["tools_used"].extend(tool_results)

        # Check if we just executed a planning tool and need to extract execution steps
        planning_result = None
        for tool_result in tool_results:
            if tool_result.get("tool") == "planning" and tool_result.get("success"):
                planning_result = tool_result
                break

        # Process tool results for entity store
        entity_store = shared.get("entity_store")
        user_message = shared.get("user_message", "")

        if entity_store:
            for tool_result in tool_results:
                tool_name = tool_result.get("tool", "")
                parameters = tool_result.get("parameters", {})
                result = tool_result.get("result", {})
                success = tool_result.get("success", False)
                execution_time_ms = tool_result.get("execution_time_ms", 0)
                error_message = tool_result.get("error_message")

                # Infer user intent from tool name and parameters
                user_intent = None
                if tool_name == "google_calendar":
                    action = parameters.get("action", "")
                    if action:
                        user_intent = f"{action}_calendar_event"

                # Process complete tool execution with metadata
                try:
                    logger.info(f"🔧 TOOL EXECUTION: {tool_name}")
                    logger.info(f"   📥 Parameters: {parameters}")
                    logger.info(f"   ✅ Success: {success}")
                    logger.info(f"   ⏱️  Execution Time: {execution_time_ms:.2f}ms")
                    if error_message:
                        logger.info(f"   ❌ Error: {error_message}")

                    execution_context = entity_store.process_tool_execution(
                        tool_name=tool_name,
                        user_request=user_message,
                        parameters=parameters,
                        result=result,
                        execution_time_ms=execution_time_ms,
                        success=success,
                        error_message=error_message,
                        user_intent=user_intent
                    )

                    logger.info(f"   💾 Stored execution: {execution_context.execution_id}")
                    logger.info(f"   🏷️  Extracted {len(execution_context.extracted_entity_ids)} entities")
                    if success and execution_context.extracted_entity_ids:
                        logger.info(f"   📋 Entity IDs: {execution_context.extracted_entity_ids}")

                except Exception as e:
                    logger.warning(f"Failed to process tool execution for entity store: {str(e)}")

        # Save entity store to disk after processing all tool executions
        if entity_store and tool_results:
            try:
                entity_store.save_to_disk()
                logger.info(f"💾 Saved entity store to disk after processing {len(tool_results)} tool executions")
            except Exception as e:
                logger.warning(f"Failed to save entity store to disk after tool executions: {str(e)}")

        # Save for response generation
        shared["current_tool_results"] = tool_results

        print(f"✅ Completed {len(tool_results)} tool calls")

        # If we just executed a planning tool successfully, extract execution steps
        if planning_result:
            print(f"📋 Planning completed, extracting execution steps for autonomous execution...")

            execution_steps = await self._extract_execution_steps_from_plan(planning_result, shared)

            if execution_steps:
                print(f"🚀 Extracted {len(execution_steps)} execution steps from plan:")
                for i, step in enumerate(execution_steps, 1):
                    print(f"   Step {i}: {step.get('name')} - {step.get('subtask_title', 'No title')}")

                shared["tools_to_use"] = execution_steps
                shared["retry_count"] = 0  # Reset retry count for new execution
                print(f"🔄 Continuing with autonomous execution of {len(execution_steps)} steps")
                return "tools"  # Continue with plan execution
            else:
                print(f"⚠️ No execution steps extracted from plan - will generate response instead")

        # Enhanced flow control: Check if we should continue execution or respond
        next_action = await self._determine_next_action(shared, tool_results)

        return next_action

    async def _determine_next_action(self, shared, tool_results: List[Dict[str, Any]]) -> str:
        """Determine whether to continue execution, retry failed steps, or respond."""
        try:
            # Check if there are failed tools that can be retried
            failed_results = [r for r in tool_results if not r.get("success", False)]
            successful_results = [r for r in tool_results if r.get("success", False)]

            # Get retry count from shared state
            retry_count = shared.get("retry_count", 0)
            max_retries = 2  # Maximum number of retries per failed tool

            # Check if we have a plan with remaining steps
            vfs_tool = shared.get("vfs_tool")
            has_remaining_steps = await self._check_for_remaining_steps(vfs_tool)

            # Decision logic for next action
            if failed_results and retry_count < max_retries:
                # Retry failed tools with error recovery
                print(f"🔄 Retrying {len(failed_results)} failed tools (attempt {retry_count + 1}/{max_retries})")

                # Update retry count
                shared["retry_count"] = retry_count + 1

                # Prepare retry tools with error recovery
                retry_tools = await self._prepare_retry_tools(failed_results, shared)
                shared["tools_to_use"] = retry_tools

                # Log retry attempt to VFS
                await self._log_retry_attempt(vfs_tool, failed_results, retry_count + 1)

                return "tools"  # Continue with tool execution (retry)

            elif has_remaining_steps and successful_results:
                # Continue with remaining steps in the plan
                print(f"▶️ Continuing with remaining plan steps")

                # Reset retry count for new steps
                shared["retry_count"] = 0

                # Get next steps from plan
                next_tools = await self._get_next_plan_steps(vfs_tool, shared)
                if next_tools:
                    shared["tools_to_use"] = next_tools
                    return "tools"  # Continue with tool execution (next steps)
                else:
                    return "respond"  # No more steps, generate response

            else:
                # All retries exhausted or no remaining steps - generate response
                if failed_results and retry_count >= max_retries:
                    print(f"⚠️ Max retries reached for {len(failed_results)} failed tools")
                    await self._log_max_retries_reached(vfs_tool, failed_results)

                return "respond"  # Generate final response

        except Exception as e:
            logger.error(f"Error determining next action: {str(e)}")
            return "respond"  # Fallback to response generation

    async def _check_for_remaining_steps(self, vfs_tool) -> bool:
        """Check if there are remaining steps in the plan."""
        try:
            if not vfs_tool:
                return False

            # Read plan.txt to check for pending steps
            plan_result = await vfs_tool.execute({"action": "read", "file_path": "plan.txt"})
            if not plan_result.get("success"):
                return False

            plan_content = plan_result.get("data", {}).get("file", {}).get("content", "")

            # Look for steps with "pending" or "in_progress" status
            lines = plan_content.split('\n')
            for line in lines:
                if "STATUS:" in line and ("pending" in line.lower() or "in_progress" in line.lower()):
                    return True

            return False

        except Exception as e:
            logger.error(f"Error checking for remaining steps: {str(e)}")
            return False

    async def _prepare_retry_tools(self, failed_results: List[Dict[str, Any]], shared) -> List[Dict[str, Any]]:
        """Prepare tools for retry with error recovery adjustments."""
        retry_tools = []

        for failed_result in failed_results:
            tool_name = failed_result.get("tool", "")
            original_params = failed_result.get("parameters", {})
            error_message = failed_result.get("error_message", "")

            # Apply error-specific recovery adjustments
            adjusted_params = await self._apply_error_recovery(tool_name, original_params, error_message)

            retry_tool = {
                "name": tool_name,
                "parameters": adjusted_params,
                "retry_attempt": True
            }
            retry_tools.append(retry_tool)

        return retry_tools

    async def _apply_error_recovery(self, tool_name: str, params: Dict[str, Any], error_message: str) -> Dict[str, Any]:
        """Apply error-specific recovery adjustments to tool parameters."""
        adjusted_params = params.copy()

        if tool_name == "google_calendar":
            if "missing attendee email" in error_message.lower():
                # Fix attendee email format issue
                if "event_data" in adjusted_params:
                    import json
                    try:
                        event_data = json.loads(adjusted_params["event_data"])
                        if "attendees" in event_data:
                            # Fix attendee format - ensure each attendee is a proper dict with email
                            fixed_attendees = []
                            for attendee in event_data["attendees"]:
                                if isinstance(attendee, dict):
                                    if "email" in attendee:
                                        fixed_attendees.append(attendee)
                                    else:
                                        # If attendee dict doesn't have email, try to extract it
                                        email_value = None
                                        for key, value in attendee.items():
                                            if "@" in str(value):
                                                email_value = str(value)
                                                break
                                        if email_value:
                                            fixed_attendees.append({"email": email_value})
                                elif isinstance(attendee, str) and "@" in attendee:
                                    # If attendee is a string email, convert to proper format
                                    fixed_attendees.append({"email": attendee})
                                elif "wilfredeveloper@gmail.com" in str(attendee):
                                    # Fallback to default email
                                    fixed_attendees.append({"email": "wilfredeveloper@gmail.com"})

                            event_data["attendees"] = fixed_attendees
                            print(f"🔧 Fixed attendees format: {fixed_attendees}")

                        adjusted_params["event_data"] = json.dumps(event_data)
                    except Exception as e:
                        logger.warning(f"Failed to adjust calendar event data: {str(e)}")
                        # Remove attendees if we can't fix them
                        try:
                            event_data = json.loads(adjusted_params["event_data"])
                            if "attendees" in event_data:
                                del event_data["attendees"]
                            adjusted_params["event_data"] = json.dumps(event_data)
                            print("🔧 Removed problematic attendees from event")
                        except:
                            pass

        elif tool_name == "gmail":
            if "authentication" in error_message.lower():
                # Add re-authentication flag
                adjusted_params["force_reauth"] = True

        return adjusted_params

    async def _extract_execution_steps_from_plan(self, planning_result: Dict[str, Any], shared) -> List[Dict[str, Any]]:
        """Extract execution steps from a successful planning tool result."""
        try:
            # The structure is: planning_result["result"]["result"]["plan"]
            # because the tool result is wrapped by PAToolCallNode, then by BaseTool.create_success_response
            outer_result = planning_result.get("result", {})

            if not outer_result.get("success"):
                return []

            inner_result = outer_result.get("result", {})
            plan_data = inner_result.get("plan", {})

            if not plan_data:
                return []

            subtasks = plan_data.get("subtasks", [])

            if not subtasks:
                return []

            execution_steps = []

            # Convert subtasks to executable tool calls
            for subtask in subtasks:
                if subtask.get("status") != "pending":
                    continue

                tool_name = self._identify_tool_for_subtask(subtask)

                if not tool_name:
                    continue

                parameters = self._generate_parameters_for_subtask(subtask, shared)

                execution_steps.append({
                    "name": tool_name,
                    "parameters": parameters,
                    "subtask_id": subtask.get("id"),
                    "subtask_title": subtask.get("title", "")
                })

            print(f"📋 Converted {len(subtasks)} subtasks into {len(execution_steps)} executable steps")
            return execution_steps

        except Exception as e:
            logger.error(f"Error extracting execution steps from plan: {str(e)}")
            return []

    def _identify_tool_for_subtask(self, subtask: Dict[str, Any]) -> Optional[str]:
        """Identify the appropriate tool for a subtask based on its content."""
        title = subtask.get("title", "").lower()
        description = subtask.get("description", "").lower()

        # Email-related keywords (check first to avoid conflicts)
        if any(keyword in title or keyword in description for keyword in
               ["email", "send", "invite", "message", "mail"]):
            return "gmail"

        # Calendar-related keywords
        if any(keyword in title or keyword in description for keyword in
               ["calendar", "event", "schedule", "meeting", "appointment", "reminder"]):
            return "google_calendar"

        # Search-related keywords
        if any(keyword in title or keyword in description for keyword in
               ["search", "research", "find", "look up"]):
            return "tavily_search"

        # File/document-related keywords
        if any(keyword in title or keyword in description for keyword in
               ["file", "document", "create", "write", "save"]):
            return "virtual_fs"

        # Default fallback
        return None

    def _generate_parameters_for_subtask(self, subtask: Dict[str, Any], shared) -> Dict[str, Any]:
        """Generate appropriate parameters for a subtask based on the tool and context."""
        title = subtask.get("title", "")
        description = subtask.get("description", "")
        user_message = shared.get("user_message", "")

        # This is a simplified parameter generation
        # In a full implementation, this would use more sophisticated NLP and context analysis

        # Check email keywords first to avoid conflicts
        if any(keyword in title.lower() for keyword in ["email", "send", "invite", "message", "mail"]):
            # Extract email details from user message and subtask
            return self._generate_email_parameters(user_message, subtask)
        elif any(keyword in title.lower() for keyword in ["calendar", "event", "schedule", "meeting"]):
            # Extract event details from user message and subtask
            return self._generate_calendar_parameters(user_message, subtask)
        elif "search" in title.lower():
            # Extract search terms from subtask
            return {"query": description or title}
        elif "file" in title.lower():
            # Extract file operation details
            return {
                "action": "create",
                "file_path": f"{title.replace(' ', '_').lower()}.txt",
                "content": description
            }

        return {}

    def _generate_calendar_parameters(self, user_message: str, subtask: Dict[str, Any]) -> Dict[str, Any]:
        """Generate calendar parameters from user message and subtask."""
        # This is a simplified implementation
        # In production, you'd use more sophisticated parsing

        import re
        from datetime import datetime, timedelta

        # Extract time information from user message
        time_match = re.search(r'(\d{1,2}):?(\d{0,2})\s*(am|pm)?', user_message.lower())
        duration_match = re.search(r'(\d+)\s*minutes?', user_message)

        # Default values
        start_time = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)
        duration_minutes = 45  # Default from user message

        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2)) if time_match.group(2) else 0
            am_pm = time_match.group(3)

            if am_pm == 'pm' and hour != 12:
                hour += 12
            elif am_pm == 'am' and hour == 12:
                hour = 0

            start_time = start_time.replace(hour=hour, minute=minute)

        if duration_match:
            duration_minutes = int(duration_match.group(1))

        end_time = start_time + timedelta(minutes=duration_minutes)

        # Extract attendees
        attendees = []
        email_match = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', user_message)
        if email_match:
            attendees.append(email_match.group(1))

        return {
            "action": "create",
            "event_data": {
                "summary": subtask.get("title", "Event"),
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "attendees": attendees,
                "reminders": [
                    {"method": "popup", "minutes": 25},  # 25 minutes before
                    {"method": "popup", "minutes": 0}    # At event time
                ]
            }
        }

    def _generate_email_parameters(self, user_message: str, subtask: Dict[str, Any]) -> Dict[str, Any]:
        """Generate email parameters from user message and subtask."""
        import re

        # Extract email address
        email_match = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', user_message)
        to_email = email_match.group(1) if email_match else ""

        # Generate subject and body based on context
        subject = f"Invitation: {subtask.get('title', 'Meeting')}"

        # Extract context about the meeting/event
        body_parts = []
        if "lunch" in user_message.lower():
            body_parts.append("You're invited to lunch!")

        if "total energies" in user_message.lower():
            body_parts.append("Please come prepared to discuss the Total Energies AI sector challenge.")

        body = " ".join(body_parts) if body_parts else subtask.get("description", "")

        return {
            "action": "send",
            "message_data": {
                "to": to_email,
                "subject": subject,
                "body": body
            }
        }

    async def _get_next_plan_steps(self, vfs_tool, shared) -> List[Dict[str, Any]]:
        """Get the next steps from the plan that need to be executed."""
        try:
            if not vfs_tool:
                return []

            # Read plan.txt to find next pending steps
            plan_result = await vfs_tool.execute({"action": "read", "file_path": "plan.txt"})
            if not plan_result.get("success"):
                return []

            plan_content = plan_result.get("data", {}).get("file", {}).get("content", "")

            # Parse plan content to find next steps
            # This implementation now parses the actual plan content
            next_tools = []

            # Look for STEP entries that are still pending
            lines = plan_content.split('\n')
            current_step = None

            for line in lines:
                line = line.strip()
                if line.startswith("STEP ") and ":" in line:
                    # Extract step information
                    step_match = re.match(r'STEP (\d+): (.+)', line)
                    if step_match:
                        current_step = {
                            "step_number": int(step_match.group(1)),
                            "title": step_match.group(2)
                        }
                elif line.startswith("STATUS: ") and current_step:
                    status = line.replace("STATUS: ", "").strip()
                    if status.lower() == "pending":
                        # This step is still pending, convert to executable tool
                        tool_name = self._identify_tool_for_step_title(current_step["title"])
                        if tool_name:
                            parameters = self._generate_parameters_for_step(current_step, shared)
                            next_tools.append({
                                "name": tool_name,
                                "parameters": parameters,
                                "step_number": current_step["step_number"],
                                "step_title": current_step["title"]
                            })
                    current_step = None

            return next_tools[:3]  # Limit to next 3 steps to avoid overwhelming

        except Exception as e:
            logger.error(f"Error getting next plan steps: {str(e)}")
            return []

    def _identify_tool_for_step_title(self, title: str) -> Optional[str]:
        """Identify tool based on step title."""
        title_lower = title.lower()

        if any(keyword in title_lower for keyword in ["calendar", "event", "schedule", "meeting"]):
            return "google_calendar"
        elif any(keyword in title_lower for keyword in ["email", "send", "invite", "message"]):
            return "gmail"
        elif any(keyword in title_lower for keyword in ["search", "research", "find"]):
            return "tavily_search"
        elif any(keyword in title_lower for keyword in ["file", "document", "create", "write"]):
            return "virtual_fs"

        return None

    def _generate_parameters_for_step(self, step: Dict[str, Any], shared) -> Dict[str, Any]:
        """Generate parameters for a step from plan.txt."""
        # This would be enhanced to parse more context from the plan
        # For now, use the same logic as subtask parameter generation
        user_message = shared.get("user_message", "")

        fake_subtask = {
            "title": step["title"],
            "description": step["title"]  # Use title as description for now
        }

        return self._generate_parameters_for_subtask(fake_subtask, shared)

    async def _log_retry_attempt(self, vfs_tool, failed_results: List[Dict[str, Any]], retry_count: int) -> None:
        """Log retry attempt to VFS."""
        try:
            if not vfs_tool:
                return

            timestamp = datetime.now().isoformat()
            failed_tools = [r.get("tool", "unknown") for r in failed_results]

            retry_log = f"""
[{timestamp}] RETRY_ATTEMPT
ATTEMPT: {retry_count}
FAILED_TOOLS: {', '.join(failed_tools)}
REASON: Automatic retry with error recovery
"""

            await vfs_tool.execute({
                "action": "append",
                "file_path": "thoughts.txt",
                "content": retry_log
            })

        except Exception as e:
            logger.warning(f"Failed to log retry attempt: {str(e)}")

    async def _log_max_retries_reached(self, vfs_tool, failed_results: List[Dict[str, Any]]) -> None:
        """Log when maximum retries are reached."""
        try:
            if not vfs_tool:
                return

            timestamp = datetime.now().isoformat()
            failed_tools = [r.get("tool", "unknown") for r in failed_results]

            max_retries_log = f"""
[{timestamp}] MAX_RETRIES_REACHED
FAILED_TOOLS: {', '.join(failed_tools)}
STATUS: Moving to response generation with partial results
RECOMMENDATION: User may need to address underlying issues or try alternative approaches
"""

            await vfs_tool.execute({
                "action": "append",
                "file_path": "thoughts.txt",
                "content": max_retries_log
            })

        except Exception as e:
            logger.warning(f"Failed to log max retries reached: {str(e)}")

    async def _update_step_status(self, vfs_tool, step_number: int, tool_name: str, status: str,
                                 timestamp: datetime, result: Any = None, evaluation: str = None) -> None:
        """Update plan.txt with step status and results."""
        try:
            # Read current plan.txt content
            plan_result = await vfs_tool.execute({"action": "read", "file_path": "plan.txt"})

            if not plan_result.get("success"):
                logger.warning("Could not read plan.txt for step update")
                return

            plan_content = plan_result.get("data", {}).get("file", {}).get("content", "")

            # Find and update the specific step
            lines = plan_content.split('\n')
            updated_lines = []
            in_step_section = False
            step_pattern = f"STEP {step_number}:"

            for line in lines:
                if line.startswith(step_pattern):
                    in_step_section = True
                    updated_lines.append(line)
                elif in_step_section and line.startswith("STEP ") and not line.startswith(step_pattern):
                    in_step_section = False
                    updated_lines.append(line)
                elif in_step_section:
                    # Update step fields
                    if line.startswith("STATUS:"):
                        updated_lines.append(f"STATUS: {status}")
                    elif line.startswith("STARTED_AT:") and status == "in_progress":
                        updated_lines.append(f"STARTED_AT: {timestamp.isoformat()}")
                    elif line.startswith("COMPLETED_AT:") and status == "completed":
                        updated_lines.append(f"COMPLETED_AT: {timestamp.isoformat()}")
                    elif line.startswith("EXECUTION_TIME:") and status == "completed":
                        exec_time = f"{(timestamp - timestamp).total_seconds():.2f}s"  # This would need proper start time
                        updated_lines.append(f"EXECUTION_TIME: {exec_time}")
                    elif line.startswith("RESULT_SUMMARY:") and result and status == "completed":
                        summary = self._summarize_result(result)
                        updated_lines.append(f"RESULT_SUMMARY: {summary}")
                    elif line.startswith("EVALUATION:") and evaluation and status == "completed":
                        updated_lines.append(f"EVALUATION: {evaluation}")
                    else:
                        updated_lines.append(line)
                else:
                    updated_lines.append(line)

            # Write updated content back to plan.txt
            updated_content = '\n'.join(updated_lines)
            await vfs_tool.execute({
                "action": "write",
                "file_path": "plan.txt",
                "content": updated_content
            })

            logger.debug(f"Updated plan.txt for step {step_number} with status: {status}")

        except Exception as e:
            logger.error(f"Failed to update step status in plan.txt: {str(e)}")

    def _evaluate_step_success(self, result: Any) -> bool:
        """Evaluate if a step was successful based on the result."""
        try:
            if isinstance(result, dict):
                # Check for explicit success indicators
                if "success" in result:
                    return bool(result["success"])
                if "error" in result:
                    return False
                if "data" in result and result["data"]:
                    return True
                # Check for common success patterns
                if any(key in result for key in ["id", "created", "sent", "scheduled"]):
                    return True
            elif isinstance(result, str):
                # Check for error patterns in string results
                error_patterns = ["error", "failed", "exception", "not found", "invalid"]
                if any(pattern in result.lower() for pattern in error_patterns):
                    return False
                return True
            elif result is not None:
                return True

            return False

        except Exception as e:
            logger.warning(f"Error evaluating step success: {str(e)}")
            return False

    def _generate_step_evaluation(self, tool_name: str, result: Any, success: bool) -> str:
        """Generate evaluation text for a step."""
        try:
            if success:
                if tool_name == "gmail":
                    return "Email sent successfully"
                elif tool_name == "google_calendar":
                    return "Calendar event created/updated successfully"
                elif tool_name == "tavily_search":
                    return "Search completed with relevant results"
                elif tool_name == "planning":
                    return "Plan created/updated successfully"
                elif tool_name == "virtual_fs":
                    return "File operation completed successfully"
                else:
                    return "Step completed successfully"
            else:
                return f"Step encountered issues - review result for details"

        except Exception as e:
            logger.warning(f"Error generating step evaluation: {str(e)}")
            return "Evaluation unavailable"

    def _summarize_result(self, result: Any) -> str:
        """Create a brief summary of the result."""
        try:
            if isinstance(result, dict):
                if "message" in result:
                    return str(result["message"])[:100]
                elif "data" in result:
                    data = result["data"]
                    if isinstance(data, dict) and "id" in data:
                        return f"Created item with ID: {data['id']}"
                    elif isinstance(data, list):
                        return f"Retrieved {len(data)} items"
                    else:
                        return "Operation completed with data"
                elif "success" in result:
                    return "Operation completed successfully" if result["success"] else "Operation failed"
                else:
                    return "Operation completed"
            elif isinstance(result, str):
                return result[:100] + "..." if len(result) > 100 else result
            else:
                return str(result)[:100]

        except Exception as e:
            logger.warning(f"Error summarizing result: {str(e)}")
            return "Result summary unavailable"

    def _analyze_tool_error(self, tool_name: str, error: Exception, parameters: Dict[str, Any]) -> str:
        """Analyze tool execution error and provide detailed analysis."""
        error_message = str(error).lower()
        error_type = type(error).__name__

        # Authentication/Authorization errors
        if any(keyword in error_message for keyword in ["auth", "unauthorized", "permission", "forbidden"]):
            return f"{tool_name} requires re-authorization - please check app settings"

        # Network/connectivity errors
        if any(keyword in error_message for keyword in ["connection", "timeout", "network", "unreachable"]):
            return f"Network connectivity issue with {tool_name} service"

        # Rate limiting errors
        if any(keyword in error_message for keyword in ["rate", "limit", "quota", "exceeded"]):
            return f"{tool_name} service rate limit exceeded - retry needed"

        # Parameter validation errors
        if any(keyword in error_message for keyword in ["parameter", "invalid", "required", "missing"]):
            missing_params = self._identify_missing_parameters(tool_name, parameters, error_message)
            return f"Parameter validation failed for {tool_name}: {missing_params}"

        # Service-specific errors
        if tool_name == "gmail":
            if "message" in error_message:
                return "Gmail message format or content issue"
            elif "attachment" in error_message:
                return "Gmail attachment processing error"
        elif tool_name == "google_calendar":
            if "event" in error_message:
                return "Calendar event creation/update issue"
            elif "timezone" in error_message:
                return "Calendar timezone configuration error"
        elif tool_name == "planning":
            if "plan" in error_message:
                return "Planning tool data structure issue"
        elif tool_name == "virtual_fs":
            if "file" in error_message:
                return "Virtual file system operation error"

        return f"Unexpected {error_type} in {tool_name}: {error_message[:100]}"

    def _get_tool_recovery_suggestion(self, tool_name: str, error: Exception) -> str:
        """Get recovery suggestion for tool error."""
        error_message = str(error).lower()

        # Authentication errors
        if any(keyword in error_message for keyword in ["auth", "unauthorized", "permission"]):
            return f"Re-authorize {tool_name} in app settings and retry"

        # Network errors
        if any(keyword in error_message for keyword in ["connection", "timeout", "network"]):
            return "Check internet connection and retry in a few moments"

        # Rate limiting
        if any(keyword in error_message for keyword in ["rate", "limit", "quota"]):
            return "Wait 1-2 minutes before retrying to avoid rate limits"

        # Parameter errors
        if any(keyword in error_message for keyword in ["parameter", "invalid", "required"]):
            return "Review and correct the request parameters, then retry"

        # Tool-specific suggestions
        if tool_name == "gmail":
            return "Verify email addresses and message format, then retry"
        elif tool_name == "google_calendar":
            return "Check date/time format and timezone settings, then retry"
        elif tool_name == "planning":
            return "Simplify the task description and retry"
        elif tool_name == "virtual_fs":
            return "Check file path and permissions, then retry"

        return "Review the request and try again with different parameters"

    def _identify_missing_parameters(self, tool_name: str, parameters: Dict[str, Any], error_message: str) -> str:
        """Identify missing or invalid parameters from error message."""
        common_required = {
            "gmail": ["action", "message_data"],
            "google_calendar": ["action", "event_data"],
            "planning": ["action", "task_description"],
            "virtual_fs": ["action", "file_path"]
        }

        if tool_name in common_required:
            required_params = common_required[tool_name]
            missing = [param for param in required_params if param not in parameters or not parameters[param]]
            if missing:
                return f"Missing required parameters: {', '.join(missing)}"

        # Extract specific parameter names from error message
        if "required" in error_message:
            # Try to extract parameter name after "required"
            parts = error_message.split("required")
            if len(parts) > 1:
                return f"Required parameter issue: {parts[1][:50]}"

        return "Parameter validation failed - check format and completeness"

    async def _log_tool_error(self, vfs_tool, tool_name: str, step_number: int, error: Exception, parameters: Dict[str, Any]) -> None:
        """Log detailed tool error information to VFS."""
        try:
            if not vfs_tool:
                return

            timestamp = datetime.now().isoformat()
            error_log = f"""
[{timestamp}] TOOL_EXECUTION_ERROR
STEP: {step_number}
TOOL: {tool_name}
ERROR_TYPE: {type(error).__name__}
ERROR_MESSAGE: {str(error)}
PARAMETERS: {json.dumps(parameters, indent=2)}
RECOVERY_SUGGESTION: {self._get_tool_recovery_suggestion(tool_name, error)}
"""

            await vfs_tool.execute({
                "action": "append",
                "file_path": "thoughts.txt",
                "content": error_log
            })

        except Exception as e:
            logger.warning(f"Failed to log tool error to VFS: {str(e)}")


class PAResponseNode(AsyncNode):
    """Node that generates final responses."""

    async def prep_async(self, shared):
        """Prepare response data."""
        user_message = shared.get("user_message", "")
        thoughts = shared.get("thoughts", [])
        tool_results = shared.get("current_tool_results", [])
        config = shared.get("config")
        baml_client = shared.get("baml_client")
        time_ctx = shared.get("time_context") or {}

        # Append time awareness to system prompt for response generation as well
        base_system_prompt = config.system_prompt if config else ""
        if time_ctx:
            time_context_prompt = (
                "\n\nTime awareness (runtime-provided):\n"
                f"- CURRENT_DATETIME_UTC: {time_ctx.get('now_utc')}\n"
                f"- USER_TIMEZONE: {time_ctx.get('timezone')}\n"
                f"- CURRENT_DATETIME_LOCAL: {time_ctx.get('now_local')}\n"
                "Guidance: Interpret relative dates/times in USER_TIMEZONE. When summarizing results, "
                "use the user's local time unless otherwise requested."
            )
            system_prompt = base_system_prompt + time_context_prompt
        else:
            system_prompt = base_system_prompt

        return {
            "user_message": user_message,
            "thoughts": thoughts,
            "tool_results": tool_results,
            "system_prompt": system_prompt,
            "baml_client": baml_client
        }

    async def exec_async(self, prep_res):
        """Generate final response."""
        user_message = prep_res["user_message"]
        thoughts = prep_res["thoughts"]
        tool_results = prep_res["tool_results"]
        system_prompt = prep_res["system_prompt"]
        baml_client = prep_res.get("baml_client")

        try:
            if baml_client:
                # Use BAML for response generation
                response = await baml_client.call_function(
                    "PersonalAssistantResponse",
                    user_query=user_message,
                    thinking_process=json.dumps([t.get("thinking", "") for t in thoughts]),
                    tool_results=json.dumps(tool_results),
                    system_prompt=system_prompt
                )

                if hasattr(response, 'response'):
                    return response.response
                else:
                    return str(response)
            else:
                # Fallback response generation
                if tool_results:
                    successful_tools = [r for r in tool_results if r.get("success")]
                    if successful_tools:
                        return f"I've completed your request using {len(successful_tools)} tools. Here's what I accomplished: " + \
                               "; ".join([f"{r['tool']}: {str(r['result'])[:100]}" for r in successful_tools])
                    else:
                        return "I attempted to use tools to help with your request, but encountered some issues. Please try again or rephrase your request."
                else:
                    return f"I understand you want help with: {user_message}. I'm ready to assist you with various tasks using my available tools."

        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")

            # Enhanced error handling for response generation
            error_context = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "user_message": user_message,
                "has_tool_results": bool(tool_results),
                "timestamp": datetime.now().isoformat()
            }

            # Generate fallback response based on available information
            fallback_response = self._generate_fallback_response(user_message, tool_results, error_context)

            return fallback_response

    async def post_async(self, shared, prep_res, exec_res):
        """Save final response."""
        shared["final_response"] = exec_res
        print(f"💬 Generated response: {exec_res[:100]}...")
        return "end"

    def _generate_fallback_response(self, user_message: str, tool_results: List[Dict[str, Any]], error_context: Dict[str, Any]) -> str:
        """Generate a helpful fallback response when response generation fails."""
        try:
            # Check if we have successful tool results to report
            successful_results = [result for result in tool_results if result.get("success", False)]
            failed_results = [result for result in tool_results if not result.get("success", False)]

            if successful_results and not failed_results:
                # All tools succeeded, but response generation failed
                return self._create_success_summary(user_message, successful_results)
            elif successful_results and failed_results:
                # Mixed results
                return self._create_mixed_results_summary(user_message, successful_results, failed_results)
            elif failed_results and not successful_results:
                # All tools failed
                return self._create_failure_summary(user_message, failed_results)
            else:
                # No tool results available
                return self._create_no_results_fallback(user_message, error_context)

        except Exception as e:
            logger.error(f"Error generating fallback response: {str(e)}")
            return "I apologize, but I encountered an error while processing your request. Please try rephrasing your request or breaking it down into smaller steps."

    def _create_success_summary(self, user_message: str, successful_results: List[Dict[str, Any]]) -> str:
        """Create summary for successful tool executions."""
        tool_names = [result.get("tool", "unknown") for result in successful_results]

        if len(successful_results) == 1:
            tool_name = tool_names[0]
            return f"I successfully completed your request using {tool_name}. The operation finished without any issues, though I had trouble generating a detailed summary. Your request has been processed successfully."
        else:
            tools_list = ", ".join(tool_names[:-1]) + f" and {tool_names[-1]}"
            return f"I successfully completed your request using multiple tools: {tools_list}. All operations finished successfully, though I had trouble generating a detailed summary. Your multi-step request has been processed completely."

    def _create_mixed_results_summary(self, user_message: str, successful_results: List[Dict[str, Any]], failed_results: List[Dict[str, Any]]) -> str:
        """Create summary for mixed success/failure results."""
        successful_tools = [result.get("tool", "unknown") for result in successful_results]
        failed_tools = [result.get("tool", "unknown") for result in failed_results]

        success_part = f"Successfully completed: {', '.join(successful_tools)}"
        failure_part = f"Encountered issues with: {', '.join(failed_tools)}"

        return f"I partially completed your request. {success_part}. However, {failure_part}. Please review the successful parts and let me know if you'd like me to retry the failed operations."

    def _create_failure_summary(self, user_message: str, failed_results: List[Dict[str, Any]]) -> str:
        """Create summary for failed tool executions."""
        failed_tools = [result.get("tool", "unknown") for result in failed_results]

        if len(failed_results) == 1:
            tool_name = failed_tools[0]
            error_msg = failed_results[0].get("error_message", "unknown error")
            return f"I encountered an issue while trying to use {tool_name} for your request. The error was: {error_msg}. Please check the requirements and try again, or let me know if you need help with a different approach."
        else:
            tools_list = ", ".join(failed_tools)
            return f"I encountered issues with multiple tools ({tools_list}) while processing your request. This might be due to connectivity issues, authorization problems, or parameter errors. Please try your request again, or break it down into smaller steps."

    def _create_no_results_fallback(self, user_message: str, error_context: Dict[str, Any]) -> str:
        """Create fallback response when no tool results are available."""
        error_type = error_context.get("error_type", "Unknown")

        if "network" in error_context.get("error_message", "").lower():
            return "I'm experiencing connectivity issues at the moment. Please try your request again in a few moments."
        elif "auth" in error_context.get("error_message", "").lower():
            return "I'm having trouble with service authorization. Please check the app settings and ensure all required services are properly authorized."
        else:
            return f"I encountered a {error_type} error while processing your request. Please try rephrasing your request or breaking it down into smaller, more specific steps. I'm here to help once we resolve this issue."


class PAEndNode(AsyncNode):
    """Node that handles flow completion."""

    async def prep_async(self, shared):
        """Prepare end data."""
        return {"final_response": shared.get("final_response", "")}

    async def exec_async(self, prep_res):
        """Complete the flow."""
        print("🏁 Personal Assistant conversation completed")
        return prep_res["final_response"]

    async def post_async(self, shared, prep_res, exec_res):
        """End the flow."""
        return None