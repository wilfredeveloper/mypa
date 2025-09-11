"""
Google OAuth2 endpoints for Google Calendar integration.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_async_session
from app.models.user import User
from app.models.tool import ToolRegistry, UserToolAccess
from app.services.google_calendar_service import (
    create_oauth_flow,
    get_or_create_user_tool_access,
    GoogleOAuthStore,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _redirect_uri() -> str:
    # Allow override via env; else default to local
    return (
        getattr(settings, "GOOGLE_OAUTH_REDIRECT_URI", None)
        or "http://localhost:8000/api/v1/google/oauth/callback"
    )


@router.get("/oauth/start")
async def google_oauth_start(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    try:
        flow = create_oauth_flow(_redirect_uri())
        auth_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",  # must be lowercase string per Google spec
            prompt="consent",
        )
        access = await get_or_create_user_tool_access(db, int(current_user.id), "google_calendar")
        cfg = dict(access.config_data or {})
        # Maintain a list of pending states to avoid race/overwrite issues
        pending = cfg.get("google_calendar_oauth_state_list") or []
        if isinstance(pending, str):
            pending = [pending]
        # Keep only recent few states
        pending = [s for s in pending if isinstance(s, str)]
        pending.append(state)
        pending = pending[-5:]
        cfg["google_calendar_oauth_state_list"] = pending
        cfg["google_calendar_oauth_state"] = state  # legacy single-state for compatibility
        access.config_data = cfg
        await db.commit()

        # Debug instrumentation to trace state persistence
        try:
            import os
            logger.info(
                "[Google OAuth Start] user_id=%s tool=google_calendar state=%s redirect_uri=%s db=%s cwd=%s",
                current_user.id,
                state,
                _redirect_uri(),
                str(settings.DATABASE_URL),
                os.getcwd(),
            )
            # Re-read and log what is stored now for this user/tool
            result = await db.execute(
                select(UserToolAccess).where(
                    UserToolAccess.user_id == int(current_user.id)
                )
            )
            uta = result.scalars().first()
            stored = uta.config_data or {}
            logger.info(
                "[Google OAuth Start] persisted for user_id=%s single=%s list_size=%s",
                current_user.id,
                stored.get("google_calendar_oauth_state"),
                len(stored.get("google_calendar_oauth_state_list") or []),
            )
        except Exception:
            pass

        return {"authorization_url": auth_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/oauth/status")
async def google_oauth_status(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    try:
        access = await get_or_create_user_tool_access(db, current_user.id, "google_calendar")
        cfg = (access.config_data or {}).get("google_calendar_oauth", {}) or {}
        tokens_present = bool(cfg.get("refresh_token") or cfg.get("token"))
        # Treat as authorized only if tokens are present AND the access record is marked authorized
        authorized = bool(tokens_present and access.is_authorized)
        try:
            logger.info(
                "[Google OAuth Status] user_id=%s authorized=%s is_authorized=%s token_present=%s refresh_present=%s",
                current_user.id,
                authorized,
                bool(access.is_authorized),
                bool(cfg.get("token")),
                bool(cfg.get("refresh_token")),
            )
        except Exception:
            pass
        return {"authorized": authorized}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/oauth/callback")
async def google_oauth_callback(
    request: Request,
    state: Optional[str] = None,
    code: Optional[str] = None,
    db: AsyncSession = Depends(get_async_session),
):
    """
    Google redirects here without your app's Authorization header.
    Do NOT require get_current_user. Identify the user via the saved OAuth state.
    """
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")
    if not state:
        raise HTTPException(status_code=400, detail="Missing OAuth state")

    try:
        # Log incoming callback parameters for debugging
        try:
            logger.info(
                "[Google OAuth Callback] received state=%s code_present=%s db=%s",
                state,
                bool(code),
                str(settings.DATABASE_URL),
            )
        except Exception:
            pass

        # Find the pending OAuth record by state
        # 1) Find the google_calendar tool id
        result = await db.execute(select(ToolRegistry).where(ToolRegistry.name == "google_calendar"))
        tool = result.scalar_one_or_none()
        if not tool:
            raise HTTPException(status_code=500, detail="Tool 'google_calendar' not found")

        # 2) Find UserToolAccess whose config_data has matching state
        result = await db.execute(select(UserToolAccess).where(UserToolAccess.tool_id == tool.id))
        candidates = result.scalars().all()
        access = None
        candidate_states = []
        for a in candidates:
            cfg_a = a.config_data or {}
            st_single = cfg_a.get("google_calendar_oauth_state")
            st_list = cfg_a.get("google_calendar_oauth_state_list") or []
            # For logging, show either the single state or first of list
            candidate_states.append(st_single or (st_list[0] if isinstance(st_list, list) and st_list else None))
            if st_single == state or (isinstance(st_list, list) and state in st_list):
                access = a
                break
        try:
            logger.info(
                "[Google OAuth Callback] candidates=%d match=%s sample_states=%s",
                len(candidates),
                bool(access),
                candidate_states[:5],
            )
        except Exception:
            pass
        if not access:
            raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

        # Exchange code for tokens
        flow = create_oauth_flow(_redirect_uri())
        flow.fetch_token(code=code)
        creds = flow.credentials

        # Persist tokens on the matched access record
        data = {
            "token": getattr(creds, "token", None),
            "refresh_token": getattr(creds, "refresh_token", None),
            "token_uri": getattr(creds, "token_uri", None),
            "client_id": getattr(creds, "client_id", None),
            "client_secret": getattr(creds, "client_secret", None),
            "scopes": list(getattr(creds, "scopes", []) or []) ,
            "expiry": getattr(creds, "expiry", None).isoformat() if getattr(creds, "expiry", None) else None,
        }
        cfg = dict(access.config_data or {})
        cfg["google_calendar_oauth"] = data
        # Remove the consumed state from both legacy key and list
        if cfg.get("google_calendar_oauth_state") == state:
            cfg.pop("google_calendar_oauth_state", None)
        pending_states = cfg.get("google_calendar_oauth_state_list") or []
        if isinstance(pending_states, list) and state in pending_states:
            pending_states = [s for s in pending_states if s != state]
            cfg["google_calendar_oauth_state_list"] = pending_states
        access.config_data = cfg
        access.authorize()
        await db.commit()
        try:
            # Verify persistence
            await db.refresh(access)
            persisted = (access.config_data or {}).get("google_calendar_oauth", {}) or {}
            logger.info(
                "[Google OAuth Callback] saved for access_id=%s token_present=%s refresh_present=%s",
                access.id,
                bool(persisted.get("token")),
                bool(persisted.get("refresh_token")),
            )
        except Exception:
            pass

        # Redirect back to the test UI for a smoother UX
        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            return RedirectResponse(url="/static/chatbot-test.html?google=authorized", status_code=302)

        return JSONResponse({"success": True})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/oauth/revoke")
async def google_oauth_revoke(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    try:
        access = await get_or_create_user_tool_access(db, current_user.id, "google_calendar")
        cfg = access.config_data or {}
        cfg.pop("google_calendar_oauth", None)
        access.config_data = cfg
        access.revoke_authorization()
        await db.commit()

        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            return RedirectResponse(url="/static/chatbot-test.html?google=revoked", status_code=302)

        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

