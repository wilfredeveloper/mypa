#!/usr/bin/env python3
"""
Interactive Intent-Driven Personal Assistant Chat
Compare the new intent-driven approach with the old autonomous mode.
"""

import asyncio
import logging
import sys
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env.local
env_path = Path(__file__).parent / ".env.local"
load_dotenv(env_path)

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.user import User
from app.models.tool import ToolRegistry, ToolType
from app.models.oauth_token import OAuthToken  # Import to resolve relationship
from app.models.agent import AgentConfig  # Import to resolve any other relationships
from app.agents.personal_assistant.agent import PersonalAssistant

# Configure logging
logging.basicConfig(
    level=logging.WARNING,  # Reduce noise for interactive use
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test database URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_intent_interactive.db"


async def setup_test_environment():
    """Set up test environment with database and user."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    # Create async session
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with AsyncSessionLocal() as session:
        # Create test user
        test_user = User(
            email="test@intentdriven.com",
            full_name="Intent Test User",
            hashed_password="test_hash",  # Required field for test
            is_active=True
        )
        session.add(test_user)
        await session.commit()
        await session.refresh(test_user)

        # Create builtin tools
        builtin_tools = [
            {
                "name": "system_prompt",
                "display_name": "System Prompt Manager",
                "description": "Manage conversation personality and system prompts",
                "category": "configuration"
            },
            {
                "name": "planning",
                "display_name": "Task Planner", 
                "description": "Break down complex tasks into actionable steps",
                "category": "productivity"
            },
            {
                "name": "virtual_fs",
                "display_name": "Virtual File System",
                "description": "Create, read, update, delete virtual files for workspace management",
                "category": "storage"
            },
            {
                "name": "tavily_search",
                "display_name": "Web Search",
                "description": "Search the web for current information and research",
                "category": "research"
            }
        ]

        for tool_data in builtin_tools:
            tool = ToolRegistry(
                name=tool_data["name"],
                display_name=tool_data["display_name"],
                description=tool_data["description"],
                tool_type=ToolType.BUILTIN,
                category=tool_data["category"],
                schema_data={
                    "type": "object",
                    "properties": {
                        "action": {"type": "string"},
                        "parameters": {"type": "object"}
                    }
                },
                rate_limit_per_minute=30,
                rate_limit_per_day=500,
                is_enabled=True
            )
            session.add(tool)

        await session.commit()
        
        return AsyncSessionLocal, test_user


def print_welcome():
    """Print welcome message and instructions."""
    print("\n" + "="*70)
    print("🎯 INTENT-DRIVEN PERSONAL ASSISTANT INTERACTIVE DEMO")
    print("="*70)
    print("Compare the new intent-driven approach with autonomous mode!")
    print()
    print("AVAILABLE MODES:")
    print("  intent <message>    - Use new intent-driven execution")
    print("  auto <message>      - Use old autonomous execution (for comparison)")
    print("  standard <message>  - Use standard single-step execution")
    print()
    print("EXAMPLE COMMANDS:")
    print("  intent Hello there!")
    print("  intent What is machine learning?")
    print("  intent Research renewable energy trends and create a report")
    print("  auto Research renewable energy trends and create a report")
    print()
    print("OTHER COMMANDS:")
    print("  files              - Show workspace files and content")
    print("  help               - Show this help message")
    print("  quit/exit/q        - Exit the demo")
    print("-" * 70)


def print_help():
    """Print help message."""
    print("\n📚 HELP - Intent-Driven Personal Assistant Demo")
    print("-" * 50)
    print("MODES COMPARISON:")
    print()
    print("🎯 INTENT-DRIVEN (NEW):")
    print("   • Classifies user intent (Simple/Focused/Complex)")
    print("   • Creates structured todo-based plans")
    print("   • Executes efficiently with clear completion criteria")
    print("   • Prevents overplanning and overthinking")
    print("   • Example: intent research AI trends and create a summary")
    print()
    print("🤖 AUTONOMOUS (OLD):")
    print("   • Multi-step execution with workspace management")
    print("   • May overplan and overthink simple tasks")
    print("   • Uses quality checks that can be too strict")
    print("   • Example: auto research AI trends and create a summary")
    print()
    print("⚡ STANDARD:")
    print("   • Single-step execution, one tool maximum")
    print("   • Quick responses for simple requests")
    print("   • Example: standard what is Python?")
    print()
    print("SAMPLE COMPARISONS:")
    print("   intent Hello! (should be quick and simple)")
    print("   auto Hello! (may overthink a simple greeting)")
    print()
    print("   intent Plan a weekend trip (focused, structured)")
    print("   auto Plan a weekend trip (may overplan)")
    print()
    print("WORKSPACE COMMANDS:")
    print("   files              - Show all workspace files and view content")
    print("   workspace          - Same as 'files'")
    print("   show files         - Same as 'files'")
    print("-" * 50)


async def execute_intent_driven_mode(pa_agent: PersonalAssistant, message: str):
    """Execute in intent-driven mode."""
    print(f"\n🎯 INTENT-DRIVEN MODE - Processing: {message}")
    print("-" * 60)
    
    start_time = datetime.now()
    
    try:
        result = await pa_agent.intent_driven_chat(message=message)
        
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds() * 1000
        
        print(f"📊 Intent-Driven Execution Summary:")
        print(f"   • Complexity: {result['metadata'].get('complexity_level', 'unknown')}")
        print(f"   • Category: {result['metadata'].get('task_category', 'unknown')}")
        print(f"   • Estimated Steps: {result['metadata'].get('estimated_steps', 0)}")
        print(f"   • Actual Todos Completed: {result['metadata'].get('actual_todos_completed', 0)}")
        print(f"   • Tools Used: {result['metadata'].get('tools_used_count', 0)}")
        print(f"   • Execution Time: {execution_time:.0f}ms")
        print(f"   • Session ID: {result['session_id']}")
        
        workspace_file = result['metadata'].get('workspace_file')
        if workspace_file:
            print(f"   • Workspace File: {workspace_file}")
        
        plan_summary = result['metadata'].get('plan_summary')
        if plan_summary:
            print(f"   • Plan: {plan_summary}")
        
        print(f"\n💬 Response:")
        print(result['response'])
        
    except Exception as e:
        print(f"❌ Intent-driven mode error: {str(e)}")


async def execute_autonomous_mode(pa_agent: PersonalAssistant, message: str):
    """Execute in autonomous mode for comparison."""
    print(f"\n🤖 AUTONOMOUS MODE - Processing: {message}")
    print("-" * 60)
    
    start_time = datetime.now()
    
    try:
        result = await pa_agent.autonomous_chat(message=message)
        
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds() * 1000
        
        print(f"📊 Autonomous Execution Summary:")
        print(f"   • Steps Completed: {result['metadata'].get('steps_completed', 0)}")
        print(f"   • Tools Used: {len(result['tools_used'])}")
        print(f"   • Execution Time: {execution_time:.0f}ms")
        print(f"   • Session ID: {result['session_id']}")
        
        workspace_file = result['metadata'].get('workspace_file')
        if workspace_file:
            print(f"   • Workspace File: {workspace_file}")
        
        print(f"\n💬 Response:")
        print(result['response'])
        
    except Exception as e:
        print(f"❌ Autonomous mode error: {str(e)}")


async def execute_standard_mode(pa_agent: PersonalAssistant, message: str):
    """Execute in standard mode for comparison."""
    print(f"\n⚡ STANDARD MODE - Processing: {message}")
    print("-" * 60)

    start_time = datetime.now()

    try:
        result = await pa_agent.chat(message=message)

        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds() * 1000

        print(f"📊 Standard Execution Summary:")
        print(f"   • Tools Used: {len(result['tools_used'])}")
        print(f"   • Execution Time: {execution_time:.0f}ms")
        print(f"   • Session ID: {result['session_id']}")

        if result['tools_used']:
            print(f"   • Tool Executed: {result['tools_used'][0].get('tool', 'unknown')}")

        print(f"\n💬 Response:")
        print(result['response'])

    except Exception as e:
        print(f"❌ Standard mode error: {str(e)}")


async def show_workspace_files(pa_agent: PersonalAssistant):
    """Show all files in the virtual workspace."""
    print(f"\n📁 WORKSPACE FILES")
    print("-" * 60)

    try:
        # Get the virtual_fs tool from the agent's tool registry
        if not pa_agent._tool_registry or "virtual_fs" not in pa_agent._tool_registry._tool_instances:
            print("❌ Virtual file system not available")
            return

        virtual_fs_tool = pa_agent._tool_registry._tool_instances["virtual_fs"]

        # List all files
        result = await virtual_fs_tool.execute({"action": "list"})

        if not result.get("success", False):
            print("❌ Failed to list files")
            return

        files = result.get("result", {}).get("files", [])

        if not files:
            print("📂 No files in workspace yet")
            print("💡 Run some intent-driven commands to generate workspace files!")
            return

        print(f"📊 Found {len(files)} file(s) in workspace:")
        print()

        for i, file_info in enumerate(files, 1):
            filename = file_info.get("filename", "unknown")
            size = file_info.get("size_bytes", 0)
            created = file_info.get("created_at", "unknown")
            updated = file_info.get("updated_at", "unknown")

            print(f"{i}. 📄 {filename}")
            print(f"   Size: {size} bytes")
            print(f"   Created: {created}")
            print(f"   Updated: {updated}")
            print()

        # Ask user if they want to view a specific file
        try:
            choice = input("💭 Enter file number to view content (or press Enter to skip): ").strip()

            if choice and choice.isdigit():
                file_index = int(choice) - 1
                if 0 <= file_index < len(files):
                    filename = files[file_index]["filename"]
                    await show_file_content(virtual_fs_tool, filename)
                else:
                    print("❌ Invalid file number")
        except KeyboardInterrupt:
            print("\n⏭️ Skipped file viewing")

    except Exception as e:
        print(f"❌ Error accessing workspace: {str(e)}")


async def show_file_content(virtual_fs_tool, filename: str):
    """Show the content of a specific file."""
    print(f"\n📄 FILE CONTENT: {filename}")
    print("=" * 70)

    try:
        result = await virtual_fs_tool.execute({
            "action": "read",
            "filename": filename
        })

        if result.get("success", False):
            content = result.get("result", {}).get("content", "")
            if content:
                print(content)
            else:
                print("📝 File is empty")
        else:
            print(f"❌ Failed to read file: {result.get('error', 'Unknown error')}")

    except Exception as e:
        print(f"❌ Error reading file: {str(e)}")

    print("=" * 70)


async def main():
    """Main interactive loop."""
    print("🚀 Setting up Intent-Driven Personal Assistant Demo...")
    
    try:
        # Setup test environment
        AsyncSessionLocal, test_user = await setup_test_environment()
        
        print("✅ Test environment ready!")
        print_welcome()
        
        async with AsyncSessionLocal() as session:
            # Initialize Personal Assistant
            pa_agent = PersonalAssistant(test_user, session)
            await pa_agent.initialize()
            
            print("✅ Personal Assistant initialized and ready!")
            
            while True:
                try:
                    # Get user input
                    user_input = input("\n💭 Enter command: ").strip()
                    
                    if not user_input:
                        continue
                    
                    # Parse command
                    if user_input.lower() in ['quit', 'exit', 'q']:
                        print("\n👋 Goodbye! Thanks for trying the Intent-Driven Personal Assistant!")
                        break
                    
                    elif user_input.lower() == 'help':
                        print_help()
                        continue
                    
                    elif user_input.lower().startswith('intent '):
                        message = user_input[7:].strip()
                        if message:
                            await execute_intent_driven_mode(pa_agent, message)
                        else:
                            print("❌ Please provide a message after 'intent'")
                    
                    elif user_input.lower().startswith('auto '):
                        message = user_input[5:].strip()
                        if message:
                            await execute_autonomous_mode(pa_agent, message)
                        else:
                            print("❌ Please provide a message after 'auto'")
                    
                    elif user_input.lower().startswith('standard '):
                        message = user_input[9:].strip()
                        if message:
                            await execute_standard_mode(pa_agent, message)
                        else:
                            print("❌ Please provide a message after 'standard'")

                    elif user_input.lower() in ['files', 'workspace', 'show files']:
                        await show_workspace_files(pa_agent)

                    else:
                        print("❌ Unknown command. Type 'help' for available commands.")
                
                except KeyboardInterrupt:
                    print("\n\n👋 Goodbye! Thanks for trying the Intent-Driven Personal Assistant!")
                    break
                except Exception as e:
                    print(f"❌ Unexpected error: {str(e)}")
                    logger.error(f"Unexpected error in main loop: {str(e)}", exc_info=True)
    
    except Exception as e:
        print(f"❌ Failed to setup demo environment: {str(e)}")
        logger.error(f"Setup failed: {str(e)}", exc_info=True)
        return False
    
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
