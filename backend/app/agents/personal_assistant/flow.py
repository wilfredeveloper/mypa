"""
Personal Assistant PocketFlow workflow definition.
"""

from pocketflow import AsyncFlow
from app.agents.personal_assistant.nodes import (
    PAThinkNode,
    PAToolCallNode,
    PAResponseNode,
    PAEndNode,
    PAAutonomousThinkNode,
    PAWorkspaceManagerNode,
    PAContentSynthesisNode
)
from app.agents.personal_assistant.intent_nodes import (
    PAIntentClassificationNode,
    PAStructuredPlanningNode,
    PAPlanExecutionNode
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
    tools - "respond" >> respond  # After tool execution, generate response

    # From respond node:
    respond - "end" >> end       # After response generation, end flow

    # Create the flow starting with think node
    flow = AsyncFlow(start=think)

    return flow


def create_autonomous_personal_assistant_flow() -> AsyncFlow:
    """
    Create Autonomous Personal Assistant workflow using PocketFlow.

    This flow enables multi-step task execution with autonomous decision making.

    Flow structure:
    1. PAWorkspaceManagerNode: Initialize workspace for multi-step tasks
    2. PAAutonomousThinkNode: Analyze request and plan autonomous execution
    3. PAToolCallNode: Execute tools as needed
    4. Loop back to thinking until goal is achieved
    5. PAContentSynthesisNode: Synthesize collected research into comprehensive reports
    6. PAResponseNode: Generate final comprehensive response
    7. PAEndNode: Complete the flow

    Returns:
        AsyncFlow: Autonomous Personal Assistant workflow
    """
    # Create node instances
    workspace = PAWorkspaceManagerNode()
    think = PAAutonomousThinkNode()
    tools = PAToolCallNode()
    synthesize = PAContentSynthesisNode()
    respond = PAResponseNode()
    end = PAEndNode()

    # Connect nodes with autonomous looping and synthesis
    # From workspace node:
    workspace - "think" >> think    # Initialize then start thinking

    # From autonomous think node:
    think - "tools" >> tools        # If tools are needed
    think - "synthesize" >> synthesize  # If research needs synthesis
    think - "respond" >> respond    # If goal is achieved, generate final response
    think - "think" >> think        # If continuing autonomous thinking (self-loop)
    think - "end" >> end           # If simple response is sufficient

    # From tools node:
    tools - "think" >> think        # After tool execution, continue thinking
    tools - "synthesize" >> synthesize  # If tools completed research, synthesize
    tools - "respond" >> respond    # If tools completed the goal

    # From synthesis node:
    synthesize - "respond" >> respond  # After synthesis, generate final response

    # From respond node:
    respond - "end" >> end         # After response generation, end flow

    # Create the flow starting with workspace manager
    flow = AsyncFlow(start=workspace)

    return flow


def create_intent_driven_personal_assistant_flow() -> AsyncFlow:
    """
    Create Intent-Driven Personal Assistant workflow using PocketFlow.

    This flow implements efficient execution through intent classification and structured planning:

    Flow structure:
    1. PAIntentClassificationNode: Classify user intent and complexity (Simple/Focused/Complex)
    2. PAStructuredPlanningNode: Create structured todo-based plan (if needed)
    3. PAPlanExecutionNode: Execute todos sequentially with progress tracking
    4. PAResponseNode: Generate final response based on execution results
    5. PAEndNode: Complete the flow

    Key improvements:
    - No overplanning: Clear completion criteria and step limits
    - Efficient execution: Match effort to task complexity
    - Structured progress: Todo-based execution with clear status tracking
    - Tool-aware planning: Only plan for available tools

    Returns:
        AsyncFlow: Intent-Driven Personal Assistant workflow
    """
    # Create node instances
    classify = PAIntentClassificationNode()
    plan = PAStructuredPlanningNode()
    execute = PAPlanExecutionNode()
    respond = PAResponseNode()
    end = PAEndNode()

    # Connect nodes with intent-driven routing
    # From classification node:
    classify - "plan" >> plan        # If planning is needed
    classify - "respond" >> respond  # If simple response is sufficient

    # From planning node:
    plan - "execute" >> execute      # After plan creation, start execution

    # From execution node:
    execute - "execute" >> execute   # Continue with next todo (self-loop)
    execute - "respond" >> respond   # When plan is complete, generate response

    # From response node:
    respond - "end" >> end          # After response generation, end flow

    return AsyncFlow(start=classify)


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