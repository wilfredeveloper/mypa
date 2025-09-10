// Personal Assistant BAML Functions

class PAThinkingResult {
  thinking string
  action string
  action_input string?
  is_final bool
  needs_tools bool
  tools_to_use PAToolCall[]?
  goal_achieved bool?
}

class PAToolCall {
  name string
  parameters map<string, string>
}

class PAResponseResult {
  response string
  confidence_score float?
  reasoning string?
}

class PASynthesisResult {
  executive_summary string
  key_findings string[]
  detailed_analysis string
  recommendations string[]
  deliverables_created string[]
  next_steps string[]
  confidence_score float?
}

function PersonalAssistantThinking(
  user_query: string,
  conversation_history: string,
  available_tools: string,
  system_prompt: string
) -> PAThinkingResult {
  client AgenticGeminiRateLimited
  prompt #"
    You are an AUTONOMOUS Personal Assistant capable of multi-step execution to complete complex tasks. You can execute multiple tools sequentially until the original goal is fully achieved.

    System Context:
    {{ system_prompt }}

    Available Tools:
    {{ available_tools }}

    Conversation History:
    {{ conversation_history }}

    Current Context (includes original goal, steps completed, and current request):
    {{ user_query }}

    AUTONOMOUS EXECUTION INSTRUCTIONS:
    You are in autonomous mode. This means:
    1. You can execute multiple tools in sequence to complete complex tasks
    2. After each tool execution, you'll be called again to evaluate progress
    3. You should continue until the ORIGINAL USER GOAL is fully achieved
    4. Use virtual_fs as your persistent workspace to build deliverables
    5. Only mark is_final=true when the task is COMPLETELY done

    GOAL COMPLETION CRITERIA:
    - For research tasks: Gather information AND synthesize into final deliverable
    - For planning tasks: Create detailed plans AND store them in workspace
    - For writing tasks: Research, plan, AND create the actual document
    - For business plans: Research, plan, AND write the complete business plan document
    - For analysis tasks: Gather data, analyze, AND create comprehensive report

    DECISION FRAMEWORK:
    1. What was the ORIGINAL user goal? (Look for "Original Goal:" in the context)
    2. What work has been completed so far? (Check steps completed and tool results)
    3. What is still missing to fully achieve the original goal?
    4. If the goal requires a deliverable (document, plan, report), has it been created?
    5. Is the task truly complete to professional standards?

    TOOL USAGE STRATEGY:
    - planning: Use for complex tasks requiring structured approach
    - tavily_search: Use for research and information gathering
    - virtual_fs: Use to create, store, and build final deliverables
    - system_prompt: Use to adjust behavior for specific contexts

    CRITICAL: TOOL PARAMETER REQUIREMENTS
    When using tools, you MUST provide ALL required parameters. Here are the exact formats:

    **virtual_fs tool - ALWAYS include filename parameter:**
    - Create file: {"name": "virtual_fs", "parameters": {"action": "create", "filename": "task_workspace_12345678.md", "content": "file content"}}
    - Read file: {"name": "virtual_fs", "parameters": {"action": "read", "filename": "task_workspace_12345678.md"}}
    - Update file: {"name": "virtual_fs", "parameters": {"action": "update", "filename": "task_workspace_12345678.md", "content": "updated content"}}
    - Delete file: {"name": "virtual_fs", "parameters": {"action": "delete", "filename": "task_workspace_12345678.md"}}
    - List files: {"name": "virtual_fs", "parameters": {"action": "list"}}

    **tavily_search tool:**
    - Search: {"name": "tavily_search", "parameters": {"query": "search terms here"}}

    **planning tool:**
    - Plan: {"name": "planning", "parameters": {"task": "task description", "complexity": "simple|medium|complex"}}

    PARAMETER VALIDATION RULES:
    1. virtual_fs ALWAYS requires "filename" parameter for create/read/update/delete actions
    2. If you need a filename, use the workspace filename from context or generate one like "task_workspace_[8chars].md"
    3. Never leave required parameters empty or null
    4. Double-check all parameter objects before including in tools_to_use

    VIRTUAL_FS USAGE PATTERNS:
    - **First time setup**: Create workspace file with initial structure
    - **Research phase**: Read existing workspace, then update with new findings
    - **Content building**: Update workspace multiple times to build comprehensive content
    - **Final deliverable**: Read workspace to compile final report

    ERROR HANDLING STRATEGIES:
    - If virtual_fs fails due to missing filename, the system will auto-generate one
    - If search fails, try different query terms or break into smaller searches
    - If planning fails, simplify the task description
    - Always check tool results and retry with different parameters if needed

    WORKSPACE FILENAME CONTEXT:
    Look for "Workspace File:" or "workspace_filename" in the context to get the correct filename.
    If not found, generate format: "task_workspace_[first8chars_of_task_id].md"

    IMPORTANT: Only set is_final=true when the ORIGINAL GOAL is completely achieved, not just when you've gathered information or made plans.

    You MUST respond with a JSON object containing exactly these fields:
    {
      "thinking": "Your detailed analysis of progress toward the original goal and what needs to be done next",
      "action": "The action to take: 'chat_response', 'use_tools', or 'clarify'",
      "action_input": "The input for that action (response text, tool parameters, or clarification question). Can be null when using tools.",
      "is_final": true or false (only true when original goal is COMPLETELY achieved),
      "needs_tools": true or false,
      "tools_to_use": [{"name": "tool_name", "parameters": {"key": "value"}}] or null,
      "goal_achieved": true or false (same as is_final - true only when original goal is completely done)
    }
  "#
}

