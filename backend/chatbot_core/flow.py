# flow.py

from pocketflow import AsyncFlow
from nodes import ThinkNode, ActionNode, ObserveNode, EndNode

def create_tao_chatbot_flow():
    """
    Create a Thought-Action-Observation loop flow for chatbot
    
    How the flow works:
    1. ThinkNode analyzes the user query and decides the next action
    2. ActionNode executes the decided action (chat response, search, etc.)
    3. ObserveNode evaluates the action result and provides feedback
    4. Return to ThinkNode to continue thinking, or end the flow
    
    Returns:
        AsyncFlow: Complete TAO loop flow for chatbot
    """
    # Create node instances
    think = ThinkNode()
    action = ActionNode()
    observe = ObserveNode()
    end = EndNode()
    
    # Connect nodes
    # If ThinkNode returns "action", go to ActionNode
    think - "action" >> action
    
    # If ThinkNode returns "end", end the flow
    think - "end" >> end
    
    # After ActionNode completes, go to ObserveNode
    action - "observe" >> observe
    
    # After ObserveNode completes, return to ThinkNode
    observe - "think" >> think
    
    # Create and return async flow, starting from ThinkNode
    return AsyncFlow(start=think)
