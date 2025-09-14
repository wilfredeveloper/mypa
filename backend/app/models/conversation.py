"""
Database models for conversation sessions and messages.
"""

from typing import Optional, Dict, Any
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import uuid

from app.core.database import Base


class ConversationSession(Base):
    """
    Represents a conversation session between a user and the assistant.
    
    A session groups related messages together and maintains conversation context.
    Sessions can be created explicitly by the user or automatically by the system.
    """
    __tablename__ = "conversation_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(36), unique=True, nullable=False, index=True)  # UUID
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Session metadata
    title = Column(String(255), nullable=True)  # Optional user-defined title
    description = Column(Text, nullable=True)  # Optional description
    
    # Session state
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Context and metadata
    context_data = Column(JSON, nullable=True)  # Session-specific context
    session_metadata = Column(JSON, nullable=True)  # Additional metadata
    
    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    last_activity_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    user = relationship("User", back_populates="conversation_sessions")
    messages = relationship(
        "ConversationMessage", 
        back_populates="session", 
        cascade="all, delete-orphan",
        order_by="ConversationMessage.created_at"
    )

    def __repr__(self) -> str:
        return f"<ConversationSession(id={self.id}, session_id='{self.session_id}', user_id={self.user_id})>"

    @classmethod
    def generate_session_id(cls) -> str:
        """Generate a new unique session ID."""
        return str(uuid.uuid4())

    def update_activity(self) -> None:
        """Update the last activity timestamp."""
        self.last_activity_at = datetime.utcnow()

    def get_message_count(self) -> int:
        """Get the number of messages in this session."""
        return len(self.messages)

    def get_latest_message(self) -> Optional['ConversationMessage']:
        """Get the most recent message in this session."""
        if self.messages:
            return max(self.messages, key=lambda m: m.created_at)
        return None


class ConversationMessage(Base):
    """
    Represents a single message in a conversation session.
    
    Messages can be from the user or the assistant, and include metadata
    about tools used, processing time, etc.
    """
    __tablename__ = "conversation_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(36), ForeignKey("conversation_sessions.session_id"), nullable=False, index=True)
    
    # Message content
    role = Column(String(20), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    
    # Message metadata
    tools_used = Column(JSON, nullable=True)  # List of tools used for this message
    processing_time_ms = Column(Integer, nullable=True)  # Time taken to generate response
    token_count = Column(Integer, nullable=True)  # Number of tokens in the message
    
    # Error handling
    has_error = Column(Boolean, default=False, nullable=False)
    error_message = Column(Text, nullable=True)
    
    # Additional metadata
    message_metadata = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    session = relationship("ConversationSession", back_populates="messages")

    def __repr__(self) -> str:
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"<ConversationMessage(id={self.id}, role='{self.role}', content='{content_preview}')>"

    def is_user_message(self) -> bool:
        """Check if this is a user message."""
        return self.role == "user"

    def is_assistant_message(self) -> bool:
        """Check if this is an assistant message."""
        return self.role == "assistant"

    def get_tools_used_names(self) -> list:
        """Get a list of tool names used in this message."""
        if not self.tools_used:
            return []
        
        if isinstance(self.tools_used, list):
            return [tool.get('tool', tool.get('name', 'unknown')) for tool in self.tools_used]
        
        return []
