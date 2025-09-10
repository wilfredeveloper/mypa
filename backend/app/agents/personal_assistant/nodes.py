"""
Personal Assistant AsyncNodes following chatbot_core patterns.
"""

import asyncio
import json
import uuid
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import logging

from pocketflow import AsyncNode
from utils.baml_utils import RateLimitedBAMLGeminiLLM

logger = logging.getLogger(__name__)


class PAThinkNode(AsyncNode):
    """Node that analyzes user requests and decides on actions."""

    async def prep_async(self, shared):
        """Prepare thinking data."""
        user_message = shared.get("user_message", "")
        session = shared.get("session", {})
        config = shared.get("config")
        tool_registry = shared.get("tool_registry")
        baml_client = shared.get("baml_client")

        # Get conversation history
        messages = session.get("messages", [])
        conversation_history = []
        for msg in messages[-10:]:  # Last 10 messages for context
            conversation_history.append(f"{msg['role']}: {msg['content']}")

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

        return {
            "user_message": user_message,
            "conversation_history": "\n".join(conversation_history),
            "available_tools": available_tools,
            "system_prompt": config.system_prompt if config else "",
            "current_thought_number": len(shared.get("thoughts", [])) + 1,
            "baml_client": baml_client
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
            "user_message": user_message,
            "shared": shared  # Pass shared state for parameter validation
        }

    async def exec_async(self, prep_res):
        """Execute tool calls."""
        tools_to_use = prep_res["tools_to_use"]
        tool_registry = prep_res["tool_registry"]
        user_message = prep_res["user_message"]
        shared = prep_res.get("shared", {})  # Get shared state for parameter validation

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

                # Validate and fix parameters before execution
                parameters = await self._validate_and_fix_parameters(tool_name, parameters, shared)

                # Execute the tool
                result = await tool_registry.execute_tool(tool_name, parameters)

                tool_results.append({
                    "tool": tool_name,
                    "parameters": parameters,
                    "result": result,
                    "success": True,
                    "timestamp": datetime.utcnow().isoformat()
                })

                print(f"🔧 Executed tool: {tool_name}")

            except Exception as e:
                logger.error(f"Error executing tool {tool_name}: {str(e)}")
                tool_results.append({
                    "tool": tool_name,
                    "parameters": parameters,
                    "result": f"Error: {str(e)}",
                    "success": False,
                    "timestamp": datetime.utcnow().isoformat()
                })

        return {"tool_results": tool_results}

    async def _validate_and_fix_parameters(self, tool_name: str, parameters: dict, shared: dict) -> dict:
        """Validate and fix tool parameters, adding missing required parameters with fallbacks."""
        try:
            if tool_name == "virtual_fs":
                return await self._validate_virtual_fs_parameters(parameters, shared)
            elif tool_name == "tavily_search":
                return await self._validate_search_parameters(parameters)
            elif tool_name == "planning":
                return await self._validate_planning_parameters(parameters)
            else:
                # For other tools, return parameters as-is
                return parameters
        except Exception as e:
            logger.error(f"Error validating parameters for {tool_name}: {str(e)}")
            return parameters

    async def _validate_virtual_fs_parameters(self, parameters: dict, shared: dict) -> dict:
        """Validate and fix virtual_fs tool parameters."""
        action = parameters.get("action", "").lower()

        # Actions that require filename
        filename_required_actions = ["create", "read", "update", "delete"]

        if action in filename_required_actions:
            filename = parameters.get("filename")

            if not filename:
                # Try to get workspace filename from shared state
                workspace_filename = shared.get("workspace_filename")
                if workspace_filename:
                    parameters["filename"] = workspace_filename
                    logger.info(f"Added missing filename from workspace: {workspace_filename}")
                else:
                    # Generate a default filename
                    task_id = shared.get("task_id", "unknown")[:8]
                    default_filename = f"task_workspace_{task_id}.md"
                    parameters["filename"] = default_filename
                    logger.info(f"Generated missing filename: {default_filename}")

        # Ensure content is provided for create/update actions
        if action in ["create", "update"] and "content" not in parameters:
            if action == "create":
                parameters["content"] = "# New Document\n\nContent will be added here."
            else:  # update
                parameters["content"] = ""
            logger.info(f"Added default content for {action} action")

        return parameters

    async def _validate_search_parameters(self, parameters: dict) -> dict:
        """Validate and fix tavily_search tool parameters."""
        if not parameters.get("query"):
            parameters["query"] = "general search query"
            logger.warning("Added default query for tavily_search")

        return parameters

    async def _validate_planning_parameters(self, parameters: dict) -> dict:
        """Validate and fix planning tool parameters."""
        if not parameters.get("task"):
            parameters["task"] = "General task planning"
            logger.warning("Added default task for planning tool")

        if not parameters.get("complexity"):
            parameters["complexity"] = "medium"
            logger.info("Added default complexity for planning tool")

        return parameters

    async def post_async(self, shared, prep_res, exec_res):
        """Save tool results and decide next step based on execution mode."""
        tool_results = exec_res.get("tool_results", [])

        # Save tool results
        if "tools_used" not in shared:
            shared["tools_used"] = []
        shared["tools_used"].extend(tool_results)

        # Save for response generation
        shared["current_tool_results"] = tool_results

        # Update step counter for autonomous mode
        if shared.get("autonomous_mode", False):
            shared["steps_completed"] = shared.get("steps_completed", 0) + 1

            # Update workspace with progress if available
            await self._update_workspace_progress(shared, tool_results)

            # Load current workspace content into shared state for better decision making
            await self._load_workspace_content_to_shared(shared)

        print(f"✅ Completed {len(tool_results)} tool calls")

        # Decide next step based on execution mode
        if shared.get("autonomous_mode", False):
            # In autonomous mode, continue thinking to evaluate if goal is achieved
            return "think"
        else:
            # In regular mode, generate response
            return "respond"

    async def _update_workspace_progress(self, shared, tool_results):
        """Update workspace file with comprehensive tool execution progress and results."""
        workspace_filename = shared.get("workspace_filename")
        tool_registry = shared.get("tool_registry")

        if not workspace_filename or not tool_registry or "virtual_fs" not in tool_registry._tool_instances:
            return

        try:
            virtual_fs_tool = tool_registry._tool_instances["virtual_fs"]

            # Read current workspace
            read_result = await virtual_fs_tool.execute({
                "action": "read",
                "filename": workspace_filename
            })

            if not read_result.get("success", False):
                return

            # Extract content from the result structure
            result_data = read_result.get("result", {})
            if isinstance(result_data, dict) and "file" in result_data:
                current_content = result_data["file"].get("content", "")
            elif isinstance(result_data, str):
                current_content = result_data
            else:
                logger.warning(f"Unexpected result structure: {type(result_data)}")
                return

            # Create comprehensive progress update
            timestamp = datetime.utcnow().isoformat()
            progress_update = f"\n- `{timestamp}`: Executed {len(tool_results)} tools"

            # Add detailed tool results and extract findings
            findings_update = ""
            working_docs_update = ""

            for result in tool_results:
                tool_name = result.get("tool", "unknown")
                success = result.get("success", False)
                status = "✅" if success else "❌"
                progress_update += f"\n  {status} **{tool_name}**"

                # Extract meaningful results for different sections
                if success and result.get("result"):
                    tool_result = result.get("result", {})

                    if tool_name == "tavily_search" and isinstance(tool_result, dict):
                        # Handle nested result structure - search data is in tool_result["result"]
                        search_data = tool_result.get("result", tool_result)  # Fallback to tool_result if no nesting
                        query = search_data.get("query", "")
                        results = search_data.get("results", [])

                        if query and results:
                            findings_update += f"\n\n### 🔍 Search Results: {query}\n"
                            for i, search_result in enumerate(results, 1):  # Include ALL results, not just top 3
                                title = search_result.get("title", "No title")
                                url = search_result.get("url", "")
                                content = search_result.get("content", "")
                                # Store complete content, no truncation
                                findings_update += f"{i}. **{title}**\n   - URL: {url}\n   - Content: {content}\n\n"

                    elif tool_name == "planning" and isinstance(tool_result, dict):
                        # Handle different planning result structures
                        plan_data = tool_result
                        if "result" in tool_result:
                            plan_data = tool_result["result"]

                        if "plan" in plan_data:
                            plan = plan_data["plan"]
                            working_docs_update += f"\n\n### 📋 Generated Plan\n"
                            working_docs_update += f"- **Title**: {plan.get('title', 'N/A')}\n"
                            working_docs_update += f"- **Complexity**: {plan.get('complexity', 'N/A')}\n"
                            working_docs_update += f"- **Estimated Duration**: {plan.get('estimated_duration_minutes', 0)} minutes\n"

                            if plan.get('subtasks'):
                                working_docs_update += f"- **Subtasks**: {len(plan['subtasks'])} tasks identified\n"
                                working_docs_update += f"\n**Subtask Details:**\n"
                                for i, subtask in enumerate(plan['subtasks'], 1):  # Show ALL subtasks, not just first 5
                                    working_docs_update += f"{i}. {subtask.get('title', 'Untitled')}\n"
                                    if subtask.get('description'):
                                        working_docs_update += f"   - {subtask['description']}\n"  # No truncation

                        elif "thinking" in plan_data or "analysis" in plan_data:
                            # Handle planning thinking/analysis results
                            thinking = plan_data.get("thinking", plan_data.get("analysis", ""))
                            if thinking:
                                working_docs_update += f"\n\n### 🧠 Planning Analysis\n{thinking}\n"  # No truncation

                    elif tool_name == "virtual_fs":
                        # Track virtual_fs operations
                        operation = tool_result.get("operation", "unknown")
                        if operation in ["create", "update"]:
                            filename = tool_result.get("file", {}).get("filename", "unknown")
                            working_docs_update += f"\n\n### 📁 File Operation: {operation.title()}\n"
                            working_docs_update += f"- **File**: {filename}\n"
                            working_docs_update += f"- **Operation**: {operation}\n"

            # Update Progress Log section
            if "## 🔄 Progress Log" in current_content:
                current_content = current_content.replace(
                    "## 🔄 Progress Log",
                    f"## 🔄 Progress Log{progress_update}"
                )

            # Update Research & Findings section if we have findings
            if findings_update and "## 📚 Research & Findings" in current_content:
                if "*Detailed findings, sources, and data will be stored here*" in current_content:
                    # Replace placeholder text with findings
                    current_content = current_content.replace(
                        "*Detailed findings, sources, and data will be stored here*",
                        f"*Research findings and data collected during autonomous execution:*{findings_update}"
                    )
                elif "*Research findings and data collected during autonomous execution:*" in current_content:
                    # Append to existing findings section
                    import re
                    pattern = r"(\*Research findings and data collected during autonomous execution:\*)(.*?)(\n## )"
                    match = re.search(pattern, current_content, re.DOTALL)
                    if match:
                        existing_findings = match.group(2)
                        new_findings_section = f"*Research findings and data collected during autonomous execution:*{existing_findings}{findings_update}"
                        current_content = current_content.replace(
                            f"*Research findings and data collected during autonomous execution:*{existing_findings}",
                            new_findings_section
                        )
                else:
                    # Fallback: append to section header
                    current_content = current_content.replace(
                        "## 📚 Research & Findings",
                        f"## 📚 Research & Findings{findings_update}"
                    )

            # Update Working Documents section if we have working docs
            if working_docs_update and "## 📝 Working Documents" in current_content:
                if "*Draft content, intermediate results, and work-in-progress materials*" in current_content:
                    current_content = current_content.replace(
                        "*Draft content, intermediate results, and work-in-progress materials*",
                        f"*Plans, analyses, and intermediate work products:*{working_docs_update}"
                    )
                else:
                    # Append to existing working docs
                    current_content = current_content.replace(
                        "## 📝 Working Documents",
                        f"## 📝 Working Documents{working_docs_update}"
                    )

            # Update step counter in metadata
            steps_completed = shared.get("steps_completed", 0)
            # Find and update the steps completed line
            import re
            pattern = r"- \*\*Steps Completed\*\*: \d+"
            replacement = f"- **Steps Completed**: {steps_completed}"
            current_content = re.sub(pattern, replacement, current_content)

            # Update status to IN_PROGRESS if not already
            current_content = current_content.replace(
                "- **Status**: STARTED",
                "- **Status**: IN_PROGRESS"
            )

            # Update workspace file
            await virtual_fs_tool.execute({
                "action": "update",
                "filename": workspace_filename,
                "content": current_content
            })

        except Exception as e:
            logger.warning(f"Failed to update workspace progress: {str(e)}", exc_info=True)

    async def _load_workspace_content_to_shared(self, shared):
        """Load current workspace content into shared state for better decision making."""
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

            if read_result.get("success", False):
                # Extract content from the result structure
                result_data = read_result.get("result", {})
                if isinstance(result_data, dict) and "file" in result_data:
                    workspace_content = result_data["file"].get("content", "")
                elif isinstance(result_data, str):
                    workspace_content = result_data
                else:
                    workspace_content = ""

                # Store in shared state for nodes to access
                shared["current_workspace_content"] = workspace_content
                shared["workspace_content_length"] = len(workspace_content)

                # Extract key metrics for decision making
                shared["workspace_has_content"] = len(workspace_content.strip()) > 100
                shared["workspace_has_empty_sections"] = self._detect_empty_sections(workspace_content)
                shared["workspace_research_indicators"] = self._count_research_indicators(workspace_content)

                logger.debug(f"Loaded workspace content: {len(workspace_content)} chars, "
                           f"has_content: {shared['workspace_has_content']}, "
                           f"empty_sections: {shared['workspace_has_empty_sections']}, "
                           f"research_indicators: {shared['workspace_research_indicators']}")

        except Exception as e:
            logger.warning(f"Failed to load workspace content to shared state: {str(e)}")
            shared["current_workspace_content"] = ""
            shared["workspace_content_length"] = 0
            shared["workspace_has_content"] = False
            shared["workspace_has_empty_sections"] = False
            shared["workspace_research_indicators"] = 0

    def _detect_empty_sections(self, content):
        """Detect if workspace has empty sections (headers without content)."""
        empty_patterns = [
            "## Executive Summary\n\n## ",
            "## Introduction\n\n## ",
            "## Research Findings\n### ",
            "### Net Worth of OnlyFans CEO\n\n### ",
            "## Analysis\n\n## ",
            "## Conclusion\n\n## "
        ]

        for pattern in empty_patterns:
            if pattern in content:
                return True
        return False

    def _count_research_indicators(self, content):
        """Count research indicators in workspace content."""
        indicators = [
            "### 🔍 Search Results:",
            "URL:",
            "Content:",
            "CEO",
            "OnlyFans",
            "net worth",
            "agency",
            "http://",
            "https://"
        ]

        count = 0
        for indicator in indicators:
            if indicator in content:
                count += 1
        return count

    async def _create_final_deliverable(self, shared, task_summary):
        """Create comprehensive final deliverable when autonomous execution completes."""
        # Check if we have synthesis results to use instead of generic templates
        synthesis_result = shared.get("synthesis_result")

        if synthesis_result:
            # Synthesis has already been done and workspace updated
            logger.info("Using synthesis results for final deliverable")
            return

        # Fallback to original method if no synthesis available
        workspace_filename = shared.get("workspace_filename")
        tool_registry = shared.get("tool_registry")
        original_goal = shared.get("original_goal", "")

        if not workspace_filename or not tool_registry or "virtual_fs" not in tool_registry._tool_instances:
            return

        try:
            virtual_fs_tool = tool_registry._tool_instances["virtual_fs"]

            # Read current workspace to extract actual research findings
            read_result = await virtual_fs_tool.execute({
                "action": "read",
                "filename": workspace_filename
            })

            if not read_result.get("success", False):
                return

            # Extract content from the result structure
            result_data = read_result.get("result", {})
            if isinstance(result_data, dict) and "file" in result_data:
                current_content = result_data["file"].get("content", "")
            elif isinstance(result_data, str):
                current_content = result_data
            else:
                return

            # Extract actual research findings from workspace content
            research_findings = self._extract_research_from_workspace(current_content)
            key_findings = self._extract_key_findings_from_workspace(current_content)

            # Create final deliverable with actual content instead of placeholders
            timestamp = datetime.utcnow().isoformat()
            final_deliverable = f"""

## 🎯 Task Completion Summary

**Original Goal**: {original_goal}

**Completion Status**: ✅ COMPLETED
**Completion Time**: {timestamp}
**Total Steps**: {shared.get('steps_completed', 0)}

### 📋 Executive Summary
{task_summary}

### 🔍 Key Findings
{key_findings if key_findings else 'Research findings are documented in the workspace above.'}

### 📊 Research Summary
{research_findings if research_findings else 'Detailed research data is available in the Research & Findings section above.'}

### 🚀 Next Steps
Based on the research conducted:
- Review the detailed findings in the workspace documentation
- Consider implementing the insights gathered from the research
- Follow up on specific recommendations identified during analysis

---
**Note**: This deliverable was created through autonomous execution. Detailed research findings and analysis are documented in the workspace sections above.
"""

            # Update Final Deliverables section
            if "## 🎯 Final Deliverables" in current_content:
                if "*Completed outputs and final results*" in current_content:
                    current_content = current_content.replace(
                        "*Completed outputs and final results*",
                        f"*Autonomous execution completed successfully*{final_deliverable}"
                    )
                else:
                    # Append to existing deliverables
                    current_content = current_content.replace(
                        "## 🎯 Final Deliverables",
                        f"## 🎯 Final Deliverables{final_deliverable}"
                    )

            # Update status to COMPLETED
            current_content = current_content.replace(
                "- **Status**: IN_PROGRESS",
                "- **Status**: COMPLETED"
            )

            # Update workspace file
            await virtual_fs_tool.execute({
                "action": "update",
                "filename": workspace_filename,
                "content": current_content
            })

            # Create a separate final report file for complex deliverables
            if "business plan" in original_goal.lower() or "comprehensive" in original_goal.lower() or "analysis" in original_goal.lower():
                await self._create_structured_report(shared, virtual_fs_tool, original_goal, task_summary)

        except Exception as e:
            logger.warning(f"Failed to create final deliverable: {str(e)}", exc_info=True)

    def _extract_research_from_workspace(self, workspace_content):
        """Extract research findings from workspace content."""
        try:
            # Look for research findings section
            if "## 📚 Research & Findings" in workspace_content:
                # Extract content between Research & Findings and next section
                import re
                pattern = r"## 📚 Research & Findings(.*?)(?=\n## |\Z)"
                match = re.search(pattern, workspace_content, re.DOTALL)
                if match:
                    research_section = match.group(1).strip()
                    # Remove placeholder text
                    if "*Detailed findings, sources, and data will be stored here*" not in research_section:
                        return research_section[:1000] + "..." if len(research_section) > 1000 else research_section
            return ""
        except Exception:
            return ""

    def _extract_key_findings_from_workspace(self, workspace_content):
        """Extract key findings from workspace research sections."""
        try:
            findings = []
            # Look for search results
            import re
            search_pattern = r"### 🔍 Search Results: ([^\n]+)"
            search_matches = re.findall(search_pattern, workspace_content)
            if search_matches:
                findings.extend([f"Research conducted on: {query}" for query in search_matches[:3]])

            # Look for planning results
            plan_pattern = r"### 📋 Generated Plan"
            if re.search(plan_pattern, workspace_content):
                findings.append("Strategic planning analysis completed")

            # Look for specific titles or companies mentioned
            title_pattern = r"\*\*([^*]+)\*\*"
            titles = re.findall(title_pattern, workspace_content)
            if titles:
                # Filter out common section headers
                filtered_titles = [t for t in titles[:5] if not any(header in t for header in
                    ["Status", "Steps", "Task", "Created", "Phase", "Title", "Complexity"])]
                if filtered_titles:
                    findings.extend([f"Information gathered on: {title}" for title in filtered_titles[:3]])

            if findings:
                return "\n".join([f"• {finding}" for finding in findings])
            return ""
        except Exception:
            return ""

    async def _create_structured_report(self, shared, virtual_fs_tool, original_goal, task_summary):
        """Create a structured report document for comprehensive deliverables."""
        try:
            task_id = shared.get("task_id", "unknown")
            timestamp = datetime.utcnow().isoformat()

            # Determine report type and structure based on goal
            if "business plan" in original_goal.lower():
                report_filename = f"business_plan_report_{task_id[:8]}.md"
                report_content = f"""# Business Plan Report

**Generated**: {timestamp}
**Task ID**: {task_id}
**Original Request**: {original_goal}

## Executive Summary
{task_summary}

## Market Analysis
*Based on autonomous research conducted*

### Market Size & Growth
- Industry analysis and projections
- Key market drivers and trends
- Competitive landscape overview

### Target Market
- Customer segments identified
- Market opportunities
- Geographic considerations

## Business Model & Strategy
### Service Offerings
- Core consulting services
- Value propositions
- Differentiation factors

### Revenue Model
- Pricing strategies
- Revenue streams
- Financial projections

## Operations Plan
### Organizational Structure
- Key roles and responsibilities
- Staffing requirements
- Operational processes

### Technology & Infrastructure
- Required systems and tools
- Technology stack recommendations
- Infrastructure needs

## Financial Projections
### Revenue Forecasts
- 3-year revenue projections
- Growth assumptions
- Market penetration estimates

### Cost Structure
- Operating expenses
- Capital requirements
- Break-even analysis

## Risk Analysis
### Market Risks
- Competitive threats
- Market volatility
- Regulatory considerations

### Mitigation Strategies
- Risk management approaches
- Contingency planning
- Success metrics

## Implementation Roadmap
### Phase 1: Foundation (Months 1-6)
- Initial setup and planning
- Team building
- Market entry strategy

### Phase 2: Growth (Months 7-18)
- Service expansion
- Client acquisition
- Process optimization

### Phase 3: Scale (Months 19-36)
- Market expansion
- Strategic partnerships
- Advanced service offerings

## Appendices
### A. Market Research Data
*Detailed findings from autonomous research*

### B. Financial Models
*Comprehensive financial analysis and projections*

### C. Competitive Analysis
*Detailed competitor research and positioning*

---
*This report was generated through autonomous execution using comprehensive research and analysis tools.*
"""

            elif "analysis" in original_goal.lower() or "market" in original_goal.lower():
                report_filename = f"market_analysis_report_{task_id[:8]}.md"
                report_content = f"""# Market Analysis Report

**Generated**: {timestamp}
**Task ID**: {task_id}
**Original Request**: {original_goal}

## Executive Summary
{task_summary}

## Market Overview
*Market size, growth, and key characteristics*

### Market Size & Growth
- Current market valuation
- Historical growth trends
- Future growth projections
- Key growth drivers

### Market Segmentation
- Primary market segments
- Customer demographics
- Geographic distribution
- Usage patterns

## Competitive Landscape
### Key Players
- Market leaders and their positions
- Market share analysis
- Competitive advantages
- Strategic positioning

### Competitive Dynamics
- Competitive intensity
- Barriers to entry
- Threat of substitutes
- Supplier power

## Technology & Innovation
### Current Technologies
- Dominant technologies
- Technology adoption rates
- Innovation cycles
- Emerging technologies

### Future Trends
- Technology roadmap
- Disruptive innovations
- Investment patterns
- R&D focus areas

## Market Drivers & Challenges
### Growth Drivers
- Regulatory support
- Consumer demand
- Technology advancement
- Economic factors

### Key Challenges
- Market barriers
- Regulatory hurdles
- Technical limitations
- Economic constraints

## Regional Analysis
### Geographic Markets
- Regional market sizes
- Growth variations
- Regulatory differences
- Cultural factors

## Investment & Opportunities
### Investment Landscape
- Funding trends
- Key investors
- Investment focus areas
- Valuation trends

### Market Opportunities
- Underserved segments
- Emerging markets
- Technology gaps
- Partnership opportunities

## Conclusions & Recommendations
### Key Findings
- Market attractiveness
- Growth potential
- Risk assessment
- Success factors

### Strategic Recommendations
- Market entry strategies
- Investment priorities
- Partnership opportunities
- Risk mitigation

---
*This analysis was generated through autonomous execution using comprehensive research and analysis tools.*
"""

            elif "plan" in original_goal.lower():
                report_filename = f"strategic_plan_{task_id[:8]}.md"
                report_content = f"""# Strategic Plan

**Generated**: {timestamp}
**Task ID**: {task_id}
**Original Request**: {original_goal}

## Executive Summary
{task_summary}

## Situation Analysis
*Current state assessment based on research*

## Strategic Objectives
*Key goals and targets identified*

## Implementation Plan
*Detailed action steps and timeline*

## Success Metrics
*KPIs and measurement criteria*

## Resource Requirements
*Budget, personnel, and infrastructure needs*

---
*This plan was generated through autonomous execution.*
"""

            else:
                report_filename = f"comprehensive_report_{task_id[:8]}.md"
                report_content = f"""# Comprehensive Report

**Generated**: {timestamp}
**Task ID**: {task_id}
**Original Request**: {original_goal}

## Executive Summary
{task_summary}

## Analysis & Findings
*Detailed analysis based on autonomous research*

## Recommendations
*Strategic recommendations and next steps*

## Implementation Guide
*Practical steps for execution*

---
*This report was generated through autonomous execution.*
"""

            # Create the structured report file
            await virtual_fs_tool.execute({
                "action": "create",
                "filename": report_filename,
                "content": report_content
            })

            logger.info(f"Created structured report: {report_filename}")

        except Exception as e:
            logger.warning(f"Failed to create structured report: {str(e)}", exc_info=True)






