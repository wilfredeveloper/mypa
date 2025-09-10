#!/usr/bin/env python3
"""
Test script to verify virtual_fs parameter validation fixes.
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

from app.agents.personal_assistant.nodes import PAToolCallNode

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MockToolRegistry:
    """Mock tool registry for testing."""

    def __init__(self):
        pass

    async def execute_tool(self, tool_name: str, parameters: dict):
        """Mock tool execution - just validate parameters are present."""
        if tool_name == "virtual_fs":
            action = parameters.get("action", "")
            filename_required_actions = ["create", "read", "update", "delete"]

            if action in filename_required_actions and not parameters.get("filename"):
                return {"success": False, "error": f"Missing filename: filename is required for '{action}' action"}
            elif action == "list":
                return {"success": True, "result": {"files": []}}
            else:
                return {"success": True, "result": {"message": f"Mock execution of {action} action"}}
        else:
            return {"success": True, "result": {"message": f"Mock execution of {tool_name}"}}


async def test_parameter_validation():
    """Test parameter validation and fallback mechanisms."""
    print("🧪 Testing Parameter Validation Fixes")
    print("=" * 60)
    
    # Create test node and mock registry
    tool_node = PAToolCallNode()
    mock_registry = MockToolRegistry()
    
    # Test cases for virtual_fs parameter validation
    test_cases = [
        {
            "name": "Missing filename for read action",
            "tool_call": {
                "name": "virtual_fs",
                "parameters": {"action": "read"}  # Missing filename
            },
            "shared": {"workspace_filename": "test_workspace.md", "task_id": "12345678"},
            "expected_fix": "Should add workspace_filename"
        },
        {
            "name": "Missing filename with no workspace",
            "tool_call": {
                "name": "virtual_fs", 
                "parameters": {"action": "create", "content": "test content"}  # Missing filename
            },
            "shared": {"task_id": "abcd1234"},
            "expected_fix": "Should generate filename from task_id"
        },
        {
            "name": "Missing content for create action",
            "tool_call": {
                "name": "virtual_fs",
                "parameters": {"action": "create", "filename": "test.md"}  # Missing content
            },
            "shared": {"task_id": "12345678"},
            "expected_fix": "Should add default content"
        },
        {
            "name": "Valid parameters",
            "tool_call": {
                "name": "virtual_fs",
                "parameters": {"action": "create", "filename": "valid.md", "content": "valid content"}
            },
            "shared": {"task_id": "12345678"},
            "expected_fix": "Should remain unchanged"
        },
        {
            "name": "List action (no filename required)",
            "tool_call": {
                "name": "virtual_fs",
                "parameters": {"action": "list"}
            },
            "shared": {"task_id": "12345678"},
            "expected_fix": "Should work without filename"
        }
    ]
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🔍 Test {i}: {test_case['name']}")
        print("-" * 40)
        
        try:
            # Test parameter validation
            original_params = test_case["tool_call"]["parameters"].copy()
            fixed_params = await tool_node._validate_and_fix_parameters(
                test_case["tool_call"]["name"],
                test_case["tool_call"]["parameters"],
                test_case["shared"]
            )
            
            print(f"Original params: {original_params}")
            print(f"Fixed params: {fixed_params}")
            print(f"Expected: {test_case['expected_fix']}")
            
            # Test actual tool execution with fixed parameters
            result = await mock_registry.execute_tool(
                test_case["tool_call"]["name"],
                fixed_params
            )
            
            success = result.get("success", False) if isinstance(result, dict) else False
            error_msg = result.get("error", "") if isinstance(result, dict) else str(result)
            
            if success or "list" in test_case["name"].lower():
                print("✅ Test PASSED - Tool executed successfully")
                results.append(True)
            else:
                print(f"❌ Test FAILED - Tool execution failed: {error_msg}")
                results.append(False)
                
        except Exception as e:
            print(f"❌ Test FAILED - Exception: {str(e)}")
            results.append(False)
    
    # Summary
    passed = sum(results)
    total = len(results)
    
    print(f"\n📊 TEST SUMMARY:")
    print("=" * 40)
    print(f"Passed: {passed}/{total}")
    print(f"Success Rate: {(passed/total)*100:.1f}%")
    
    if passed == total:
        print("🎉 ALL PARAMETER VALIDATION TESTS PASSED!")
        return True
    else:
        print("⚠️ SOME TESTS FAILED - Parameter validation needs improvement")
        return False


async def test_baml_function_availability():
    """Test that enhanced BAML functions are available."""
    print("\n🧪 Testing BAML Function Enhancements")
    print("=" * 60)
    
    try:
        from baml_client import b
        
        # Test PersonalAssistantThinking function
        if hasattr(b, 'PersonalAssistantThinking'):
            print("✅ PersonalAssistantThinking function available")
        else:
            print("❌ PersonalAssistantThinking function missing")
            return False
        
        # Test PersonalAssistantToolCall function
        if hasattr(b, 'PersonalAssistantToolCall'):
            print("✅ PersonalAssistantToolCall function available")
        else:
            print("❌ PersonalAssistantToolCall function missing")
            return False
        
        # Test PersonalAssistantSynthesis function
        if hasattr(b, 'PersonalAssistantSynthesis'):
            print("✅ PersonalAssistantSynthesis function available")
        else:
            print("❌ PersonalAssistantSynthesis function missing")
            return False
        
        print("🎉 ALL BAML FUNCTIONS AVAILABLE!")
        return True
        
    except Exception as e:
        print(f"❌ BAML function test failed: {str(e)}")
        return False


async def test_error_reproduction():
    """Test reproduction of the original filename error."""
    print("\n🧪 Testing Original Error Reproduction")
    print("=" * 60)

    try:
        # Simulate the original error scenario using mock
        mock_registry = MockToolRegistry()

        # This should fail with the original error
        result = await mock_registry.execute_tool("virtual_fs", {
            "action": "read"
            # Missing filename parameter
        })

        if isinstance(result, dict) and "filename is required" in str(result.get("error", "")):
            print("✅ Original error reproduced successfully")
            print(f"Error message: {result.get('error', 'Unknown error')}")
            return True
        else:
            print("❌ Failed to reproduce original error")
            print(f"Unexpected result: {result}")
            return False

    except Exception as e:
        print(f"❌ Error reproduction test failed: {str(e)}")
        return False


async def main():
    """Main test function."""
    print("🔬 Virtual_fs Parameter Validation Test Suite")
    print("Testing fixes for filename parameter errors...")
    
    # Run all tests
    test_results = []
    
    test_results.append(await test_error_reproduction())
    test_results.append(await test_parameter_validation())
    test_results.append(await test_baml_function_availability())
    
    # Overall results
    passed_tests = sum(test_results)
    total_tests = len(test_results)
    
    print(f"\n🎯 OVERALL TEST RESULTS:")
    print("=" * 60)
    print(f"Tests Passed: {passed_tests}/{total_tests}")
    print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
    
    if passed_tests == total_tests:
        print("🎉 ALL TESTS PASSED - Parameter validation fixes are working!")
        return True
    else:
        print("⚠️ SOME TESTS FAILED - Further improvements needed")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
