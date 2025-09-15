"""
Google Calendar API service using OAuth2 credentials and per-user token storage.
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.tool import ToolRegistry, UserToolAccess

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.modify",
]


def _resolve_client_secrets_path() -> str:
    """Resolve the path to the Google OAuth client secrets JSON.

    Order of resolution:
    1) GOOGLE_CLIENT_SECRETS_FILE env var (must exist)
    2) Common filenames in the backend/ directory relative to this file:
       - client-secret.json
       - google-client-secret.json
       - client_secret.json
       - client_secrets.json

    Raises FileNotFoundError if none are found.
    """
    env_path = os.getenv("GOOGLE_CLIENT_SECRETS_FILE")
    if env_path and os.path.exists(env_path):
        return env_path

    this_file = Path(__file__).resolve()
    backend_root = this_file.parents[2]
    candidates = [
        backend_root / "client-secret.json",
        backend_root / "google-client-secret.json",
        backend_root / "client_secret.json",
        backend_root / "client_secrets.json",
    ]
    for c in candidates:
        if c.exists():
            return str(c)

    raise FileNotFoundError(
        "Google OAuth client secret file not found. Set GOOGLE_CLIENT_SECRETS_FILE or add one of: "
        + ", ".join([str(c) for c in candidates])
    )


class GoogleOAuthStore:
    """Utility for reading/writing OAuth tokens in UserToolAccess.config_data."""

    KEY = "google_oauth"

    @staticmethod
    def read(user_access: Optional[UserToolAccess]) -> Dict[str, Any]:
        if not user_access or not user_access.config_data:
            return {}

        # Check both the new shared key and the legacy key for backward compatibility
        config_data = user_access.config_data
        google_oauth_data = config_data.get(GoogleOAuthStore.KEY, {}) or {}
        legacy_data = config_data.get("google_calendar_oauth", {}) or {}

        # Use whichever has tokens (prefer the shared key)
        return google_oauth_data if google_oauth_data else legacy_data

    @staticmethod
    async def write(db: AsyncSession, user_access: UserToolAccess, data: Dict[str, Any]) -> None:
        cfg = user_access.config_data or {}
        cfg[GoogleOAuthStore.KEY] = data
        user_access.config_data = cfg
        await db.commit()


class GoogleCalendarAPI:
    """
    Async-friendly wrapper over googleapiclient Calendar v3, with per-user credentials.
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
                build, "calendar", "v3", credentials=creds, cache_discovery=False
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
        raise PermissionError("Google Calendar not authorized. Please complete OAuth flow.")

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

    async def list_events(
        self,
        calendar_id: str,
        time_min: str,
        time_max: str,
        max_results: int = 10,
        single_events: bool = True,
        order_by: str = "startTime",
    ) -> Dict[str, Any]:
        await self._ensure_service()
        def _call():
            return (
                self._service.events()
                .list(
                    calendarId=calendar_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    maxResults=max_results,
                    singleEvents=single_events,
                    orderBy=order_by,
                )
                .execute()
            )
        return await self._with_backoff(_call)

    async def create_event(self, calendar_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
        await self._ensure_service()
        def _call():
            return self._service.events().insert(calendarId=calendar_id, body=event).execute()
        return await self._with_backoff(_call)

    async def get_event(self, calendar_id: str, event_id: str) -> Optional[Dict[str, Any]]:
        await self._ensure_service()
        def _call():
            return self._service.events().get(calendarId=calendar_id, eventId=event_id).execute()
        try:
            return await self._with_backoff(_call)
        except HttpError as e:
            if getattr(e, "status_code", None) == 404 or (hasattr(e, "resp") and e.resp.status == 404):
                return None
            raise

    async def update_event(self, calendar_id: str, event_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
        await self._ensure_service()
        def _call():
            return self._service.events().update(calendarId=calendar_id, eventId=event_id, body=event).execute()
        return await self._with_backoff(_call)

    async def delete_event(self, calendar_id: str, event_id: str) -> None:
        await self._ensure_service()
        def _call():
            return self._service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        await self._with_backoff(_call)

    # ------------------ Backoff helper ------------------

    async def _with_backoff(self, func, *, retries: int = 5) -> Any:
        delay = 1.0
        for attempt in range(retries):
            try:
                return await asyncio.to_thread(func)
            except HttpError as e:
                status = None
                try:
                    status = e.resp.status
                except Exception:
                    pass
                # Provide actionable guidance for common Google API errors
                if status == 403:
                    # Try to decode and inspect error payload
                    reason = None
                    message = None
                    try:
                        content = e.content.decode() if isinstance(e.content, (bytes, bytearray)) else e.content
                        data = json.loads(content) if isinstance(content, str) else {}
                        errors = (data.get("error", {}) or {}).get("errors", []) or []
                        if errors:
                            reason = errors[0].get("reason")
                        message = (data.get("error", {}) or {}).get("message")
                    except Exception:
                        pass
                    if (reason == "accessNotConfigured") or (message and "not been used in project" in message):
                        raise PermissionError(
                            "Google Calendar API is not enabled for your Google Cloud project. "
                            "Please enable it in the Cloud Console and retry."
                        ) from e
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


# ---------- OAuth Flow helpers (for API endpoints) ----------

def create_oauth_flow(redirect_uri: str) -> Flow:
    client_secrets = _resolve_client_secrets_path()
    flow = Flow.from_client_secrets_file(client_secrets, scopes=SCOPES)
    flow.redirect_uri = redirect_uri
    return flow

async def get_or_create_user_tool_access(db: AsyncSession, user_id: int, tool_name: str = "google_calendar") -> UserToolAccess:
    result = await db.execute(select(ToolRegistry).where(ToolRegistry.name == tool_name))
    tool = result.scalar_one_or_none()
    if not tool:
        raise RuntimeError(f"Tool '{tool_name}' not found in registry. Seed it first.")

    result = await db.execute(
        select(UserToolAccess).where(UserToolAccess.user_id == user_id, UserToolAccess.tool_id == tool.id)
    )
    access = result.scalar_one_or_none()
    if not access:
        access = UserToolAccess(user_id=user_id, tool_id=tool.id, is_authorized=False, config_data={})
        db.add(access)
        await db.commit()
        await db.refresh(access)
    return access

