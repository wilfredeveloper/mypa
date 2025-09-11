"""
Tool schemas package for parameter validation.

This package contains JSON Schema definitions for all tools
in the personal assistant system.
"""

from .google_calendar import GOOGLE_CALENDAR_SCHEMA

__all__ = [
    "GOOGLE_CALENDAR_SCHEMA"
]
