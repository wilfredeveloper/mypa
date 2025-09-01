# nodes.py

from pocketflow import AsyncNode
import sys
import os

# Add the backend directory to the path so we can import baml_utils
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.baml_utils import RateLimitedBAMLGeminiLLM, BAMLCollectorManager

# Global rate-limited BAML client instance
_baml_client = None

def get_baml_client():
    """Get or create a rate-limited BAML client instance."""
    global _baml_client

    if _baml_client is None:
        # Create collector manager for tracking usage
        collector_manager = BAMLCollectorManager()

        # Create rate-limited client with conservative limits for free tier
        _baml_client = RateLimitedBAMLGeminiLLM(
            collector_manager=collector_manager,
            enable_streaming=False,
            rate_limit_rpm=6,  # Very conservative: 6 requests per minute
            rate_limit_rpd=150  # Conservative: 150 requests per day
        )

    return _baml_client

async def call_baml_llm(function_name: str, **kwargs):
    """Call a BAML function with rate limiting and error handling."""
    try:
        client = get_baml_client()
        result = await client.call_function(function_name, **kwargs)
        return result
    except Exception as e:
        print(f"❌ BAML call failed for {function_name}: {str(e)}")
        # Provide fallback responses based on function type
        if "thinking" in function_name.lower():
            # Create a mock ThinkingResult object
            class MockThinkingResult:
                def __init__(self):
                    self.thinking = "I need to think about this request and provide a helpful response."
                    self.action = "chat_response"
                    self.action_input = "I apologize, but I'm having trouble processing your request right now. Please try again."
                    self.is_final = True
            return MockThinkingResult()
        elif "response" in function_name.lower():
            return "I apologize, but I'm having trouble generating a response right now. Please try again."
        elif "observation" in function_name.lower():
            return "The response appears to be adequate for the user's query."
        else:
            return "I'm experiencing technical difficulties. Please try again."

class ThinkNode(AsyncNode):
    """Node that analyzes the user query and decides the next action"""
    
    async def prep_async(self, shared):
        """Prepare the context needed for thinking"""
        query = shared.get("query", "")
        observations = shared.get("observations", [])
        thoughts = shared.get("thoughts", [])
        current_thought_number = shared.get("current_thought_number", 0)
        conversation_history = shared.get("conversation_history", [])
        
        # Update thought count
        shared["current_thought_number"] = current_thought_number + 1
        
        # Format previous observations
        observations_text = "\n".join([f"Observation {i+1}: {obs}" for i, obs in enumerate(observations)])
        if not observations_text:
            observations_text = "No observations yet."
            
        # Format conversation history
        history_text = "\n".join([f"{entry['role']}: {entry['content']}" for entry in conversation_history[-5:]])  # Last 5 exchanges
        if not history_text:
            history_text = "No previous conversation."
            
        return {
            "query": query,
            "observations_text": observations_text,
            "thoughts": thoughts,
            "current_thought_number": current_thought_number + 1,
            "conversation_history": history_text
        }
    
    async def exec_async(self, prep_res):
        """Execute the thinking process, decide the next action"""
        query = prep_res["query"]
        observations_text = prep_res["observations_text"]
        current_thought_number = prep_res["current_thought_number"]
        conversation_history = prep_res["conversation_history"]

        # Call BAML function with structured output
        try:
            thinking_result = await call_baml_llm(
                "AgenticChatThinking",
                user_query=query,
                conversation_history=conversation_history,
                observations=observations_text
            )

            # Convert BAML result to dict format
            thought_data = {
                "thinking": thinking_result.thinking,
                "action": thinking_result.action,
                "action_input": thinking_result.action_input,
                "is_final": thinking_result.is_final,
                "thought_number": current_thought_number
            }

        except Exception as e:
            print(f"❌ Error in thinking: {e}")
            # Fallback response
            thought_data = {
                "thinking": "Providing a direct response to the user's query",
                "action": "chat_response",
                "action_input": f"I'll help you with: {query}",
                "is_final": True,
                "thought_number": current_thought_number
            }

        return thought_data
    
    async def post_async(self, shared, prep_res, exec_res):
        """Save the thinking result and decide the next step in the flow"""
        # Save thinking result
        if "thoughts" not in shared:
            shared["thoughts"] = []
        shared["thoughts"].append(exec_res)
        
        # Save action information
        shared["current_action"] = exec_res["action"]
        shared["current_action_input"] = exec_res["action_input"]
        
        # If it's the final answer, end the flow
        if exec_res.get("is_final", False):
            shared["final_answer"] = exec_res["action_input"]
            print(f"🎯 Final Answer: {exec_res['action_input']}")
            return "end"
        
        # Otherwise continue with the action
        print(f"🤔 Thought {exec_res['thought_number']}: Decided to execute {exec_res['action']}")
        return "action"

