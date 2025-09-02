#!/usr/bin/env python3
"""
Test script for Personal Assistant built-in tools.
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
from app.models.oauth_token import OAuthToken  # Import OAuthToken to resolve relationship
from app.agents.personal_assistant.agent import PersonalAssistant


async def setup_test_database():
    """Set up test database with sample data."""
    print("🔧 Setting up test database...")

    # Create async engine for SQLite
    engine = create_async_engine(
        "sqlite+aiosqlite:///test_pa.db",
        echo=False  # Set to False to reduce noise
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
            email="test@example.com",
            full_name="Test User",
            hashed_password="test_hash",
            is_active=True
        )
        session.add(test_user)
        await session.commit()
        await session.refresh(test_user)

        # Create tool registry entries
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
            )
        ]

        for tool in tools:
            session.add(tool)

        await session.commit()

        # Create user tool access for builtin tools
        for tool in tools:
            user_access = UserToolAccess(
                user_id=test_user.id,
                tool_id=tool.id,
                is_authorized=True
            )
            session.add(user_access)

        await session.commit()

        print(f"✅ Test database setup complete with user ID: {test_user.id}")
        return engine, async_session, test_user


async def test_direct_tool_execution(pa_agent):
    """Test direct tool execution without full chat flow."""
    print("\n🔧 Testing Direct Tool Execution...")

    # Test system prompt tool directly
    print("  🧠 Testing SystemPromptTool directly...")
    try:
        tool_registry = pa_agent._tool_registry
        if tool_registry and "system_prompt" in tool_registry._tool_instances:
            system_prompt_tool = tool_registry._tool_instances["system_prompt"]
            result = await system_prompt_tool.execute({"action": "get"})
            print(f"    ✅ SystemPromptTool result: {result.get('success', False)}")
        else:
            print("    ❌ SystemPromptTool not found in registry")
    except Exception as e:
        print(f"    ❌ SystemPromptTool error: {str(e)}")

    # Test planning tool directly
    print("  📋 Testing PlanningTool directly...")
    try:
        if tool_registry and "planning" in tool_registry._tool_instances:
            planning_tool = tool_registry._tool_instances["planning"]
            result = await planning_tool.execute({
                "action": "create",
                "task": "Test task",
                "complexity": "simple"
            })
            print(f"    ✅ PlanningTool result: {result.get('success', False)}")
        else:
            print("    ❌ PlanningTool not found in registry")
    except Exception as e:
        print(f"    ❌ PlanningTool error: {str(e)}")

    # Test virtual fs tool directly
    print("  💾 Testing VirtualFileSystemTool directly...")
    try:
        if tool_registry and "virtual_fs" in tool_registry._tool_instances:
            vfs_tool = tool_registry._tool_instances["virtual_fs"]
            result = await vfs_tool.execute({
                "action": "create",
                "filename": "test.txt",
                "content": "Hello World"
            })
            print(f"    ✅ VirtualFileSystemTool result: {result.get('success', False)}")
        else:
            print("    ❌ VirtualFileSystemTool not found in registry")
    except Exception as e:
        print(f"    ❌ VirtualFileSystemTool error: {str(e)}")


async def test_tool_usage_scenarios(pa_agent):
    """Test scenarios that should trigger tool usage."""
    print("\n🛠️ Testing Tool Usage Scenarios...")

    # Test 1: Request that should use the planning tool
    print("  📋 Test 1: Task planning request...")
    result = await pa_agent.chat("Help me create a plan to organize my home office. Break it down into steps.")
    print(f"    Response: {result.get('response', 'No response')[:150]}...")
    print(f"    Tools used: {result.get('tools_used', [])}")
    print(f"    Session ID: {result.get('session_id')}")

    # Test 2: Request that should use the virtual file system
    print("\n  💾 Test 2: File creation request...")
    result = await pa_agent.chat("Create a file called 'meeting_notes.txt' with the content 'Today we discussed project timeline and budget allocation.'")
    print(f"    Response: {result.get('response', 'No response')[:150]}...")
    print(f"    Tools used: {result.get('tools_used', [])}")

    # Test 3: Request that should use system prompt management
    print("\n  🧠 Test 3: System prompt management...")
    result = await pa_agent.chat("Switch to a more casual and friendly tone for our conversation.")
    print(f"    Response: {result.get('response', 'No response')[:150]}...")
    print(f"    Tools used: {result.get('tools_used', [])}")

    # Test 4: Complex request that might use multiple tools
    print("\n  🎯 Test 4: Complex multi-tool request...")
    result = await pa_agent.chat("I need to plan a project for redesigning my workspace. Create a plan, save some initial notes about it, and switch to a task-focused mode.")
    print(f"    Response: {result.get('response', 'No response')[:150]}...")
    print(f"    Tools used: {result.get('tools_used', [])}")

    # Test 5: Follow-up request to check what was created
    print("\n  🔍 Test 5: Follow-up to check created files...")
    result = await pa_agent.chat("Show me what files I have created so far.")
    print(f"    Response: {result.get('response', 'No response')[:150]}...")
    print(f"    Tools used: {result.get('tools_used', [])}")

    print("\n  ✅ Tool usage scenario tests completed")


async def main():
    """Main test function."""
    print("🚀 Starting Personal Assistant Built-in Tools Test")
    print("=" * 60)

    try:
        # Setup test database
        engine, async_session, test_user = await setup_test_database()

        # Create Personal Assistant instance
        print("\n🤖 Initializing Personal Assistant...")
        async with async_session() as session:
            pa_agent = PersonalAssistant(test_user, session)
            await pa_agent.initialize()
            print("✅ Personal Assistant initialized successfully")

            # Test tool registry
            print(f"📊 Tool registry has {len(pa_agent._tool_registry._tool_instances)} tools loaded")
            for tool_name in pa_agent._tool_registry._tool_instances.keys():
                print(f"  - {tool_name}")

            # Run direct tool tests first
            await test_direct_tool_execution(pa_agent)

            # Test basic chat functionality
            print("\n💬 Testing basic chat...")
            result = await pa_agent.chat("Hello, can you help me?")
            print(f"Chat result: {result}")

            # Test tool usage scenarios
            await test_tool_usage_scenarios(pa_agent)

        print("\n🎉 All tests completed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        # Cleanup
        if 'engine' in locals():
            await engine.dispose()

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())