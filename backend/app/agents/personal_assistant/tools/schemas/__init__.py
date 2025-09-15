"""
Tool schemas package for parameter validation.

This package contains JSON Schema definitions for all tools
in the personal assistant system.
"""

from .google_calendar import GOOGLE_CALENDAR_SCHEMA
from .gmail import GMAIL_SCHEMA
from .builtin_tools import (
    SYSTEM_PROMPT_SCHEMA,
    PLANNING_SCHEMA,
    VIRTUAL_FS_SCHEMA,
    TAVILY_SEARCH_SCHEMA
)

__all__ = [
    "GOOGLE_CALENDAR_SCHEMA",
    "GMAIL_SCHEMA",
    "SYSTEM_PROMPT_SCHEMA",
    "PLANNING_SCHEMA",
    "VIRTUAL_FS_SCHEMA",
    "TAVILY_SEARCH_SCHEMA"
]
