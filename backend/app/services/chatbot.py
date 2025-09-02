"""
Chatbot service layer that integrates the chatbot core functionality
with the API system, providing both streaming and non-streaming responses.
"""

import asyncio
import json
import uuid
from typing import Dict, Any, List, Optional, AsyncGenerator
from datetime import datetime
import logging

from pocketflow import AsyncFlow
from fastapi import HTTPException

# Import chatbot core components
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'chatbot_core'))

from flow import create_tao_chatbot_flow
from nodes import get_baml_client
from utils.baml_utils import RateLimitedBAMLGeminiLLM, BAMLCollectorManager

# Import schemas
from app.schemas.chatbot import (
    ChatRequest, ChatResponse, StreamChunk, ThoughtStep,
    ChatHealthCheck, UsageStats, ConversationSummary, SSEEvent
)

logger = logging.getLogger(__name__)


class ChatbotService:
    """
    Service class that handles chatbot interactions with both streaming
    and non-streaming capabilities.
    """

    def __init__(self):
        """Initialize the chatbot service."""
        self._baml_client = None
        self._conversation_sessions: Dict[str, Dict[str, Any]] = {}
        self._last_successful_call: Optional[datetime] = None

    def _get_baml_client(self) -> RateLimitedBAMLGeminiLLM:
        """Get or create the BAML client instance."""
        if self._baml_client is None:
            self._baml_client = get_baml_client()
        return self._baml_client

    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        return str(uuid.uuid4())

    def _prepare_conversation_context(self, request: ChatRequest) -> Dict[str, Any]:
        """Prepare the conversation context for the chatbot flow."""
        # Convert conversation history to the format expected by the chatbot core
        conversation_history = []
        for msg in request.conversation_history:
            conversation_history.append({
                "role": msg.role,
                "content": msg.content
            })

        # Add the current message to history
        conversation_history.append({
            "role": "user",
            "content": request.message
        })

        return {
            "query": request.message,
            "conversation_history": conversation_history,
            "session_id": request.session_id or self._generate_session_id(),
            "observations": [],
            "thoughts": [],
            "current_thought_number": 0
        }

    async def chat_non_streaming(self, request: ChatRequest) -> ChatResponse:
        """
        Handle non-streaming chat requests.

        Args:
            request: The chat request

        Returns:
            ChatResponse with the complete response

        Raises:
            HTTPException: If there's an error processing the request
        """
        try:
            logger.info(f"Processing non-streaming chat request: {request.message[:100]}...")

            # Prepare context
            context = self._prepare_conversation_context(request)
            session_id = context["session_id"]

            # Store session info
            self._conversation_sessions[session_id] = {
                "start_time": datetime.now(),
                "last_activity": datetime.now(),
                "message_count": len(request.conversation_history) + 1,
                "total_tokens": 0
            }

            # Create and run the chatbot flow
            flow = create_tao_chatbot_flow()
            result = await flow.run_async(shared=context)

            # Extract the final response and metadata
            final_answer = context.get("final_answer", "I apologize, but I couldn't generate a proper response.")
            thoughts = context.get("thoughts", [])
            observations = context.get("observations", [])

            # Convert thoughts to the expected format
            thought_steps = []
            for thought in thoughts:
                thought_steps.append(ThoughtStep(
                    thinking=thought.get("thinking", ""),
                    action=thought.get("action", ""),
                    action_input=thought.get("action_input", ""),
                    is_final=thought.get("is_final", False),
                    thought_number=thought.get("thought_number", 0)
                ))

            # Get usage statistics
            baml_client = self._get_baml_client()
            usage_stats = baml_client.get_usage_stats()

            # Update session info
            self._conversation_sessions[session_id]["last_activity"] = datetime.now()
            self._conversation_sessions[session_id]["total_tokens"] = usage_stats.get("total_tokens", 0)

            self._last_successful_call = datetime.now()

            return ChatResponse(
                response=final_answer,
                session_id=session_id,
                thoughts=thought_steps,
                observations=observations,
                metadata={
                    "processing_time_ms": (datetime.now() - self._conversation_sessions[session_id]["start_time"]).total_seconds() * 1000,
                    "flow_completed": True
                },
                usage_stats=usage_stats
            )

        except Exception as e:
            logger.error(f"Error in non-streaming chat: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process chat request: {str(e)}"
            )

    async def chat_streaming(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        """
        Handle streaming chat requests using Server-Sent Events.

        Args:
            request: The chat request

        Yields:
            SSE-formatted strings containing streaming chunks

        Raises:
            HTTPException: If there's an error processing the request
        """
        try:
            logger.info(f"Processing streaming chat request: {request.message[:100]}...")

            # Prepare context
            context = self._prepare_conversation_context(request)
            session_id = context["session_id"]
            stream_id = str(uuid.uuid4())

            # Store session info
            self._conversation_sessions[session_id] = {
                "start_time": datetime.now(),
                "last_activity": datetime.now(),
                "message_count": len(request.conversation_history) + 1,
                "total_tokens": 0,
                "stream_id": stream_id
            }

            # Send initial stream start event
            start_event = SSEEvent(
                event="stream_start",
                data=json.dumps({
                    "session_id": session_id,
                    "stream_id": stream_id,
                    "status": "started"
                }),
                id=str(uuid.uuid4())
            )
            yield start_event.format_sse()

            # Create the chatbot flow
            flow = create_tao_chatbot_flow()

            # Run the flow with streaming by monitoring the shared context
            async for chunk in self._run_flow_with_streaming(flow, context, stream_id):
                yield chunk

            # Send final completion event
            final_answer = context.get("final_answer", "I apologize, but I couldn't generate a proper response.")

            completion_event = SSEEvent(
                event="stream_complete",
                data=json.dumps({
                    "type": "final",
                    "content": final_answer,
                    "session_id": session_id,
                    "stream_id": stream_id,
                    "is_complete": True
                }),
                id=str(uuid.uuid4())
            )
            yield completion_event.format_sse()

            # Update session info
            self._conversation_sessions[session_id]["last_activity"] = datetime.now()
            self._last_successful_call = datetime.now()

        except Exception as e:
            logger.error(f"Error in streaming chat: {str(e)}")
            # Send error event
            error_event = SSEEvent(
                event="stream_error",
                data=json.dumps({
                    "type": "error",
                    "content": f"Error: {str(e)}",
                    "error_code": "PROCESSING_ERROR"
                }),
                id=str(uuid.uuid4())
            )
            yield error_event.format_sse()

    async def _run_flow_with_streaming(self, flow: AsyncFlow, context: Dict[str, Any], stream_id: str):
        """
        Run the chatbot flow while streaming intermediate results.

        Args:
            flow: The chatbot flow to run
            context: The conversation context
            stream_id: Unique stream identifier
        """
        # This is a simplified streaming implementation
        # In a more advanced version, you would hook into the flow execution
        # to stream thoughts, actions, and observations as they happen

        # For now, we'll run the flow and then stream the results
        result = await flow.run_async(shared=context)

        # Stream thoughts as they were processed
        thoughts = context.get("thoughts", [])
        for i, thought in enumerate(thoughts):
            thought_event = SSEEvent(
                event="stream_chunk",
                data=json.dumps({
                    "type": "thought",
                    "content": thought.get("thinking", ""),
                    "metadata": {
                        "action": thought.get("action", ""),
                        "thought_number": thought.get("thought_number", i + 1)
                    },
                    "is_complete": True
                }),
                id=str(uuid.uuid4())
            )
            yield thought_event.format_sse()

            # Small delay to simulate real-time streaming
            await asyncio.sleep(0.1)

        # Stream observations
        observations = context.get("observations", [])
        for observation in observations:
            obs_event = SSEEvent(
                event="stream_chunk",
                data=json.dumps({
                    "type": "observation",
                    "content": observation,
                    "is_complete": True
                }),
                id=str(uuid.uuid4())
            )
            yield obs_event.format_sse()
            await asyncio.sleep(0.1)

        # Stream the final answer as a chunk before the completion event
        final_answer = context.get("final_answer")
        if final_answer:
            logger.info(f"Streaming final answer: {final_answer}")
            final_chunk_event = SSEEvent(
                event="stream_chunk",
                data=json.dumps({
                    "type": "final_answer",
                    "content": final_answer,
                    "is_complete": True
                }),
                id=str(uuid.uuid4())
            )
            yield final_chunk_event.format_sse()
            await asyncio.sleep(0.1)

    async def get_health_check(self) -> ChatHealthCheck:
        """
        Get the health status of the chatbot service.

        Returns:
            ChatHealthCheck with current service status
        """
        try:
            # Check BAML client availability
            baml_client = self._get_baml_client()
            baml_available = baml_client is not None

            # Get rate limit status
            rate_limit_status = {}
            if baml_available:
                usage_stats = baml_client.get_usage_stats()
                rate_limit_status = {
                    "total_calls_today": usage_stats.get("total_calls", 0),
                    "successful_calls": usage_stats.get("successful_calls", 0),
                    "failed_calls": usage_stats.get("failed_calls", 0)
                }

            # Determine overall health status
            if baml_available and self._last_successful_call:
                # Check if last successful call was recent (within last hour)
                time_since_last_call = datetime.now() - self._last_successful_call
                if time_since_last_call.total_seconds() < 3600:  # 1 hour
                    status = "healthy"
                else:
                    status = "degraded"
            elif baml_available:
                status = "degraded"  # BAML available but no successful calls yet
            else:
                status = "unhealthy"

            return ChatHealthCheck(
                status=status,
                baml_available=baml_available,
                rate_limit_status=rate_limit_status,
                last_successful_call=self._last_successful_call,
                error_details=None if status != "unhealthy" else "BAML client not available"
            )

        except Exception as e:
            logger.error(f"Error in health check: {str(e)}")
            return ChatHealthCheck(
                status="unhealthy",
                baml_available=False,
                rate_limit_status={},
                last_successful_call=self._last_successful_call,
                error_details=str(e)
            )

    async def get_usage_stats(self) -> UsageStats:
        """
        Get usage statistics for the chatbot service.

        Returns:
            UsageStats with current usage information
        """
        try:
            baml_client = self._get_baml_client()
            if baml_client:
                stats = baml_client.get_usage_stats()
                return UsageStats(
                    total_calls=stats.get("total_calls", 0),
                    successful_calls=stats.get("successful_calls", 0),
                    failed_calls=stats.get("failed_calls", 0),
                    total_tokens=stats.get("total_tokens", 0),
                    total_input_tokens=stats.get("total_input_tokens", 0),
                    total_output_tokens=stats.get("total_output_tokens", 0),
                    total_cost=stats.get("total_cost", 0.0),
                    average_duration_ms=stats.get("average_duration_ms", 0.0)
                )
            else:
                return UsageStats(
                    total_calls=0,
                    successful_calls=0,
                    failed_calls=0,
                    total_tokens=0,
                    total_input_tokens=0,
                    total_output_tokens=0,
                    total_cost=0.0,
                    average_duration_ms=0.0
                )
        except Exception as e:
            logger.error(f"Error getting usage stats: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get usage statistics: {str(e)}"
            )

    async def get_conversation_summary(self, session_id: str) -> ConversationSummary:
        """
        Get a summary of a conversation session.

        Args:
            session_id: The session ID to get summary for

        Returns:
            ConversationSummary with session information

        Raises:
            HTTPException: If session not found
        """
        if session_id not in self._conversation_sessions:
            raise HTTPException(
                status_code=404,
                detail=f"Session {session_id} not found"
            )

        session_data = self._conversation_sessions[session_id]

        # Calculate estimated cost based on tokens used
        total_tokens = session_data.get("total_tokens", 0)
        estimated_cost = total_tokens * 0.000001  # Rough estimate: $1 per 1M tokens

        return ConversationSummary(
            session_id=session_id,
            message_count=session_data.get("message_count", 0),
            start_time=session_data.get("start_time", datetime.now()),
            last_activity=session_data.get("last_activity", datetime.now()),
            total_tokens_used=total_tokens,
            estimated_cost=estimated_cost
        )

    async def clear_session(self, session_id: str) -> bool:
        """
        Clear a conversation session.

        Args:
            session_id: The session ID to clear

        Returns:
            True if session was cleared, False if not found
        """
        if session_id in self._conversation_sessions:
            del self._conversation_sessions[session_id]
            return True
        return False

    async def list_active_sessions(self) -> List[str]:
        """
        Get a list of active session IDs.

        Returns:
            List of active session IDs
        """
        return list(self._conversation_sessions.keys())


# Global service instance
chatbot_service = ChatbotService()