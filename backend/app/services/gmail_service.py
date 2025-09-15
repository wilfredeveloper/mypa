"""
Gmail API service using OAuth2 credentials and per-user token storage.
"""

import asyncio
import base64
import email
import json
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Any, Dict, List, Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tool import UserToolAccess
from app.services.google_calendar_service import GoogleOAuthStore, _resolve_client_secrets_path, SCOPES


class GmailAPI:
    """
    Async-friendly wrapper over googleapiclient Gmail v1, with per-user credentials.
    """

    def __init__(self, db: AsyncSession, user_access: UserToolAccess):
        self.db = db
        self.user_access = user_access
        self._service = None
        self._lock = asyncio.Lock()

    async def _ensure_service(self):
        async with self._lock:
            if self._service is not None:
                return
            creds = await self._ensure_credentials()
            # build() is blocking; offload to thread
            self._service = await asyncio.to_thread(
                build, "gmail", "v1", credentials=creds, cache_discovery=False
            )

    async def _ensure_credentials(self) -> Credentials:
        oauth = GoogleOAuthStore.read(self.user_access)
        client_secrets = _resolve_client_secrets_path()
        creds: Optional[Credentials] = None

        if oauth:
            # Restore saved credentials
            creds = Credentials(
                token=oauth.get("token"),
                refresh_token=oauth.get("refresh_token"),
                token_uri=oauth.get("token_uri"),
                client_id=oauth.get("client_id"),
                client_secret=oauth.get("client_secret"),
                scopes=oauth.get("scopes") or SCOPES,
            )
            # Optionally set expiry
            try:
                if oauth.get("expiry"):
                    creds.expiry = datetime.fromisoformat(oauth["expiry"])  # naive UTC
            except Exception:
                pass

        if creds and creds.valid:
            return creds

        if creds and creds.expired and creds.refresh_token:
            # Refresh token
            refreshed = await asyncio.to_thread(self._refresh_creds, creds)
            if refreshed:
                await self._persist_creds(creds)
                return creds

        # If no creds or refresh failed, the user must authorize via OAuth flow
        raise PermissionError("Gmail not authorized. Please complete OAuth flow.")

    def _refresh_creds(self, creds: Credentials) -> bool:
        try:
            creds.refresh(Request())
            return True
        except Exception:
            return False

    async def _persist_creds(self, creds: Credentials) -> None:
        data = {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": list(creds.scopes) if creds.scopes else SCOPES,
            "expiry": creds.expiry.isoformat() if getattr(creds, "expiry", None) else None,
        }
        await GoogleOAuthStore.write(self.db, self.user_access, data)

    # ------------------ API methods (wrapped in to_thread) ------------------

    async def get_profile(self) -> Dict[str, Any]:
        """Get user's Gmail profile information."""
        await self._ensure_service()
        def _call():
            return self._service.users().getProfile(userId="me").execute()
        return await self._with_backoff(_call)

    async def list_messages(
        self,
        label_ids: Optional[List[str]] = None,
        query: Optional[str] = None,
        max_results: int = 10,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List messages in user's mailbox."""
        await self._ensure_service()
        def _call():
            params = {
                "userId": "me",
                "maxResults": max_results,
            }
            if label_ids:
                params["labelIds"] = label_ids
            if query:
                params["q"] = query
            if page_token:
                params["pageToken"] = page_token
            
            return self._service.users().messages().list(**params).execute()
        return await self._with_backoff(_call)

    async def get_message(self, message_id: str, format: str = "full") -> Dict[str, Any]:
        """Get a specific message by ID."""
        await self._ensure_service()
        def _call():
            return (
                self._service.users()
                .messages()
                .get(userId="me", id=message_id, format=format)
                .execute()
            )
        return await self._with_backoff(_call)

    async def send_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send an email message."""
        await self._ensure_service()
        def _call():
            return (
                self._service.users()
                .messages()
                .send(userId="me", body=message)
                .execute()
            )
        return await self._with_backoff(_call)

    async def modify_message(
        self, 
        message_id: str, 
        add_label_ids: Optional[List[str]] = None,
        remove_label_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Modify labels on a message."""
        await self._ensure_service()
        def _call():
            body = {}
            if add_label_ids:
                body["addLabelIds"] = add_label_ids
            if remove_label_ids:
                body["removeLabelIds"] = remove_label_ids
            
            return (
                self._service.users()
                .messages()
                .modify(userId="me", id=message_id, body=body)
                .execute()
            )
        return await self._with_backoff(_call)

    async def list_labels(self) -> Dict[str, Any]:
        """List all labels in user's mailbox."""
        await self._ensure_service()
        def _call():
            return self._service.users().labels().list(userId="me").execute()
        return await self._with_backoff(_call)

    async def _with_backoff(self, func, retries: int = 3):
        """Execute API call with exponential backoff retry logic."""
        delay = 1.0
        for attempt in range(retries):
            try:
                return await asyncio.to_thread(func)
            except HttpError as e:
                status = e.resp.status
                if attempt == retries - 1:
                    # Last attempt, check for specific errors
                    if status == 403:
                        reason = e.error_details[0].get("reason", "") if e.error_details else ""
                        message = e.error_details[0].get("message", "") if e.error_details else ""
                        if (reason == "accessNotConfigured") or (message and "not been used in project" in message):
                            raise PermissionError(
                                "Gmail API is not enabled for your Google Cloud project. "
                                "Please enable it in the Cloud Console and retry."
                            ) from e
                    if status == 401:
                        raise PermissionError("Gmail authorization expired. Please re-authorize.") from e
                if status in (429, 500, 502, 503, 504):
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 10.0)
                    continue
                raise
            except Exception:
                if attempt < retries - 1:
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 10.0)
                    continue
                raise


