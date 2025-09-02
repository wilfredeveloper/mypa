"""
Pydantic schemas for chatbot API endpoints.
"""

from typing import List, Optional, Dict, Any, Literal, Union
from pydantic import BaseModel, Field
from datetime import datetime


class ConversationMessage(BaseModel):
    """A single message in the conversation history."""
    role: Literal["user", "assistant"] = Field(..., description="The role of the message sender")
    content: str = Field(..., description="The content of the message")
    timestamp: Optional[datetime] = Field(default=None, description="When the message was sent")


class ChatRequest(BaseModel):
    """Request schema for chatbot interactions."""
    message: str = Field(..., description="The user's message to the chatbot", min_length=1, max_length=4000)
    conversation_history: Optional[List[ConversationMessage]] = Field(
        default=[],
        description="Previous conversation history for context",
        max_items=50
    )
    stream: bool = Field(default=False, description="Whether to stream the response")
    session_id: Optional[str] = Field(default=None, description="Optional session ID for conversation tracking")


class ThoughtStep(BaseModel):
    """A single thought step in the reasoning process."""
    thinking: str = Field(..., description="The reasoning or thought process")
    action: str = Field(..., description="The action decided upon")
    action_input: str = Field(..., description="The input for the action")
    is_final: bool = Field(..., description="Whether this is the final step")
    thought_number: int = Field(..., description="The sequential number of this thought")


class ChatResponse(BaseModel):
    """Response schema for non-streaming chatbot interactions."""
    response: str = Field(..., description="The chatbot's response")
    session_id: Optional[str] = Field(default=None, description="Session ID for conversation tracking")
    thoughts: Optional[List[ThoughtStep]] = Field(default=[], description="The reasoning steps taken")
    observations: Optional[List[str]] = Field(default=[], description="Observations made during processing")
    metadata: Optional[Dict[str, Any]] = Field(default={}, description="Additional metadata about the response")
    usage_stats: Optional[Dict[str, Any]] = Field(default={}, description="Token usage and cost information")


class StreamChunk(BaseModel):
    """A single chunk in a streaming response."""
    type: Literal["thought", "action", "observation", "response", "final", "error"] = Field(
        ..., description="The type of chunk being streamed"
    )
    content: str = Field(..., description="The content of this chunk")
    metadata: Optional[Dict[str, Any]] = Field(default={}, description="Additional metadata for this chunk")
    is_complete: bool = Field(default=False, description="Whether this chunk represents a complete unit")


class StreamingChatResponse(BaseModel):
    """Response schema for streaming chatbot interactions."""
    session_id: Optional[str] = Field(default=None, description="Session ID for conversation tracking")
    stream_id: str = Field(..., description="Unique identifier for this streaming session")
    status: Literal["started", "streaming", "completed", "error"] = Field(
        ..., description="Current status of the stream"
    )


class ChatError(BaseModel):
    """Error response schema for chatbot interactions."""
    error: str = Field(..., description="Error message")
    error_code: str = Field(..., description="Error code for programmatic handling")
    details: Optional[Dict[str, Any]] = Field(default={}, description="Additional error details")
    session_id: Optional[str] = Field(default=None, description="Session ID if available")


class ChatHealthCheck(BaseModel):
    """Health check response for chatbot service."""
    status: Literal["healthy", "degraded", "unhealthy"] = Field(..., description="Service health status")
    baml_available: bool = Field(..., description="Whether BAML client is available")
    rate_limit_status: Dict[str, Any] = Field(..., description="Current rate limiting status")
    last_successful_call: Optional[datetime] = Field(default=None, description="Last successful BAML call")
    error_details: Optional[str] = Field(default=None, description="Error details if unhealthy")


class UsageStats(BaseModel):
    """Usage statistics for the chatbot service."""
    total_calls: int = Field(..., description="Total number of calls made")
    successful_calls: int = Field(..., description="Number of successful calls")
    failed_calls: int = Field(..., description="Number of failed calls")
    total_tokens: int = Field(..., description="Total tokens used")
    total_input_tokens: int = Field(..., description="Total input tokens")
    total_output_tokens: int = Field(..., description="Total output tokens")
    total_cost: float = Field(..., description="Total estimated cost in USD")
    average_duration_ms: float = Field(..., description="Average response duration in milliseconds")


class ConversationSummary(BaseModel):
    """Summary of a conversation session."""
    session_id: str = Field(..., description="Session identifier")
    message_count: int = Field(..., description="Number of messages in the conversation")
    start_time: datetime = Field(..., description="When the conversation started")
    last_activity: datetime = Field(..., description="Last activity timestamp")
    total_tokens_used: int = Field(..., description="Total tokens used in this conversation")
    estimated_cost: float = Field(..., description="Estimated cost for this conversation")


# Server-Sent Events schemas for streaming
class SSEEvent(BaseModel):
    """Server-Sent Event format for streaming responses."""
    event: Optional[str] = Field(default=None, description="Event type")
    data: str = Field(..., description="Event data as JSON string")
    id: Optional[str] = Field(default=None, description="Event ID")
    retry: Optional[int] = Field(default=None, description="Retry interval in milliseconds")

    def format_sse(self) -> str:
        """Format as Server-Sent Event string."""
        lines = []
        if self.event:
            lines.append(f"event: {self.event}")
        if self.id:
            lines.append(f"id: {self.id}")
        if self.retry:
            lines.append(f"retry: {self.retry}")
        lines.append(f"data: {self.data}")
        lines.append("")  # Empty line to end the event
        lines.append("")  # Second empty line for proper SSE separation
        return "\n".join(lines)