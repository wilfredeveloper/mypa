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
from app.agents.personal_assistant.tool_entity_store import ToolEntityStore
from app.services.conversation_service import ConversationService
from app.models.conversation import ConversationSession, ConversationMessage
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

        logger.info(f"\n\n >>Initialized Personal Assistant for user {user.id}\n")

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
            
            logger.info(f"\n\n >>Available tools at initialization for user {self.user.id}: [{tool_names}] (count={len(available_tools)})\n")
        except Exception as e:
            logger.error(f"Failed to list available tools at initialization: {e}")


        logger.info(f"\n\n >>Personal Assistant initialized for user {self.user.id}\n")

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

            logger.info(f"\n\n >>Created default config for user {self.user.id}\n")

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
        # Debug: Log received session_id
        logger.info(f"\n\n >>🔍 DEBUG: Received session_id: {repr(session_id)} (type: {type(session_id)})\n")
        logger.info(f"\n\n >>🔥Received Context: {context}\n")

        # Initialize conversation service
        conversation_service = ConversationService(self.db)

        # Get or create database session
        db_session = await conversation_service.get_or_create_session(
            user=self.user,
            session_id=session_id,
            context_data=context
        )

        # Use the database session ID (in case we created a new one)
        session_id = str(db_session.session_id)  # Ensure it's a string
        logger.info(f"\n\n >>🎯 Using session_id: {session_id} (DB session exists: {db_session.id is not None})\n")

        # Debug: Log session state
        logger.info(f"\n\n >>🔍 DEBUG: Checking session {session_id}\n")
        logger.info(f"\n\n >>   📋 Current sessions in agent: {list(self._sessions.keys())}\n")
        logger.info(f"\n\n >>   🎯 Session exists in memory: {session_id in self._sessions}\n")

        # Initialize session if new
        if session_id not in self._sessions:
            # Try to load existing entity store from disk
            entity_store = ToolEntityStore.load_from_disk(session_id)
            if entity_store is None:
                entity_store = ToolEntityStore(session_id)
                logger.info(f"\n\n >>🆕 Created NEW entity store for session {session_id}\n")
            else:
                logger.info(f"\n\n >>💾 Loaded EXISTING entity store for session {session_id}\n")
                # Log what was loaded
                context_summary = entity_store.get_context_summary()
                logger.info(f"\n\n >>📊 Loaded entity store contains: {context_summary['total_entities']} entities, {context_summary['total_tool_executions']} tool executions\n")

            self._sessions[session_id] = {
                "id": session_id,
                "created_at": datetime.utcnow(),
                "messages": [],
                "context": context or {},
                "tools_used": [],
                "entity_store": entity_store
            }
            logger.info(f"\n\n >>🎯 Initialized NEW session {session_id} for user {self.user.id}\n")
        else:
            logger.info(f"\n\n >>♻️  Reusing EXISTING session {session_id} for user {self.user.id}\n")
            # Log current session state
            session = self._sessions[session_id]
            entity_store = session["entity_store"]
            context_summary = entity_store.get_context_summary()
            logger.info(f"\n\n >>📊 Current session state: {len(session['messages'])} messages, {context_summary['total_entities']} entities, {context_summary['total_tool_executions']} tool executions\n")

        session = self._sessions[session_id]

        # Add user message to database and session
        await conversation_service.add_message(
            session=db_session,
            role="user",
            content=message
        )

        session["messages"].append({
            "role": "user",
            "content": message,
            "timestamp": datetime.utcnow()
        })

        try:
            # Log detailed context before processing
            entity_store = session["entity_store"]
            context_summary = entity_store.get_context_summary()
            logger.info(f"\n\n >>🧠 AGENT CONTEXT BEFORE PROCESSING:\n")
            logger.info(f"\n\n >>   📝 User Message: '{message}'\n")
            logger.info(f"\n\n >>   🆔 Session ID: {session_id}\n")
            logger.info(f"\n\n >>   👤 User ID: {self.user.id}\n")
            logger.info(f"\n\n >>   📊 Memory Summary: {context_summary}\n")

            # Log recent conversation history
            recent_messages = session["messages"][-3:]  # Last 3 messages including current
            logger.info(f"\n\n >>   💬 Recent Messages ({len(recent_messages)}):\n")
            for i, msg in enumerate(recent_messages):
                logger.info(f"\n\n >>      {i+1}. [{msg['role']}]: {msg['content'][:100]}...\n")

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
                "context": context or {},
                "entity_store": session["entity_store"]
            }

            # Execute the flow
            result = await flow.run_async(shared=shared_data)

            # Extract response from flow result
            response = shared_data.get("final_response", "I apologize, but I encountered an issue processing your request.")
            tools_used = shared_data.get("tools_used", [])

            # Log detailed context after processing
            context_summary_after = entity_store.get_context_summary()
            logger.info(f"\n\n >>🎯 AGENT CONTEXT AFTER PROCESSING:\n")
            logger.info(f"\n\n >>   📤 Response: '{response[:100]}...'\n")
            logger.info(f"\n\n >>   🔧 Tools Used: {[tool.get('name', 'unknown') for tool in tools_used]}\n")
            logger.info(f"\n\n >>   📊 Memory Summary After: {context_summary_after}\n")

            # Log changes in memory
            entities_added = context_summary_after['total_entities'] - context_summary['total_entities']
            tools_executed = context_summary_after['total_tool_executions'] - context_summary['total_tool_executions']
            if entities_added > 0 or tools_executed > 0:
                logger.info(f"\n\n >>   📈 Changes: +{entities_added} entities, +{tools_executed} tool executions\n")

            # Calculate processing time
            processing_time_ms = None
            if session["messages"]:
                last_user_msg = session["messages"][-1]
                if "timestamp" in last_user_msg:
                    processing_time_ms = int((datetime.utcnow() - last_user_msg["timestamp"]).total_seconds() * 1000)

            # Add assistant response to database and session
            await conversation_service.add_message(
                session=db_session,
                role="assistant",
                content=response,
                tools_used=tools_used,
                processing_time_ms=processing_time_ms
            )

            session["messages"].append({
                "role": "assistant",
                "content": response,
                "timestamp": datetime.utcnow(),
                "tools_used": tools_used
            })

            # Update session metadata
            session["tools_used"].extend(tools_used)
            session["updated_at"] = datetime.utcnow()

            # Save entity store to disk
            try:
                entity_store = session.get("entity_store")
                if entity_store:
                    entity_store.save_to_disk()
            except Exception as e:
                logger.warning(f"Failed to save entity store to disk: {str(e)}")

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

            # Add error message to database
            await conversation_service.add_message(
                session=db_session,
                role="assistant",
                content=error_response,
                has_error=True,
                error_message=str(e)
            )

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