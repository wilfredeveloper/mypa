#!/usr/bin/env python3
"""
Debug script to test tool registry loading.
"""

import asyncio
import sys
import os

# Add the backend directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

async def test_tool_registry():
    """Test if the tool registry properly loads the schema."""
    from app.core.database import AsyncSessionLocal
    from app.models.user import User
    from app.agents.personal_assistant.tools.registry import ToolRegistryManager
    from sqlalchemy import select

    print("🔍 Testing Tool Registry Schema Loading")
    print("=" * 50)

    async with AsyncSessionLocal() as session:
        # Get a test user (assuming user ID 1 exists)
        result = await session.execute(select(User).where(User.id == 1))
        user = result.scalar_one_or_none()

        if not user:
            print("❌ No user found with ID 1")
            return

        print(f"✅ Found user: {user.email}")

        # Create tool registry instance
        tool_registry = ToolRegistryManager(user=user, db=session)

        # Initialize the registry
        await tool_registry.initialize()

        # Check if google_calendar schema is available
        schema = tool_registry.get_tool_schema("google_calendar")

        if schema:
            print(f"✅ Tool registry found google_calendar schema")
            print(f"   Schema type: {type(schema)}")
            print(f"   Schema keys: {list(schema.keys())}")
            if 'properties' in schema:
                print(f"   Schema properties: {list(schema['properties'].keys())}")
        else:
            print("❌ Tool registry did not find google_calendar schema")

            # Check what tools are available
            available_tools = list(tool_registry._tool_registry.keys())
            print(f"   Available tools in registry: {available_tools}")

if __name__ == "__main__":
    asyncio.run(test_tool_registry())
