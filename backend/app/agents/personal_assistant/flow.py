"""
Personal Assistant PocketFlow workflow definition.
"""

from pocketflow import AsyncFlow
from app.agents.personal_assistant.nodes import (
    PAThinkNode,
    PAToolCallNode,
    PAResponseNode,
    PAEndNode
)


def create_personal_assistant_flow() -> AsyncFlow:
    """
    Create Personal Assistant workflow using PocketFlow.

    Flow structure:
    1. PAThinkNode: Analyze user request and decide actions
    2. PAToolCallNode: Execute tools if needed
    3. PAResponseNode: Generate final response
    4. PAEndNode: Complete the flow

    Returns:
        AsyncFlow: Complete Personal Assistant workflow
    """
    # Create node instances
    think = PAThinkNode()
    tools = PAToolCallNode()
    respond = PAResponseNode()
    end = PAEndNode()

    # Connect nodes with conditional routing
    # From think node:
    think - "tools" >> tools      # If tools are needed
    think - "respond" >> respond  # If direct response needed
    think - "end" >> end         # If final answer ready

    # From tools node:
    tools - "tools" >> tools      # For retries and continuing with plan steps
    tools - "respond" >> respond  # After tool execution, generate response

    # From respond node:
    respond - "end" >> end       # After response generation, end flow

    # Create the flow starting with think node
    flow = AsyncFlow(start=think)

    return flow


def create_streaming_personal_assistant_flow() -> AsyncFlow:
    """
    Create streaming version of Personal Assistant workflow.

    This version is optimized for real-time streaming responses
    where partial results can be sent to the client.

    Returns:
        AsyncFlow: Streaming Personal Assistant workflow
    """
    # For now, use the same flow structure
    # In the future, this could be enhanced with streaming-specific nodes
    return create_personal_assistant_flow()