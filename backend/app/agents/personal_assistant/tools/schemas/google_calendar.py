"""
JSON Schema definition for Google Calendar tool parameters.

This schema defines the structure and validation rules for all
Google Calendar tool operations including create, list, update,
delete, and availability checking.
"""

GOOGLE_CALENDAR_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["list", "create", "update", "delete", "availability"],
            "description": "The action to perform on the calendar"
        },
        "calendar_id": {
            "type": "string",
            "default": "primary",
            "description": "The calendar ID to operate on"
        },
        "event_data": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 1024,
                    "description": "Event title/summary"
                },
                "description": {
                    "type": "string",
                    "maxLength": 8192,
                    "description": "Event description"
                },
                "start": {
                    "type": "string",
                    "format": "date-time",
                    "description": "Event start time in ISO 8601 format"
                },
                "end": {
                    "type": "string",
                    "format": "date-time",
                    "description": "Event end time in ISO 8601 format"
                },
                "location": {
                    "type": "string",
                    "maxLength": 1024,
                    "description": "Event location"
                },
                "attendees": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "email": {
                                "type": "string",
                                "format": "email",
                                "description": "Attendee email address"
                            },
                            "displayName": {
                                "type": "string",
                                "description": "Attendee display name"
                            },
                            "optional": {
                                "type": "boolean",
                                "default": False,
                                "description": "Whether attendance is optional"
                            }
                        },
                        "required": ["email"],
                        "additionalProperties": False
                    },
                    "maxItems": 100,
                    "description": "List of event attendees"
                },
                "reminders": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "method": {
                                "type": "string",
                                "enum": ["popup", "email"],
                                "description": "Reminder method"
                            },
                            "minutes": {
                                "type": "integer",
                                "minimum": 0,
                                "maximum": 40320,
                                "description": "Minutes before event to remind"
                            }
                        },
                        "required": ["method", "minutes"],
                        "additionalProperties": False
                    },
                    "maxItems": 5,
                    "description": "Event reminders"
                },
                "recurrence": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "pattern": "^RRULE:",
                        "description": "RRULE recurrence pattern"
                    },
                    "maxItems": 1,
                    "description": "Recurrence rules for repeating events"
                },
                "visibility": {
                    "type": "string",
                    "enum": ["default", "public", "private", "confidential"],
                    "default": "default",
                    "description": "Event visibility"
                },
                "transparency": {
                    "type": "string",
                    "enum": ["opaque", "transparent"],
                    "default": "opaque",
                    "description": "Whether event blocks time (opaque) or not (transparent)"
                }
            },
            "required": ["summary", "start", "end"],
            "additionalProperties": False,
            "description": "Event data for create/update operations"
        },
        "time_range": {
            "type": "object",
            "properties": {
                "start": {
                    "type": "string",
                    "format": "date-time",
                    "description": "Start time for the query range"
                },
                "end": {
                    "type": "string",
                    "format": "date-time",
                    "description": "End time for the query range"
                },
                "max_results": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 2500,
                    "default": 10,
                    "description": "Maximum number of events to return"
                }
            },
            "additionalProperties": False,
            "description": "Time range for list/availability operations"
        },
        "event_id": {
            "type": "string",
            "minLength": 1,
            "description": "Event ID for update/delete operations"
        },
        "send_notifications": {
            "type": "boolean",
            "default": True,
            "description": "Whether to send notifications to attendees"
        }
    },
    "required": ["action"],
    "additionalProperties": False,
    "allOf": [
        {
            "if": {
                "properties": {
                    "action": {"const": "create"}
                }
            },
            "then": {
                "required": ["event_data"]
            }
        },
        {
            "if": {
                "properties": {
                    "action": {"const": "update"}
                }
            },
            "then": {
                "required": ["event_id", "event_data"]
            }
        },
        {
            "if": {
                "properties": {
                    "action": {"const": "delete"}
                }
            },
            "then": {
                "required": ["event_id"]
            }
        },
        {
            "if": {
                "properties": {
                    "action": {"enum": ["list", "availability"]}
                }
            },
            "then": {
                "properties": {
                    "time_range": {
                        "type": "object"
                    }
                }
            }
        }
    ]
}
