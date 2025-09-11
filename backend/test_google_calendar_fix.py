#!/usr/bin/env python3
"""
Test script to verify the Google Calendar tool fix for JSON string parsing.
"""

import json
import sys
import os

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from app.agents.personal_assistant.tools.external.google_calendar import GoogleCalendarTool


def test_parse_event_data():
    """Test the _parse_event_data method with various input types."""
    
    # Create a minimal GoogleCalendarTool instance for testing
    tool = GoogleCalendarTool(user=None, db=None, registry=None, user_access=None)
    
    # Test data
    test_event_dict = {
        "summary": "Test Meeting",
        "start": "2025-09-15T15:00:00+00:00",
        "end": "2025-09-15T16:00:00+00:00",
        "description": "A test meeting",
        "attendees": ["test@example.com"]
    }
    
    test_event_json = json.dumps(test_event_dict)
    
    print("Testing Google Calendar tool event_data parsing...")
    
    # Test 1: Dictionary input (should work as before)
    try:
        result = tool._parse_event_data(test_event_dict)
        assert result == test_event_dict
        print("✓ Test 1 PASSED: Dictionary input parsed correctly")
    except Exception as e:
        print(f"✗ Test 1 FAILED: Dictionary input failed: {e}")
        return False
    
    # Test 2: JSON string input (this was the failing case)
    try:
        result = tool._parse_event_data(test_event_json)
        assert result == test_event_dict
        print("✓ Test 2 PASSED: JSON string input parsed correctly")
    except Exception as e:
        print(f"✗ Test 2 FAILED: JSON string input failed: {e}")
        return False
    
    # Test 3: Invalid JSON string
    try:
        tool._parse_event_data('{"invalid": json}')
        print("✗ Test 3 FAILED: Invalid JSON should have raised ValueError")
        return False
    except ValueError:
        print("✓ Test 3 PASSED: Invalid JSON correctly raised ValueError")
    except Exception as e:
        print(f"✗ Test 3 FAILED: Unexpected exception: {e}")
        return False
    
    # Test 4: None input
    try:
        tool._parse_event_data(None)
        print("✗ Test 4 FAILED: None input should have raised ValueError")
        return False
    except ValueError:
        print("✓ Test 4 PASSED: None input correctly raised ValueError")
    except Exception as e:
        print(f"✗ Test 4 FAILED: Unexpected exception: {e}")
        return False
    
    # Test 5: Non-dict JSON
    try:
        tool._parse_event_data('["not", "a", "dict"]')
        print("✗ Test 5 FAILED: Non-dict JSON should have raised ValueError")
        return False
    except ValueError:
        print("✓ Test 5 PASSED: Non-dict JSON correctly raised ValueError")
    except Exception as e:
        print(f"✗ Test 5 FAILED: Unexpected exception: {e}")
        return False

    # Test 6: Quasi-JSON format (the actual failing case from the agent)
    quasi_json = "{summary: Meeting with Martin, start: 2025-09-12T16:00:00+03:00, end: 2025-09-12T17:00:00+03:00, reminders: [{method: popup, minutes: 30}]}"
    expected_result = {
        "summary": "Meeting with Martin",
        "start": "2025-09-12T16:00:00+03:00",
        "end": "2025-09-12T17:00:00+03:00",
        "reminders": [{"method": "popup", "minutes": 30}]
    }

    try:
        result = tool._parse_event_data(quasi_json)
        assert result == expected_result
        print("✓ Test 6 PASSED: Quasi-JSON format parsed correctly")
    except Exception as e:
        print(f"✗ Test 6 FAILED: Quasi-JSON format failed: {e}")
        return False

    print("\nAll tests passed! The Google Calendar tool should now handle both dictionary and JSON string inputs correctly.")
    return True


def test_edge_cases():
    """Test edge cases for event data parsing."""
    
    tool = GoogleCalendarTool(user=None, db=None, registry=None, user_access=None)
    
    print("\nTesting edge cases...")
    
    # Test empty dict
    try:
        result = tool._parse_event_data({})
        assert result == {}
        print("✓ Empty dictionary handled correctly")
    except Exception as e:
        print(f"✗ Empty dictionary failed: {e}")
        return False
    
    # Test empty JSON object
    try:
        result = tool._parse_event_data('{}')
        assert result == {}
        print("✓ Empty JSON object handled correctly")
    except Exception as e:
        print(f"✗ Empty JSON object failed: {e}")
        return False
    
    # Test complex nested structure
    complex_event = {
        "summary": "Complex Meeting",
        "start": {"dateTime": "2025-09-15T15:00:00+00:00", "timeZone": "UTC"},
        "end": {"dateTime": "2025-09-15T16:00:00+00:00", "timeZone": "UTC"},
        "reminders": [{"method": "email", "minutes": 30}],
        "attendees": ["user1@example.com", "user2@example.com"]
    }
    
    try:
        result = tool._parse_event_data(json.dumps(complex_event))
        assert result == complex_event
        print("✓ Complex nested structure handled correctly")
    except Exception as e:
        print(f"✗ Complex nested structure failed: {e}")
        return False
    
    print("All edge case tests passed!")
    return True


if __name__ == "__main__":
    success = test_parse_event_data() and test_edge_cases()
    
    if success:
        print("\n🎉 All tests passed! The fix should resolve the AttributeError.")
        print("\nThe Google Calendar tool now properly handles:")
        print("- Dictionary inputs (existing functionality)")
        print("- JSON string inputs (the bug that was causing the error)")
        print("- Proper error handling for invalid inputs")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed. Please check the implementation.")
        sys.exit(1)
