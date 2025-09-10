#!/usr/bin/env python3
"""
Interactive chat script demonstrating both standard and autonomous Personal Assistant modes.

This script allows you to compare:
1. Standard mode: Single tool execution per interaction
2. Autonomous mode: Multi-step execution until goal completion
"""

import asyncio
import logging
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env.local
env_path = Path(__file__).parent / ".env.local"
load_dotenv(env_path)

# Add the backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.models.user import User
from app.models.agent import AgentConfig
from app.models.tool import ToolRegistry, UserToolAccess, ToolType
from app.models.oauth_token import OAuthToken
from app.agents.personal_assistant.agent import PersonalAssistant
from sqlalchemy import select

# Configure logging
logging.basicConfig(level=logging.WARNING)  # Reduce noise for interactive use


async def setup_database():
    """Set up database with sample data."""
    print("🔧 Setting up database...")

    # Create async engine for SQLite
    engine = create_async_engine(
        "sqlite+aiosqlite:///interactive_autonomous_pa.db",
        echo=False
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    # Create async session
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        # Create test user
        test_user = User(
            email="interactive_autonomous@example.com",
            full_name="Interactive Autonomous User",
            hashed_password="test_hash",
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
            # Check if tool already exists
            existing_tool = await session.execute(
                select(ToolRegistry).where(ToolRegistry.name == tool_data["name"])
            )
            existing_tool_obj = existing_tool.scalar_one_or_none()
            if existing_tool_obj:
                continue

            tool = ToolRegistry(
                name=tool_data["name"],
                display_name=tool_data["display_name"],
                description=tool_data["description"],
                tool_type=ToolType.BUILTIN,
                category=tool_data["category"],
                schema_data={},
                is_enabled=True
            )
            session.add(tool)
            await session.flush()  # Flush to get the tool.id

            # Grant access to test user
            user_access = UserToolAccess(
                user_id=test_user.id,
                tool_id=tool.id,
                is_authorized=True
            )
            session.add(user_access)

        await session.commit()

    return engine, async_session, test_user





def print_banner():
    """Print the application banner."""
    print("\n" + "="*80)
    print("🤖 AUTONOMOUS PERSONAL ASSISTANT - INTERACTIVE DEMO")
    print("="*80)
    print("Compare Standard vs Autonomous execution modes!")
    print("\nCommands:")
    print("  'standard <message>' - Use standard single-tool mode")
    print("  'auto <message>'     - Use autonomous multi-step mode")
    print("  'help'               - Show this help")
    print("  'quit'               - Exit the demo")
    print("="*80)


def print_help():
    """Print help information."""
    print("\n📚 HELP - Understanding the Modes:")
    print("-" * 50)
    print("🔧 STANDARD MODE:")
    print("   • Executes at most one tool per interaction")
    print("   • Requires multiple back-and-forth for complex tasks")
    print("   • Traditional chatbot behavior")
    print("   • Example: 'standard plan a research project'")
    print()
    print("🚀 AUTONOMOUS MODE:")
    print("   • Executes multiple tools sequentially")
    print("   • Continues until goal is fully achieved")
    print("   • Uses virtual_fs as persistent workspace")
    print("   • Maintains state across tool calls")
    print("   • Example: 'auto research TotalEnergies station challenges'")
    print()
    print("💡 TRY THESE EXAMPLES:")
    print("   standard help me plan a meeting")
    print("   auto research renewable energy trends and create a report")
    print("   auto plan and execute a market analysis for electric vehicles")
    print("-" * 50)


async def execute_standard_mode(pa_agent: PersonalAssistant, message: str):
    """Execute in standard mode."""
    print(f"\n🔧 STANDARD MODE - Processing: {message}")
    print("-" * 60)
    
    try:
        result = await pa_agent.chat(message=message)
        
        print(f"📊 Standard Execution Summary:")
        print(f"   • Tools Used: {len(result['tools_used'])}")
        print(f"   • Session ID: {result['session_id']}")
        
        if result['tools_used']:
            print(f"   • Tool Executed: {result['tools_used'][0].get('tool', 'unknown')}")
        
        print(f"\n💬 Response:")
        print(result['response'])
        
    except Exception as e:
        print(f"❌ Standard mode error: {str(e)}")


async def execute_autonomous_mode(pa_agent: PersonalAssistant, message: str):
    """Execute in autonomous mode."""
    print(f"\n🚀 AUTONOMOUS MODE - Processing: {message}")
    print("-" * 60)
    print("⏳ Executing autonomously... (this may take a moment)")
    
    try:
        result = await pa_agent.autonomous_chat(message=message)
        
        print(f"\n📊 Autonomous Execution Summary:")
        print(f"   • Tools Used: {len(result['tools_used'])}")
        print(f"   • Steps Completed: {result['metadata'].get('steps_completed', 0)}")
        print(f"   • Task ID: {result['metadata'].get('task_id', 'N/A')[:8]}...")
        print(f"   • Workspace: {result['metadata'].get('workspace_file', 'N/A')}")
        print(f"   • Duration: {result['metadata'].get('session_duration_minutes', 0):.1f}min")
        
        if result['tools_used']:
            print(f"\n🔧 Tools Executed:")
            for i, tool in enumerate(result['tools_used'], 1):
                status = "✅" if tool.get('success', False) else "❌"
                print(f"   {i}. {status} {tool.get('tool', 'unknown')}")
        
        print(f"\n💬 Final Response:")
        print(result['response'])
        
        # Offer to show workspace content
        workspace_file = result['metadata'].get('workspace_file')
        if workspace_file:
            show_workspace = input(f"\n📁 Show workspace content? (y/n): ").lower().strip()
            if show_workspace == 'y':
                await show_workspace_content(pa_agent, workspace_file)
        
    except Exception as e:
        print(f"❌ Autonomous mode error: {str(e)}")


async def show_workspace_content(pa_agent: PersonalAssistant, workspace_file: str):
    """Show workspace file content."""
    if pa_agent._tool_registry and "virtual_fs" in pa_agent._tool_registry._tool_instances:
        try:
            virtual_fs_tool = pa_agent._tool_registry._tool_instances["virtual_fs"]
            result = await virtual_fs_tool.execute({
                "action": "read",
                "filename": workspace_file
            })
            
            if result.get("success", False):
                print(f"\n📄 Workspace Content ({workspace_file}):")
                print("=" * 60)
                content = result.get("result", "No content")
                # Truncate if too long
                if len(content) > 2000:
                    content = content[:2000] + "\n... (truncated)"
                print(content)
                print("=" * 60)
            else:
                print("❌ Could not read workspace file")
                
        except Exception as e:
            print(f"❌ Error reading workspace: {str(e)}")


async def main():
    """Main interactive loop."""
    print("🔧 Initializing...")

    # Setup database
    engine, async_session, test_user = await setup_database()

    async with async_session() as session:
        pa_agent = PersonalAssistant(test_user, session)
        await pa_agent.initialize()

        print_banner()
        
        while True:
            try:
                # Get user input
                user_input = input("\n💭 Enter command: ").strip()
                
                if not user_input:
                    continue
                
                # Parse command
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("\n👋 Goodbye! Thanks for trying the Autonomous Personal Assistant!")
                    break
                
                elif user_input.lower() == 'help':
                    print_help()
                    continue
                
                elif user_input.lower().startswith('standard '):
                    message = user_input[9:].strip()
                    if message:
                        await execute_standard_mode(pa_agent, message)
                    else:
                        print("❌ Please provide a message after 'standard'")
                
                elif user_input.lower().startswith('auto '):
                    message = user_input[5:].strip()
                    if message:
                        await execute_autonomous_mode(pa_agent, message)
                    else:
                        print("❌ Please provide a message after 'auto'")
                
                else:
                    print("❌ Unknown command. Use 'help' for available commands.")
                    print("   Format: 'standard <message>' or 'auto <message>'")
                
            except KeyboardInterrupt:
                print("\n\n👋 Interrupted. Goodbye!")
                break
            except Exception as e:
                print(f"❌ Unexpected error: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())
