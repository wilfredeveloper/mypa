"""
JSON Schema definitions for builtin Personal Assistant tools.

This module contains comprehensive schema definitions for all builtin tools
including system_prompt, planning, virtual_fs, and tavily_search.
"""

# System Prompt Manager Tool Schema
SYSTEM_PROMPT_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["get", "set", "list", "switch"],
            "description": "The action to perform on system prompts"
        },
        "prompt_name": {
            "type": "string",
            "description": "Name of the prompt template (required for 'switch' action)"
        },
        "prompt_content": {
            "type": "string",
            "description": "Custom prompt content (required for 'set' action)"
        }
    },
    "required": ["action"],
    "additionalProperties": False,
    "allOf": [
        {
            "if": {
                "properties": {
                    "action": {"const": "set"}
                }
            },
            "then": {
                "required": ["prompt_content"]
            }
        },
        {
            "if": {
                "properties": {
                    "action": {"const": "switch"}
                }
            },
            "then": {
                "required": ["prompt_name"]
            }
        }
    ]
}

# Task Planning Tool Schema
PLANNING_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["create", "update", "get", "list"],
            "description": "The action to perform on plans"
        },
        "task": {
            "type": "string",
            "description": "Task description (required for 'create' action)"
        },
        "complexity": {
            "type": "string",
            "enum": ["simple", "medium", "complex"],
            "default": "medium",
            "description": "Task complexity level"
        },
        "plan_id": {
            "type": "string",
            "description": "Plan ID (required for 'update' and 'get' actions)"
        },
        "updates": {
            "type": "object",
            "description": "Updates to apply (required for 'update' action)",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["pending", "in_progress", "completed", "cancelled"]
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "urgent"]
                },
                "progress": {
                    "type": "object",
                    "properties": {
                        "completed_tasks": {"type": "integer", "minimum": 0},
                        "completion_percentage": {"type": "number", "minimum": 0, "maximum": 100}
                    }
                }
            },
            "additionalProperties": False
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
                "required": ["task"]
            }
        },
        {
            "if": {
                "properties": {
                    "action": {"enum": ["update", "get"]}
                }
            },
            "then": {
                "required": ["plan_id"]
            }
        },
        {
            "if": {
                "properties": {
                    "action": {"const": "update"}
                }
            },
            "then": {
                "required": ["updates"]
            }
        }
    ]
}

# Virtual File System Tool Schema
VIRTUAL_FS_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["create", "read", "update", "delete", "append", "exists", "list", "search", "write"],
            "description": "The action to perform on virtual files. 'write' overwrites existing files, 'create' fails if file exists, 'append' adds to existing content"
        },
        "file_path": {
            "type": "string",
            "description": "Path/name of the file to operate on (preferred parameter name)"
        },
        "filename": {
            "type": "string",
            "description": "Alternative name for file_path (for backward compatibility)"
        },
        "content": {
            "type": "string",
            "description": "File content (required for 'create', 'update', 'append', and 'write' actions)"
        },
        "search_term": {
            "type": "string",
            "description": "Search term (required for 'search' action)"
        },
        "metadata": {
            "type": "object",
            "description": "File metadata (optional for 'create' and 'update' actions)",
            "additionalProperties": True
        },
        "session_id": {
            "type": "string",
            "description": "Session ID for session-scoped operations"
        },
        "user_timezone": {
            "type": "string",
            "description": "User timezone for session initialization (e.g., 'UTC', 'America/New_York')"
        },
        "user_id": {
            "type": "string",
            "description": "User ID for session initialization"
        }
    },
    "required": ["action"],
    "additionalProperties": False,
    "allOf": [
        {
            "if": {
                "properties": {
                    "action": {"enum": ["create", "read", "update", "delete", "append", "exists", "write"]}
                }
            },
            "then": {
                "anyOf": [
                    {"required": ["file_path"]},
                    {"required": ["filename"]}
                ]
            }
        },
        {
            "if": {
                "properties": {
                    "action": {"enum": ["create", "update", "append", "write"]}
                }
            },
            "then": {
                "required": ["content"]
            }
        },
        {
            "if": {
                "properties": {
                    "action": {"const": "search"}
                }
            },
            "then": {
                "required": ["search_term"]
            }
        }
    ]
}

# Tavily Web Search Tool Schema
TAVILY_SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "Search query (required)"
        },
        "max_results": {
            "type": "integer",
            "minimum": 1,
            "maximum": 20,
            "default": 5,
            "description": "Maximum number of results to return"
        },
        "search_depth": {
            "type": "string",
            "enum": ["basic", "advanced"],
            "default": "basic",
            "description": "Search depth level"
        },
        "include_domains": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of domains to include in search"
        },
        "exclude_domains": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of domains to exclude from search"
        }
    },
    "required": ["query"],
    "additionalProperties": False
}
