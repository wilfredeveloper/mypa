"""
Personal Assistant API endpoints (non-streaming for now).
"""

from typing import Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.api.deps import get_current_user
from app.core.database import get_async_session
from app.models.user import User
from app.agents.personal_assistant.agent import PersonalAssistant
from app.services.agent_session_manager import get_personal_assistant_agent
from app.services.conversation_service import ConversationService
from app.models.conversation import ConversationSession, ConversationMessage

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
    """Get session manager statistics and debug information."""
    try:
        from app.services.agent_session_manager import get_agent_session_manager
        session_manager = await get_agent_session_manager()
        stats = session_manager.get_stats()

        # Add additional debug information
        debug_info = {
            "agent_stats": stats,
            "user_id": current_user.id,
            "user_email": current_user.email,
            "timestamp": datetime.utcnow().isoformat(),
            "active_agents": len(session_manager._agents) if hasattr(session_manager, '_agents') else 0
        }

        return debug_info
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


@router.post("/sessions/new")
async def create_new_session(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Create a new conversation session."""
    try:
        conversation_service = ConversationService(db)
        session = await conversation_service.create_session(user=current_user)

        return {
            "session_id": session.session_id,
            "created_at": session.created_at,
            "message": "New conversation session created"
        }
    except Exception as e:
        logger.error(f"Failed to create new session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create new session")


@router.get("/sessions")
async def get_user_sessions(
    limit: int = 20,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Get conversation sessions for the current user."""
    try:
        conversation_service = ConversationService(db)
        sessions = await conversation_service.get_user_sessions(
            user=current_user,
            limit=limit
        )

        # Get message counts for each session using a separate query to avoid lazy loading issues
        session_data = []
        for session in sessions:
            # Get message count using a direct query to avoid lazy loading

            count_query = select(func.count(ConversationMessage.id)).where(
                ConversationMessage.session_id == session.session_id
            )
            count_result = await db.execute(count_query)
            message_count = count_result.scalar() or 0

            session_data.append({
                "session_id": session.session_id,
                "title": session.title,
                "created_at": session.created_at,
                "last_activity_at": session.last_activity_at,
                "message_count": message_count,
                "is_active": session.is_active
            })

        return {"sessions": session_data}
    except Exception as e:
        logger.error(f"Failed to get user sessions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get user sessions")


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Get messages for a specific session."""
    try:
        conversation_service = ConversationService(db)
        session = await conversation_service.get_session(
            session_id=session_id,
            user=current_user,
            include_messages=True
        )

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        return {
            "session_id": session.session_id,
            "messages": [
                {
                    "id": msg.id,
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": msg.created_at,
                    "tools_used": msg.get_tools_used_names(),
                    "has_error": msg.has_error,
                    "processing_time_ms": msg.processing_time_ms
                }
                for msg in session.messages
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get session messages: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get session messages")


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    """Delete a conversation session."""
    try:
        conversation_service = ConversationService(db)
        session = await conversation_service.get_session(
            session_id=session_id,
            user=current_user,
            include_messages=False
        )

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        await conversation_service.delete_session(session)

        return {"message": f"Session {session_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete session")

