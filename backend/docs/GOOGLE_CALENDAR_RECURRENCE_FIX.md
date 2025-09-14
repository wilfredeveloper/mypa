# Google Calendar Recurrence Fix

## Issue Summary

The Google Calendar tool was failing when trying to update/create events with recurrence data due to:

1. **JSON Format Error**: The `event_data` parameter contained invalid JSON format like `{recurrence: [RRULE:FREQ=DAILY]}` instead of proper JSON with quoted property names
2. **Missing Recurrence Support**: The tool didn't handle recurrence rules in event creation/updates
3. **Quasi-JSON Parser Issues**: The parser couldn't handle RRULE patterns within quasi-JSON format

## Root Cause Analysis

### 1. JSON Format Issues
- Property names were not enclosed in double quotes (`recurrence` should be `"recurrence"`)
- RRULE values needed proper string formatting within arrays
- The quasi-JSON parser didn't handle RRULE patterns correctly

### 2. Missing Recurrence Support
- The `_create_event` method didn't include recurrence rules in the Google Calendar API event object
- The `_update_event` method also lacked recurrence support
- No validation or processing of recurrence data

### 3. Context Resolver Issues
- The context resolver enhancement process could generate malformed quasi-JSON
- No specific handling for recurrence data in parameter enhancement

## Fixes Implemented

### 1. Enhanced Quasi-JSON Parser (`_fix_quasi_json`)

**Added RRULE Pattern Protection:**
```python
# Protect RRULE patterns by temporarily replacing them
rrule_pattern = r'(RRULE:[A-Z0-9=;,]+)'
rrule_placeholders = {}

def replace_rrule(match):
    nonlocal placeholder_counter
    placeholder = f"__RRULE_PLACEHOLDER_{placeholder_counter}__"
    rrule_placeholders[placeholder] = match.group(1)
    placeholder_counter += 1
    return placeholder

fixed = re.sub(rrule_pattern, replace_rrule, fixed)
```

**Updated Value Quoting Logic:**
```python
# Don't quote if it's already quoted, a number, boolean, array, object, or our placeholders
if (value.startswith('"') and value.endswith('"') or
    value.startswith('[') or value.startswith('{') or
    value.lower() in ['true', 'false', 'null'] or
    re.match(r'^-?\d+(\.\d+)?$', value) or
    value.startswith('__DATETIME_PLACEHOLDER_') or
    value.startswith('__RRULE_PLACEHOLDER_')):  # Added RRULE protection
    return match.group(0)
```

**Added RRULE Restoration:**
```python
# Restore RRULE values with quotes
for placeholder, rrule_value in rrule_placeholders.items():
    fixed = fixed.replace(placeholder, f'"{rrule_value}"')
```

### 2. Added Recurrence Support to Event Creation

**In `_create_event` method:**
```python
# Add recurrence if provided
if event_data.get('recurrence'):
    event['recurrence'] = event_data['recurrence']
```

**In `_update_event` method:**
```python
# Update recurrence if provided
if parsed_event_data.get('recurrence') is not None:
    updated_event['recurrence'] = parsed_event_data['recurrence']
```

### 3. Updated BAML Prompts and Configuration

**Enhanced BAML prompt with recurrence examples:**
```baml
Recurring event (daily):
{
  "name": "google_calendar", 
  "parameters": {
    "action": "create",
    "event_data": "{\"summary\": \"Daily Standup\", \"start\": \"2025-01-15T09:00:00Z\", \"end\": \"2025-01-15T09:30:00Z\", \"recurrence\": [\"RRULE:FREQ=DAILY\"]}"
  }
}
```

**Updated agent configuration with recurrence examples:**
```python
- Correct (create recurring event):
  {
    "name": "google_calendar",
    "parameters": {
      "action": "create",
      "calendar_id": "primary",
      "event_data": {
        "summary": "Daily Standup",
        "start": "2025-09-15T09:00:00+00:00",
        "end": "2025-09-15T09:30:00+00:00",
        "recurrence": ["RRULE:FREQ=DAILY"]
      }
    }
  }
```

## Test Results

### Original Failing Case
✅ **FIXED**: `{recurrence: [RRULE:FREQ=DAILY]}` now parses correctly to `{"recurrence": ["RRULE:FREQ=DAILY"]}`

### Comprehensive Test Coverage
✅ Valid JSON with recurrence  
✅ JSON string with recurrence  
✅ Quasi-JSON with recurrence (original failing case)  
✅ Complex quasi-JSON with advanced recurrence rules  
✅ Mixed quasi-JSON with reminders and recurrence  
✅ Direct quasi-JSON fix functionality  
✅ Event building includes recurrence correctly  

### Supported Recurrence Patterns
✅ Daily: `RRULE:FREQ=DAILY`  
✅ Weekly: `RRULE:FREQ=WEEKLY`  
✅ Monthly: `RRULE:FREQ=MONTHLY`  
✅ With count: `RRULE:FREQ=WEEKLY;COUNT=4`  
✅ Specific days: `RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR`  
✅ Complex patterns: `RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR;COUNT=10`  

## Validation

### JSON Parsing
- ✅ Property names are properly quoted
- ✅ RRULE values are correctly formatted as strings in arrays
- ✅ No more JSON parsing exceptions
- ✅ Backward compatibility maintained

### Google Calendar API Compatibility
- ✅ Recurrence format matches Google Calendar API requirements
- ✅ Event creation includes recurrence rules
- ✅ Event updates preserve recurrence rules
- ✅ All existing functionality preserved

### Error Handling
- ✅ Invalid JSON still raises appropriate errors
- ✅ Malformed RRULE patterns are handled gracefully
- ✅ Existing error handling paths unchanged

## Files Modified

1. `backend/app/agents/personal_assistant/tools/external/google_calendar.py`
   - Enhanced `_fix_quasi_json` method with RRULE pattern protection
   - Added recurrence support to `_create_event` and `_update_event` methods

2. `backend/baml_src/personal_assistant.baml`
   - Added recurrence examples to BAML prompts

3. `backend/app/agents/personal_assistant/config.py`
   - Added recurring event examples to agent configuration

## Testing Files Created

1. `backend/test_recurrence_fix.py` - Comprehensive recurrence testing
2. `backend/test_original_failing_case.py` - Specific failing case validation

The fix ensures that daily recurring events (and all other recurrence patterns) can now be created successfully through the Google Calendar tool, resolving the JSON formatting issues that were preventing proper event creation.
