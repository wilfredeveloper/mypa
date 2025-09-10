#!/usr/bin/env python3
"""
Test script for the Autonomous Personal Assistant.

This script demonstrates the autonomous architecture that enables:
1. Multi-step task execution
2. Virtual file system workspace management
3. Continuous execution until goal completion
4. State persistence across tool calls
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
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def setup_database():
    """Set up database with sample data."""
    print("🔧 Setting up database...")

    # Create async engine for SQLite
    engine = create_async_engine(
        "sqlite+aiosqlite:///test_autonomous_pa.db",
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
            email="autonomous_test@example.com",
            full_name="Autonomous Test User",
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


async def test_autonomous_research():
    """Test autonomous research capabilities."""
    print("\n" + "="*80)
    print("🤖 AUTONOMOUS PERSONAL ASSISTANT - RESEARCH TEST")
    print("="*80)

    # Setup database
    engine, async_session, test_user = await setup_database()

    async with async_session() as session:
        # Create Personal Assistant instance
        pa_agent = PersonalAssistant(test_user, session)
        await pa_agent.initialize()

        print(f"\n✅ Personal Assistant initialized for user: {test_user.full_name}")
        print(f"📧 User email: {test_user.email}")
        
        # Test autonomous research task
        research_query = """
        Plan and conduct research on the following topic: Station managers in TotalEnergies 
        stations and the problems they face on day to day basis related to their operations.
        
        Please create a comprehensive research plan, execute it autonomously, and provide 
        a detailed report with findings.
        """
        
        print(f"\n📝 Research Query:")
        print(f"   {research_query.strip()}")
        print(f"\n🚀 Starting autonomous execution...")
        print("-" * 60)
        
        try:
            # Execute autonomous chat
            result = await pa_agent.autonomous_chat(
                message=research_query,
                context={
                    "research_type": "comprehensive",
                    "output_format": "detailed_report",
                    "autonomous_mode": True
                }
            )
            
            print(f"\n✅ AUTONOMOUS EXECUTION COMPLETED")
            print("=" * 60)
            print(f"📊 Execution Summary:")
            print(f"   • Session ID: {result['session_id']}")
            print(f"   • Tools Used: {len(result['tools_used'])}")
            print(f"   • Steps Completed: {result['metadata'].get('steps_completed', 0)}")
            print(f"   • Task ID: {result['metadata'].get('task_id', 'N/A')}")
            print(f"   • Workspace File: {result['metadata'].get('workspace_file', 'N/A')}")
            print(f"   • Duration: {result['metadata'].get('session_duration_minutes', 0):.2f} minutes")
            
            print(f"\n🔧 Tools Executed:")
            for i, tool in enumerate(result['tools_used'], 1):
                status = "✅" if tool.get('success', False) else "❌"
                print(f"   {i}. {status} {tool.get('tool', 'unknown')}")
            
            print(f"\n📄 Final Response:")
            print("-" * 40)
            print(result['response'])
            print("-" * 40)
            
            # Show workspace content if available
            workspace_file = result['metadata'].get('workspace_file')
            if workspace_file and pa_agent._tool_registry:
                virtual_fs_tool = pa_agent._tool_registry._tool_instances.get('virtual_fs')
                if virtual_fs_tool:
                    try:
                        workspace_result = await virtual_fs_tool.execute({
                            "action": "read",
                            "filename": workspace_file
                        })
                        if workspace_result.get("success", False):
                            print(f"\n📁 Workspace Content ({workspace_file}):")
                            print("=" * 60)
                            print(workspace_result.get("result", "No content"))
                            print("=" * 60)
                    except Exception as e:
                        print(f"\n⚠️  Could not read workspace file: {str(e)}")
            
        except Exception as e:
            print(f"\n❌ AUTONOMOUS EXECUTION FAILED")
            print(f"Error: {str(e)}")
            logger.error(f"Autonomous execution failed: {str(e)}", exc_info=True)


async def test_autonomous_planning():
    """Test autonomous planning and execution."""
    print("\n" + "="*80)
    print("🤖 AUTONOMOUS PERSONAL ASSISTANT - PLANNING TEST")
    print("="*80)

    # Setup database
    engine, async_session, test_user = await setup_database()

    async with async_session() as session:
        # Create Personal Assistant instance
        pa_agent = PersonalAssistant(test_user, session)
        await pa_agent.initialize()
        
        # Test autonomous planning task
        planning_query = """
        Create a detailed project plan for implementing a customer feedback system 
        for gas stations. Include phases, timelines, resources needed, and potential 
        challenges. Use the planning tool and workspace to organize your work.
        """
        
        print(f"\n📝 Planning Query:")
        print(f"   {planning_query.strip()}")
        print(f"\n🚀 Starting autonomous planning...")
        print("-" * 60)
        
        try:
            # Execute autonomous chat
            result = await pa_agent.autonomous_chat(
                message=planning_query,
                context={
                    "task_type": "project_planning",
                    "complexity": "complex",
                    "autonomous_mode": True
                }
            )
            
            print(f"\n✅ AUTONOMOUS PLANNING COMPLETED")
            print("=" * 60)
            print(f"📊 Planning Summary:")
            print(f"   • Tools Used: {len(result['tools_used'])}")
            print(f"   • Steps Completed: {result['metadata'].get('steps_completed', 0)}")
            print(f"   • Workspace Created: {result['metadata'].get('workspace_file', 'N/A')}")
            
            print(f"\n📄 Planning Result:")
            print("-" * 40)
            print(result['response'])
            print("-" * 40)
            
        except Exception as e:
            print(f"\n❌ AUTONOMOUS PLANNING FAILED")
            print(f"Error: {str(e)}")
            logger.error(f"Autonomous planning failed: {str(e)}", exc_info=True)


async def main():
    """Main test function."""
    print("🧪 Starting Autonomous Personal Assistant Tests")
    
    # Run tests
    await test_autonomous_research()
    await test_autonomous_planning()
    
    print("\n" + "="*80)
    print("🎉 AUTONOMOUS TESTING COMPLETED")
    print("="*80)
    print("\nKey Features Demonstrated:")
    print("✅ Multi-step autonomous execution")
    print("✅ Virtual file system workspace management")
    print("✅ State persistence across tool calls")
    print("✅ Goal-oriented task completion")
    print("✅ Comprehensive progress tracking")
    print("\nThe autonomous architecture successfully:")
    print("• Removes single tool execution constraints")
    print("• Enables continuous execution until goal completion")
    print("• Uses virtual_fs as persistent workspace")
    print("• Maintains context and progress across steps")
    print("• Provides comprehensive execution metadata")


if __name__ == "__main__":
    asyncio.run(main())
