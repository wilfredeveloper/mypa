"""
Agent configuration database models.
"""

from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class AgentConfig(Base):
    """Agent configuration model for storing user-specific agent settings."""

    __tablename__ = "agent_configs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    agent_type = Column(String(50), nullable=False, index=True)  # 'personal_assistant'
    name = Column(String(255), nullable=False)
    system_prompt = Column(Text, nullable=True)
    config_data = Column(JSON, nullable=True)  # Agent-specific configuration

    # Status fields
    is_active = Column(Boolean, default=True, nullable=False)

    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="agent_configs")

    def __repr__(self):
        return f"<AgentConfig(id={self.id}, user_id={self.user_id}, type={self.agent_type}, name={self.name})>"

    @property
    def config(self) -> Dict[str, Any]:
        """Get configuration data as dictionary."""
        return self.config_data or {}

    @config.setter
    def config(self, value: Dict[str, Any]):
        """Set configuration data."""
        self.config_data = value

    def update_config(self, updates: Dict[str, Any]) -> None:
        """Update specific configuration keys."""
        current_config = self.config
        current_config.update(updates)
        self.config_data = current_config

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get a specific configuration value."""
        return self.config.get(key, default)

    def set_config_value(self, key: str, value: Any) -> None:
        """Set a specific configuration value."""
        current_config = self.config
        current_config[key] = value
        self.config_data = current_config