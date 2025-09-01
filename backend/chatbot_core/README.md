# TAO Core Chatbot

A simple chatbot implementation using the **Thought-Action-Observation (TAO)** pattern with PocketFlow and BAML integration. This serves as a core workflow that can be reused across other projects.

## Overview

This chatbot uses the TAO pattern to provide intelligent conversational responses:

1. **Thought**: Analyzes the user query and decides the next action
2. **Action**: Executes the decided action (chat response, search, etc.)
3. **Observation**: Evaluates the action result and provides feedback

## Architecture

- **PocketFlow**: Orchestrates the TAO workflow using AsyncFlow and AsyncNodes
- **BAML**: Handles LLM calls with rate limiting and structured prompts
- **Rate Limiting**: Built-in rate limiting for free tier usage (6 RPM, 150 RPD)

## Files

- `main.py`: Entry point for the chatbot
- `flow.py`: Defines the TAO flow structure
- `nodes.py`: Implements the Think, Action, Observe, and End nodes (uses `../utils/baml_utils.py` for BAML integration)

## BAML Functions

The chatbot uses three BAML functions defined in `../baml_src/tao.baml`:

- `AgenticChatThinking`: Analyzes user queries and decides actions
- `AgenticChatResponse`: Generates conversational responses
- `AgenticChatObservation`: Evaluates response quality

## Setup

1. Ensure BAML is properly configured with Gemini API key:
   ```bash
   export GEMINI_API_KEY="your-api-key-here"
   ```

2. Make sure PocketFlow is installed:
   ```bash
   uv add pocketflow
   ```

3. Generate BAML client (from backend directory):
   ```bash
   uv run baml-cli generate
   ```

## Usage

Run the chatbot:
```bash
cd backend/chatbot_core
uv run python main.py
```

Type your messages and the chatbot will respond using the TAO pattern. Type 'quit', 'exit', or 'q' to end the conversation.

## Rate Limiting

The chatbot includes conservative rate limiting for Gemini free tier:
- 6 requests per minute
- 150 requests per day

This can be adjusted in `../utils/baml_utils.py` if you have a paid tier.

## Example Interaction

```
🤖 Welcome to the TAO Chatbot!
Type 'quit' or 'exit' to end the conversation.

You: Hello, how are you?
🤔 Thought 1: Decided to execute chat_response
🚀 Executing action: chat_response
✅ Action completed
👁️ Observation: The response appears to be adequate...
🏁 Conversation turn completed
🤖 Bot: Hello! I'm doing well, thank you for asking. I'm here and ready to help you with any questions or tasks you might have. How are you doing today?

You: quit
👋 Goodbye! Thanks for chatting!
```