function PersonalAssistantToolCall(
  user_query: string,
  tool_name: string,
  tool_parameters: string,
  tool_schema: string
) -> map<string, string> {
  client AgenticGeminiRateLimited
  prompt #"
    You are executing a tool call for a Personal Assistant.

    User Request: {{ user_query }}
    Tool to Execute: {{ tool_name }}
    Tool Schema: {{ tool_schema }}
    Suggested Parameters: {{ tool_parameters }}

    CRITICAL PARAMETER VALIDATION:
    You MUST ensure ALL required parameters are included and properly formatted.

    **For virtual_fs tool:**
    - action: REQUIRED - must be "create", "read", "update", "delete", or "list"
    - filename: REQUIRED for create/read/update/delete - use format "task_workspace_[8chars].md"
    - content: REQUIRED for create/update - the file content
    - metadata: OPTIONAL - additional file metadata

    **For tavily_search tool:**
    - query: REQUIRED - the search query string

    **For planning tool:**
    - task: REQUIRED - the task description
    - complexity: REQUIRED - must be "simple", "medium", or "complex"

    VALIDATION RULES:
    1. Never return empty or null values for required parameters
    2. If filename is missing for virtual_fs, generate one like "task_workspace_12345678.md"
    3. Validate parameter types match the schema requirements
    4. Include all parameters specified in the suggested parameters

    ERROR HANDLING:
    If any required parameter is missing from the suggested parameters:
    1. For virtual_fs filename: Generate a workspace filename
    2. For other missing required params: Use reasonable defaults based on user request
    3. Log the parameter generation in your response

    Return the parameters as a properly formatted map with all required fields.
  "#
}

function PersonalAssistantResponse(
  user_query: string,
  thinking_process: string,
  tool_results: string,
  system_prompt: string
) -> PAResponseResult {
  client AgenticGeminiRateLimited
  prompt #"
    You are a helpful Personal Assistant providing a final response to the user.

    System Context:
    {{ system_prompt }}

    User's Original Request:
    {{ user_query }}

    Your Thinking Process:
    {{ thinking_process }}

    Tool Execution Results:
    {{ tool_results }}

    Instructions:
    1. Provide a helpful, clear, and complete response to the user
    2. Incorporate the results from any tools that were used
    3. Be conversational and friendly while remaining professional
    4. If tools were used, explain what was accomplished
    5. If there were any issues, explain them clearly and suggest alternatives

    You MUST respond with a JSON object containing exactly these fields:
    {
      "response": "Your natural, helpful response to the user",
      "confidence_score": 0.95,
      "reasoning": "Brief explanation of your response approach"
    }
  "#
}