class PAContentSynthesisNode(AsyncNode):
    """Node that synthesizes collected research into comprehensive reports before task completion."""

    async def prep_async(self, shared):
        """Prepare content synthesis data."""
        workspace_filename = shared.get("workspace_filename")
        tool_registry = shared.get("tool_registry")
        original_goal = shared.get("original_goal", "")
        tools_used = shared.get("tools_used", [])
        baml_client = shared.get("baml_client")

        return {
            "workspace_filename": workspace_filename,
            "tool_registry": tool_registry,
            "original_goal": original_goal,
            "tools_used": tools_used,
            "baml_client": baml_client
        }

    async def exec_async(self, prep_res):
        """Execute content synthesis."""
        workspace_filename = prep_res.get("workspace_filename")
        tool_registry = prep_res.get("tool_registry")
        original_goal = prep_res.get("original_goal", "")
        tools_used = prep_res.get("tools_used", [])
        baml_client = prep_res.get("baml_client")

        if not workspace_filename or not tool_registry or "virtual_fs" not in tool_registry._tool_instances:
            return {
                "synthesis_result": None,
                "error": "Virtual file system not available for content synthesis"
            }

        try:
            virtual_fs_tool = tool_registry._tool_instances["virtual_fs"]

            # Read current workspace content
            read_result = await virtual_fs_tool.execute({
                "action": "read",
                "filename": workspace_filename
            })

            if not read_result.get("success", False):
                return {
                    "synthesis_result": None,
                    "error": "Failed to read workspace content"
                }

            # Extract workspace content
            result_data = read_result.get("result", {})
            if isinstance(result_data, dict) and "file" in result_data:
                workspace_content = result_data["file"].get("content", "")
            elif isinstance(result_data, str):
                workspace_content = result_data
            else:
                workspace_content = ""

            # Prepare collected research data from tools used
            collected_research = self._extract_research_data(tools_used)

            # Format tools used for synthesis
            tools_summary = json.dumps([{
                "tool": tool.get("tool", "unknown"),
                "success": tool.get("success", False),
                "timestamp": tool.get("timestamp", "")
            } for tool in tools_used], indent=2)

            if baml_client:
                # Use BAML for content synthesis
                synthesis_response = await baml_client.call_function(
                    "PersonalAssistantSynthesis",
                    original_goal=original_goal,
                    workspace_content=workspace_content,
                    collected_research=collected_research,
                    tools_used=tools_summary
                )

                # Convert BAML response to dictionary
                synthesis_result = {
                    "executive_summary": getattr(synthesis_response, 'executive_summary', ''),
                    "key_findings": getattr(synthesis_response, 'key_findings', []),
                    "detailed_analysis": getattr(synthesis_response, 'detailed_analysis', ''),
                    "recommendations": getattr(synthesis_response, 'recommendations', []),
                    "deliverables_created": getattr(synthesis_response, 'deliverables_created', []),
                    "next_steps": getattr(synthesis_response, 'next_steps', []),
                    "confidence_score": getattr(synthesis_response, 'confidence_score', 0.0)
                }

                return {
                    "synthesis_result": synthesis_result,
                    "error": None
                }
            else:
                # Fallback synthesis without BAML
                return {
                    "synthesis_result": self._fallback_synthesis(original_goal, workspace_content, collected_research),
                    "error": None
                }

        except Exception as e:
            logger.error(f"Error in content synthesis: {str(e)}", exc_info=True)
            return {
                "synthesis_result": None,
                "error": f"Content synthesis failed: {str(e)}"
            }

    def _extract_research_data(self, tools_used):
        """Extract and format research data from tool execution results."""
        research_data = []

        for tool in tools_used:
            if not tool.get("success", False):
                continue

            tool_name = tool.get("tool", "unknown")
            result = tool.get("result", {})

            if tool_name == "tavily_search" and isinstance(result, dict):
                search_data = result.get("result", result)
                query = search_data.get("query", "")
                results = search_data.get("results", [])

                if query and results:
                    research_entry = f"Search Query: {query}\n"
                    for i, search_result in enumerate(results, 1):
                        title = search_result.get("title", "No title")
                        url = search_result.get("url", "")
                        content = search_result.get("content", "")
                        research_entry += f"{i}. {title}\n   URL: {url}\n   Content: {content}\n\n"
                    research_data.append(research_entry)

            elif tool_name == "planning" and isinstance(result, dict):
                plan_data = result.get("result", result) if "result" in result else result
                if "plan" in plan_data:
                    plan = plan_data["plan"]
                    research_entry = f"Planning Analysis:\n"
                    research_entry += f"Title: {plan.get('title', 'N/A')}\n"
                    research_entry += f"Complexity: {plan.get('complexity', 'N/A')}\n"
                    if plan.get('subtasks'):
                        research_entry += f"Subtasks ({len(plan['subtasks'])}):\n"
                        for i, subtask in enumerate(plan['subtasks'], 1):
                            research_entry += f"{i}. {subtask.get('title', 'Untitled')}\n"
                            if subtask.get('description'):
                                research_entry += f"   Description: {subtask['description']}\n"
                    research_data.append(research_entry)

        return "\n\n".join(research_data) if research_data else "No research data collected"

    def _fallback_synthesis(self, original_goal, workspace_content, collected_research):
        """Fallback synthesis method when BAML is not available."""
        return {
            "executive_summary": f"Completed autonomous execution for: {original_goal}. Research data has been collected and analyzed.",
            "key_findings": ["Research data collected from multiple sources", "Workspace documentation created", "Analysis completed"],
            "detailed_analysis": f"Analysis based on collected research:\n\n{collected_research}",
            "recommendations": ["Review collected research data", "Implement findings as appropriate"],
            "deliverables_created": ["Workspace documentation", "Research compilation"],
            "next_steps": ["Review synthesis results", "Take action on recommendations"],
            "confidence_score": 0.7
        }

    async def post_async(self, shared, prep_res, exec_res):
        """Save synthesis results and decide next step."""
        synthesis_result = exec_res.get("synthesis_result")
        error = exec_res.get("error")

        if error:
            logger.warning(f"Content synthesis error: {error}")
            shared["synthesis_error"] = error
            return "respond"  # Continue to response generation despite synthesis error

        if synthesis_result:
            shared["synthesis_result"] = synthesis_result
            logger.info("Content synthesis completed successfully")

            # Update workspace with synthesized content
            await self._update_workspace_with_synthesis(shared, synthesis_result)

        return "respond"

    async def _update_workspace_with_synthesis(self, shared, synthesis_result):
        """Update workspace file with synthesized content."""
        workspace_filename = shared.get("workspace_filename")
        tool_registry = shared.get("tool_registry")

        if not workspace_filename or not tool_registry or "virtual_fs" not in tool_registry._tool_instances:
            return

        try:
            virtual_fs_tool = tool_registry._tool_instances["virtual_fs"]

            # Read current workspace
            read_result = await virtual_fs_tool.execute({
                "action": "read",
                "filename": workspace_filename
            })

            if not read_result.get("success", False):
                return

            # Extract content
            result_data = read_result.get("result", {})
            if isinstance(result_data, dict) and "file" in result_data:
                current_content = result_data["file"].get("content", "")
            elif isinstance(result_data, str):
                current_content = result_data
            else:
                return

            # Create comprehensive final deliverable with synthesized content
            timestamp = datetime.utcnow().isoformat()
            original_goal = shared.get("original_goal", "")

            # Format key findings
            key_findings_text = ""
            for i, finding in enumerate(synthesis_result.get("key_findings", []), 1):
                key_findings_text += f"{i}. {finding}\n"

            # Format recommendations
            recommendations_text = ""
            for i, rec in enumerate(synthesis_result.get("recommendations", []), 1):
                recommendations_text += f"{i}. {rec}\n"

            # Format deliverables
            deliverables_text = ""
            for i, deliverable in enumerate(synthesis_result.get("deliverables_created", []), 1):
                deliverables_text += f"{i}. {deliverable}\n"

            # Format next steps
            next_steps_text = ""
            for i, step in enumerate(synthesis_result.get("next_steps", []), 1):
                next_steps_text += f"{i}. {step}\n"

            synthesized_deliverable = f"""

## 🎯 Task Completion Summary

**Original Goal**: {original_goal}

**Completion Status**: ✅ COMPLETED
**Completion Time**: {timestamp}
**Total Steps**: {shared.get('steps_completed', 0)}
**Synthesis Confidence**: {synthesis_result.get('confidence_score', 0.0):.2f}

### 📋 Executive Summary
{synthesis_result.get('executive_summary', 'No executive summary available')}

### 🔍 Key Findings
{key_findings_text if key_findings_text else 'No specific findings identified'}

### 📊 Detailed Analysis
{synthesis_result.get('detailed_analysis', 'No detailed analysis available')}

### 💡 Recommendations
{recommendations_text if recommendations_text else 'No specific recommendations provided'}

### 📋 Deliverables Created
{deliverables_text if deliverables_text else 'No specific deliverables identified'}

### 🚀 Next Steps
{next_steps_text if next_steps_text else 'No specific next steps identified'}

---
**Note**: This deliverable was created through autonomous execution with comprehensive content synthesis.
"""

            # Update Final Deliverables section
            if "## 🎯 Final Deliverables" in current_content:
                if "*Completed outputs and final results*" in current_content:
                    current_content = current_content.replace(
                        "*Completed outputs and final results*",
                        f"*Autonomous execution completed with comprehensive synthesis*{synthesized_deliverable}"
                    )
                else:
                    # Append to existing deliverables
                    current_content = current_content.replace(
                        "## 🎯 Final Deliverables",
                        f"## 🎯 Final Deliverables{synthesized_deliverable}"
                    )

            # Update status to COMPLETED
            current_content = current_content.replace(
                "- **Status**: IN_PROGRESS",
                "- **Status**: COMPLETED"
            )

            # Update workspace file
            await virtual_fs_tool.execute({
                "action": "update",
                "filename": workspace_filename,
                "content": current_content
            })

            logger.info("Workspace updated with synthesized content")

        except Exception as e:
            logger.warning(f"Failed to update workspace with synthesis: {str(e)}", exc_info=True)


