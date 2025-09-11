#!/usr/bin/env python3
"""
Test script for the new centralized parameter processor.

This script tests the refactored JSON parsing architecture to ensure
it works correctly with various input formats.
"""

import asyncio
import json
from app.services.parameter_processor import ParameterProcessor, ParameterProcessingError
from app.agents.personal_assistant.tools.schemas import GOOGLE_CALENDAR_SCHEMA


async def test_parameter_processor():
    """Test the parameter processor with various inputs."""
    processor = ParameterProcessor()
    
    print("🧪 Testing Parameter Processor")
    print("=" * 50)
    
    # Test cases
    test_cases = [
        {
            "name": "Valid JSON string",
            "input": '{"action": "create", "event_data": {"summary": "Test Meeting", "start": "2025-01-15T14:00:00Z", "end": "2025-01-15T15:00:00Z"}}',
            "should_pass": True
        },
        {
            "name": "Valid dictionary",
            "input": {
                "action": "create",
                "event_data": {
                    "summary": "Test Meeting",
                    "start": "2025-01-15T14:00:00Z",
                    "end": "2025-01-15T15:00:00Z"
                }
            },
            "should_pass": True
        },
        {
            "name": "Quasi-JSON with unquoted keys",
            "input": '{action: "create", event_data: {summary: "Test Meeting", start: "2025-01-15T14:00:00Z", end: "2025-01-15T15:00:00Z"}}',
            "should_pass": True
        },
        {
            "name": "Quasi-JSON with single quotes",
            "input": "{'action': 'create', 'event_data': {'summary': 'Test Meeting', 'start': '2025-01-15T14:00:00Z', 'end': '2025-01-15T15:00:00Z'}}",
            "should_pass": True
        },
        {
            "name": "Missing required field",
            "input": {"event_data": {"summary": "Test Meeting"}},
            "should_pass": False
        },
        {
            "name": "Invalid action",
            "input": {"action": "invalid_action"},
            "should_pass": False
        },
        {
            "name": "Complex event with attendees",
            "input": {
                "action": "create",
                "event_data": {
                    "summary": "Team Meeting",
                    "description": "Weekly team sync",
                    "start": "2025-01-15T14:00:00Z",
                    "end": "2025-01-15T15:00:00Z",
                    "location": "Conference Room A",
                    "attendees": [
                        {"email": "john@example.com", "displayName": "John Doe"},
                        {"email": "jane@example.com", "displayName": "Jane Smith"}
                    ],
                    "reminders": [
                        {"method": "popup", "minutes": 15},
                        {"method": "email", "minutes": 60}
                    ]
                }
            },
            "should_pass": True
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📋 Test {i}: {test_case['name']}")
        print("-" * 30)
        
        try:
            result = await processor.process_baml_parameters(
                test_case["input"],
                GOOGLE_CALENDAR_SCHEMA,
                "google_calendar"
            )
            
            if test_case["should_pass"]:
                print("✅ PASS - Parameters processed successfully")
                print(f"   Result: {json.dumps(result, indent=2)}")
            else:
                print("❌ FAIL - Expected validation error but processing succeeded")
                print(f"   Result: {json.dumps(result, indent=2)}")
                
        except ParameterProcessingError as e:
            if not test_case["should_pass"]:
                print("✅ PASS - Expected validation error occurred")
                print(f"   Error: {str(e)}")
            else:
                print("❌ FAIL - Unexpected processing error")
                print(f"   Error: {str(e)}")
                
        except Exception as e:
            print("❌ FAIL - Unexpected exception")
            print(f"   Error: {str(e)}")
    
    print("\n" + "=" * 50)
    print("🏁 Parameter Processor Tests Complete")


async def test_google_calendar_transformations():
    """Test Google Calendar specific transformations."""
    processor = ParameterProcessor()
    
    print("\n🗓️  Testing Google Calendar Transformations")
    print("=" * 50)
    
    # Test nested JSON string parsing
    test_input = {
        "action": "create",
        "event_data": '{"summary": "Nested JSON Test", "start": "2025-01-15T14:00:00Z", "end": "2025-01-15T15:00:00Z"}',
        "time_range": '{"start": "2025-01-15T00:00:00Z", "end": "2025-01-15T23:59:59Z", "max_results": 10}'
    }
    
    try:
        result = await processor.process_baml_parameters(
            test_input,
            GOOGLE_CALENDAR_SCHEMA,
            "google_calendar"
        )
        
        print("✅ PASS - Nested JSON strings processed successfully")
        print(f"   Event Data Type: {type(result['event_data'])}")
        print(f"   Time Range Type: {type(result['time_range'])}")
        print(f"   Result: {json.dumps(result, indent=2)}")
        
    except Exception as e:
        print("❌ FAIL - Nested JSON processing failed")
        print(f"   Error: {str(e)}")


if __name__ == "__main__":
    print("Starting parameter processor tests...")
    try:
        asyncio.run(test_parameter_processor())
        asyncio.run(test_google_calendar_transformations())
        print("Tests completed successfully!")
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()
