#!/usr/bin/env python3
"""
Interactive chat interface for Personal Assistant.
"""

import asyncio
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


async def setup_database():
    """Set up database with sample data."""
    print("🔧 Setting up database...")

    # Create async engine for SQLite
    engine = create_async_engine(
        "sqlite+aiosqlite:///interactive_pa.db",
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
            email="chat@example.com",
            full_name="Chat User",
            hashed_password="test_hash",
            is_active=True
        )
        session.add(test_user)
        await session.commit()
        await session.refresh(test_user)

        # Create all built-in tools
        tools = [
            ToolRegistry(
                name="system_prompt",
                display_name="System Prompt Manager",
                description="Manage and switch between different system prompts",
                tool_type=ToolType.BUILTIN,
                category="configuration",
                schema_data={
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["get", "set", "list", "switch"]},
                        "prompt_name": {"type": "string"},
                        "prompt_content": {"type": "string"}
                    },
                    "required": ["action"]
                },
                rate_limit_per_minute=60,
                rate_limit_per_day=1000,
                is_enabled=True
            ),
            ToolRegistry(
                name="planning",
                display_name="Task Planning",
                description="Break down complex requests into actionable steps",
                tool_type=ToolType.BUILTIN,
                category="productivity",
                schema_data={
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["create", "update", "get", "list"]},
                        "task": {"type": "string"},
                        "complexity": {"type": "string", "enum": ["simple", "medium", "complex"]}
                    }
                },
                rate_limit_per_minute=30,
                rate_limit_per_day=500,
                is_enabled=True
            ),
            ToolRegistry(
                name="virtual_fs",
                display_name="Virtual File System",
                description="Create and manage temporary files during task execution",
                tool_type=ToolType.BUILTIN,
                category="utility",
                schema_data={
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["create", "read", "update", "delete", "list", "search"]},
                        "filename": {"type": "string"},
                        "content": {"type": "string"},
                        "search_term": {"type": "string"}
                    }
                },
                rate_limit_per_minute=120,
                rate_limit_per_day=2000,
                is_enabled=True
            ),
            ToolRegistry(
                name="tavily_search",
                display_name="Tavily Web Search",
                description="Perform web searches using the Tavily Search API with structured results",
                tool_type=ToolType.BUILTIN,
                category="research",
                schema_data={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query (required)"
                        },
                        "max_results": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 20,
                            "default": 5,
                            "description": "Maximum number of results to return"
                        },
                        "search_depth": {
                            "type": "string",
                            "enum": ["basic", "advanced"],
                            "default": "basic",
                            "description": "Search depth level"
                        },
                        "include_domains": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of domains to include in search"
                        },
                        "exclude_domains": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of domains to exclude from search"
                        }
                    },
                    "required": ["query"]
                },
                rate_limit_per_minute=30,
                rate_limit_per_day=500,
                is_enabled=True
            )
        ]

        for tool in tools:
            session.add(tool)

        await session.commit()

        # Create user tool access for all tools
        for tool in tools:
            user_access = UserToolAccess(
                user_id=test_user.id,
                tool_id=tool.id,
                is_authorized=True
            )
            session.add(user_access)

        await session.commit()

        print(f"✅ Database setup complete with user ID: {test_user.id}")
        return engine, async_session, test_user


def print_banner():
    """Print welcome banner."""
    print("\n" + "="*60)
    print("🤖 PERSONAL ASSISTANT - Interactive Chat")
    print("="*60)
    print("💬 Start chatting! Try these examples:")
    print("   • Create a file called 'notes.txt' with some content")
    print("   • Help me plan a project to organize my workspace")
    print("   • Switch to a more casual tone")
    print("   • List all my files")
    print("   • Search for files containing 'project'")
    print("   • Search the web for 'latest Python features'")
    print("   • Find recent news about artificial intelligence")
    print("\n📝 Type 'quit', 'exit', or 'bye' to end the chat")
    print("🔧 Type 'tools' to see available tools")
    print("📊 Type 'stats' to see session statistics")
    print("="*60)


def print_tools_info():
    """Print available tools information."""
    print("\n🔧 Available Tools:")
    print("  📝 system_prompt - Manage conversation personality and context")
    print("  📋 planning - Break down complex tasks into actionable steps")
    print("  💾 virtual_fs - Create, read, update, delete virtual files")
    print("  🔍 tavily_search - Search the web for current information and research")
    print()


async def interactive_chat():
    """Main interactive chat loop."""
    try:
        # Setup database
        engine, async_session, test_user = await setup_database()

        # Print banner
        print_banner()

        # Create Personal Assistant instance
        async with async_session() as session:
            pa_agent = PersonalAssistant(test_user, session)
            await pa_agent.initialize()

            print("🤖 Personal Assistant is ready! How can I help you?\n")

            # Chat loop
            while True:
                try:
                    # Get user input
                    user_input = input("You: ").strip()

                    # Handle special commands
                    if user_input.lower() in ['quit', 'exit', 'bye']:
                        print("\n👋 Goodbye! Thanks for chatting!")
                        break
                    elif user_input.lower() == 'tools':
                        print_tools_info()
                        continue
                    elif user_input.lower() == 'stats':
                        # Show session stats (you could implement this)
                        print("\n📊 Session Statistics:")
                        print("  • Tools available: 3 (system_prompt, planning, virtual_fs)")
                        print("  • Session active: ✅")
                        print()
                        continue
                    elif not user_input:
                        continue

                    # Process with Personal Assistant
                    print("🤖 Assistant: ", end="", flush=True)

                    result = await pa_agent.chat(user_input)

                    # Display response
                    response = result.get('response', 'I apologize, but I encountered an error.')
                    print(response)

                    # Show tools used if any
                    tools_used = result.get('tools_used', [])
                    if tools_used:
                        print(f"\n🔧 Tools used: {', '.join([tool['tool'] for tool in tools_used])}")

                    print()  # Add spacing

                except KeyboardInterrupt:
                    print("\n\n👋 Chat interrupted. Goodbye!")
                    break
                except Exception as e:
                    print(f"\n❌ Error: {str(e)}")
                    print("Please try again.\n")

    except Exception as e:
        print(f"\n❌ Failed to start chat: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        # Cleanup
        if 'engine' in locals():
            await engine.dispose()

    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(interactive_chat())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)