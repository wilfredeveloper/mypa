"""
Personal Assistant Agent - Main agent class.
"""

import asyncio
import uuid
from typing import Dict, Any, List, Optional, AsyncGenerator
from datetime import datetime
import logging

from pocketflow import AsyncFlow
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import AgentConfig
from app.models.tool import ToolRegistry, UserToolAccess
from app.models.user import User
from app.agents.personal_assistant.flow import create_personal_assistant_flow
from app.agents.personal_assistant.tools.registry import ToolRegistryManager
from app.agents.personal_assistant.config import PersonalAssistantConfig
from utils.baml_utils import RateLimitedBAMLGeminiLLM, BAMLCollectorManager

logger = logging.getLogger(__name__)


class PersonalAssistant:
    """
    Personal Assistant Agent with tool calling capabilities.

    This agent follows the existing chatbot_core patterns while providing
    enhanced capabilities through a plugin-based tool system.
    """

    def __init__(self, user: User, db: AsyncSession, config: Optional[AgentConfig] = None):
        """
        Initialize the Personal Assistant agent.

        Args:
            user: The user this agent belongs to
            db: Database session
            config: Optional agent configuration (will create default if None)
        """
        self.user = user
        self.db = db
        self.config = config
        self._baml_client: Optional[RateLimitedBAMLGeminiLLM] = None
        self._tool_registry: Optional[ToolRegistryManager] = None
        self._sessions: Dict[str, Dict[str, Any]] = {}

        # Initialize configuration
        self._pa_config = PersonalAssistantConfig()

        logger.info(f"Initialized Personal Assistant for user {user.id}")

    async def initialize(self) -> None:
        """Initialize the agent with database configuration."""
        if not self.config:
            self.config = await self._get_or_create_config()

        # Initialize BAML client
        self._baml_client = self._get_baml_client()

        # Initialize tool registry
        self._tool_registry = ToolRegistryManager(self.user, self.db)
        await self._tool_registry.initialize()
        # Log available tools right after registry initialization
        try:
            available_tools = await self._tool_registry.get_available_tools()
            tool_names = ", ".join([t.name for t in available_tools]) if available_tools else "none"
            logger.info(
                f"Available tools at initialization for user {self.user.id}: [{tool_names}] (count={len(available_tools)})"
            )
        except Exception as e:
            logger.error(f"Failed to list available tools at initialization: {e}")


        logger.info(f"Personal Assistant initialized for user {self.user.id}")

    async def _get_or_create_config(self) -> AgentConfig:
        """Get existing config or create default one."""
        from sqlalchemy import select

        # Try to get existing config
        result = await self.db.execute(
            select(AgentConfig).where(
                AgentConfig.user_id == self.user.id,
                AgentConfig.agent_type == "personal_assistant",
                AgentConfig.is_active == True
            )
        )
        config = result.scalar_one_or_none()

        if not config:
            # Create default configuration
            config = AgentConfig(
                user_id=self.user.id,
                agent_type="personal_assistant",
                name=f"{self.user.full_name or self.user.email}'s Assistant",
                system_prompt=self._pa_config.default_system_prompt,
                config_data={
                    "personality": "professional",
                    "response_style": "conversational",
                    "enabled_tools": ["system_prompt", "planning", "virtual_fs", "tavily_search"],
                    "preferences": {
                        "timezone": "UTC",
                        "language": "en"
                    }
                },
                is_active=True
            )
            self.db.add(config)
            await self.db.commit()
            await self.db.refresh(config)

            logger.info(f"Created default config for user {self.user.id}")

        return config

    def _get_baml_client(self) -> RateLimitedBAMLGeminiLLM:
        """Get or create BAML client instance."""
        if self._baml_client is None:
            collector_manager = BAMLCollectorManager()
            self._baml_client = RateLimitedBAMLGeminiLLM(
                collector_manager=collector_manager,
                enable_streaming=True
            )
        return self._baml_client

    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        return str(uuid.uuid4())

    async def chat(self, message: str, session_id: Optional[str] = None,
                   context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process a chat message and return response.

        Args:
            message: User message
            session_id: Optional session ID for conversation continuity
            context: Optional context data

        Returns:
            Dictionary containing response and metadata
        """
        if not session_id:
            session_id = self._generate_session_id()

        # Initialize session if new
        if session_id not in self._sessions:
            self._sessions[session_id] = {
                "id": session_id,
                "created_at": datetime.utcnow(),
                "messages": [],
                "context": context or {},
                "tools_used": []
            }

        session = self._sessions[session_id]

        # Add user message to session
        session["messages"].append({
            "role": "user",
            "content": message,
            "timestamp": datetime.utcnow()
        })

        try:
            # Refresh tool registry to reflect latest OAuth status/permissions
            if self._tool_registry:
                await self._tool_registry.initialize()

            # Create and run the workflow
            flow = create_personal_assistant_flow()

            # Prepare shared data for the flow
            shared_data = {
                "user_message": message,
                "session_id": session_id,
                "session": session,
                "user": self.user,
                "config": self.config,
                "tool_registry": self._tool_registry,
                "baml_client": self._baml_client,
                "context": context or {}
            }

            # Execute the flow
            result = await flow.run_async(shared=shared_data)

            # Extract response from flow result
            response = shared_data.get("final_response", "I apologize, but I encountered an issue processing your request.")
            tools_used = shared_data.get("tools_used", [])

            # Add assistant response to session
            session["messages"].append({
                "role": "assistant",
                "content": response,
                "timestamp": datetime.utcnow(),
                "tools_used": tools_used
            })

            # Update session metadata
            session["tools_used"].extend(tools_used)
            session["updated_at"] = datetime.utcnow()

            return {
                "response": response,
                "session_id": session_id,
                "tools_used": tools_used,
                "context": session["context"],
                "metadata": {
                    "response_time_ms": (datetime.utcnow() - session["messages"][-2]["timestamp"]).total_seconds() * 1000,
                    "message_count": len(session["messages"]),
                    "session_duration_minutes": (datetime.utcnow() - session["created_at"]).total_seconds() / 60
                }
            }

        except Exception as e:
            logger.error(f"Error in chat processing: {str(e)}", exc_info=True)

            error_response = "I apologize, but I encountered an error while processing your request. Please try again."

            session["messages"].append({
                "role": "assistant",
                "content": error_response,
                "timestamp": datetime.utcnow(),
                "error": str(e)
            })

            return {
                "response": error_response,
                "session_id": session_id,
                "tools_used": [],
                "context": session["context"],
                "metadata": {
                    "error": str(e),
                    "message_count": len(session["messages"])
                }
            }