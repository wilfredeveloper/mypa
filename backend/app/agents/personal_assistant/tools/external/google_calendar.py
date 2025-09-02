"""
Google Calendar Tool for Personal Assistant.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging

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

    async def execute(self, parameters: Dict[str, Any]) -> Any:
        """
        Execute Google Calendar operations.

        Parameters:
            action (str): Action to perform - 'list', 'create', 'update', 'delete', 'availability'
            event_data (dict): Event data for create/update operations
            event_id (str): Event ID for update/delete operations
            time_range (dict): Time range for list/availability operations
            calendar_id (str, optional): Calendar ID (defaults to primary)

        Returns:
            Calendar operation result
        """
        if not await self.is_authorized():
            return await self.handle_error(
                ValueError("Google Calendar access not authorized"),
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
        """Initialize Google Calendar API service."""
        try:
            # This is a placeholder for the actual Google Calendar API initialization
            # In the OAuth implementation phase, this will be properly implemented
            # with actual Google API client setup

            # For now, we'll simulate the service initialization
            self.calendar_service = MockGoogleCalendarService()

            logger.info("Google Calendar service initialized")

        except Exception as e:
            logger.error(f"Failed to initialize Google Calendar service: {str(e)}")
            raise

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

    async def _create_event(self, calendar_id: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new calendar event."""
        try:
            # Validate required fields
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

    async def _update_event(self, calendar_id: str, event_id: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing calendar event."""
        try:
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

            if event_data.get('summary'):
                updated_event['summary'] = event_data['summary']
            if event_data.get('description') is not None:
                updated_event['description'] = event_data['description']
            if event_data.get('location') is not None:
                updated_event['location'] = event_data['location']
            if event_data.get('start'):
                updated_event['start'] = self._format_datetime(event_data['start'])
            if event_data.get('end'):
                updated_event['end'] = self._format_datetime(event_data['end'])

            # Update attendees if provided
            if event_data.get('attendees') is not None:
                updated_event['attendees'] = [
                    {'email': email} for email in event_data['attendees']
                ]

            # Update reminders if provided
            if event_data.get('reminders') is not None:
                updated_event['reminders'] = {
                    'useDefault': False,
                    'overrides': event_data['reminders']
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


class MockGoogleCalendarService:
    """Mock Google Calendar service for development/testing."""

    def __init__(self):
        self.events = {}  # event_id -> event_data
        self.event_counter = 1

    async def list_events(self, calendar_id: str, time_min: str, time_max: str,
                         max_results: int = 10, single_events: bool = True,
                         order_by: str = 'startTime') -> Dict[str, Any]:
        """Mock list events."""
        # Return sample events for demonstration
        sample_events = [
            {
                'id': 'sample_event_1',
                'summary': 'Team Meeting',
                'description': 'Weekly team sync',
                'start': {'dateTime': '2024-01-15T10:00:00Z'},
                'end': {'dateTime': '2024-01-15T11:00:00Z'},
                'location': 'Conference Room A',
                'attendees': [
                    {'email': 'colleague@example.com', 'responseStatus': 'accepted'}
                ],
                'reminders': {'useDefault': True},
                'created': '2024-01-10T09:00:00Z',
                'updated': '2024-01-10T09:00:00Z'
            }
        ]

        return {'items': sample_events}

    async def create_event(self, calendar_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
        """Mock create event."""
        event_id = f"mock_event_{self.event_counter}"
        self.event_counter += 1

        created_event = event.copy()
        created_event.update({
            'id': event_id,
            'htmlLink': f'https://calendar.google.com/event?eid={event_id}',
            'created': datetime.utcnow().isoformat() + 'Z',
            'updated': datetime.utcnow().isoformat() + 'Z'
        })

        self.events[event_id] = created_event
        return created_event

    async def get_event(self, calendar_id: str, event_id: str) -> Optional[Dict[str, Any]]:
        """Mock get event."""
        return self.events.get(event_id)

    async def update_event(self, calendar_id: str, event_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
        """Mock update event."""
        if event_id not in self.events:
            raise ValueError(f"Event not found: {event_id}")

        updated_event = event.copy()
        updated_event['updated'] = datetime.utcnow().isoformat() + 'Z'

        self.events[event_id] = updated_event
        return updated_event

    async def delete_event(self, calendar_id: str, event_id: str) -> None:
        """Mock delete event."""
        if event_id in self.events:
            del self.events[event_id]