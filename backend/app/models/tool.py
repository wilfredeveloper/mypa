"""
Tool registry database models.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class ToolType(str, Enum):
    """Tool type enumeration."""
    BUILTIN = "builtin"
    EXTERNAL = "external"


class ToolRegistry(Base):
    """Registry of available tools in the system."""

    __tablename__ = "tool_registry"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    display_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    tool_type = Column(SQLEnum(ToolType), nullable=False, index=True)
    category = Column(String(50), nullable=True, index=True)  # e.g., 'productivity', 'communication'

    # Tool schema and configuration
    schema_data = Column(JSON, nullable=False)  # Tool schema definition (parameters, etc.)
    config_schema = Column(JSON, nullable=True)  # Configuration schema for user settings

    # Permissions and requirements
    permissions_required = Column(JSON, nullable=True)  # List of required permissions/scopes
    oauth_provider = Column(String(50), nullable=True)  # e.g., 'google' for external tools

    # Rate limiting
    rate_limit_per_minute = Column(Integer, default=60, nullable=False)
    rate_limit_per_day = Column(Integer, default=1000, nullable=False)

    # Status fields
    is_enabled = Column(Boolean, default=True, nullable=False)
    is_beta = Column(Boolean, default=False, nullable=False)

    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user_access = relationship("UserToolAccess", back_populates="tool")

    def __repr__(self):
        return f"<ToolRegistry(id={self.id}, name={self.name}, type={self.tool_type})>"

    @property
    def schema(self) -> Dict[str, Any]:
        """Get tool schema as dictionary."""
        return self.schema_data or {}

    @property
    def config_template(self) -> Dict[str, Any]:
        """Get configuration template as dictionary."""
        return self.config_schema or {}

    @property
    def required_permissions(self) -> List[str]:
        """Get list of required permissions."""
        return self.permissions_required or []

    def is_external_tool(self) -> bool:
        """Check if this is an external tool requiring OAuth."""
        return self.tool_type == ToolType.EXTERNAL

    def requires_oauth(self) -> bool:
        """Check if tool requires OAuth authentication."""
        return self.is_external_tool() and self.oauth_provider is not None

    @classmethod
    def get_tool_schema(cls, tool_name: str, session) -> Optional[Dict[str, Any]]:
        """Get schema for a specific tool by name."""
        tool = session.query(cls).filter(cls.name == tool_name).first()
        return tool.schema if tool else None


class UserToolAccess(Base):
    """User-specific tool access and configuration."""

    __tablename__ = "user_tool_access"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    tool_id = Column(Integer, ForeignKey("tool_registry.id"), nullable=False, index=True)

    # Authorization status
    is_authorized = Column(Boolean, default=False, nullable=False)
    authorization_date = Column(DateTime(timezone=True), nullable=True)

    # User-specific configuration
    config_data = Column(JSON, nullable=True)  # User-specific tool configuration

    # Usage tracking
    usage_count = Column(Integer, default=0, nullable=False)
    last_used = Column(DateTime(timezone=True), nullable=True)

    # Rate limiting tracking
    daily_usage_count = Column(Integer, default=0, nullable=False)
    daily_usage_reset = Column(DateTime(timezone=True), nullable=True)

    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="tool_access")
    tool = relationship("ToolRegistry", back_populates="user_access")

    def __repr__(self):
        return f"<UserToolAccess(id={self.id}, user_id={self.user_id}, tool_id={self.tool_id}, authorized={self.is_authorized})>"

    @property
    def config(self) -> Dict[str, Any]:
        """Get user configuration as dictionary."""
        return self.config_data or {}

    @config.setter
    def config(self, value: Dict[str, Any]):
        """Set user configuration."""
        self.config_data = value

    def update_config(self, updates: Dict[str, Any]) -> None:
        """Update specific configuration keys."""
        current_config = self.config
        current_config.update(updates)
        self.config_data = current_config

    def increment_usage(self) -> None:
        """Increment usage counters."""
        self.usage_count += 1
        self.daily_usage_count += 1
        self.last_used = datetime.utcnow()

    def reset_daily_usage(self) -> None:
        """Reset daily usage counter."""
        self.daily_usage_count = 0
        self.daily_usage_reset = datetime.utcnow()

    def is_rate_limited(self) -> bool:
        """Check if user has exceeded rate limits for this tool."""
        if not self.tool:
            return False

        # Check daily limit
        if self.daily_usage_count >= self.tool.rate_limit_per_day:
            return True

        return False

    def authorize(self) -> None:
        """Mark tool as authorized for user."""
        self.is_authorized = True
        self.authorization_date = datetime.utcnow()

    def revoke_authorization(self) -> None:
        """Revoke tool authorization for user."""
        self.is_authorized = False
        self.authorization_date = None