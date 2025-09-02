#!/usr/bin/env python3
"""
Simple tool usage test for Personal Assistant.
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


async def setup_test_database():
    """Set up test database with sample data."""
    print("🔧 Setting up test database...")

    # Create async engine for SQLite
    engine = create_async_engine(
        "sqlite+aiosqlite:///simple_test_pa.db",
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


async def main():
    """Main test function."""
    print("🚀 Starting Simple Tool Usage Test")
    print("=" * 50)

    try:
        # Setup test database
        engine, async_session, test_user = await setup_test_database()

        # Create Personal Assistant instance
        print("\n🤖 Initializing Personal Assistant...")
        async with async_session() as session:
            pa_agent = PersonalAssistant(test_user, session)
            await pa_agent.initialize()
            print("✅ Personal Assistant initialized successfully")

            # Test simple file creation request
            print("\n💾 Testing file creation request...")
            result = await pa_agent.chat("Create a file called 'test.txt' with the content 'Hello World'")
            print(f"Response: {result.get('response', 'No response')}")
            print(f"Tools used: {result.get('tools_used', [])}")
            print(f"Success: {'✅' if result.get('tools_used') else '❌'}")

        print("\n🎉 Test completed!")
        print("=" * 50)

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