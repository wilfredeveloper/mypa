"""
Google Calendar Tool for Personal Assistant.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging
import json

from app.agents.personal_assistant.tools.base import ExternalTool

logger = logging.getLogger(__name__)


class GoogleCalendarTool(ExternalTool):
    """
    Google Calendar integration tool for Personal Assistant.

    This tool provides:
    - List calendar events with filtering
    - Create new calendar events
    - Update existing events
    - Delete events
    - Check availability
    - Set reminders and notifications
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.calendar_service = None

        # Default calendar settings
        self.default_calendar_id = "primary"
        self.default_timezone = "UTC"

    async def is_authorized(self) -> bool:
        """Override to ensure tokens exist before use (refresh or access)."""
        try:
            if not self.user_access or not self.user_access.is_authorized:
                return False
            cfg = (self.user_access.config_data or {}).get("google_calendar_oauth", {})
            # Accept either refresh_token or current access token
            return bool(cfg.get("refresh_token") or cfg.get("token"))
        except Exception:
            return False

    async def execute(self, parameters: Dict[str, Any]) -> Any:
        """
        Execute Google Calendar operations.

        Parameters:
            action (str): Action to perform - 'list', 'create', 'update', 'delete', 'availability'
            event_data (dict|str): Event data for create/update operations (accepts dict or JSON string)
            event_id (str): Event ID for update/delete operations
            time_range (dict): Time range for list/availability operations
            calendar_id (str, optional): Calendar ID (defaults to primary)

        Returns:
            Calendar operation result
        """
        if not await self.is_authorized():
            return await self.handle_error(
                ValueError(
                    "Google Calendar not authorized. Please authorize in the app (click 'Authorize Google Calendar') "
                    "or visit /api/v1/google/oauth/start to begin the OAuth flow."
                ),
                "Authorization required"
            )

        if not self.validate_parameters(parameters):
            return await self.handle_error(
                ValueError("Invalid parameters"),
                "Parameter validation failed"
            )

        action = parameters.get("action", "list").lower()

        try:
            # Initialize calendar service if needed
            if not self.calendar_service:
                await self._initialize_calendar_service()

            if action == "list":
                time_range = parameters.get("time_range", {})
                calendar_id = parameters.get("calendar_id", self.default_calendar_id)
                return await self._list_events(calendar_id, time_range)

            elif action == "create":
                event_data = parameters.get("event_data")
                calendar_id = parameters.get("calendar_id", self.default_calendar_id)

                if not event_data:
                    return await self.handle_error(
                        ValueError("event_data is required for 'create' action"),
                        "Missing event data"
                    )

                return await self._create_event(calendar_id, event_data)

            elif action == "update":
                event_id = parameters.get("event_id")
                event_data = parameters.get("event_data")
                calendar_id = parameters.get("calendar_id", self.default_calendar_id)

                if not event_id or not event_data:
                    return await self.handle_error(
                        ValueError("event_id and event_data are required for 'update' action"),
                        "Missing event ID or data"
                    )

                return await self._update_event(calendar_id, event_id, event_data)

            elif action == "delete":
                event_id = parameters.get("event_id")
                calendar_id = parameters.get("calendar_id", self.default_calendar_id)

                if not event_id:
                    return await self.handle_error(
                        ValueError("event_id is required for 'delete' action"),
                        "Missing event ID"
                    )

                return await self._delete_event(calendar_id, event_id)

            elif action == "availability":
                time_range = parameters.get("time_range", {})
                calendar_id = parameters.get("calendar_id", self.default_calendar_id)
                return await self._check_availability(calendar_id, time_range)

            else:
                return await self.handle_error(
                    ValueError(f"Unknown action: {action}"),
                    "Invalid action"
                )

        except Exception as e:
            return await self.handle_error(e, f"Action: {action}")

    async def _initialize_calendar_service(self) -> None:
        """Initialize Google Calendar API service using real Google APIs."""
        try:
            from app.services.google_calendar_service import GoogleCalendarAPI
            # Use per-user access from the tool instance
            self.calendar_service = GoogleCalendarAPI(self.db, self.user_access)
            logger.info("Google Calendar service initialized (Google API client)")
        except Exception as e:
            logger.error(f"Failed to initialize Google Calendar service: {str(e)}")
            raise

    def _parse_event_data(self, event_data: Any) -> Dict[str, Any]:
        """
        Parse event_data parameter, handling both dictionary and JSON string inputs.
        Also handles quasi-JSON format that agents sometimes generate.

        Args:
            event_data: Either a dictionary or JSON string containing event data

        Returns:
            Dictionary containing parsed event data

        Raises:
            ValueError: If event_data cannot be parsed or is invalid
        """
        if event_data is None:
            raise ValueError("event_data cannot be None")

        # If it's already a dictionary, return as-is
        if isinstance(event_data, dict):
            return event_data

        # If it's a string, try to parse as JSON
        if isinstance(event_data, str):
            # First try standard JSON parsing
            try:
                parsed_data = json.loads(event_data)
                if not isinstance(parsed_data, dict):
                    raise ValueError(f"Parsed event_data must be a dictionary, got {type(parsed_data)}")
                return parsed_data
            except json.JSONDecodeError:
                # If standard JSON fails, try to fix common quasi-JSON issues
                try:
                    fixed_json = self._fix_quasi_json(event_data)
                    parsed_data = json.loads(fixed_json)
                    if not isinstance(parsed_data, dict):
                        raise ValueError(f"Parsed event_data must be a dictionary, got {type(parsed_data)}")
                    return parsed_data
                except (json.JSONDecodeError, Exception) as e:
                    raise ValueError(f"Invalid JSON in event_data: {str(e)}")

        # For any other type, try to convert to string and parse
        try:
            json_str = str(event_data)
            parsed_data = json.loads(json_str)
            if not isinstance(parsed_data, dict):
                raise ValueError(f"Parsed event_data must be a dictionary, got {type(parsed_data)}")
            return parsed_data
        except (json.JSONDecodeError, TypeError) as e:
            raise ValueError(f"Cannot parse event_data of type {type(event_data)}: {str(e)}")

    def _fix_quasi_json(self, quasi_json: str) -> str:
        """
        Fix common quasi-JSON issues like unquoted property names and values.

        Args:
            quasi_json: String that looks like JSON but may have syntax issues

        Returns:
            Fixed JSON string
        """
        import re

        # Remove any leading/trailing whitespace
        fixed = quasi_json.strip()

        # Step 1: Fix unquoted property names (e.g., {summary: -> {"summary":)
        fixed = re.sub(r'([{,\[]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', fixed)

        # Step 2: Fix unquoted string values
        # We need to be more careful here to handle nested structures

        # First, let's handle simple string values after colons
        # Pattern: "key": unquoted_value where unquoted_value should be quoted
        def quote_simple_values(text):
            # Find all "key": value patterns
            pattern = r'("[^"]+"\s*:\s*)([^,}\]\[{]+?)(?=\s*[,}\]])'

            def replacer(match):
                key_part = match.group(1)
                value = match.group(2).strip()

                # Don't quote if already quoted, or if it's a number, boolean, null
                if (value.startswith('"') or value.startswith("'") or
                    value.lower() in ['true', 'false', 'null'] or
                    re.match(r'^-?\d+(\.\d+)?([eE][+-]?\d+)?$', value)):
                    return match.group(0)

                # Quote the value
                return f'{key_part}"{value}"'

            return re.sub(pattern, replacer, text)

        # Apply simple value quoting
        fixed = quote_simple_values(fixed)

        # Step 3: Handle array elements that need quoting
        # Pattern: [unquoted_value, or ,unquoted_value, or ,unquoted_value]
        def quote_array_values(text):
            # Find array contexts and quote unquoted string values
            def array_replacer(match):
                array_content = match.group(1)

                # Split by comma and process each element
                elements = []
                current_element = ""
                bracket_depth = 0
                brace_depth = 0
                in_quotes = False

                for char in array_content:
                    if char == '"' and (not current_element or current_element[-1] != '\\'):
                        in_quotes = not in_quotes
                    elif not in_quotes:
                        if char == '[':
                            bracket_depth += 1
                        elif char == ']':
                            bracket_depth -= 1
                        elif char == '{':
                            brace_depth += 1
                        elif char == '}':
                            brace_depth -= 1
                        elif char == ',' and bracket_depth == 0 and brace_depth == 0:
                            elements.append(current_element.strip())
                            current_element = ""
                            continue

                    current_element += char

                if current_element.strip():
                    elements.append(current_element.strip())

                # Process each element
                processed_elements = []
                for element in elements:
                    element = element.strip()
                    if element:
                        # If it's an object or array, recursively process
                        if element.startswith('{') or element.startswith('['):
                            processed_elements.append(element)
                        # If it's already quoted, a number, boolean, or null, keep as-is
                        elif (element.startswith('"') or element.startswith("'") or
                              element.lower() in ['true', 'false', 'null'] or
                              re.match(r'^-?\d+(\.\d+)?([eE][+-]?\d+)?$', element)):
                            processed_elements.append(element)
                        # Otherwise, quote it
                        else:
                            processed_elements.append(f'"{element}"')

                return '[' + ', '.join(processed_elements) + ']'

            # Apply to arrays
            return re.sub(r'\[([^\[\]]*)\]', array_replacer, text)

        # Apply array value quoting
        fixed = quote_array_values(fixed)

        return fixed

    async def _list_events(self, calendar_id: str, time_range: Dict[str, Any]) -> Dict[str, Any]:
        """List calendar events."""
        try:
            # Parse time range
            start_time = time_range.get("start")
            end_time = time_range.get("end")
            max_results = time_range.get("max_results", 10)

            # Default to next 7 days if no time range specified
            if not start_time:
                start_time = datetime.utcnow().isoformat() + 'Z'
            if not end_time:
                end_dt = datetime.utcnow() + timedelta(days=7)
                end_time = end_dt.isoformat() + 'Z'

            # Call Google Calendar API (mocked for now)
            events_result = await self.calendar_service.list_events(
                calendar_id=calendar_id,
                time_min=start_time,
                time_max=end_time,
                max_results=max_results,
                single_events=True,
                order_by='startTime'
            )

            events = events_result.get('items', [])

            # Format events for response
            formatted_events = []
            for event in events:
                formatted_event = {
                    "id": event.get('id'),
                    "summary": event.get('summary', 'No title'),
                    "description": event.get('description', ''),
                    "start": event.get('start', {}).get('dateTime') or event.get('start', {}).get('date'),
                    "end": event.get('end', {}).get('dateTime') or event.get('end', {}).get('date'),
                    "location": event.get('location', ''),
                    "attendees": [
                        {
                            "email": attendee.get('email'),
                            "status": attendee.get('responseStatus', 'needsAction')
                        }
                        for attendee in event.get('attendees', [])
                    ],
                    "reminders": event.get('reminders', {}),
                    "created": event.get('created'),
                    "updated": event.get('updated')
                }
                formatted_events.append(formatted_event)

            return await self.create_success_response({
                "events": formatted_events,
                "total_count": len(formatted_events),
                "time_range": {
                    "start": start_time,
                    "end": end_time
                },
                "calendar_id": calendar_id,
                "operation": "list"
            })

        except Exception as e:
            return await self.handle_error(e, "Listing calendar events")

    async def _create_event(self, calendar_id: str, event_data: Any) -> Dict[str, Any]:
        """Create a new calendar event."""
        try:
            # Parse event_data (handles both dict and JSON string inputs)
            try:
                parsed_event_data = self._parse_event_data(event_data)
            except ValueError as e:
                return await self.handle_error(e, "Invalid event data format")

            # Validate required fields
            if not parsed_event_data.get("summary"):
                return await self.handle_error(
                    ValueError("Event summary is required"),
                    "Missing event summary"
                )

            # Build event object for Google Calendar API
            event = {
                'summary': parsed_event_data.get('summary'),
                'description': parsed_event_data.get('description', ''),
                'location': parsed_event_data.get('location', ''),
                'start': self._format_datetime(parsed_event_data.get('start')),
                'end': self._format_datetime(parsed_event_data.get('end')),
            }

            # Add attendees if provided
            if parsed_event_data.get('attendees'):
                event['attendees'] = [
                    {'email': email} for email in parsed_event_data['attendees']
                ]

            # Add reminders if provided
            if parsed_event_data.get('reminders'):
                event['reminders'] = {
                    'useDefault': False,
                    'overrides': parsed_event_data['reminders']
                }
            else:
                event['reminders'] = {'useDefault': True}

            # Create event via Google Calendar API (mocked for now)
            created_event = await self.calendar_service.create_event(
                calendar_id=calendar_id,
                event=event
            )

            return await self.create_success_response({
                "event": {
                    "id": created_event.get('id'),
                    "summary": created_event.get('summary'),
                    "start": created_event.get('start', {}).get('dateTime'),
                    "end": created_event.get('end', {}).get('dateTime'),
                    "html_link": created_event.get('htmlLink')
                },
                "message": f"Event '{parsed_event_data.get('summary')}' created successfully",
                "operation": "create"
            })

        except Exception as e:
            return await self.handle_error(e, "Creating calendar event")

    async def _update_event(self, calendar_id: str, event_id: str, event_data: Any) -> Dict[str, Any]:
        """Update an existing calendar event."""
        try:
            # Parse event_data (handles both dict and JSON string inputs)
            try:
                parsed_event_data = self._parse_event_data(event_data)
            except ValueError as e:
                return await self.handle_error(e, "Invalid event data format")

            # Get existing event first
            existing_event = await self.calendar_service.get_event(
                calendar_id=calendar_id,
                event_id=event_id
            )

            if not existing_event:
                return await self.handle_error(
                    ValueError(f"Event not found: {event_id}"),
                    "Event not found"
                )

            # Update event fields
            updated_event = existing_event.copy()

            if parsed_event_data.get('summary'):
                updated_event['summary'] = parsed_event_data['summary']
            if parsed_event_data.get('description') is not None:
                updated_event['description'] = parsed_event_data['description']
            if parsed_event_data.get('location') is not None:
                updated_event['location'] = parsed_event_data['location']
            if parsed_event_data.get('start'):
                updated_event['start'] = self._format_datetime(parsed_event_data['start'])
            if parsed_event_data.get('end'):
                updated_event['end'] = self._format_datetime(parsed_event_data['end'])

            # Update attendees if provided
            if parsed_event_data.get('attendees') is not None:
                updated_event['attendees'] = [
                    {'email': email} for email in parsed_event_data['attendees']
                ]

            # Update reminders if provided
            if parsed_event_data.get('reminders') is not None:
                updated_event['reminders'] = {
                    'useDefault': False,
                    'overrides': parsed_event_data['reminders']
                }

            # Update event via Google Calendar API
            result = await self.calendar_service.update_event(
                calendar_id=calendar_id,
                event_id=event_id,
                event=updated_event
            )

            return await self.create_success_response({
                "event": {
                    "id": result.get('id'),
                    "summary": result.get('summary'),
                    "start": result.get('start', {}).get('dateTime'),
                    "end": result.get('end', {}).get('dateTime'),
                    "updated": result.get('updated')
                },
                "message": f"Event '{result.get('summary')}' updated successfully",
                "operation": "update"
            })

        except Exception as e:
            return await self.handle_error(e, f"Updating calendar event: {event_id}")

    async def _delete_event(self, calendar_id: str, event_id: str) -> Dict[str, Any]:
        """Delete a calendar event."""
        try:
            # Get event details before deletion for confirmation
            event = await self.calendar_service.get_event(
                calendar_id=calendar_id,
                event_id=event_id
            )

            if not event:
                return await self.handle_error(
                    ValueError(f"Event not found: {event_id}"),
                    "Event not found"
                )

            event_summary = event.get('summary', 'Untitled Event')

            # Delete event via Google Calendar API
            await self.calendar_service.delete_event(
                calendar_id=calendar_id,
                event_id=event_id
            )

            return await self.create_success_response({
                "message": f"Event '{event_summary}' deleted successfully",
                "deleted_event": {
                    "id": event_id,
                    "summary": event_summary
                },
                "operation": "delete"
            })

        except Exception as e:
            return await self.handle_error(e, f"Deleting calendar event: {event_id}")

    async def _check_availability(self, calendar_id: str, time_range: Dict[str, Any]) -> Dict[str, Any]:
        """Check availability for a given time range."""
        try:
            start_time = time_range.get("start")
            end_time = time_range.get("end")

            if not start_time or not end_time:
                return await self.handle_error(
                    ValueError("Both start and end times are required for availability check"),
                    "Missing time range"
                )

            # Get events in the specified time range
            events_result = await self.calendar_service.list_events(
                calendar_id=calendar_id,
                time_min=start_time,
                time_max=end_time,
                single_events=True,
                order_by='startTime'
            )

            events = events_result.get('items', [])

            # Check for conflicts
            conflicts = []
            for event in events:
                # Skip all-day events and events marked as free
                if (event.get('start', {}).get('date') or
                    event.get('transparency') == 'transparent'):
                    continue

                conflicts.append({
                    "id": event.get('id'),
                    "summary": event.get('summary', 'No title'),
                    "start": event.get('start', {}).get('dateTime'),
                    "end": event.get('end', {}).get('dateTime')
                })

            is_available = len(conflicts) == 0

            return await self.create_success_response({
                "available": is_available,
                "time_range": {
                    "start": start_time,
                    "end": end_time
                },
                "conflicts": conflicts,
                "conflict_count": len(conflicts),
                "operation": "availability"
            })

        except Exception as e:
            return await self.handle_error(e, "Checking availability")

    def _format_datetime(self, dt_input: Any) -> Dict[str, str]:
        """Format datetime for Google Calendar API."""
        if not dt_input:
            return {}

        if isinstance(dt_input, str):
            # Assume ISO format string
            return {'dateTime': dt_input, 'timeZone': self.default_timezone}
        elif isinstance(dt_input, dict):
            # Already formatted
            return dt_input
        elif isinstance(dt_input, datetime):
            # Convert datetime object
            return {
                'dateTime': dt_input.isoformat(),
                'timeZone': self.default_timezone
            }
        else:
            # Try to convert to string
            return {'dateTime': str(dt_input), 'timeZone': self.default_timezone}


