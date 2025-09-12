"""
Google Calendar Tool for Personal Assistant.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging
import json

from app.agents.personal_assistant.tools.base import ExternalTool
from app.agents.personal_assistant.context_resolver import ContextResolver

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

        # Context resolution
        self._context_resolver = None
        self._user_message = None

    def set_context(self, context_resolver: ContextResolver, user_message: Optional[str] = None):
        """Set context resolver and user message for context-aware operations."""
        self._context_resolver = context_resolver
        self._user_message = user_message

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

        # Enhance parameters with context resolution if available
        if self._context_resolver and self._user_message:
            try:
                parameters = self._context_resolver.enhance_tool_parameters(
                    "google_calendar", parameters, self._user_message
                )
                logger.debug("Enhanced parameters with context resolution")
            except Exception as e:
                logger.warning(f"Context resolution failed: {str(e)}")

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

                return await self._delete_event(calendar_id, event_id, parameters)

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





    async def _list_events(self, calendar_id: str, time_range: Dict[str, Any]) -> Dict[str, Any]:
        """List calendar events."""
        try:
            # Parse time_range if it's a string (handle parameter processing edge cases)
            if isinstance(time_range, str):
                time_range = self._parse_time_range_string(time_range)

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
        """Create a new calendar event with pre-validated data."""
        try:
            # Parse event_data if it's a string (handle parameter processing edge cases)
            if isinstance(event_data, str):
                try:
                    event_data = self._parse_event_data(event_data)
                except ValueError as e:
                    return await self.handle_error(e, "Invalid event data format")

            # Validate required fields (additional safety check)
            if not event_data.get("summary"):
                return await self.handle_error(
                    ValueError("Event summary is required"),
                    "Missing event summary"
                )

            # Build event object for Google Calendar API
            event = {
                'summary': event_data.get('summary'),
                'description': event_data.get('description', ''),
                'location': event_data.get('location', ''),
                'start': self._format_datetime(event_data.get('start')),
                'end': self._format_datetime(event_data.get('end')),
            }

            # Add attendees if provided
            if event_data.get('attendees'):
                event['attendees'] = [
                    {'email': email} for email in event_data['attendees']
                ]

            # Add reminders if provided
            if event_data.get('reminders'):
                event['reminders'] = {
                    'useDefault': False,
                    'overrides': event_data['reminders']
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
                "message": f"Event '{event_data.get('summary')}' created successfully",
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

    async def _delete_event(self, calendar_id: str, event_id: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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

            # Generate context-aware confirmation message
            confirmation_message = f"Event '{event_summary}' deleted successfully"
            if self._context_resolver and self._user_message and parameters:
                context_message = self._context_resolver.generate_confirmation_message(
                    "google_calendar", parameters, "delete"
                )
                if context_message:
                    confirmation_message = context_message + f" The event '{event_summary}' has been deleted."

            return await self.create_success_response({
                "message": confirmation_message,
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
            # Parse time_range if it's a string (handle parameter processing edge cases)
            if isinstance(time_range, str):
                time_range = self._parse_time_range_string(time_range)

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

    def _parse_time_range_string(self, time_range_str: str) -> Dict[str, Any]:
        """Parse time_range string using regex extraction."""
        import re

        time_range_dict = {}

        # Extract start time
        start_match = re.search(r"start\s*:\s*([^,}]+)", time_range_str)
        if start_match:
            time_range_dict["start"] = start_match.group(1).strip().strip("'\"")

        # Extract end time
        end_match = re.search(r"end\s*:\s*([^,}]+)", time_range_str)
        if end_match:
            time_range_dict["end"] = end_match.group(1).strip().strip("'\"")

        # Extract max_results
        max_match = re.search(r"max_results\s*:\s*([0-9]+)", time_range_str)
        if max_match:
            try:
                time_range_dict["max_results"] = int(max_match.group(1))
            except ValueError:
                pass

        return time_range_dict

    def _parse_event_data(self, event_data: Any) -> Dict[str, Any]:
        """Parse event_data from various input formats (dict, JSON string, quasi-JSON)."""
        if isinstance(event_data, dict):
            return event_data

        if isinstance(event_data, str):
            # Try to parse as JSON first
            try:
                parsed = json.loads(event_data)
                if isinstance(parsed, dict):
                    return parsed
                else:
                    raise ValueError(f"Expected JSON object, got {type(parsed).__name__}")
            except json.JSONDecodeError:
                # Try quasi-JSON parsing
                try:
                    fixed_json = self._fix_quasi_json(event_data)
                    parsed = json.loads(fixed_json)
                    if isinstance(parsed, dict):
                        return parsed
                    else:
                        raise ValueError(f"Expected JSON object after quasi-JSON fix, got {type(parsed).__name__}")
                except json.JSONDecodeError as e:
                    raise ValueError(f"Could not parse event_data as JSON: {str(e)}")

        raise ValueError(f"event_data must be a dict or JSON string, got {type(event_data)}")

    def _fix_quasi_json(self, quasi_json: str) -> str:
        """Fix common quasi-JSON issues to make it valid JSON."""
        import re

        # Remove outer braces if present and re-add them
        quasi_json = quasi_json.strip()
        if quasi_json.startswith('{') and quasi_json.endswith('}'):
            quasi_json = quasi_json[1:-1]

        # First, protect datetime values by temporarily replacing them
        datetime_pattern = r'([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}[+\-][0-9]{2}:[0-9]{2})'
        datetime_placeholders = {}
        placeholder_counter = 0

        def replace_datetime(match):
            nonlocal placeholder_counter
            placeholder = f"__DATETIME_PLACEHOLDER_{placeholder_counter}__"
            datetime_placeholders[placeholder] = match.group(1)
            placeholder_counter += 1
            return placeholder

        fixed = re.sub(datetime_pattern, replace_datetime, quasi_json)

        # Add quotes around unquoted keys
        def quote_unquoted_keys(match):
            key = match.group(1)
            if not (key.startswith('"') and key.endswith('"')):
                return f'"{key}":'
            return match.group(0)

        fixed = re.sub(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*:', quote_unquoted_keys, fixed)

        # Add quotes around unquoted string values (but not numbers, booleans, arrays, or objects)
        def quote_unquoted_values(match):
            value = match.group(1).strip()
            # Don't quote if it's already quoted, a number, boolean, array, object, or our placeholder
            if (value.startswith('"') and value.endswith('"') or
                value.startswith('[') or value.startswith('{') or
                value.lower() in ['true', 'false', 'null'] or
                re.match(r'^-?\d+(\.\d+)?$', value) or
                value.startswith('__DATETIME_PLACEHOLDER_')):
                return match.group(0)
            return f': "{value}"'

        fixed = re.sub(r':\s*([^",\[\]{}]+?)(?=\s*[,}])', quote_unquoted_values, fixed)

        # Remove trailing commas
        fixed = re.sub(r',\s*([}\]])', r'\1', fixed)

        # Restore datetime values with quotes
        for placeholder, datetime_value in datetime_placeholders.items():
            fixed = fixed.replace(placeholder, f'"{datetime_value}"')

        # Re-add outer braces
        return '{' + fixed + '}'


