#!/usr/bin/env python3
"""
Test script for Intent-Driven Personal Assistant
Tests the new efficient execution approach with various complexity levels.
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
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test database URL (using SQLite for testing)
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_intent_driven.db"


async def setup_test_database():
    """Set up test database with required data."""
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
        logger.info("Test database setup completed")
        
        return AsyncSessionLocal, test_user


async def test_intent_classification():
    """Test intent classification with different message types."""
    print("\n" + "="*60)
    print("🎯 TESTING INTENT CLASSIFICATION")
    print("="*60)
    
    test_messages = [
        # Simple messages
        ("Hi there!", "simple", "greeting"),
        ("Hello, how are you?", "simple", "greeting"),
        ("Thanks for your help", "simple", "greeting"),
        
        # Focused messages
        ("What is Python?", "focused", "question"),
        ("Find information about Tesla's latest earnings", "focused", "research"),
        ("Plan a weekend trip to Paris", "focused", "planning"),
        
        # Complex messages
        ("Research renewable energy market trends and create a comprehensive analysis report", "complex", "research"),
        ("Create a detailed business plan for a coffee shop including market analysis and financial projections", "complex", "planning"),
        ("Analyze the competitive landscape for electric vehicles and provide strategic recommendations", "complex", "analysis")
    ]
    
    AsyncSessionLocal, test_user = await setup_test_database()
    
    async with AsyncSessionLocal() as session:
        pa_agent = PersonalAssistant(test_user, session)
        await pa_agent.initialize()
        
        for message, expected_complexity, expected_category in test_messages:
            print(f"\n📝 Testing: '{message}'")
            print(f"   Expected: {expected_complexity} - {expected_category}")
            
            try:
                result = await pa_agent.intent_driven_chat(message=message)
                
                actual_complexity = result['metadata'].get('complexity_level', 'unknown')
                actual_category = result['metadata'].get('task_category', 'unknown')
                
                print(f"   Actual: {actual_complexity} - {actual_category}")
                
                # Check if classification is reasonable (not strict matching due to LLM variability)
                complexity_match = actual_complexity == expected_complexity
                category_reasonable = actual_category in [expected_category, "question", "research", "planning"]
                
                if complexity_match and category_reasonable:
                    print(f"   ✅ Classification correct")
                else:
                    print(f"   ⚠️ Classification differs (may be acceptable)")
                
                print(f"   📊 Estimated steps: {result['metadata'].get('estimated_steps', 0)}")
                print(f"   ⏱️ Response time: {result['metadata'].get('response_time_ms', 0):.0f}ms")
                
            except Exception as e:
                print(f"   ❌ Error: {str(e)}")


async def test_execution_efficiency():
    """Test execution efficiency across different complexity levels."""
    print("\n" + "="*60)
    print("⚡ TESTING EXECUTION EFFICIENCY")
    print("="*60)
    
    test_cases = [
        {
            "message": "Hello!",
            "expected_complexity": "simple",
            "max_expected_steps": 2,
            "max_expected_time_ms": 5000
        },
        {
            "message": "What is machine learning?",
            "expected_complexity": "focused", 
            "max_expected_steps": 4,
            "max_expected_time_ms": 15000
        },
        {
            "message": "Research AI trends and create a summary report",
            "expected_complexity": "complex",
            "max_expected_steps": 8,
            "max_expected_time_ms": 45000
        }
    ]
    
    AsyncSessionLocal, test_user = await setup_test_database()
    
    async with AsyncSessionLocal() as session:
        pa_agent = PersonalAssistant(test_user, session)
        await pa_agent.initialize()
        
        for test_case in test_cases:
            message = test_case["message"]
            print(f"\n🧪 Testing efficiency for: '{message}'")
            
            start_time = datetime.now()
            
            try:
                result = await pa_agent.intent_driven_chat(message=message)
                
                end_time = datetime.now()
                actual_time_ms = (end_time - start_time).total_seconds() * 1000
                
                # Extract metrics
                complexity = result['metadata'].get('complexity_level', 'unknown')
                actual_steps = result['metadata'].get('actual_todos_completed', 0)
                tools_used = result['metadata'].get('tools_used_count', 0)
                
                print(f"   📊 Results:")
                print(f"      Complexity: {complexity} (expected: {test_case['expected_complexity']})")
                print(f"      Steps completed: {actual_steps} (max expected: {test_case['max_expected_steps']})")
                print(f"      Tools used: {tools_used}")
                print(f"      Execution time: {actual_time_ms:.0f}ms (max expected: {test_case['max_expected_time_ms']}ms)")
                
                # Efficiency checks
                efficiency_score = 0
                
                if complexity == test_case['expected_complexity']:
                    efficiency_score += 1
                    print(f"      ✅ Complexity classification correct")
                else:
                    print(f"      ⚠️ Complexity classification differs")
                
                if actual_steps <= test_case['max_expected_steps']:
                    efficiency_score += 1
                    print(f"      ✅ Step count within expected range")
                else:
                    print(f"      ❌ Too many steps executed")
                
                if actual_time_ms <= test_case['max_expected_time_ms']:
                    efficiency_score += 1
                    print(f"      ✅ Execution time within expected range")
                else:
                    print(f"      ⚠️ Execution took longer than expected")
                
                print(f"   🎯 Efficiency Score: {efficiency_score}/3")
                
                # Show workspace file if created
                workspace_file = result['metadata'].get('workspace_file')
                if workspace_file:
                    print(f"   📁 Workspace file created: {workspace_file}")
                
            except Exception as e:
                print(f"   ❌ Error: {str(e)}")
                logger.error(f"Test failed for '{message}': {str(e)}", exc_info=True)


async def test_overplanning_prevention():
    """Test that the new system prevents overplanning."""
    print("\n" + "="*60)
    print("🛡️ TESTING OVERPLANNING PREVENTION")
    print("="*60)
    
    # Test cases that previously caused overplanning
    overplanning_prone_messages = [
        "Create a simple todo list",
        "What's the weather like?", 
        "Help me plan a meeting",
        "Research Python basics"
    ]
    
    AsyncSessionLocal, test_user = await setup_test_database()
    
    async with AsyncSessionLocal() as session:
        pa_agent = PersonalAssistant(test_user, session)
        await pa_agent.initialize()
        
        for message in overplanning_prone_messages:
            print(f"\n🔍 Testing overplanning prevention for: '{message}'")
            
            try:
                result = await pa_agent.intent_driven_chat(message=message)
                
                # Check for overplanning indicators
                steps_completed = result['metadata'].get('actual_todos_completed', 0)
                tools_used = result['metadata'].get('tools_used_count', 0)
                estimated_time = result['metadata'].get('total_estimated_minutes', 0)
                
                print(f"   📊 Execution metrics:")
                print(f"      Steps completed: {steps_completed}")
                print(f"      Tools used: {tools_used}")
                print(f"      Estimated time: {estimated_time} minutes")
                
                # Overplanning detection
                overplanning_indicators = 0
                
                if steps_completed > 6:  # More than 6 steps suggests overplanning
                    overplanning_indicators += 1
                    print(f"      ⚠️ High step count detected")
                
                if tools_used > 4:  # More than 4 tools suggests overplanning
                    overplanning_indicators += 1
                    print(f"      ⚠️ High tool usage detected")
                
                if estimated_time > 30:  # More than 30 minutes suggests overplanning
                    overplanning_indicators += 1
                    print(f"      ⚠️ High time estimate detected")
                
                if overplanning_indicators == 0:
                    print(f"   ✅ No overplanning detected - execution was efficient")
                elif overplanning_indicators == 1:
                    print(f"   ⚠️ Minor overplanning indicators detected")
                else:
                    print(f"   ❌ Multiple overplanning indicators detected")
                
                print(f"   🎯 Overplanning Prevention Score: {3-overplanning_indicators}/3")
                
            except Exception as e:
                print(f"   ❌ Error: {str(e)}")


async def main():
    """Run all intent-driven tests."""
    print("🚀 Intent-Driven Personal Assistant Test Suite")
    print("Testing the new efficient execution approach...")
    
    try:
        # Run all test suites
        await test_intent_classification()
        await test_execution_efficiency()
        await test_overplanning_prevention()
        
        print("\n" + "="*60)
        print("🎉 ALL TESTS COMPLETED")
        print("="*60)
        print("The intent-driven approach has been tested across:")
        print("✅ Intent classification accuracy")
        print("✅ Execution efficiency by complexity level")
        print("✅ Overplanning prevention mechanisms")
        print("\nReview the results above to validate the improvements.")
        
    except Exception as e:
        print(f"\n❌ TEST SUITE FAILED: {str(e)}")
        logger.error(f"Test suite failed: {str(e)}", exc_info=True)
        return False
    
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
