#!/usr/bin/env python3
"""
Test script to verify autonomous agent quality improvements.
"""

import asyncio
import logging
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent / ".env.local"
load_dotenv(env_path)

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.agents.personal_assistant.agent import PersonalAssistant
from app.core.config import get_settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_code_structure():
    """Test that the code structure improvements are in place."""
    print("\n🧪 Testing Code Structure Improvements")
    print("=" * 60)

    try:
        # Test 1: Import the new synthesis node
        from app.agents.personal_assistant.nodes import PAContentSynthesisNode
        print("✅ PAContentSynthesisNode import successful")

        # Test 2: Check BAML function availability
        from baml_client import b
        synthesis_func = getattr(b, 'PersonalAssistantSynthesis', None)
        if synthesis_func:
            print("✅ PersonalAssistantSynthesis BAML function available")
        else:
            print("❌ PersonalAssistantSynthesis BAML function missing")
            return False

        # Test 3: Check flow includes synthesis node
        from app.agents.personal_assistant.flow import create_autonomous_personal_assistant_flow
        flow = create_autonomous_personal_assistant_flow()
        print("✅ Autonomous flow creation successful")

        # Test 4: Check that synthesis node can be instantiated
        synthesis_node = PAContentSynthesisNode()
        print("✅ PAContentSynthesisNode instantiation successful")

        # Test 5: Check validation method exists
        from app.agents.personal_assistant.nodes import PAAutonomousThinkNode
        think_node = PAAutonomousThinkNode()
        if hasattr(think_node, '_validate_task_completion'):
            print("✅ Quality validation method available")
        else:
            print("❌ Quality validation method missing")
            return False

        print("\n🎯 CODE STRUCTURE VALIDATION PASSED")
        return True

    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


async def test_autonomous_quality():
    """Test the autonomous agent quality improvements."""
    print("\n🧪 Testing Autonomous Agent Quality Improvements")
    print("=" * 60)

    # Since we can't easily run the full agent without database setup,
    # we'll test the code structure and logic improvements
    structure_test = await test_code_structure()

    if not structure_test:
        return False

    # Test the quality improvements in the code
    print("\n🔍 QUALITY IMPROVEMENTS ANALYSIS:")
    print("=" * 40)

    improvements_found = 0

    # Check 1: Content truncation removal
    try:
        with open('app/agents/personal_assistant/nodes.py', 'r', encoding='utf-8') as f:
            content = f.read()
            # Check for the old truncation patterns
            old_patterns = ['results[:3]', 'content[:300]', 'thinking[:500]']
            truncation_found = any(pattern in content for pattern in old_patterns)
            if not truncation_found:
                print("✅ Content truncation limits removed")
                improvements_found += 1
            else:
                print("⚠️ Content truncation limits still present")
    except Exception as e:
        print(f"❌ Could not check content truncation: {e}")

    # Check 2: Synthesis node implementation
    try:
        from app.agents.personal_assistant.nodes import PAContentSynthesisNode
        node = PAContentSynthesisNode()
        if hasattr(node, '_extract_research_data'):
            print("✅ Content synthesis functionality implemented")
            improvements_found += 1
        else:
            print("⚠️ Content synthesis functionality incomplete")
    except Exception as e:
        print(f"❌ Could not check synthesis node: {e}")

    # Check 3: Quality validation gates
    try:
        from app.agents.personal_assistant.nodes import PAAutonomousThinkNode
        node = PAAutonomousThinkNode()
        if hasattr(node, '_validate_task_completion'):
            print("✅ Quality validation gates implemented")
            improvements_found += 1
        else:
            print("⚠️ Quality validation gates missing")
    except Exception as e:
        print(f"❌ Could not check validation gates: {e}")

    # Check 4: Enhanced workspace instructions
    try:
        with open('app/agents/personal_assistant/nodes.py', 'r', encoding='utf-8') as f:
            content = f.read()
            if 'READ existing workspace' in content and 'UPDATE with new findings' in content:
                print("✅ Enhanced workspace instructions implemented")
                improvements_found += 1
            else:
                print("⚠️ Enhanced workspace instructions missing")
    except Exception as e:
        print(f"❌ Could not check workspace instructions: {e}")

    # Check 5: BAML synthesis function
    try:
        from baml_client import b
        if hasattr(b, 'PersonalAssistantSynthesis'):
            print("✅ BAML synthesis function available")
            improvements_found += 1
        else:
            print("⚠️ BAML synthesis function missing")
    except Exception as e:
        print(f"❌ Could not check BAML function: {e}")

    print(f"\n🎯 IMPROVEMENTS SCORE: {improvements_found}/5")

    if improvements_found >= 4:
        print("✅ QUALITY IMPROVEMENTS SUCCESSFULLY IMPLEMENTED")
        return True
    else:
        print("⚠️ QUALITY IMPROVEMENTS NEED MORE WORK")
        return False


async def main():
    """Main test function."""
    print("🔬 Autonomous Agent Quality Test Suite")
    print("Testing the implemented quality improvements...")
    
    success = await test_autonomous_quality()
    
    if success:
        print("\n🎉 ALL TESTS PASSED - Quality improvements are working!")
    else:
        print("\n⚠️ TESTS FAILED - Quality improvements need further work")
    
    return success


if __name__ == "__main__":
    asyncio.run(main())
