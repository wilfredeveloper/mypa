"""
Gmail Tool for Personal Assistant.
"""

import base64
import email
import json
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

    async def is_authorized(self) -> bool:
        """Override to ensure tokens exist before use (refresh or access)."""
        try:
            if not self.user_access or not self.user_access.is_authorized:
                return False
            cfg = (self.user_access.config_data or {}).get("google_oauth", {})
            # Accept either refresh_token or current access token
            return bool(cfg.get("refresh_token") or cfg.get("token"))
        except Exception:
            return False

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
        logger.info(f"🔧 GMAIL TOOL EXECUTION STARTED")
        logger.info(f"📥 Input Parameters: {json.dumps(parameters, indent=2)}")

        if not await self.is_authorized():
            error_result = await self.handle_error(
                ValueError(
                    "Gmail not authorized. Please authorize in the app (click 'Authorize Gmail') "
                    "or visit /api/v1/google/oauth/start to begin the OAuth flow."
                ),
                "Authorization required"
            )
            logger.error(f"❌ Gmail Tool Authorization Failed: {error_result}")
            return error_result

        if not self.validate_parameters(parameters):
            return await self.handle_error(
                ValueError("Invalid parameters"),
                "Parameter validation failed"
            )

        action = parameters.get("action", "read").lower()
        logger.info(f"🎯 Executing Gmail action: {action}")

        try:
            # Initialize Gmail service if needed
            if not self.gmail_service:
                await self._initialize_gmail_service()

            result = None
            if action == "read":
                folder = parameters.get("folder", "INBOX")
                max_results = parameters.get("max_results", self.default_max_results)
                logger.info(f"📂 Reading messages from folder: {folder}, max_results: {max_results}")
                result = await self._read_messages(folder, max_results)

            elif action == "send":
                message_data = parameters.get("message_data")
                if not message_data:
                    return await self.handle_error(
                        ValueError("message_data is required for 'send' action"),
                        "Missing message data"
                    )

                # Parse message_data from various formats
                message_data = self._parse_message_data(message_data)

                logger.info(f"📤 Sending message to: {message_data.get('to', 'unknown') if isinstance(message_data, dict) else 'unknown'}")
                result = await self._send_message(message_data)

            elif action == "reply":
                message_id = parameters.get("message_id")
                message_data = parameters.get("message_data")

                if not message_id or not message_data:
                    return await self.handle_error(
                        ValueError("message_id and message_data are required for 'reply' action"),
                        "Missing message ID or data"
                    )

                # Parse message_data from various formats
                message_data = self._parse_message_data(message_data)

                logger.info(f"↩️ Replying to message: {message_id}")
                result = await self._reply_to_message(message_id, message_data)

            elif action == "search":
                query = parameters.get("query")
                max_results = parameters.get("max_results", self.default_max_results)

                if not query:
                    return await self.handle_error(
                        ValueError("query is required for 'search' action"),
                        "Missing search query"
                    )

                logger.info(f"🔍 Searching messages with query: {query}, max_results: {max_results}")
                result = await self._search_messages(query, max_results)

            elif action == "label":
                message_id = parameters.get("message_id")
                labels = parameters.get("labels", [])

                if not message_id:
                    return await self.handle_error(
                        ValueError("message_id is required for 'label' action"),
                        "Missing message ID"
                    )

                logger.info(f"🏷️ Managing labels for message: {message_id}, labels: {labels}")
                result = await self._manage_labels(message_id, labels)

            else:
                return await self.handle_error(
                    ValueError(f"Unknown action: {action}"),
                    "Invalid action"
                )

            # Log the complete result that will be passed to the agent
            logger.info(f"✅ GMAIL TOOL EXECUTION COMPLETED")
            logger.info(f"📤 RESULT BEING PASSED TO AGENT:")
            logger.info(f"📋 Result Summary: success={result.get('success', False)}, "
                       f"data_keys={list(result.get('data', {}).keys()) if result.get('data') else []}")

            # Log detailed message content if it's a read/search operation
            if action in ["read", "search"] and result.get("success") and result.get("data", {}).get("messages"):
                messages = result["data"]["messages"]
                logger.info(f"📧 FETCHED {len(messages)} MESSAGES WITH FULL CONTENT:")
                for i, msg in enumerate(messages[:3]):  # Log first 3 messages in detail
                    logger.info(f"  📨 Message {i+1}:")
                    logger.info(f"    📧 From: {msg.get('from', 'N/A')}")
                    logger.info(f"    📧 Subject: {msg.get('subject', 'N/A')}")
                    logger.info(f"    📧 Date: {msg.get('date', 'N/A')}")
                    body = msg.get('body', '')
                    body_preview = body[:200] + "..." if len(body) > 200 else body
                    logger.info(f"    📧 Body Preview: {repr(body_preview)}")
                    logger.info(f"    📧 Full Body Length: {len(body)} characters")
                    logger.info(f"    📧 Has Attachments: {len(msg.get('attachments', []))} files")
                if len(messages) > 3:
                    logger.info(f"  📧 ... and {len(messages) - 3} more messages")

            return result

        except Exception as e:
            error_result = await self.handle_error(e, f"Action: {action}")
            logger.error(f"❌ GMAIL TOOL EXECUTION FAILED: {error_result}")
            return error_result

    def _parse_message_data(self, message_data: Any) -> Dict[str, Any]:
        """Parse message_data from various formats (string, dict) into a dictionary."""
        if isinstance(message_data, dict):
            return message_data

        if isinstance(message_data, str):
            try:
                # Try to parse as JSON first
                return json.loads(message_data)
            except json.JSONDecodeError:
                # Handle BAML-generated format like "{to: email, subject: text, body: text}"
                parsed_data = {}

                # Remove outer braces if present
                content = message_data.strip()
                if content.startswith('{') and content.endswith('}'):
                    content = content[1:-1]

                # Split by commas, but be careful with commas inside values
                parts = []
                current_part = ""
                paren_depth = 0
                bracket_depth = 0
                in_quotes = False
                quote_char = None

                for char in content:
                    if char in ['"', "'"] and not in_quotes:
                        in_quotes = True
                        quote_char = char
                    elif char == quote_char and in_quotes:
                        in_quotes = False
                        quote_char = None
                    elif not in_quotes:
                        if char == '(':
                            paren_depth += 1
                        elif char == ')':
                            paren_depth -= 1
                        elif char == '[':
                            bracket_depth += 1
                        elif char == ']':
                            bracket_depth -= 1
                        elif char == ',' and paren_depth == 0 and bracket_depth == 0:
                            parts.append(current_part.strip())
                            current_part = ""
                            continue

                    current_part += char

                if current_part.strip():
                    parts.append(current_part.strip())

                # Parse each part as key: value
                for part in parts:
                    if ': ' in part:
                        key, value = part.split(': ', 1)
                        key = key.strip()
                        value = value.strip()

                        # Clean up value - remove quotes and handle null
                        if value.lower() == 'null':
                            value = None
                        elif value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        elif value.startswith("'") and value.endswith("'"):
                            value = value[1:-1]
                        elif value.startswith('[') and value.endswith(']'):
                            # Handle arrays - for now just store as string
                            value = value

                        parsed_data[key] = value

                # Log the parsing result for debugging
                logger.info(f"🔍 Parsed message_data: {parsed_data}")

                return parsed_data

        # If it's neither dict nor string, return empty dict
        return {}

    async def _initialize_gmail_service(self) -> None:
        """Initialize Gmail API service using real Google APIs."""
        try:
            from app.services.gmail_service import GmailAPI
            # Use per-user access from the tool instance
            self.gmail_service = GmailAPI(self.db, self.user_access)

            # Get user's email address
            profile = await self.gmail_service.get_profile()
            self.user_email = profile.get('emailAddress')

            logger.info("Gmail service initialized (Google API client)")
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

    async def _send_message(self, message_data: Any) -> Dict[str, Any]:
        """Send a new email message."""
        try:
            # Parse message_data (handles both dict and JSON string inputs)
            try:
                parsed_message_data = self._parse_event_data(message_data)
            except ValueError as e:
                return await self.handle_error(e, "Invalid message data format")

            # Validate required fields
            if not parsed_message_data.get("to"):
                return await self.handle_error(
                    ValueError("Recipient email is required"),
                    "Missing recipient"
                )

            if not parsed_message_data.get("subject"):
                return await self.handle_error(
                    ValueError("Email subject is required"),
                    "Missing subject"
                )

            # Build email message
            message = self._build_email_message(
                to=parsed_message_data["to"],
                subject=parsed_message_data["subject"],
                body=parsed_message_data.get("body", ""),
                cc=parsed_message_data.get("cc"),
                bcc=parsed_message_data.get("bcc"),
                attachments=parsed_message_data.get("attachments")
            )

            # Send message via Gmail API
            sent_message = await self.gmail_service.send_message(message)

            return await self.create_success_response({
                "message": {
                    "id": sent_message.get('id'),
                    "thread_id": sent_message.get('threadId'),
                    "to": parsed_message_data["to"],
                    "subject": parsed_message_data["subject"]
                },
                "message_text": f"Email sent to {parsed_message_data['to']} with subject '{parsed_message_data['subject']}'",
                "operation": "send"
            })

        except Exception as e:
            return await self.handle_error(e, "Sending email message")

    async def _reply_to_message(self, message_id: str, message_data: Any) -> Dict[str, Any]:
        """Reply to an existing email message."""
        try:
            # Parse message_data (handles both dict and JSON string inputs)
            try:
                parsed_message_data = self._parse_event_data(message_data)
            except ValueError as e:
                return await self.handle_error(e, "Invalid message data format")

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
            reply_body = parsed_message_data.get("body", "")
            if parsed_message_data.get("include_original", True):
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

    async def _search_messages(self, query: str, max_results: int) -> Dict[str, Any]:
        """Search messages using Gmail search query syntax."""
        try:
            # Search messages using Gmail API
            messages_result = await self.gmail_service.list_messages(
                query=query,
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
                "query": query,
                "operation": "search"
            })

        except Exception as e:
            return await self.handle_error(e, f"Searching messages with query: {query}")

    async def _manage_labels(self, message_id: str, labels: List[str]) -> Dict[str, Any]:
        """Manage labels on a message."""
        try:
            # Get current message to see existing labels
            current_message = await self.gmail_service.get_message(message_id, format="minimal")

            if not current_message:
                return await self.handle_error(
                    ValueError(f"Message not found: {message_id}"),
                    "Message not found"
                )

            # For simplicity, we'll add the specified labels
            # In a more sophisticated implementation, you could support remove operations
            result = await self.gmail_service.modify_message(
                message_id=message_id,
                add_label_ids=labels
            )

            return await self.create_success_response({
                "message_id": message_id,
                "labels_added": labels,
                "message": f"Labels {', '.join(labels)} added to message {message_id}",
                "operation": "label"
            })

        except Exception as e:
            return await self.handle_error(e, f"Managing labels for message: {message_id}")

    def _parse_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Parse a Gmail API message response into a more readable format."""
        try:
            from app.services.gmail_service import parse_gmail_message
            return parse_gmail_message(message)
        except Exception as e:
            logger.error(f"Error parsing message: {str(e)}")
            # Fallback to basic parsing
            return {
                'id': message.get('id'),
                'thread_id': message.get('threadId'),
                'snippet': message.get('snippet', ''),
                'from': 'Unknown',
                'to': 'Unknown',
                'subject': 'Unknown',
                'body': message.get('snippet', ''),
                'date': '',
                'label_ids': message.get('labelIds', [])
            }

    def _build_email_message(
        self,
        to: str,
        subject: str,
        body: str,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        thread_id: Optional[str] = None,
        in_reply_to: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build an email message in the format expected by Gmail API."""
        try:
            from app.services.gmail_service import create_email_message
            return create_email_message(
                to=to,
                subject=subject,
                body=body,
                from_email=self.user_email,
                cc=cc,
                bcc=bcc,
                thread_id=thread_id,
                in_reply_to=in_reply_to,
            )
        except Exception as e:
            logger.error(f"Error building email message: {str(e)}")
            raise ValueError(f"Failed to build email message: {str(e)}")

    def _parse_event_data(self, message_data: Any) -> Dict[str, Any]:
        """
        Parse message_data parameter, handling both dictionary and JSON string inputs.

        Args:
            message_data: Either a dictionary or JSON string containing message data

        Returns:
            Dictionary containing parsed message data

        Raises:
            ValueError: If message_data cannot be parsed or is invalid
        """
        if message_data is None:
            raise ValueError("message_data cannot be None")

        # If it's already a dictionary, return as-is
        if isinstance(message_data, dict):
            return message_data

        # If it's a string, try to parse as JSON
        if isinstance(message_data, str):
            try:
                parsed_data = json.loads(message_data)
                if not isinstance(parsed_data, dict):
                    raise ValueError(f"Parsed message_data must be a dictionary, got {type(parsed_data)}")
                return parsed_data
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in message_data: {str(e)}")

        # For any other type, try to convert to string and parse
        try:
            json_str = str(message_data)
            parsed_data = json.loads(json_str)
            if not isinstance(parsed_data, dict):
                raise ValueError(f"Parsed message_data must be a dictionary, got {type(parsed_data)}")
            return parsed_data
        except (json.JSONDecodeError, TypeError) as e:
            raise ValueError(f"Cannot parse message_data of type {type(message_data)}: {str(e)}")