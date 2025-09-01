# main.py

import asyncio
import os
from dotenv import load_dotenv
from flow import create_tao_chatbot_flow

# Load environment variables from .env.local
env_path = os.path.join(os.path.dirname(__file__), '..', '.env.local')
load_dotenv(env_path)

async def main():
    """
    Main function to run the TAO chatbot.
    """
    print("🤖 Welcome to the TAO Core Chatbot!")
    print("Type 'quit' or 'exit' to end the conversation.\n")
    
    while True:
        # Get user input
        user_query = input("You: ").strip()
        
        if user_query.lower() in ['quit', 'exit', 'q']:
            print("👋 Goodbye! Thanks for chatting!")
            break
            
        if not user_query:
            print("Please enter a message.")
            continue
        
        # Create shared data for this conversation turn
        shared = {
            "query": user_query,
            "thoughts": [],
            "observations": [],
            "current_thought_number": 0,
            "conversation_history": []
        }
        
        try:
            # Create and run flow
            tao_flow = create_tao_chatbot_flow()
            await tao_flow.run_async(shared)
            
            # Print final result
            if "final_answer" in shared:
                print(f"🤖 Bot: {shared['final_answer']}\n")
            else:
                print("🤖 Bot: I'm sorry, I couldn't generate a response.\n")
                
        except Exception as e:
            print(f"❌ Error: {str(e)}\n")

if __name__ == "__main__":
    asyncio.run(main())
