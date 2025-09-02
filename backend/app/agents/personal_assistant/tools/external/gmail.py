"""
Gmail Tool for Personal Assistant.
"""

import base64
import email
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

from app.agents.personal_assistant.tools.base import ExternalTool

logger = logging.getLogger(__name__)


class GmailTool(ExternalTool):
    """
    Gmail integration tool for Personal Assistant.

    This tool provides:
    - Read inbox and specific folders
    - Compose and send emails
    - Reply to emails
    - Search emails with filters
    - Manage labels and folders
    - Handle attachments
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.gmail_service = None

        # Default settings
        self.default_max_results = 10
        self.user_email = None

    async def execute(self, parameters: Dict[str, Any]) -> Any:
        """
        Execute Gmail operations.

        Parameters:
            action (str): Action to perform - 'read', 'send', 'reply', 'search', 'label'
            message_data (dict): Message data for send/reply operations
            message_id (str): Message ID for reply/label operations
            query (str): Search query for search operations
            folder (str): Folder/label name for read operations
            max_results (int): Maximum results for list operations

        Returns:
            Gmail operation result
        """
        if not await self.is_authorized():
            return await self.handle_error(
                ValueError("Gmail access not authorized"),
                "Authorization required"
            )

        if not self.validate_parameters(parameters):
            return await self.handle_error(
                ValueError("Invalid parameters"),
                "Parameter validation failed"
            )

        action = parameters.get("action", "read").lower()

        try:
            # Initialize Gmail service if needed
            if not self.gmail_service:
                await self._initialize_gmail_service()

            if action == "read":
                folder = parameters.get("folder", "INBOX")
                max_results = parameters.get("max_results", self.default_max_results)
                return await self._read_messages(folder, max_results)

            elif action == "send":
                message_data = parameters.get("message_data")
                if not message_data:
                    return await self.handle_error(
                        ValueError("message_data is required for 'send' action"),
                        "Missing message data"
                    )
                return await self._send_message(message_data)

            elif action == "reply":
                message_id = parameters.get("message_id")
                message_data = parameters.get("message_data")

                if not message_id or not message_data:
                    return await self.handle_error(
                        ValueError("message_id and message_data are required for 'reply' action"),
                        "Missing message ID or data"
                    )

                return await self._reply_to_message(message_id, message_data)

            elif action == "search":
                query = parameters.get("query")
                max_results = parameters.get("max_results", self.default_max_results)

                if not query:
                    return await self.handle_error(
                        ValueError("query is required for 'search' action"),
                        "Missing search query"
                    )

                return await self._search_messages(query, max_results)

            elif action == "label":
                message_id = parameters.get("message_id")
                labels = parameters.get("labels", [])

                if not message_id:
                    return await self.handle_error(
                        ValueError("message_id is required for 'label' action"),
                        "Missing message ID"
                    )

                return await self._manage_labels(message_id, labels)

            else:
                return await self.handle_error(
                    ValueError(f"Unknown action: {action}"),
                    "Invalid action"
                )

        except Exception as e:
            return await self.handle_error(e, f"Action: {action}")

    async def _initialize_gmail_service(self) -> None:
        """Initialize Gmail API service."""
        try:
            # This is a placeholder for the actual Gmail API initialization
            # In the OAuth implementation phase, this will be properly implemented
            # with actual Google API client setup

            # For now, we'll simulate the service initialization
            self.gmail_service = MockGmailService()

            # Get user's email address
            profile = await self.gmail_service.get_profile()
            self.user_email = profile.get('emailAddress')

            logger.info("Gmail service initialized")

        except Exception as e:
            logger.error(f"Failed to initialize Gmail service: {str(e)}")
            raise

    async def _read_messages(self, folder: str, max_results: int) -> Dict[str, Any]:
        """Read messages from a specific folder."""
        try:
            # Get message list from Gmail API
            messages_result = await self.gmail_service.list_messages(
                label_ids=[folder],
                max_results=max_results
            )

            messages = messages_result.get('messages', [])

            # Get detailed information for each message
            detailed_messages = []
            for message in messages:
                message_detail = await self.gmail_service.get_message(message['id'])

                # Parse message details
                parsed_message = self._parse_message(message_detail)
                detailed_messages.append(parsed_message)

            return await self.create_success_response({
                "messages": detailed_messages,
                "total_count": len(detailed_messages),
                "folder": folder,
                "operation": "read"
            })

        except Exception as e:
            return await self.handle_error(e, f"Reading messages from {folder}")

    async def _send_message(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send a new email message."""
        try:
            # Validate required fields
            if not message_data.get("to"):
                return await self.handle_error(
                    ValueError("Recipient email is required"),
                    "Missing recipient"
                )

            if not message_data.get("subject"):
                return await self.handle_error(
                    ValueError("Email subject is required"),
                    "Missing subject"
                )

            # Build email message
            message = self._build_email_message(
                to=message_data["to"],
                subject=message_data["subject"],
                body=message_data.get("body", ""),
                cc=message_data.get("cc"),
                bcc=message_data.get("bcc"),
                attachments=message_data.get("attachments")
            )

            # Send message via Gmail API
            sent_message = await self.gmail_service.send_message(message)

            return await self.create_success_response({
                "message": {
                    "id": sent_message.get('id'),
                    "thread_id": sent_message.get('threadId'),
                    "to": message_data["to"],
                    "subject": message_data["subject"]
                },
                "message_text": f"Email sent to {message_data['to']} with subject '{message_data['subject']}'",
                "operation": "send"
            })

        except Exception as e:
            return await self.handle_error(e, "Sending email message")

    async def _reply_to_message(self, message_id: str, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Reply to an existing email message."""
        try:
            # Get original message
            original_message = await self.gmail_service.get_message(message_id)

            if not original_message:
                return await self.handle_error(
                    ValueError(f"Original message not found: {message_id}"),
                    "Original message not found"
                )

            # Parse original message for reply context
            original_parsed = self._parse_message(original_message)

            # Build reply message
            reply_to = original_parsed.get("from")
            reply_subject = original_parsed.get("subject", "")
            if not reply_subject.lower().startswith("re:"):
                reply_subject = f"Re: {reply_subject}"

            # Include original message in reply body
            reply_body = message_data.get("body", "")
            if message_data.get("include_original", True):
                original_body = original_parsed.get("body", "")
                reply_body += f"\n\n--- Original Message ---\n{original_body}"

            message = self._build_email_message(
                to=reply_to,
                subject=reply_subject,
                body=reply_body,
                thread_id=original_message.get('threadId'),
                in_reply_to=message_id
            )

            # Send reply via Gmail API
            sent_reply = await self.gmail_service.send_message(message)

            return await self.create_success_response({
                "reply": {
                    "id": sent_reply.get('id'),
                    "thread_id": sent_reply.get('threadId'),
                    "to": reply_to,
                    "subject": reply_subject,
                    "original_message_id": message_id
                },
                "message_text": f"Reply sent to {reply_to}",
                "operation": "reply"
            })

        except Exception as e:
            return await self.handle_error(e, f"Replying to message: {message_id}")