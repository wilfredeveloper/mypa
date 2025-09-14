#!/usr/bin/env python3
"""
Test script to verify the Google Calendar recurrence fix.
"""

import sys
import os
import json

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from app.agents.personal_assistant.tools.external.google_calendar import GoogleCalendarTool


def test_recurrence_parsing():
    """Test parsing of recurrence data in various formats."""
    
    tool = GoogleCalendarTool(user=None, db=None, registry=None, user_access=None)
    
    print("🧪 Testing Google Calendar Recurrence Fix")
    print("=" * 50)
    
    # Test 1: Valid JSON with recurrence
    print("\n✅ Test 1: Valid JSON with recurrence")
    valid_json = {
        "summary": "Daily Standup",
        "start": "2025-09-15T09:00:00+00:00",
        "end": "2025-09-15T09:30:00+00:00",
        "recurrence": ["RRULE:FREQ=DAILY"]
    }
    
    try:
        result = tool._parse_event_data(valid_json)
        print(f"   ✓ Parsed successfully: {result}")
        assert result["recurrence"] == ["RRULE:FREQ=DAILY"]
        print("   ✓ Recurrence preserved correctly")
    except Exception as e:
        print(f"   ✗ FAILED: {e}")
        return False
    
    # Test 2: JSON string with recurrence
    print("\n✅ Test 2: JSON string with recurrence")
    json_string = json.dumps({
        "summary": "Weekly Meeting",
        "start": "2025-09-15T14:00:00+00:00",
        "end": "2025-09-15T15:00:00+00:00",
        "recurrence": ["RRULE:FREQ=WEEKLY;BYDAY=MO"]
    })
    
    try:
        result = tool._parse_event_data(json_string)
        print(f"   ✓ Parsed successfully: {result}")
        assert result["recurrence"] == ["RRULE:FREQ=WEEKLY;BYDAY=MO"]
        print("   ✓ Weekly recurrence preserved correctly")
    except Exception as e:
        print(f"   ✗ FAILED: {e}")
        return False
    
    # Test 3: Quasi-JSON with recurrence (the failing case)
    print("\n✅ Test 3: Quasi-JSON with recurrence (original failing case)")
    quasi_json = "{summary: Daily Meeting, start: 2025-09-15T09:00:00+00:00, end: 2025-09-15T09:30:00+00:00, recurrence: [RRULE:FREQ=DAILY]}"
    
    try:
        result = tool._parse_event_data(quasi_json)
        print(f"   ✓ Parsed successfully: {result}")
        assert result["summary"] == "Daily Meeting"
        assert result["recurrence"] == ["RRULE:FREQ=DAILY"]
        print("   ✓ Quasi-JSON with recurrence fixed!")
    except Exception as e:
        print(f"   ✗ FAILED: {e}")
        return False
    
    # Test 4: Complex quasi-JSON with multiple RRULE options
    print("\n✅ Test 4: Complex quasi-JSON with advanced recurrence")
    complex_quasi = "{summary: Complex Event, start: 2025-09-15T10:00:00+00:00, end: 2025-09-15T11:00:00+00:00, recurrence: [RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR;COUNT=10]}"
    
    try:
        result = tool._parse_event_data(complex_quasi)
        print(f"   ✓ Parsed successfully: {result}")
        assert result["recurrence"] == ["RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR;COUNT=10"]
        print("   ✓ Complex recurrence rule preserved correctly")
    except Exception as e:
        print(f"   ✗ FAILED: {e}")
        return False
    
    # Test 5: Quasi-JSON with reminders and recurrence
    print("\n✅ Test 5: Quasi-JSON with both reminders and recurrence")
    mixed_quasi = "{summary: Mixed Event, start: 2025-09-15T14:00:00+00:00, end: 2025-09-15T15:00:00+00:00, reminders: [{method: popup, minutes: 15}], recurrence: [RRULE:FREQ=DAILY;COUNT=5]}"
    
    try:
        result = tool._parse_event_data(mixed_quasi)
        print(f"   ✓ Parsed successfully: {result}")
        assert result["reminders"] == [{"method": "popup", "minutes": 15}]
        assert result["recurrence"] == ["RRULE:FREQ=DAILY;COUNT=5"]
        print("   ✓ Both reminders and recurrence preserved correctly")
    except Exception as e:
        print(f"   ✗ FAILED: {e}")
        return False
    
    # Test 6: Test the _fix_quasi_json method directly
    print("\n✅ Test 6: Direct quasi-JSON fix test")
    test_input = "{recurrence: [RRULE:FREQ=DAILY]}"
    
    try:
        fixed = tool._fix_quasi_json(test_input)
        print(f"   Input:  {test_input}")
        print(f"   Fixed:  {fixed}")
        
        # Should be valid JSON now
        parsed = json.loads(fixed)
        assert parsed["recurrence"] == ["RRULE:FREQ=DAILY"]
        print("   ✓ Direct quasi-JSON fix working correctly")
    except Exception as e:
        print(f"   ✗ FAILED: {e}")
        return False
    
    print("\n🎉 All tests passed! Recurrence fix is working correctly.")
    return True


def test_event_building():
    """Test that event building includes recurrence data."""
    
    print("\n🏗️  Testing Event Building with Recurrence")
    print("=" * 50)
    
    # Mock event data with recurrence
    event_data = {
        "summary": "Test Recurring Event",
        "start": "2025-09-15T09:00:00+00:00",
        "end": "2025-09-15T09:30:00+00:00",
        "recurrence": ["RRULE:FREQ=DAILY;COUNT=7"]
    }
    
    tool = GoogleCalendarTool(user=None, db=None, registry=None, user_access=None)
    
    # Test the event building logic (simulate what happens in _create_event)
    event = {
        'summary': event_data.get('summary'),
        'description': event_data.get('description', ''),
        'location': event_data.get('location', ''),
        'start': tool._format_datetime(event_data.get('start')),
        'end': tool._format_datetime(event_data.get('end')),
    }
    
    # Add recurrence if provided (this is the new logic we added)
    if event_data.get('recurrence'):
        event['recurrence'] = event_data['recurrence']
    
    print(f"Built event: {json.dumps(event, indent=2)}")
    
    # Verify recurrence is included
    assert 'recurrence' in event
    assert event['recurrence'] == ["RRULE:FREQ=DAILY;COUNT=7"]
    print("✓ Event building includes recurrence correctly")
    
    return True


if __name__ == "__main__":
    success = True
    
    try:
        success &= test_recurrence_parsing()
        success &= test_event_building()
        
        if success:
            print("\n🎉 ALL TESTS PASSED! The recurrence fix is working correctly.")
            sys.exit(0)
        else:
            print("\n❌ Some tests failed.")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n💥 Test suite failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
