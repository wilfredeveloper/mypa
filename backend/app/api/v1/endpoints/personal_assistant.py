"""
Personal Assistant API endpoints (non-streaming for now).
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_async_session
from app.models.user import User
from app.agents.personal_assistant.agent import PersonalAssistant
from app.services.agent_session_manager import get_personal_assistant_agent

logger = logging.getLogger(__name__)
router = APIRouter()


class PAChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class PAChatResponse(BaseModel):
    response: str
    session_id: str
    tools_used: list
    context: Dict[str, Any]
    metadata: Dict[str, Any]


@router.post("/chat", response_model=PAChatResponse)
async def pa_chat(
    request: PAChatRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Non-streaming chat via Personal Assistant agent (with tools)."""
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    try:
        # Get cached agent instance from session manager
        from app.services.agent_session_manager import get_agent_session_manager
        session_manager = await get_agent_session_manager()
        agent = await session_manager.get_agent(current_user, db)

        result = await agent.chat(
            message=request.message,
            session_id=request.session_id,
            context=request.context,
        )

        # Shape result to response model
        return PAChatResponse(
            response=result.get("response", ""),
            session_id=result.get("session_id", ""),
            tools_used=result.get("tools_used", []),
            context=result.get("context", {}),
            metadata=result.get("metadata", {}),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PA chat failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process chat request")


@router.get("/session-stats")
async def get_session_stats(
    current_user: User = Depends(get_current_user),
):
    """Get session manager statistics."""
    try:
        from app.services.agent_session_manager import get_agent_session_manager
        session_manager = await get_agent_session_manager()
        stats = session_manager.get_stats()
        return stats
    except Exception as e:
        logger.error(f"Failed to get session stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get session statistics")


@router.post("/cleanup-sessions")
async def cleanup_idle_sessions(
    current_user: User = Depends(get_current_user),
):
    """Manually trigger cleanup of idle agent sessions."""
    try:
        from app.services.agent_session_manager import get_agent_session_manager
        session_manager = await get_agent_session_manager()
        cleaned_count = await session_manager.cleanup_idle_agents()
        return {"cleaned_agents": cleaned_count}
    except Exception as e:
        logger.error(f"Failed to cleanup sessions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to cleanup sessions")

