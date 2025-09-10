"""
Personal Assistant service layer for handling business logic.
"""

import logging
import time
from typing import Optional, Dict, Any, List
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.agents.personal_assistant.agent import PersonalAssistant
from app.schemas.personal_assistant import (
    PersonalAssistantChatRequest,
    PersonalAssistantChatResponse,
    AutonomousChatRequest,
    AutonomousChatResponse,
    AutonomousExecutionMetadata,
    ToolUsage,
    ToolInfo,
    ConfigResponse,
    WorkspaceResponse,
    HealthResponse
)

logger = logging.getLogger(__name__)


class PersonalAssistantService:
    """Service class for Personal Assistant operations."""
    
    def __init__(self):
        self._start_time = time.time()
    
    async def chat_standard(
        self, 
        request: PersonalAssistantChatRequest, 
        current_user: Optional[dict] = None
    ) -> PersonalAssistantChatResponse:
        """
        Process a standard chat request using single-tool execution mode.
        
        Args:
            request: The chat request
            current_user: Current authenticated user
            
        Returns:
            PersonalAssistantChatResponse: Standard chat response
        """
        async with AsyncSessionLocal() as session:
            # Get user from database
            user = await self._get_user(session, current_user)

            # Create Personal Assistant instance
            pa_agent = PersonalAssistant(user, session)
            await pa_agent.initialize()
            
            # Process chat using standard mode
            result = await pa_agent.chat(
                message=request.message,
                session_id=request.session_id,
                context=request.context
            )
            
            # Convert tool usage to schema format
            tools_used = [
                ToolUsage(
                    tool=tool.get("tool", "unknown"),
                    parameters=tool.get("parameters", {}),
                    result=tool.get("result", {}),
                    success=tool.get("success", False),
                    timestamp=tool.get("timestamp", datetime.utcnow().isoformat()),
                    execution_time_ms=tool.get("execution_time_ms")
                )
                for tool in result.get("tools_used", [])
            ]
            
            return PersonalAssistantChatResponse(
                response=result["response"],
                session_id=result["session_id"],
                tools_used=tools_used,
                context=result.get("context", {}),
                metadata=result.get("metadata", {})
            )
    
    async def chat_autonomous(
        self, 
        request: AutonomousChatRequest, 
        current_user: Optional[dict] = None
    ) -> AutonomousChatResponse:
        """
        Process an autonomous chat request using multi-step execution mode.
        
        Args:
            request: The autonomous chat request
            current_user: Current authenticated user
            
        Returns:
            AutonomousChatResponse: Autonomous chat response with comprehensive metadata
        """
        async with AsyncSessionLocal() as session:
            # Get user from database
            user = await self._get_user(session, current_user)
            
            # Create Personal Assistant instance
            pa_agent = PersonalAssistant(user, session)
            await pa_agent.initialize()
            
            # Process chat using autonomous mode
            result = await pa_agent.autonomous_chat(
                message=request.message,
                session_id=request.session_id,
                context=request.context
            )
            
            # Convert tool usage to schema format
            tools_used = [
                ToolUsage(
                    tool=tool.get("tool", "unknown"),
                    parameters=tool.get("parameters", {}),
                    result=tool.get("result", {}),
                    success=tool.get("success", False),
                    timestamp=tool.get("timestamp", datetime.utcnow().isoformat()),
                    execution_time_ms=tool.get("execution_time_ms")
                )
                for tool in result.get("tools_used", [])
            ]
            
            # Create autonomous execution metadata
            metadata = AutonomousExecutionMetadata(
                message_count=result.get("metadata", {}).get("message_count", 0),
                tools_count=len(tools_used),
                steps_completed=result.get("metadata", {}).get("steps_completed", 0),
                task_id=result.get("metadata", {}).get("task_id"),
                workspace_file=result.get("metadata", {}).get("workspace_file"),
                session_duration_minutes=result.get("metadata", {}).get("session_duration_minutes", 0),
                goal_achieved=result.get("metadata", {}).get("goal_achieved", False)
            )
            
            return AutonomousChatResponse(
                response=result["response"],
                session_id=result["session_id"],
                tools_used=tools_used,
                context=result.get("context", {}),
                autonomous_execution=result.get("autonomous_execution", True),
                metadata=metadata
            )
    
    async def list_tools(self, current_user: Optional[dict] = None) -> List[ToolInfo]:
        """
        List available tools for the user.
        
        Args:
            current_user: Current authenticated user
            
        Returns:
            List of available tools with their information
        """
        async with AsyncSessionLocal() as session:
            # Get user from database
            user = await self._get_user(session, current_user)
            
            # Create Personal Assistant instance
            pa_agent = PersonalAssistant(user, session)
            await pa_agent.initialize()
            
            # Get available tools from tool registry
            tools = []
            if pa_agent._tool_registry:
                for tool_name, tool_instance in pa_agent._tool_registry._tool_instances.items():
                    tool_info = ToolInfo(
                        name=tool_name,
                        display_name=getattr(tool_instance.registry, 'display_name', tool_name),
                        description=getattr(tool_instance.registry, 'description', 'No description available'),
                        category=getattr(tool_instance.registry, 'category', None),
                        authorized=await tool_instance.is_authorized(),
                        schema=getattr(tool_instance.registry, 'schema_data', {})
                    )
                    tools.append(tool_info)
            
            return tools
    
    async def get_config(self, current_user: Optional[dict] = None) -> ConfigResponse:
        """
        Get Personal Assistant configuration for the user.
        
        Args:
            current_user: Current authenticated user
            
        Returns:
            User's PA configuration
        """
        async with AsyncSessionLocal() as session:
            # Get user from database
            user = await self._get_user(session, current_user)
            
            # Create Personal Assistant instance
            pa_agent = PersonalAssistant(user, session)
            await pa_agent.initialize()
            
            config = pa_agent.config
            
            return ConfigResponse(
                agent_config={
                    "name": config.name,
                    "system_prompt": config.system_prompt,
                    "personality": config.get_config_value("personality", "professional"),
                    "response_style": config.get_config_value("response_style", "conversational")
                },
                enabled_tools=config.get_config_value("enabled_tools", []),
                preferences=config.get_config_value("preferences", {}),
                limits=config.get_config_value("limits", {})
            )
    
    async def update_config(
        self, 
        config_update: Dict[str, Any], 
        current_user: Optional[dict] = None
    ) -> ConfigResponse:
        """
        Update Personal Assistant configuration for the user.
        
        Args:
            config_update: Configuration updates to apply
            current_user: Current authenticated user
            
        Returns:
            Updated configuration
        """
        async with AsyncSessionLocal() as session:
            # Get user from database
            user = await self._get_user(session, current_user)
            
            # Create Personal Assistant instance
            pa_agent = PersonalAssistant(user, session)
            await pa_agent.initialize()
            
            # Update configuration
            config = pa_agent.config
            if "system_prompt" in config_update:
                config.system_prompt = config_update["system_prompt"]
            
            # Update config data
            config_data = config.config_data or {}
            for key, value in config_update.items():
                if key != "system_prompt":
                    config_data[key] = value
            
            config.config_data = config_data
            await session.commit()
            
            # Return updated configuration
            return await self.get_config(current_user)
    
    async def get_workspace(
        self, 
        task_id: str, 
        current_user: Optional[dict] = None
    ) -> WorkspaceResponse:
        """
        Get workspace file content for a specific task.
        
        Args:
            task_id: Task identifier
            current_user: Current authenticated user
            
        Returns:
            Workspace file content and metadata
        """
        async with AsyncSessionLocal() as session:
            # Get user from database
            user = await self._get_user(session, current_user)
            
            # Create Personal Assistant instance
            pa_agent = PersonalAssistant(user, session)
            await pa_agent.initialize()
            
            # Try to read workspace file using virtual_fs tool
            if pa_agent._tool_registry and "virtual_fs" in pa_agent._tool_registry._tool_instances:
                virtual_fs_tool = pa_agent._tool_registry._tool_instances["virtual_fs"]
                workspace_filename = f"task_workspace_{task_id[:8]}.md"
                
                result = await virtual_fs_tool.execute({
                    "action": "read",
                    "filename": workspace_filename
                })
                
                if result.get("success", False):
                    return WorkspaceResponse(
                        task_id=task_id,
                        filename=workspace_filename,
                        content=result.get("result", ""),
                        created_at=datetime.utcnow(),  # Would need to track this properly
                        updated_at=datetime.utcnow(),  # Would need to track this properly
                        metadata={"file_size": len(result.get("result", ""))}
                    )
            
            raise ValueError(f"Workspace not found for task: {task_id}")
    
    async def get_health(self) -> HealthResponse:
        """
        Get Personal Assistant service health status.
        
        Returns:
            Health status and diagnostics
        """
        uptime = time.time() - self._start_time
        
        return HealthResponse(
            status="healthy",
            version="1.0.0",
            uptime_seconds=uptime,
            tools_available=4,  # system_prompt, planning, virtual_fs, tavily_search
            baml_client_status="available",
            autonomous_mode_enabled=True
        )
    
    async def _get_user(self, session: AsyncSession, current_user: Optional[dict]) -> User:
        """
        Get user from database or create a test user.
        
        Args:
            session: Database session
            current_user: Current authenticated user info
            
        Returns:
            User instance
        """
        if current_user and "id" in current_user:
            # Get user from database
            user = await session.get(User, current_user["id"])
            if not user:
                raise ValueError(f"User not found: {current_user['id']}")
            return user
        else:
            # For testing, create or get a test user
            from sqlalchemy import select
            result = await session.execute(
                select(User).where(User.email == "test@example.com")
            )
            user = result.scalar_one_or_none()
            
            if not user:
                user = User(
                    email="test@example.com",
                    full_name="Test User",
                    is_active=True
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
            
            return user


# Create service instance
personal_assistant_service = PersonalAssistantService()
