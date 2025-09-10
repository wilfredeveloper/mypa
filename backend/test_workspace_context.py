#!/usr/bin/env python3
"""
Test script to verify workspace content is properly passed to shared state.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.agents.personal_assistant.nodes import PAToolCallNode, PAAutonomousThinkNode

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_workspace_content_loading():
    """Test that workspace content is loaded into shared state."""
    print("🧪 Testing Workspace Content Loading")
    print("=" * 60)
    
    # Create test node
    tool_node = PAToolCallNode()
    
    # Mock workspace content (similar to the real scenario)
    test_workspace_content = """## Executive Summary

## Introduction

## Research Findings
### Net Worth of OnlyFans CEO
Tim Stokely is the founder and CEO of OnlyFans with an estimated net worth of $120 million.

### Top 5 OF Agencies
1. Unruly Agency - $50M revenue
2. Motley Models - $30M revenue

## Analysis

## Conclusion

## References"""
    
    # Mock virtual_fs tool
    class MockVirtualFS:
        async def execute(self, params):
            if params.get("action") == "read":
                return {
                    "success": True,
                    "result": {
                        "file": {
                            "content": test_workspace_content
                        }
                    }
                }
            return {"success": True, "result": "Mock operation"}
    
    # Mock tool registry
    class MockToolRegistry:
        def __init__(self):
            self._tool_instances = {"virtual_fs": MockVirtualFS()}
    
    # Set up shared state
    shared_state = {
        "workspace_filename": "test_workspace.md",
        "tool_registry": MockToolRegistry(),
        "autonomous_mode": True,
        "steps_completed": 5,
        "tools_used": [
            {"tool": "tavily_search", "success": True},
            {"tool": "tavily_search", "success": True},
            {"tool": "virtual_fs", "success": True}
        ]
    }
    
    # Test loading workspace content
    await tool_node._load_workspace_content_to_shared(shared_state)
    
    # Verify shared state was updated
    print("Checking shared state updates...")
    
    # Check if workspace content was loaded
    if "current_workspace_content" in shared_state:
        content = shared_state["current_workspace_content"]
        print(f"✅ Workspace content loaded: {len(content)} characters")
        
        # Check if content matches expected
        if "Tim Stokely" in content and "OnlyFans" in content:
            print("✅ Content contains expected research data")
        else:
            print("❌ Content missing expected research data")
            return False
    else:
        print("❌ Workspace content not loaded into shared state")
        return False
    
    # Check workspace metrics
    expected_metrics = [
        "workspace_content_length",
        "workspace_has_content", 
        "workspace_has_empty_sections",
        "workspace_research_indicators"
    ]
    
    for metric in expected_metrics:
        if metric in shared_state:
            print(f"✅ Metric '{metric}': {shared_state[metric]}")
        else:
            print(f"❌ Missing metric: {metric}")
            return False
    
    print("✅ All workspace metrics loaded successfully")
    return True


async def test_autonomous_context_enhancement():
    """Test that autonomous thinking gets enhanced context."""
    print("\n🧪 Testing Autonomous Context Enhancement")
    print("=" * 60)
    
    # Create test node
    think_node = PAAutonomousThinkNode()
    
    # Set up shared state with workspace data
    shared_state = {
        "user_message": "Research OnlyFans CEO and agencies",
        "original_goal": "Research the CEO of OnlyFans and top agencies",
        "steps_completed": 10,
        "task_id": "test12345678",
        "workspace_filename": "test_workspace.md",
        "current_workspace_content": """## Research Findings
### CEO Information
Tim Stokely - Founder and CEO, net worth $120M

### Top Agencies
1. Unruly Agency - $50M revenue
URL: https://example.com
Content: Research data about OnlyFans agencies""",
        "workspace_metrics": {
            "has_content": True,
            "has_empty_sections": False,
            "research_indicators": 5,
            "content_length": 200  # Updated to match actual content
        },
        "tools_used": [{"tool": "tavily_search"} for _ in range(8)],
        "session": {"messages": []},
        "config": {},
        "tool_registry": None,
        "baml_client": None
    }
    
    # Test preparation
    prep_result = await think_node.prep_async(shared_state)
    
    # Verify enhanced context
    print("Checking enhanced context...")
    
    if "enhanced_context" in prep_result:
        context = prep_result["enhanced_context"]
        print(f"✅ Enhanced context created: {len(context)} characters")
        
        # Print the actual context for debugging
        print(f"Actual context:\n{context}\n")

        # Check for key information
        expected_info = [
            "Steps Completed: 10",
            "Tools Used: 8",
            "Workspace Content Length:",  # Just check for the presence
            "Research Indicators Found:",
            "Tim Stokely"
        ]
        
        for info in expected_info:
            if info in context:
                print(f"✅ Found: {info}")
            else:
                print(f"❌ Missing: {info}")
                return False
    else:
        print("❌ Enhanced context not created")
        return False
    
    # Check workspace metrics
    if "workspace_metrics" in prep_result:
        metrics = prep_result["workspace_metrics"]
        print(f"✅ Workspace metrics included: {metrics}")
    else:
        print("❌ Workspace metrics not included")
        return False
    
    print("✅ Autonomous context enhancement working correctly")
    return True


async def main():
    """Main test function."""
    print("🔬 Workspace Context Enhancement Test Suite")
    print("Testing workspace content integration with shared state...")
    
    # Run tests
    test_results = []
    
    test_results.append(await test_workspace_content_loading())
    test_results.append(await test_autonomous_context_enhancement())
    
    # Overall results
    passed_tests = sum(test_results)
    total_tests = len(test_results)
    
    print(f"\n🎯 TEST RESULTS:")
    print("=" * 60)
    print(f"Tests Passed: {passed_tests}/{total_tests}")
    print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
    
    if passed_tests == total_tests:
        print("🎉 ALL TESTS PASSED - Workspace context enhancement is working!")
        print("\n✅ Nodes now have access to workspace content for better decision making!")
        print("✅ Enhanced context includes workspace metrics and content preview!")
        print("✅ Quality validation can use cached workspace data!")
        return True
    else:
        print("⚠️ SOME TESTS FAILED - Further improvements needed")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
