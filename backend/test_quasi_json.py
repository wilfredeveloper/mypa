#!/usr/bin/env python3
"""
Simple test for the quasi-JSON parsing functionality.
"""

import sys
import os
import json

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from app.agents.personal_assistant.tools.external.google_calendar import GoogleCalendarTool


def test_specific_failing_case():
    """Test the specific failing case from the agent."""
    
    tool = GoogleCalendarTool(user=None, db=None, registry=None, user_access=None)
    
    # The exact failing input from the error log
    failing_input = "{summary: Meeting with Martin, start: 2025-09-12T16:00:00+03:00, end: 2025-09-12T17:00:00+03:00, reminders: [{method: popup, minutes: 30}]}"
    
    print("Testing quasi-JSON parsing...")
    print(f"Input: {failing_input}")
    
    try:
        # First, let's see what the _fix_quasi_json method produces
        fixed_json = tool._fix_quasi_json(failing_input)
        print(f"Fixed JSON: {fixed_json}")
        
        # Try to parse the fixed JSON
        parsed = json.loads(fixed_json)
        print(f"Parsed successfully: {parsed}")
        
        # Now test the full _parse_event_data method
        result = tool._parse_event_data(failing_input)
        print(f"Final result: {result}")
        
        expected = {
            "summary": "Meeting with Martin",
            "start": "2025-09-12T16:00:00+03:00",
            "end": "2025-09-12T17:00:00+03:00",
            "reminders": [{"method": "popup", "minutes": 30}]
        }
        
        if result == expected:
            print("✅ SUCCESS: Quasi-JSON parsing works correctly!")
            return True
        else:
            print(f"❌ MISMATCH: Expected {expected}, got {result}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_other_cases():
    """Test other quasi-JSON cases."""
    
    tool = GoogleCalendarTool(user=None, db=None, registry=None, user_access=None)
    
    test_cases = [
        # Simple case
        "{summary: Test Event}",
        # Multiple properties
        "{summary: Test, description: A test event}",
        # Nested array with objects
        "{attendees: [{email: test@example.com, status: accepted}]}",
        # Mixed quoted and unquoted
        '{"summary": Test, "start": 2025-01-01T10:00:00Z}',
    ]
    
    print("\nTesting additional quasi-JSON cases...")
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test_case}")
        try:
            result = tool._parse_event_data(test_case)
            print(f"✅ Parsed: {result}")
        except Exception as e:
            print(f"❌ Failed: {e}")
            return False
    
    return True


if __name__ == "__main__":
    print("Testing Google Calendar quasi-JSON parsing fix...")
    
    success1 = test_specific_failing_case()
    success2 = test_other_cases()
    
    if success1 and success2:
        print("\n🎉 All tests passed! The quasi-JSON parsing should work now.")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed.")
        sys.exit(1)