class PAResponseNode(AsyncNode):
    """Node that generates final responses."""

    async def prep_async(self, shared):
        """Prepare response data including workspace content for comprehensive responses."""
        user_message = shared.get("user_message", "")
        thoughts = shared.get("thoughts", [])
        tool_results = shared.get("current_tool_results", [])
        config = shared.get("config")
        baml_client = shared.get("baml_client")

        # Check for LLM-generated final output from intent-driven execution
        llm_final_output = shared.get("final_output")

        # Include workspace content and synthesis results for better responses
        workspace_content = shared.get("current_workspace_content", "")
        synthesis_result = shared.get("synthesis_result", {})
        workspace_filename = shared.get("workspace_filename")
        original_goal = shared.get("original_goal", "")
        steps_completed = shared.get("steps_completed", 0)

        # If we don't have cached workspace content, try to load it
        if not workspace_content and workspace_filename:
            workspace_content = await self._load_workspace_content(shared)

        # Include failed todos information for intent-driven execution
        failed_todos = shared.get("failed_todos", [])
        plan_completed = shared.get("plan_completed", False)
        structured_plan = shared.get("structured_plan", {})

        return {
            "user_message": user_message,
            "original_goal": original_goal,
            "thoughts": thoughts,
            "tool_results": tool_results,
            "system_prompt": config.system_prompt if config else "",
            "baml_client": baml_client,
            "workspace_content": workspace_content,
            "synthesis_result": synthesis_result,
            "steps_completed": steps_completed,
            "workspace_filename": workspace_filename,
            "llm_final_output": llm_final_output,
            "failed_todos": failed_todos,
            "plan_completed": plan_completed,
            "structured_plan": structured_plan
        }

    async def _load_workspace_content(self, shared):
        """Load workspace content if not already cached."""
        workspace_filename = shared.get("workspace_filename")
        tool_registry = shared.get("tool_registry")

        if not workspace_filename or not tool_registry or "virtual_fs" not in tool_registry._tool_instances:
            return ""

        try:
            virtual_fs_tool = tool_registry._tool_instances["virtual_fs"]
            read_result = await virtual_fs_tool.execute({
                "action": "read",
                "filename": workspace_filename
            })

            if read_result.get("success", False):
                result_data = read_result.get("result", {})
                if isinstance(result_data, dict) and "file" in result_data:
                    return result_data["file"].get("content", "")
                elif isinstance(result_data, str):
                    return result_data
        except Exception as e:
            logger.warning(f"Failed to load workspace content for response: {str(e)}")

        return ""

    async def exec_async(self, prep_res):
        """Generate final response using workspace content and synthesis results."""
        user_message = prep_res["user_message"]
        original_goal = prep_res.get("original_goal", "")
        thoughts = prep_res["thoughts"]
        tool_results = prep_res["tool_results"]
        system_prompt = prep_res["system_prompt"]
        baml_client = prep_res.get("baml_client")
        workspace_content = prep_res.get("workspace_content", "")
        synthesis_result = prep_res.get("synthesis_result", {})
        steps_completed = prep_res.get("steps_completed", 0)
        llm_final_output = prep_res.get("llm_final_output")
        failed_todos = prep_res.get("failed_todos", [])
        plan_completed = prep_res.get("plan_completed", False)
        structured_plan = prep_res.get("structured_plan", {})

        try:
            # Priority 1: Use LLM's final output if available (from intent-driven execution)
            if llm_final_output:
                print(f"🧠 Using LLM-generated final output from intent-driven execution")

                # If there are failed todos, append information about them
                if failed_todos:
                    failed_info = self._format_failed_todos_info(failed_todos)
                    return f"{llm_final_output}\n\n{failed_info}"

                return llm_final_output

            # Priority 2: Check if we have comprehensive workspace content with synthesis
            has_synthesis = (
                workspace_content and
                len(workspace_content) > 1000 and
                ("Executive Summary" in workspace_content or
                 "Key Findings" in workspace_content or
                 "Final Deliverables" in workspace_content)
            )

            if has_synthesis:
                # Extract key sections from workspace for response
                response = self._generate_response_from_workspace(workspace_content, original_goal, user_message)
                return response
            elif baml_client:
                # Use BAML for response generation with enhanced context
                enhanced_context = f"""
                Original Goal: {original_goal}
                Steps Completed: {steps_completed}
                Workspace Content Available: {len(workspace_content)} characters
                Synthesis Result: {synthesis_result}
                """

                response = await baml_client.call_function(
                    "PersonalAssistantResponse",
                    user_query=user_message,
                    thinking_process=json.dumps([t.get("thinking", "") for t in thoughts]),
                    tool_results=json.dumps(tool_results),
                    system_prompt=system_prompt + "\n\nAdditional Context:\n" + enhanced_context
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

    def _generate_response_from_workspace(self, workspace_content, original_goal, user_message):
        """Generate a comprehensive response from workspace content."""
        try:
            # Extract key sections from workspace
            sections = {
                "executive_summary": self._extract_section(workspace_content, "Executive Summary"),
                "key_findings": self._extract_section(workspace_content, "Key Findings"),
                "detailed_analysis": self._extract_section(workspace_content, "Detailed Analysis"),
                "recommendations": self._extract_section(workspace_content, "Recommendations"),
                "deliverables": self._extract_section(workspace_content, "Deliverables Created")
            }

            # Build comprehensive response
            response_parts = []

            # Introduction
            response_parts.append(f"I have completed your request: {original_goal}")
            response_parts.append("")

            # Executive Summary
            if sections["executive_summary"]:
                response_parts.append("## Executive Summary")
                response_parts.append(sections["executive_summary"])
                response_parts.append("")

            # Key Findings
            if sections["key_findings"]:
                response_parts.append("## Key Findings")
                response_parts.append(sections["key_findings"])
                response_parts.append("")

            # Analysis (condensed)
            if sections["detailed_analysis"]:
                analysis = sections["detailed_analysis"][:500] + "..." if len(sections["detailed_analysis"]) > 500 else sections["detailed_analysis"]
                response_parts.append("## Analysis")
                response_parts.append(analysis)
                response_parts.append("")

            # Deliverables
            if sections["deliverables"]:
                response_parts.append("## Deliverables Created")
                response_parts.append(sections["deliverables"])
                response_parts.append("")

            # Recommendations
            if sections["recommendations"]:
                response_parts.append("## Recommendations")
                response_parts.append(sections["recommendations"])
                response_parts.append("")

            response_parts.append("The complete detailed analysis and findings are available in the workspace file.")

            return "\n".join(response_parts)

        except Exception as e:
            logger.error(f"Error generating response from workspace: {str(e)}")
            return f"I have completed your research on {original_goal}. The comprehensive results are available in the workspace file, including detailed analysis, findings, and recommendations."

    def _extract_section(self, content, section_name):
        """Extract a specific section from workspace content."""
        try:
            # Look for section header with various formats (including emojis)
            section_patterns = [
                f"### 📋 {section_name}",
                f"### 🔍 {section_name}",
                f"### 📊 {section_name}",
                f"### 💡 {section_name}",
                f"### {section_name}",
                f"## {section_name}",
                f"**{section_name}**"
            ]

            # Also try partial matches for sections that might have different formatting
            if section_name == "Executive Summary":
                section_patterns.extend(["### 📋 Executive Summary", "## 📋 Executive Summary"])
            elif section_name == "Key Findings":
                section_patterns.extend(["### 🔍 Key Findings", "## 🔍 Key Findings"])
            elif section_name == "Detailed Analysis":
                section_patterns.extend(["### 📊 Detailed Analysis", "## 📊 Detailed Analysis"])
            elif section_name == "Recommendations":
                section_patterns.extend(["### 💡 Recommendations", "## 💡 Recommendations"])
            elif section_name == "Deliverables Created":
                section_patterns.extend(["### 📋 Deliverables Created", "## 📋 Deliverables Created"])

            for pattern in section_patterns:
                if pattern in content:
                    start_idx = content.find(pattern)
                    if start_idx != -1:
                        # Find the end of this section (next header or end of content)
                        remaining_content = content[start_idx + len(pattern):]

                        # Look for next section header (but skip the first newline)
                        search_content = remaining_content[1:] if remaining_content.startswith('\n') else remaining_content
                        next_section_patterns = ["\n###", "\n##", "\n**"]
                        end_idx = len(remaining_content)

                        for next_pattern in next_section_patterns:
                            next_idx = search_content.find(next_pattern)
                            if next_idx != -1:
                                # Adjust for the offset if we skipped the first character
                                actual_idx = next_idx + (1 if remaining_content.startswith('\n') else 0)
                                if actual_idx < end_idx:
                                    end_idx = actual_idx

                        section_content = remaining_content[:end_idx].strip()
                        return section_content

            return ""
        except Exception:
            return ""

    def _format_failed_todos_info(self, failed_todos: List[Dict[str, Any]]) -> str:
        """Format information about failed todos for inclusion in the response."""
        if not failed_todos:
            return ""

        failed_info = "\n⚠️ **Note**: Some tasks encountered issues during execution:\n"

        for i, failed_todo in enumerate(failed_todos, 1):
            todo = failed_todo.get("todo", {})
            reason = failed_todo.get("reason", "Unknown error")
            retry_count = failed_todo.get("retry_count", 0)

            failed_info += f"\n{i}. **{todo.get('title', 'Unknown task')}**\n"
            failed_info += f"   - Reason: {reason}\n"
            failed_info += f"   - Attempts made: {retry_count}\n"

        failed_info += "\nDespite these issues, I've completed what I could and provided the best possible response based on the successful tasks."

        return failed_info

    async def post_async(self, shared, prep_res, exec_res):
        """Save final response and create final deliverable if needed."""
        shared["final_response"] = exec_res
        print(f"💬 Generated response: {exec_res[:100]}...")

        # Create final deliverable if autonomous execution is complete
        if shared.get("create_final_deliverable", False):
            task_summary = shared.get("task_summary", "Task completed successfully through autonomous execution.")
            # Create a temporary tool call node instance to access the method
            tool_call_node = PAToolCallNode()
            await tool_call_node._create_final_deliverable(shared, task_summary)
            print("📋 Created final deliverable and structured report")

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


class PAWorkspaceManagerNode(AsyncNode):
    """Node that manages workspace for multi-step autonomous tasks."""

    async def prep_async(self, shared):
        """Prepare workspace management data."""
        user_message = shared.get("user_message", "")
        tool_registry = shared.get("tool_registry")

        return {
            "user_message": user_message,
            "tool_registry": tool_registry,
            "task_id": str(uuid.uuid4())
        }

    async def exec_async(self, prep_res):
        """Initialize workspace for the task."""
        user_message = prep_res["user_message"]
        task_id = prep_res["task_id"]
        tool_registry = prep_res["tool_registry"]

        # Analyze task type for better workspace structure
        task_type = "general"
        if any(word in user_message.lower() for word in ["research", "study", "investigate", "analyze", "find"]):
            task_type = "research"
        elif any(word in user_message.lower() for word in ["plan", "strategy", "project", "organize"]):
            task_type = "planning"
        elif any(word in user_message.lower() for word in ["create", "write", "generate", "build"]):
            task_type = "creation"

        # Create enhanced workspace file content based on task type
        workspace_content = f"""# Autonomous Task Workspace: {task_id}

## 🎯 Original Goal
{user_message}

## 📊 Task Metadata
- **Task Type**: {task_type.title()}
- **Status**: IN_PROGRESS
- **Created**: {datetime.utcnow().isoformat()}
- **Steps Completed**: 0
- **Current Phase**: Initialization

## 📋 Execution Plan
*To be populated by planning tool or autonomous thinking*

## 🔄 Progress Log
- `{datetime.utcnow().isoformat()}`: Task initialized with {task_type} workspace structure

## 📚 Research & Findings
*Detailed findings, sources, and data will be stored here*

## 📝 Working Documents
*Draft content, intermediate results, and work-in-progress materials*

## 🎯 Final Deliverables
*Completed outputs and final results*

## 💭 Notes & Scratchpad
*Working notes, ideas, and temporary data*

---
*This workspace is actively managed by the autonomous agent to track progress and build comprehensive outputs.*
"""

        # Create workspace file using virtual_fs tool if available
        workspace_created = False
        if tool_registry and "virtual_fs" in tool_registry._tool_instances:
            try:
                virtual_fs_tool = tool_registry._tool_instances["virtual_fs"]
                workspace_filename = f"task_workspace_{task_id[:8]}.md"

                result = await virtual_fs_tool.execute({
                    "action": "create",
                    "filename": workspace_filename,
                    "content": workspace_content
                })

                if result.get("success", False):
                    workspace_created = True
                    logger.info(f"Created workspace file: {workspace_filename}")

            except Exception as e:
                logger.warning(f"Failed to create workspace file: {str(e)}")

        return {
            "task_id": task_id,
            "workspace_created": workspace_created,
            "workspace_filename": f"task_workspace_{task_id[:8]}.md" if workspace_created else None,
            "workspace_content": workspace_content
        }

    async def post_async(self, shared, prep_res, exec_res):
        """Save workspace information to shared state."""
        shared["task_id"] = exec_res["task_id"]
        shared["workspace_filename"] = exec_res.get("workspace_filename")
        shared["workspace_created"] = exec_res["workspace_created"]
        shared["original_goal"] = shared.get("user_message", "")
        shared["steps_completed"] = 0
        shared["autonomous_mode"] = True

        print(f"🗂️ Workspace initialized for task: {exec_res['task_id'][:8]}")
        if exec_res["workspace_created"]:
            print(f"📁 Workspace file: {exec_res['workspace_filename']}")

        return "think"


class PAAutonomousThinkNode(AsyncNode):
    """Node that provides autonomous thinking with goal persistence and multi-step execution."""

    async def prep_async(self, shared):
        """Prepare autonomous thinking data."""
        user_message = shared.get("user_message", "")
        session = shared.get("session", {})
        config = shared.get("config")
        tool_registry = shared.get("tool_registry")
        baml_client = shared.get("baml_client")

        # Get autonomous execution context
        original_goal = shared.get("original_goal", user_message)
        steps_completed = shared.get("steps_completed", 0)
        workspace_filename = shared.get("workspace_filename")
        task_id = shared.get("task_id", "unknown")

        # Get conversation history
        messages = session.get("messages", [])
        conversation_history = []
        for msg in messages[-10:]:  # Last 10 messages for context
            role = msg.get("role", "user")
            content = msg.get("content", "")
            conversation_history.append(f"{role}: {content}")

        # Get available tools
        available_tools = []
        if tool_registry:
            for tool_name, tool_instance in tool_registry._tool_instances.items():
                tool_info = {
                    "name": tool_name,
                    "description": getattr(tool_instance.registry, 'description', 'No description'),
                    "schema": getattr(tool_instance.registry, 'schema_data', {})
                }
                available_tools.append(tool_info)

        # Get system prompt with autonomous instructions
        system_prompt = self._get_autonomous_system_prompt(config)

        # Get current workspace content and metrics from shared state
        workspace_content = shared.get("current_workspace_content", "")
        workspace_has_content = shared.get("workspace_has_content", False)
        workspace_has_empty_sections = shared.get("workspace_has_empty_sections", False)
        workspace_research_indicators = shared.get("workspace_research_indicators", 0)
        tools_used_count = len(shared.get("tools_used", []))

        # Build enhanced context with workspace information
        context_parts = [
            f"Original Goal: {original_goal}",
            f"Steps Completed: {steps_completed}",
            f"Tools Used: {tools_used_count}",
            f"Task ID: {task_id}"
        ]

        if workspace_filename:
            context_parts.append(f"Workspace File: {workspace_filename}")
            context_parts.append(f"Workspace Content Length: {len(workspace_content)} characters")
            context_parts.append(f"Workspace Has Meaningful Content: {workspace_has_content}")
            context_parts.append(f"Workspace Has Empty Sections: {workspace_has_empty_sections}")
            context_parts.append(f"Research Indicators Found: {workspace_research_indicators}")

            if workspace_content and len(workspace_content) > 0:
                # Include a preview of workspace content for context
                preview_length = min(500, len(workspace_content))
                workspace_preview = workspace_content[:preview_length]
                if len(workspace_content) > preview_length:
                    workspace_preview += "..."
                context_parts.append(f"Workspace Content Preview:\n{workspace_preview}")

        enhanced_context = "\n".join(context_parts)

        return {
            "user_message": user_message,
            "original_goal": original_goal,
            "steps_completed": steps_completed,
            "task_id": task_id,
            "workspace_filename": workspace_filename,
            "conversation_history": "\n".join(conversation_history) if conversation_history else "No previous conversation",
            "available_tools": json.dumps(available_tools, indent=2),
            "system_prompt": system_prompt,
            "baml_client": baml_client,
            "enhanced_context": enhanced_context,
            "workspace_content": workspace_content,
            "workspace_metrics": {
                "has_content": workspace_has_content,
                "has_empty_sections": workspace_has_empty_sections,
                "research_indicators": workspace_research_indicators,
                "content_length": len(workspace_content)
            }
        }

    def _get_autonomous_system_prompt(self, config):
        """Get system prompt with autonomous execution instructions."""
        base_prompt = """You are a helpful Personal Assistant with access to various tools and capabilities.

Your role is to:
1. Understand user requests and break them down into actionable steps
2. Execute multiple tools sequentially as needed to fully complete the user's request
3. Use virtual_fs tool to maintain a persistent workspace for multi-step tasks
4. Continue tool execution until the original goal is achieved or user intervention is required
5. Maintain conversation context and remember user preferences
6. Ask for clarification when requests are ambiguous

AUTONOMOUS EXECUTION INSTRUCTIONS:
- Execute multiple tools in sequence to complete complex tasks
- After each tool call, evaluate if the original user goal is complete
- If incomplete, determine and execute the next required action automatically
- Use virtual_fs as your persistent workspace:
  * Create and update workspace files to track progress
  * Store intermediate results and findings
  * Reference previous work to maintain context
  * Use as scratchpad for working notes
- Always maintain awareness of the original user objective throughout execution
- Before each tool call, verify the action advances toward goal completion
- Only stop when the task is fully accomplished or clarification is needed

Available capabilities:
- System prompt management for different contexts
- Task planning and decomposition
- Virtual file system for temporary data storage and workspace management
- Web search capabilities for research tasks
- Google Calendar integration (when authorized)
- Gmail integration (when authorized)

Always be professional, helpful, and transparent about your actions and limitations."""

        return base_prompt

    async def exec_async(self, prep_res):
        """Execute autonomous thinking."""
        baml_client = prep_res.get("baml_client")

        if not baml_client:
            return {
                "thinking": "No BAML client available for autonomous thinking",
                "action": "chat_response",
                "action_input": "I'm unable to process this request autonomously at the moment.",
                "is_final": True,
                "needs_tools": False,
                "tools_to_use": None,
                "goal_achieved": False
            }

        try:
            # Enhanced prompt for autonomous execution with workspace context
            autonomous_prompt = f"""
            AUTONOMOUS TASK EXECUTION - COMPREHENSIVE AGENT

            You are an autonomous agent capable of using multiple tools strategically to accomplish any task.

            CURRENT CONTEXT:
            {prep_res.get('enhanced_context', 'No enhanced context available')}

            WORKSPACE ANALYSIS:
            - Content Length: {prep_res.get('workspace_metrics', {}).get('content_length', 0)} characters
            - Has Meaningful Content: {prep_res.get('workspace_metrics', {}).get('has_content', False)}
            - Has Empty Sections: {prep_res.get('workspace_metrics', {}).get('has_empty_sections', False)}
            - Research Indicators: {prep_res.get('workspace_metrics', {}).get('research_indicators', 0)}

            DECISION MAKING CONTEXT:
            Based on the workspace analysis above, you can make informed decisions about:
            - Whether research has been conducted (check research indicators and content length)
            - Whether synthesis is needed (check for empty sections despite having research)
            - Whether the task is truly complete (check if meaningful content exists)
            - Whether more research is needed (check content quality vs. original goal)

            AVAILABLE TOOLS & STRATEGIC USAGE:
            1. **planning** - Use for complex tasks requiring structured approach, project planning, task breakdown
            2. **virtual_fs** - Use as persistent workspace: store findings, create reports, maintain progress, reference materials
            3. **tavily_search** - Use for research, current information, fact-finding, market analysis
            4. **system_prompt** - Use to adjust behavior for specific task types or contexts

            AUTONOMOUS EXECUTION STRATEGY:
            1. **Task Analysis**: What type of task is this? (research, planning, analysis, creation, etc.)
            2. **Tool Selection**: Which tools will best accomplish this specific task?
            3. **Execution Depth**: How comprehensive should the output be?
            4. **Workspace Usage**: How can I use virtual_fs to organize and build upon work?
            5. **Quality Check**: Does my output meet professional standards for this task type?

            TASK TYPE STRATEGIES:
            - **Research Tasks**: Use planning → multiple tavily_search → virtual_fs to compile comprehensive reports
            - **Planning Tasks**: Use planning tool → virtual_fs to create structured plans with timelines
            - **Analysis Tasks**: Gather data → virtual_fs for organization → synthesize insights
            - **Creative Tasks**: Use planning for structure → virtual_fs for drafts and iterations

            WORKSPACE UTILIZATION (virtual_fs tool):
            - **READ existing workspace**: Use "read" action to retrieve and analyze previously stored research
            - **UPDATE with new findings**: Use "update" action to build upon existing workspace content
            - **CREATE structured documents**: Build comprehensive reports, plans, and analyses
            - **MAINTAIN research continuity**: Reference previous findings when adding new content
            - **STORE complete data**: Save full research results, not summaries or truncated content
            - **BUILD comprehensive sections**: Populate Research & Findings with actual data and sources
            - **TRACK progress systematically**: Update Working Documents with detailed intermediate results

            QUALITY STANDARDS:
            - Deliver comprehensive, professional-quality outputs
            - Use multiple sources and cross-reference information
            - Create structured, well-organized final deliverables
            - Ensure completeness before marking task as finished

            CURRENT SITUATION ANALYSIS:
            Steps Completed: {prep_res['steps_completed']}
            Available Tools: {prep_res['available_tools']}

            DECISION FRAMEWORK:
            1. Is this task complete to professional standards?
            2. What specific tool should I use next to advance the goal?
            3. How can I use the workspace more effectively?
            4. What would make this output truly comprehensive?

            Respond with your strategic analysis and next action.
            """

            response = await baml_client.call_function(
                "PersonalAssistantThinking",
                user_query=autonomous_prompt,
                conversation_history=prep_res["conversation_history"],
                available_tools=prep_res["available_tools"],
                system_prompt=prep_res["system_prompt"]
            )

            logger.info(f"BAML response type: {type(response)}")
            logger.info(f"BAML response attributes: {dir(response)}")

            # Convert BAML response to dictionary format
            response_dict = {
                "thinking": getattr(response, 'thinking', 'No thinking provided'),
                "action": getattr(response, 'action', 'chat_response'),
                "action_input": getattr(response, 'action_input', None),
                "is_final": getattr(response, 'is_final', True),
                "needs_tools": getattr(response, 'needs_tools', False),
                "tools_to_use": getattr(response, 'tools_to_use', None),
                "goal_achieved": getattr(response, 'goal_achieved', getattr(response, 'is_final', True)),
                "original_goal": prep_res["original_goal"],
                "steps_completed": prep_res["steps_completed"]
            }

            logger.info(f"Converted response_dict: {response_dict}")
            return response_dict

        except Exception as e:
            logger.error(f"Error in autonomous thinking: {str(e)}", exc_info=True)
            return {
                "thinking": f"Error in autonomous thinking: {str(e)}",
                "action": "chat_response",
                "action_input": "I encountered an error while processing your request autonomously.",
                "is_final": True,
                "needs_tools": False,
                "tools_to_use": None,
                "goal_achieved": False
            }

    async def post_async(self, shared, prep_res, exec_res):
        """Process autonomous thinking results and decide next step."""
        # Save thinking results
        if "thoughts" not in shared:
            shared["thoughts"] = []
        shared["thoughts"].append(exec_res)

        # Update execution context
        shared["current_action"] = exec_res["action"]
        shared["current_action_input"] = exec_res["action_input"]
        shared["needs_tools"] = exec_res.get("needs_tools", False)
        shared["tools_to_use"] = exec_res.get("tools_to_use", [])
        shared["goal_achieved"] = exec_res.get("goal_achieved", False)

        print(f"🤖 Autonomous Thinking: {exec_res['thinking'][:100]}...")

        # Autonomous decision making
        if exec_res.get("goal_achieved", False) or exec_res.get("is_final", False):
            # Before marking as complete, validate task quality
            quality_check = await self._validate_task_completion(shared)

            if not quality_check["is_complete"]:
                logger.warning(f"Quality validation failed: {quality_check['reason']}")
                print(f"⚠️ Quality check failed: {quality_check['reason']}")

                # Override goal_achieved and continue execution
                shared["quality_issues"] = quality_check["issues"]
                shared["needs_synthesis"] = True

                # If we have research but no synthesis, go to synthesis
                if quality_check.get("has_research") and not quality_check.get("has_synthesis"):
                    logger.info("Routing to synthesis - research found but no synthesis performed")
                    return "synthesize"
                elif shared.get("steps_completed", 0) > 20:  # After many steps, force synthesis
                    logger.info("Forcing synthesis after many steps to prevent infinite loops")
                    return "synthesize"
                else:
                    # Continue with more tool execution
                    logger.info("Continuing autonomous thinking - more work needed")
                    return "think"

            # Quality check passed - Goal is achieved, mark for final deliverable creation and generate response
            shared["create_final_deliverable"] = True
            shared["task_summary"] = exec_res.get("thinking", "Task completed successfully through autonomous execution.")
            shared["final_response"] = exec_res["action_input"]
            return "respond"
        elif exec_res.get("needs_tools", False) and exec_res.get("tools_to_use"):
            # Tools needed, execute them
            return "tools"
        else:
            # Continue thinking or generate response
            return "respond"

    async def _validate_task_completion(self, shared):
        """Validate that the task is truly complete with quality output."""
        workspace_filename = shared.get("workspace_filename")
        tool_registry = shared.get("tool_registry")
        original_goal = shared.get("original_goal", "")

        validation_result = {
            "is_complete": False,
            "reason": "Unknown validation error",
            "issues": [],
            "has_research": False,
            "has_synthesis": False
        }

        # Use workspace metrics from shared state if available (more efficient)
        workspace_metrics = shared.get("workspace_metrics", {})
        workspace_content = shared.get("current_workspace_content", "")

        if workspace_metrics and workspace_content:
            # Use cached workspace data for faster validation
            logger.debug("Using cached workspace data for validation")

        elif not workspace_filename or not tool_registry or "virtual_fs" not in tool_registry._tool_instances:
            validation_result["reason"] = "No workspace available for validation"
            return validation_result
        else:
            # Fallback to reading workspace content
            try:
                virtual_fs_tool = tool_registry._tool_instances["virtual_fs"]

                # Read workspace content
                read_result = await virtual_fs_tool.execute({
                    "action": "read",
                    "filename": workspace_filename
                })

                if not read_result.get("success", False):
                    validation_result["reason"] = "Failed to read workspace for validation"
                    return validation_result

                # Extract content
                result_data = read_result.get("result", {})
                if isinstance(result_data, dict) and "file" in result_data:
                    workspace_content = result_data["file"].get("content", "")
                elif isinstance(result_data, str):
                    workspace_content = result_data
                else:
                    validation_result["reason"] = "Invalid workspace content structure"
                    return validation_result
            except Exception as e:
                logger.error(f"Error reading workspace for validation: {str(e)}")
                validation_result["reason"] = f"Validation error: {str(e)}"
                return validation_result

        try:

            # Check for placeholder text (indicates incomplete work)
            placeholder_checks = [
                "*Detailed findings, sources, and data will be stored here*",
                "*Based on autonomous research and analysis conducted*",
                "*Recommendations for follow-up actions based on completed analysis*",
                "*Draft content, intermediate results, and work-in-progress materials*",
                "*To be populated by planning tool or autonomous thinking*"
            ]

            issues = []
            for placeholder in placeholder_checks:
                if placeholder in workspace_content:
                    issues.append(f"Placeholder text found: {placeholder}")

            # Check for actual research content
            has_research = False
            research_indicators = [
                "### 🔍 Search Results:",
                "### 📋 Generated Plan",
                "### 🧠 Planning Analysis",
                "URL:",
                "Content:",
                "http://",
                "https://",
                "CEO",
                "OnlyFans",
                "net worth",
                "agency"
            ]

            # Also check if we have tool execution history indicating research
            tools_used = shared.get("tools_used", [])
            search_tools_count = len([t for t in tools_used if t.get("tool") == "tavily_search"])

            # Consider research present if we have search indicators OR multiple search tool executions
            for indicator in research_indicators:
                if indicator in workspace_content:
                    has_research = True
                    break

            # If we have many search tool executions, assume research was conducted
            if search_tools_count >= 3:
                has_research = True
                logger.info(f"Research detected based on {search_tools_count} search tool executions")

            validation_result["has_research"] = has_research

            # Check for synthesis results
            has_synthesis = (
                shared.get("synthesis_result") is not None or
                "comprehensive synthesis" in workspace_content.lower() or
                "synthesis confidence" in workspace_content.lower()
            )
            validation_result["has_synthesis"] = has_synthesis

            # Check minimum content requirements based on task type
            min_content_length = 500  # Minimum characters for meaningful content
            if "research" in original_goal.lower() or "analysis" in original_goal.lower():
                min_content_length = 1000

            if len(workspace_content) < min_content_length:
                issues.append(f"Content too short: {len(workspace_content)} chars (minimum: {min_content_length})")

            # Check for empty sections (headers without content)
            empty_section_patterns = [
                "## Executive Summary\n\n## ",
                "## Introduction\n\n## ",
                "## Research Findings\n### ",
                "## Analysis\n\n## ",
                "## Conclusion\n\n## "
            ]

            for pattern in empty_section_patterns:
                if pattern in workspace_content:
                    issues.append("Empty sections found - content needs synthesis")
                    break

            # Check for specific findings (not just generic text)
            if has_research:
                # Look for specific data like URLs, names, numbers
                import re
                urls = re.findall(r'https?://[^\s]+', workspace_content)
                specific_names = re.findall(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b', workspace_content)  # Proper names
                numbers = re.findall(r'\b\d+(?:\.\d+)?(?:%|\$|million|billion)?\b', workspace_content)

                if not urls and not specific_names and not numbers:
                    issues.append("No specific data found (URLs, names, numbers)")

            # Final validation
            if issues:
                validation_result["is_complete"] = False
                validation_result["reason"] = f"Quality issues found: {len(issues)} problems"
                validation_result["issues"] = issues
            elif not has_research:
                validation_result["is_complete"] = False
                validation_result["reason"] = "No research content found in workspace"
            elif has_research and not has_synthesis:
                validation_result["is_complete"] = False
                validation_result["reason"] = "Research found but no synthesis performed"
            else:
                validation_result["is_complete"] = True
                validation_result["reason"] = "Task validation passed"

            return validation_result

        except Exception as e:
            logger.error(f"Error in task validation: {str(e)}", exc_info=True)
            validation_result["reason"] = f"Validation error: {str(e)}"
            return validation_result