class ActionNode(AsyncNode):
    """Node that executes the decided action"""
    
    async def prep_async(self, shared):
        """Prepare to execute action"""
        action = shared["current_action"]
        action_input = shared["current_action_input"]
        query = shared.get("query", "")
        return action, action_input, query
    
    async def exec_async(self, inputs):
        """Execute action and return result"""
        action, action_input, query = inputs
        
        print(f"🚀 Executing action: {action}")
        
        # Execute different operations based on action type
        if action == "chat_response":
            # Generate a conversational response
            result = await self.generate_chat_response(action_input, query)
        elif action == "search":
            # Simulate search operation (could integrate with real search)
            result = await self.search_information(action_input)
        elif action == "clarify":
            # Ask for clarification
            result = action_input
        else:
            # Unknown action type
            result = f"I'm not sure how to handle that request: {action}"
        
        return result
    
    async def post_async(self, shared, prep_res, exec_res):
        """Save action result"""
        # Save the current action result
        shared["current_action_result"] = exec_res
        print(f"✅ Action completed")
        
        # Continue to observation node
        return "observe"
    
    # Action implementation methods
    async def generate_chat_response(self, action_input, original_query):
        """Generate a conversational response using BAML"""
        response = await call_baml_llm(
            "AgenticChatResponse",
            user_query=original_query,
            action_input=action_input
        )
        return response
    
    async def search_information(self, query):
        """Simulate search operation (placeholder for real search integration)"""
        # This could be integrated with actual search APIs
        return f"Search results for '{query}': [This is a simulated search result. In a real implementation, this would query actual search engines or knowledge bases.]"

class ObserveNode(AsyncNode):
    """Node that observes and evaluates action results"""
    
    async def prep_async(self, shared):
        """Prepare observation data"""
        action = shared["current_action"]
        action_input = shared["current_action_input"]
        action_result = shared["current_action_result"]
        query = shared.get("query", "")
        return action, action_input, action_result, query
    
    async def exec_async(self, inputs):
        """Analyze action results, generate observation"""
        action, action_input, action_result, query = inputs

        # Call BAML function for observation
        observation = await call_baml_llm(
            "AgenticChatObservation",
            user_query=query,
            action=action,
            action_result=action_result
        )

        print(f"👁️ Observation: {observation[:100]}...")
        return observation
    
    async def post_async(self, shared, prep_res, exec_res):
        """Save observation result and decide next flow step"""
        # Save observation result
        if "observations" not in shared:
            shared["observations"] = []
        shared["observations"].append(exec_res)
        
        # For chatbot, we typically want to end after one cycle
        # But we could continue thinking if the response was inadequate
        action_result = shared.get("current_action_result", "")
        
        # Simple heuristic: if the response seems complete, end the flow
        if len(action_result) > 20 and "I'm not sure" not in action_result:
            shared["final_answer"] = action_result
            return "end"
        else:
            # Continue thinking for a better response
            return "think"

class EndNode(AsyncNode):
    """Node that handles flow termination"""
    
    async def prep_async(self, shared):
        """Prepare end node"""
        return {}
    
    async def exec_async(self, prep_res):
        """Execute end operation"""
        print("🏁 Conversation turn completed")
        return None
    
    async def post_async(self, shared, prep_res, exec_res):
        """End flow"""
        return None
