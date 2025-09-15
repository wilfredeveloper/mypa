"""
JSON Schema definition for Gmail tool parameters.

This schema defines the structure and validation rules for all
Gmail tool operations including read, send, reply, search, and label management.
"""

GMAIL_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["read", "send", "reply", "search", "label"],
            "description": "The action to perform with Gmail"
        },
        "folder": {
            "type": "string",
            "default": "INBOX",
            "description": "Gmail folder/label to read from (e.g., INBOX, SENT, DRAFT, SPAM, TRASH, or custom labels)"
        },
        "max_results": {
            "type": "integer",
            "minimum": 1,
            "maximum": 50,
            "default": 10,
            "description": "Maximum number of messages to return for read/search operations"
        },
        "message_id": {
            "type": "string",
            "description": "Gmail message ID (required for reply and label operations)"
        },
        "query": {
            "type": "string",
            "description": "Gmail search query using Gmail search syntax (required for search action)"
        },
        "labels": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of label IDs to add to a message (for label action)"
        },
        "message_data": {
            "oneOf": [
                {"type": "string"},
                {
                    "type": "object",
                    "properties": {
                        "to": {
                            "type": "string",
                            "format": "email",
                            "description": "Recipient email address (required for send action)"
                        },
                        "subject": {
                            "type": "string",
                            "description": "Email subject line (required for send action)"
                        },
                        "body": {
                            "type": "string",
                            "description": "Email body content (plain text)"
                        },
                        "cc": {
                            "type": "string",
                            "format": "email",
                            "description": "CC recipient email address (optional)"
                        },
                        "bcc": {
                            "type": "string",
                            "format": "email",
                            "description": "BCC recipient email address (optional)"
                        },
                        "include_original": {
                            "type": "boolean",
                            "default": True,
                            "description": "Whether to include original message in reply (for reply action)"
                        },
                        "attachments": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "filename": {"type": "string"},
                                    "content": {"type": "string"},
                                    "mime_type": {"type": "string"}
                                },
                                "required": ["filename", "content"],
                                "additionalProperties": False
                            },
                            "description": "Email attachments (currently not fully supported)"
                        }
                    },
                    "additionalProperties": False
                }
            ],
            "description": "Message data for send/reply operations (can be JSON string or object)"
        }
    },
    "required": ["action"],
    "additionalProperties": False,
    "allOf": [
        {
            "if": {
                "properties": {
                    "action": {"const": "send"}
                }
            },
            "then": {
                "required": ["message_data"],
                "properties": {
                    "message_data": {
                        "oneOf": [
                            {"type": "string"},
                            {
                                "type": "object",
                                "required": ["to", "subject"]
                            }
                        ]
                    }
                }
            }
        },
        {
            "if": {
                "properties": {
                    "action": {"const": "reply"}
                }
            },
            "then": {
                "required": ["message_id", "message_data"]
            }
        },
        {
            "if": {
                "properties": {
                    "action": {"const": "search"}
                }
            },
            "then": {
                "required": ["query"]
            }
        },
        {
            "if": {
                "properties": {
                    "action": {"const": "label"}
                }
            },
            "then": {
                "required": ["message_id", "labels"]
            }
        }
    ]
}

# Gmail search query examples and documentation
GMAIL_SEARCH_EXAMPLES = {
    "basic_search": {
        "description": "Search for emails containing specific text",
        "example": "project update",
        "query": "project update"
    },
    "from_sender": {
        "description": "Search for emails from a specific sender",
        "example": "from:john@example.com",
        "query": "from:john@example.com"
    },
    "to_recipient": {
        "description": "Search for emails sent to a specific recipient",
        "example": "to:jane@example.com",
        "query": "to:jane@example.com"
    },
    "subject_search": {
        "description": "Search for emails with specific subject",
        "example": "subject:meeting",
        "query": "subject:meeting"
    },
    "date_range": {
        "description": "Search for emails within a date range",
        "example": "after:2024/1/1 before:2024/12/31",
        "query": "after:2024/1/1 before:2024/12/31"
    },
    "has_attachment": {
        "description": "Search for emails with attachments",
        "example": "has:attachment",
        "query": "has:attachment"
    },
    "label_search": {
        "description": "Search for emails with specific label",
        "example": "label:important",
        "query": "label:important"
    },
    "unread_emails": {
        "description": "Search for unread emails",
        "example": "is:unread",
        "query": "is:unread"
    },
    "starred_emails": {
        "description": "Search for starred emails",
        "example": "is:starred",
        "query": "is:starred"
    },
    "complex_search": {
        "description": "Complex search combining multiple criteria",
        "example": "from:john@example.com subject:project has:attachment after:2024/1/1",
        "query": "from:john@example.com subject:project has:attachment after:2024/1/1"
    }
}

# Common Gmail labels/folders
GMAIL_COMMON_LABELS = [
    "INBOX",
    "SENT",
    "DRAFT", 
    "SPAM",
    "TRASH",
    "IMPORTANT",
    "STARRED",
    "UNREAD",
    "CATEGORY_PERSONAL",
    "CATEGORY_SOCIAL", 
    "CATEGORY_PROMOTIONS",
    "CATEGORY_UPDATES",
    "CATEGORY_FORUMS"
]

# Tool usage guidelines
GMAIL_USAGE_GUIDELINES = {
    "read_inbox": {
        "description": "Read recent emails from inbox",
        "parameters": {
            "action": "read",
            "folder": "INBOX",
            "max_results": 10
        }
    },
    "send_email": {
        "description": "Send a new email",
        "parameters": {
            "action": "send",
            "message_data": {
                "to": "recipient@example.com",
                "subject": "Email subject",
                "body": "Email content"
            }
        }
    },
    "reply_to_email": {
        "description": "Reply to an existing email",
        "parameters": {
            "action": "reply",
            "message_id": "message_id_here",
            "message_data": {
                "body": "Reply content"
            }
        }
    },
    "search_emails": {
        "description": "Search for specific emails",
        "parameters": {
            "action": "search",
            "query": "from:sender@example.com subject:important",
            "max_results": 5
        }
    },
    "manage_labels": {
        "description": "Add labels to an email",
        "parameters": {
            "action": "label",
            "message_id": "message_id_here",
            "labels": ["IMPORTANT", "STARRED"]
        }
    }
}
