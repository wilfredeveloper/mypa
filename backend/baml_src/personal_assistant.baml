// Personal Assistant BAML Functions

class PAThinkingResult {
  thinking string
  action string
  action_input string?
  is_final bool
  needs_tools bool
  tools_to_use PAToolCall[]?
  validation_notes string?
}

class PAToolCall {
  name string
  parameters map<string, string>
  confidence_score float?
}

class PAResponseResult {
  response string
  confidence_score float?
  reasoning string?
}

function PersonalAssistantThinking(
  user_query: string,
  conversation_history: string,
  available_tools: string,
  system_prompt: string
) -> PAThinkingResult {
  client AgenticGeminiRateLimited
  prompt #"
    You are a helpful Personal Assistant with access to various tools. Your role is to analyze user requests and decide on the best course of action.

    System Context:
    {{ system_prompt }}

    Available Tools:
    {{ available_tools }}

    Conversation History:
    {{ conversation_history }}

    Current User Request:
    {{ user_query }}

    Instructions:
    1. Think through the user's request carefully
    2. Determine if you need to use any tools to fulfill the request
    3. If tools are needed, specify which tools and their parameters
    4. If no tools are needed, prepare to give a direct response

    Your thinking process should be clear and logical. Consider:
    - What is the user actually asking for?
    - What information or actions are needed to fulfill this request?
    - Which tools (if any) would be most helpful?
    - Can I provide a complete answer without tools?

    IMPORTANT: When specifying tool parameters, ensure they are valid JSON objects.
    For complex parameters like event_data or time_range, provide properly structured JSON strings.

    Example tool call for Google Calendar:
    {
      "name": "google_calendar",
      "parameters": {
        "action": "create",
        "event_data": "{\"summary\": \"Meeting with John\", \"start\": \"2025-01-15T14:00:00Z\", \"end\": \"2025-01-15T15:00:00Z\"}"
      }
    }

    You MUST respond with a JSON object containing exactly these fields:
    {
      "thinking": "Your detailed thought process about the user's request",
      "action": "The action to take: 'chat_response', 'use_tools', or 'clarify'",
      "action_input": "The input for that action (response text, tool parameters, or clarification question). Can be null when using tools.",
      "is_final": true or false,
      "needs_tools": true or false,
      "tools_to_use": [{"name": "tool_name", "parameters": {"key": "value"}, "confidence_score": 0.9}] or null,
      "validation_notes": "Any notes about parameter validation or structure"
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

    Your task is to format the parameters correctly for the tool execution.
    Ensure all required parameters are included and properly formatted according to the schema.

    Return the parameters as a properly formatted map.
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