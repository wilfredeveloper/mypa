"""
User database model.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base
# Ensure related models are imported so SQLAlchemy can resolve relationship targets
from app.models.agent import AgentConfig  # noqa: F401
from app.models.tool import UserToolAccess  # noqa: F401
from app.models.oauth_token import OAuthToken  # noqa: F401



class User(Base):
    """User model for authentication and user management."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=True)
    full_name = Column(String(255), nullable=True)
    hashed_password = Column(String(255), nullable=False)

    # User status
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)

    # Profile information
    bio = Column(Text, nullable=True)
    avatar_url = Column(String(500), nullable=True)

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
    last_login = Column(DateTime(timezone=True), nullable=True)

    # Relationships for Personal Assistant
    agent_configs = relationship("AgentConfig", back_populates="user", cascade="all, delete-orphan")
    tool_access = relationship("UserToolAccess", back_populates="user", cascade="all, delete-orphan")
    oauth_tokens = relationship("OAuthToken", back_populates="user", cascade="all, delete-orphan")
    conversation_sessions = relationship("ConversationSession", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}')>"
