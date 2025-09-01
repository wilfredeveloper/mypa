
// =====================================
// TAO Chatbot Types
// =====================================

class ThinkingResult {
  thinking string
  action string
  action_input string
  is_final bool
}

// =====================================
// TAO Chatbot Functions
// =====================================

function AgenticChatThinking(user_query: string, conversation_history: string, observations: string) -> ThinkingResult {
  client AgenticGeminiRateLimited
  prompt #"
    You are an intelligent chatbot assistant analyzing a user query to decide the next action.

    User query: {{ user_query }}

    Conversation history:
    {{ conversation_history }}

    Previous observations:
    {{ observations }}

    Think carefully about the user's request and decide the next action.

    Available actions:
    - chat_response: Provide a direct conversational response
    - search: Search for information (if needed)
    - clarify: Ask for clarification from the user

    Respond in JSON format with exactly these fields:
    {
      "thinking": "Your detailed thought process",
      "action": "chat_response, search, or clarify",
      "action_input": "The input for that action",
      "is_final": false
    }
  "#
}

function AgenticChatResponse(user_query: string, action_input: string) -> string {
  client AgenticGeminiRateLimited
  prompt #"
    You are a helpful, conversational AI assistant. Generate a natural, engaging response.

    User query: {{ user_query }}
    Context/guidance: {{ action_input }}

    Provide a clear, helpful, and conversational response that directly addresses the user's needs.
    Be friendly, informative, and concise while maintaining a natural tone.
  "#
}

function AgenticChatObservation(user_query: string, action: string, action_result: string) -> string {
  client AgenticGeminiRateLimited
  prompt #"
    You are an objective observer evaluating the quality of an AI assistant's response.

    Original user query: {{ user_query }}
    Action taken: {{ action }}
    Action result: {{ action_result }}

    Provide a brief, objective assessment of whether the response adequately addresses the user's query.
    Focus on completeness, accuracy, and helpfulness.
  "#
}