def create_email_message(
    to: str,
    subject: str,
    body: str,
    from_email: Optional[str] = None,
    cc: Optional[str] = None,
    bcc: Optional[str] = None,
    thread_id: Optional[str] = None,
    in_reply_to: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create an email message in the format expected by Gmail API.
    
    Args:
        to: Recipient email address
        subject: Email subject
        body: Email body (plain text)
        from_email: Sender email (optional, will use authenticated user)
        cc: CC recipients (optional)
        bcc: BCC recipients (optional)
        thread_id: Thread ID for replies (optional)
        in_reply_to: Message ID being replied to (optional)
    
    Returns:
        Dictionary containing the message in Gmail API format
    """
    message = MIMEText(body)
    message['to'] = to
    message['subject'] = subject
    
    if from_email:
        message['from'] = from_email
    if cc:
        message['cc'] = cc
    if bcc:
        message['bcc'] = bcc
    if in_reply_to:
        message['In-Reply-To'] = in_reply_to
        message['References'] = in_reply_to

    # Encode the message
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
    
    gmail_message = {'raw': raw_message}
    if thread_id:
        gmail_message['threadId'] = thread_id
    
    return gmail_message


def parse_gmail_message(message: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse a Gmail API message response into a more readable format.
    
    Args:
        message: Gmail API message response
    
    Returns:
        Dictionary with parsed message data
    """
    parsed = {
        'id': message.get('id'),
        'thread_id': message.get('threadId'),
        'label_ids': message.get('labelIds', []),
        'snippet': message.get('snippet', ''),
        'history_id': message.get('historyId'),
        'internal_date': message.get('internalDate'),
        'size_estimate': message.get('sizeEstimate'),
    }
    
    payload = message.get('payload', {})
    headers = payload.get('headers', [])
    
    # Extract common headers
    header_map = {}
    for header in headers:
        name = header.get('name', '').lower()
        value = header.get('value', '')
        header_map[name] = value
    
    parsed.update({
        'from': header_map.get('from', ''),
        'to': header_map.get('to', ''),
        'cc': header_map.get('cc', ''),
        'bcc': header_map.get('bcc', ''),
        'subject': header_map.get('subject', ''),
        'date': header_map.get('date', ''),
        'message_id': header_map.get('message-id', ''),
        'in_reply_to': header_map.get('in-reply-to', ''),
        'references': header_map.get('references', ''),
    })
    
    # Extract body
    body = _extract_message_body(payload)
    parsed['body'] = body
    
    # Extract attachments info
    attachments = _extract_attachments_info(payload)
    parsed['attachments'] = attachments
    
    return parsed


def _extract_message_body(payload: Dict[str, Any]) -> str:
    """Extract the body text from a Gmail message payload."""
    body = ""
    
    if 'parts' in payload:
        # Multipart message
        for part in payload['parts']:
            if part.get('mimeType') == 'text/plain':
                data = part.get('body', {}).get('data', '')
                if data:
                    body = base64.urlsafe_b64decode(data).decode('utf-8')
                    break
            elif part.get('mimeType') == 'text/html' and not body:
                # Fallback to HTML if no plain text
                data = part.get('body', {}).get('data', '')
                if data:
                    body = base64.urlsafe_b64decode(data).decode('utf-8')
    else:
        # Single part message
        if payload.get('mimeType') == 'text/plain':
            data = payload.get('body', {}).get('data', '')
            if data:
                body = base64.urlsafe_b64decode(data).decode('utf-8')
    
    return body


def _extract_attachments_info(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract attachment information from a Gmail message payload."""
    attachments = []
    
    def _process_part(part):
        filename = part.get('filename')
        if filename:
            attachments.append({
                'filename': filename,
                'mime_type': part.get('mimeType'),
                'size': part.get('body', {}).get('size', 0),
                'attachment_id': part.get('body', {}).get('attachmentId'),
            })
        
        # Process nested parts
        if 'parts' in part:
            for subpart in part['parts']:
                _process_part(subpart)
    
    if 'parts' in payload:
        for part in payload['parts']:
            _process_part(part)
    
    return attachments
