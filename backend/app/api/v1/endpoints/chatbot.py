"""
Chatbot API endpoints with streaming and non-streaming support.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer
import logging

from app.schemas.chatbot import (
    ChatRequest, ChatResponse, ChatHealthCheck, UsageStats,
    ConversationSummary, StreamingChatResponse
)
from app.services.chatbot import chatbot_service
from app.api.deps import get_current_user  # Assuming auth dependency exists

logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer(auto_error=False)


@router.post("/chat", response_model=ChatResponse)
async def chat_non_streaming(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    current_user: Optional[dict] = Depends(get_current_user)
):
    """
    Handle non-streaming chat requests.

    This endpoint processes a chat message and returns the complete response
    after the chatbot has finished processing through its thought-action-observation loop.

    Args:
        request: The chat request containing message and conversation history
        background_tasks: FastAPI background tasks for cleanup
        current_user: Optional authenticated user information

    Returns:
        ChatResponse: Complete response with thoughts, observations, and metadata

    Raises:
        HTTPException: If there's an error processing the request
    """
    try:
        logger.info(f"Received non-streaming chat request from user: {current_user.id if current_user else 'anonymous'}")

        # Validate request
        if not request.message.strip():
            raise HTTPException(
                status_code=400,
                detail="Message cannot be empty"
            )

        # Process the chat request
        response = await chatbot_service.chat_non_streaming(request)

        # Add user context to response metadata if available
        if current_user:
            response.metadata["user_id"] = current_user.id

        logger.info(f"Successfully processed non-streaming chat request for session: {response.session_id}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in chat endpoint: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while processing chat request"
        )


@router.post("/chat/stream")
async def chat_streaming(
    request: ChatRequest,
    current_user: Optional[dict] = Depends(get_current_user)
):
    """
    Handle streaming chat requests using Server-Sent Events.

    This endpoint processes a chat message and streams the response in real-time
    as the chatbot progresses through its thought-action-observation loop.

    Args:
        request: The chat request containing message and conversation history
        current_user: Optional authenticated user information

    Returns:
        StreamingResponse: SSE stream with real-time chat processing updates

    Raises:
        HTTPException: If there's an error processing the request
    """
    try:
        logger.info(f"Received streaming chat request from user: {current_user.id if current_user else 'anonymous'}")

        # Validate request
        if not request.message.strip():
            raise HTTPException(
                status_code=400,
                detail="Message cannot be empty"
            )

        # Force streaming mode
        request.stream = True

        # Create the streaming response
        async def generate_stream():
            try:
                async for chunk in chatbot_service.chat_streaming(request):
                    yield chunk
            except Exception as e:
                logger.error(f"Error in streaming generator: {str(e)}")
                # Send error event and close stream
                error_chunk = f"event: stream_error\ndata: {{\"error\": \"{str(e)}\"}}\n\n"
                yield error_chunk

        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in streaming chat endpoint: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while setting up chat stream"
        )


@router.get("/health", response_model=ChatHealthCheck)
async def get_chatbot_health():
    """
    Get the health status of the chatbot service.

    This endpoint provides information about the chatbot service health,
    including BAML client availability and rate limiting status.

    Returns:
        ChatHealthCheck: Current health status and diagnostics
    """
    try:
        health_check = await chatbot_service.get_health_check()
        return health_check
    except Exception as e:
        logger.error(f"Error in health check endpoint: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get health status"
        )


@router.get("/usage", response_model=UsageStats)
async def get_usage_statistics(
    current_user: Optional[dict] = Depends(get_current_user)
):
    """
    Get usage statistics for the chatbot service.

    This endpoint provides detailed usage metrics including token consumption,
    costs, and performance statistics. Requires authentication.

    Args:
        current_user: Authenticated user information

    Returns:
        UsageStats: Current usage statistics and metrics

    Raises:
        HTTPException: If user is not authenticated or there's an error
    """
    if not current_user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required to access usage statistics"
        )

    try:
        usage_stats = await chatbot_service.get_usage_stats()
        return usage_stats
    except Exception as e:
        logger.error(f"Error getting usage statistics: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get usage statistics"
        )


@router.get("/sessions/{session_id}", response_model=ConversationSummary)
async def get_conversation_summary(
    session_id: str,
    current_user: Optional[dict] = Depends(get_current_user)
):
    """
    Get a summary of a specific conversation session.

    Args:
        session_id: The session ID to get summary for
        current_user: Authenticated user information

    Returns:
        ConversationSummary: Summary of the conversation session

    Raises:
        HTTPException: If session not found or access denied
    """
    try:
        summary = await chatbot_service.get_conversation_summary(session_id)
        return summary
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation summary: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get conversation summary"
        )


@router.delete("/sessions/{session_id}")
async def clear_conversation_session(
    session_id: str,
    current_user: Optional[dict] = Depends(get_current_user)
):
    """
    Clear a specific conversation session.

    Args:
        session_id: The session ID to clear
        current_user: Authenticated user information

    Returns:
        dict: Success message

    Raises:
        HTTPException: If session not found or access denied
    """
    try:
        success = await chatbot_service.clear_session(session_id)
        if success:
            return {"message": f"Session {session_id} cleared successfully"}
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Session {session_id} not found"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing session: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to clear session"
        )


@router.get("/sessions")
async def list_active_sessions(
    current_user: Optional[dict] = Depends(get_current_user)
):
    """
    Get a list of active conversation sessions.

    Args:
        current_user: Authenticated user information

    Returns:
        dict: List of active session IDs

    Raises:
        HTTPException: If user is not authenticated
    """
    if not current_user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required to list sessions"
        )

    try:
        sessions = await chatbot_service.list_active_sessions()
        return {"active_sessions": sessions, "count": len(sessions)}
    except Exception as e:
        logger.error(f"Error listing sessions: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to list active sessions"
        )