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
        # Initialize agent per request to ensure fresh tool registry tied to user
        agent = PersonalAssistant(current_user, db)
        await agent.initialize()

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

