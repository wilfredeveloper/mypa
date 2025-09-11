"""
Personal Assistant AsyncNodes following chatbot_core patterns.
"""

import asyncio
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import logging
import re


from pocketflow import AsyncNode
from utils.baml_utils import RateLimitedBAMLGeminiLLM
from app.services.parameter_processor import ParameterProcessor, ParameterProcessingError

logger = logging.getLogger(__name__)





class PAThinkNode(AsyncNode):
    """Node that analyzes user requests and decides on actions."""

    def __init__(self):
        super().__init__()
        self.parameter_processor = ParameterProcessor()

    async def prep_async(self, shared):
        """Prepare thinking data."""
        user_message = shared.get("user_message", "")
        session = shared.get("session", {})
        config = shared.get("config")
        tool_registry = shared.get("tool_registry")
        baml_client = shared.get("baml_client")
        ctx = shared.get("context", {}) or {}

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

        base_system_prompt = config.system_prompt if config else ""
        system_prompt = base_system_prompt + time_context_prompt

        return {
            "user_message": user_message,
            "conversation_history": "\n".join(conversation_history),
            "available_tools": available_tools,
            "system_prompt": system_prompt,
            "current_thought_number": len(shared.get("thoughts", [])) + 1,
            "baml_client": baml_client,
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
            return {
                "thinking": "I encountered an issue while processing your request.",
                "action": "respond",
                "action_input": "I apologize, but I encountered an error while thinking about your request. Please try again.",
                "is_final": True,
                "needs_tools": False
            }

    async def post_async(self, shared, prep_res, exec_res):
        """Save thinking result and decide next step."""
        # Save thinking result
        if "thoughts" not in shared:
            shared["thoughts"] = []
        shared["thoughts"].append(exec_res)

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
            return "tools"
        elif exec_res.get("is_final", False):
            shared["final_response"] = exec_res["action_input"]
            return "end"
        else:
            return "respond"


class PAToolCallNode(AsyncNode):
    """Node that executes tool calls."""

    async def prep_async(self, shared):
        """Prepare tool call data."""
        tools_to_use = shared.get("tools_to_use", [])
        tool_registry = shared.get("tool_registry")
        user_message = shared.get("user_message", "")

        return {
            "tools_to_use": tools_to_use,
            "tool_registry": tool_registry,
            "user_message": user_message
        }

    async def exec_async(self, prep_res):
        """Execute tool calls."""
        tools_to_use = prep_res["tools_to_use"]
        tool_registry = prep_res["tool_registry"]
        user_message = prep_res["user_message"]

        if not tool_registry:
            return {"error": "Tool registry not available"}

        tool_results = []

        for tool_call in tools_to_use:
            tool_name = "unknown"
            parameters = {}
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

                # Parameters are already processed by centralized processor
                # Check for processing errors
                if isinstance(tool_call, dict) and 'error' in tool_call:
                    logger.warning(f"Tool {tool_name} has processing error: {tool_call['error']}")
                    # Still try to execute with available parameters

                # Execute the tool
                result = await tool_registry.execute_tool(tool_name, parameters)

                tool_results.append({
                    "tool": tool_name,
                    "parameters": parameters,
                    "result": result,
                    "success": True,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })

                print(f"🔧 Executed tool: {tool_name}")

            except Exception as e:
                logger.error(f"Error executing tool {tool_name}: {str(e)}")
                tool_results.append({
                    "tool": tool_name,
                    "parameters": parameters,
                    "result": f"Error: {str(e)}",
                    "success": False,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })

        return {"tool_results": tool_results}

    async def post_async(self, shared, prep_res, exec_res):
        """Save tool results and continue to response."""
        tool_results = exec_res.get("tool_results", [])

        # Save tool results
        if "tools_used" not in shared:
            shared["tools_used"] = []
        shared["tools_used"].extend(tool_results)

        # Save for response generation
        shared["current_tool_results"] = tool_results

        print(f"✅ Completed {len(tool_results)} tool calls")

        return "respond"


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
            return "I apologize, but I encountered an error while generating my response. Please try again."

    async def post_async(self, shared, prep_res, exec_res):
        """Save final response."""
        shared["final_response"] = exec_res
        print(f"💬 Generated response: {exec_res[:100]}...")
        return "end"


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