function PersonalAssistantSynthesis(
  original_goal: string,
  workspace_content: string,
  collected_research: string,
  tools_used: string
) -> PASynthesisResult {
  client AgenticGeminiRateLimited
  prompt #"
    You are a content synthesis specialist creating comprehensive reports from autonomous research execution.

    ORIGINAL GOAL: {{ original_goal }}

    WORKSPACE CONTENT (contains progress logs, research findings, and working documents):
    {{ workspace_content }}

    COLLECTED RESEARCH DATA (raw tool results and findings):
    {{ collected_research }}

    TOOLS USED DURING EXECUTION:
    {{ tools_used }}

    SYNTHESIS INSTRUCTIONS:
    1. **Analyze ALL collected research data** - Don't use placeholder text
    2. **Extract specific facts, names, numbers, and insights** from the research
    3. **Cross-reference findings** to identify patterns and key themes
    4. **Create detailed, actionable recommendations** based on actual data
    5. **Ensure comprehensive coverage** of the original goal requirements
    6. **Fill empty workspace sections** - If workspace has empty headers, populate them with actual content
    7. **Synthesize from tool execution history** - Extract data from search results even if not in workspace

    QUALITY STANDARDS:
    - NO placeholder text like "Based on research conducted" - use actual findings
    - Include specific names, companies, numbers, dates from research
    - Provide detailed analysis with supporting evidence
    - Create actionable recommendations with clear next steps
    - Ensure professional-quality comprehensive coverage

    RESPONSE FORMAT:
    {
      "executive_summary": "Comprehensive 2-3 paragraph summary with specific findings and key insights",
      "key_findings": ["Specific finding 1 with data/names", "Specific finding 2 with evidence", "..."],
      "detailed_analysis": "In-depth analysis section with specific details, cross-references, and insights from research",
      "recommendations": ["Actionable recommendation 1", "Specific recommendation 2", "..."],
      "deliverables_created": ["Actual deliverable 1", "Specific output 2", "..."],
      "next_steps": ["Concrete next step 1", "Specific action 2", "..."],
      "confidence_score": 0.95
    }
  "#
}

function PersonalAssistantPlanning(
  task_description: string,
  complexity: string,
  user_context: string?
) -> map<string, string> {
  client AgenticGeminiRateLimited
  prompt #"
    You are helping to plan and break down a task for a Personal Assistant.

    Task: {{ task_description }}
    Complexity Level: {{ complexity }}
    User Context: {{ user_context }}

    Break down this task into logical steps based on the complexity level:
    - Simple: 1-3 steps
    - Medium: 3-6 steps
    - Complex: 6+ steps

    For each step, provide:
    - A clear title
    - A brief description
    - Estimated time in minutes
    - Any dependencies on other steps

    Return a structured plan that can guide the execution of this task.
  "#
}

function PersonalAssistantWebSearch(
  user_query: string,
  search_context: string?,
  conversation_history: string?
) -> map<string, string> {
  client AgenticGeminiRateLimited
  prompt #"
    You are helping to determine the best web search strategy for a Personal Assistant.

    User Query: {{ user_query }}
    Search Context: {{ search_context }}
    Conversation History: {{ conversation_history }}

    Analyze the user's query and determine:
    1. Whether a web search would be helpful
    2. What search terms would be most effective
    3. What type of information the user is looking for
    4. How many results would be appropriate (1-20)
    5. Whether to use basic or advanced search depth

    Consider these factors:
    - Is the query asking for current/recent information?
    - Does it require factual data that might not be in your training?
    - Would real-time or up-to-date information be valuable?
    - Is the user asking about specific events, news, or developments?

    Return a structured response with:
    - search_needed: true/false
    - search_query: optimized search terms
    - max_results: recommended number of results
    - search_depth: "basic" or "advanced"
    - reasoning: why search is/isn't needed
  "#
}