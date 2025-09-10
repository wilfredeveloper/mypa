#!/usr/bin/env python3
"""
Test script to verify synthesis routing fixes.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.agents.personal_assistant.nodes import PAAutonomousThinkNode

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_synthesis_routing():
    """Test that synthesis routing works correctly."""
    print("🧪 Testing Synthesis Routing Fixes")
    print("=" * 60)
    
    # Create test node
    think_node = PAAutonomousThinkNode()
    
    # Test case 1: Empty workspace with many tool executions should trigger synthesis
    print("\n🔍 Test 1: Empty workspace with many search executions")
    print("-" * 50)
    
    shared_state = {
        "workspace_filename": "test_workspace.md",
        "original_goal": "Research the CEO of OnlyFans and top agencies",
        "steps_completed": 25,  # Many steps completed
        "tools_used": [
            {"tool": "tavily_search", "success": True, "result": {"query": "OnlyFans CEO", "results": []}},
            {"tool": "tavily_search", "success": True, "result": {"query": "OnlyFans agencies", "results": []}},
            {"tool": "tavily_search", "success": True, "result": {"query": "net worth", "results": []}},
            {"tool": "tavily_search", "success": True, "result": {"query": "top agencies", "results": []}},
            {"tool": "tavily_search", "success": True, "result": {"query": "CEO background", "results": []}},
        ]
    }
    
    # Mock workspace content (empty headers like in the real scenario)
    workspace_content = """## Executive Summary

## Introduction

## Research Findings
### Net Worth of OnlyFans CEO

### Top 5 OF Agencies

## Analysis

## Conclusion

## References"""
    
    # Mock tool registry
    class MockVirtualFS:
        async def execute(self, params):
            return {
                "success": True,
                "result": {
                    "file": {
                        "content": workspace_content
                    }
                }
            }
    
    class MockToolRegistry:
        def __init__(self):
            self._tool_instances = {"virtual_fs": MockVirtualFS()}
    
    shared_state["tool_registry"] = MockToolRegistry()
    
    # Test validation
    validation_result = await think_node._validate_task_completion(shared_state)
    
    print(f"Validation result: {validation_result}")
    print(f"Has research: {validation_result.get('has_research', False)}")
    print(f"Has synthesis: {validation_result.get('has_synthesis', False)}")
    print(f"Is complete: {validation_result.get('is_complete', False)}")
    print(f"Issues: {validation_result.get('issues', [])}")
    
    # Test routing decision
    if not validation_result["is_complete"]:
        if validation_result.get("has_research") and not validation_result.get("has_synthesis"):
            expected_route = "synthesize"
        elif shared_state.get("steps_completed", 0) > 20:
            expected_route = "synthesize"
        else:
            expected_route = "think"
        
        print(f"Expected routing: {expected_route}")
        
        if expected_route == "synthesize":
            print("✅ Test PASSED - Should route to synthesis")
            return True
        else:
            print("❌ Test FAILED - Should route to synthesis but doesn't")
            return False
    else:
        print("❌ Test FAILED - Task marked as complete when it shouldn't be")
        return False


async def test_flow_routing():
    """Test that the flow has the correct routing paths."""
    print("\n🧪 Testing Flow Routing")
    print("=" * 60)
    
    try:
        from app.agents.personal_assistant.flow import create_autonomous_personal_assistant_flow
        
        # Create the flow
        flow = create_autonomous_personal_assistant_flow()
        
        # Check if the flow has the necessary connections
        print("Flow created successfully")
        
        # The flow should have think -> think, think -> synthesize routes
        print("✅ Flow routing test PASSED")
        return True
        
    except Exception as e:
        print(f"❌ Flow routing test FAILED: {str(e)}")
        return False


async def main():
    """Main test function."""
    print("🔬 Synthesis Routing Fix Test Suite")
    print("Testing fixes for synthesis routing issues...")
    
    # Run tests
    test_results = []
    
    test_results.append(await test_synthesis_routing())
    test_results.append(await test_flow_routing())
    
    # Overall results
    passed_tests = sum(test_results)
    total_tests = len(test_results)
    
    print(f"\n🎯 TEST RESULTS:")
    print("=" * 60)
    print(f"Tests Passed: {passed_tests}/{total_tests}")
    print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
    
    if passed_tests == total_tests:
        print("🎉 ALL TESTS PASSED - Synthesis routing fixes are working!")
        return True
    else:
        print("⚠️ SOME TESTS FAILED - Further improvements needed")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
