"""
Tool Registry Manager for Personal Assistant.
"""

import importlib
import inspect
from typing import Dict, Any, List, Optional, Type
from datetime import datetime
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.models.tool import ToolRegistry, UserToolAccess, ToolType
from app.agents.personal_assistant.tools.base import BaseTool

logger = logging.getLogger(__name__)


class ToolRegistryManager:
    """
    Manages tool registration, authorization, and execution for Personal Assistant.

    This class provides a plugin-style architecture where new tools can be added
    by defining tool classes and registering them without core code changes.
    """

    def __init__(self, user: User, db: AsyncSession):
        """
        Initialize the tool registry manager.

        Args:
            user: The user this registry belongs to
            db: Database session
        """
        self.user = user
        self.db = db
        self._tool_instances: Dict[str, BaseTool] = {}
        self._tool_registry: Dict[str, ToolRegistry] = {}
        self._user_access: Dict[str, UserToolAccess] = {}

    async def initialize(self) -> None:
        """Initialize the tool registry with database data."""
        await self._load_tool_registry()
        await self._load_user_access()
        await self._initialize_tool_instances()

        logger.info(f"Tool registry initialized for user {self.user.id} with {len(self._tool_instances)} tools")

    async def _load_tool_registry(self) -> None:
        """Load available tools from database."""
        result = await self.db.execute(
            select(ToolRegistry).where(ToolRegistry.is_enabled == True)
        )
        tools = result.scalars().all()

        self._tool_registry = {tool.name: tool for tool in tools}
        logger.debug(f"Loaded {len(tools)} tools from registry")

    async def _load_user_access(self) -> None:
        """Load user's tool access permissions."""
        result = await self.db.execute(
            select(UserToolAccess).where(UserToolAccess.user_id == self.user.id)
        )
        access_records = result.scalars().all()

        self._user_access = {access.tool.name: access for access in access_records if access.tool}
        logger.debug(f"Loaded access for {len(access_records)} tools")

    async def _initialize_tool_instances(self) -> None:
        """Initialize tool instances for available tools."""
        for tool_name, tool_registry in self._tool_registry.items():
            try:
                # Get user access record
                user_access = self._user_access.get(tool_name)

                # Create tool instance
                tool_instance = await self._create_tool_instance(tool_registry, user_access)
                if tool_instance:
                    self._tool_instances[tool_name] = tool_instance
                    logger.debug(f"Initialized tool: {tool_name}")

            except Exception as e:
                logger.error(f"Failed to initialize tool {tool_name}: {str(e)}")

    async def _create_tool_instance(self, tool_registry: ToolRegistry, user_access: Optional[UserToolAccess]) -> Optional[BaseTool]:
        """Create a tool instance based on registry information."""
        try:
            if tool_registry.tool_type == ToolType.BUILTIN:
                # Import builtin tool
                module_path = f"app.agents.personal_assistant.tools.builtin.{tool_registry.name}"
                module = importlib.import_module(module_path)

                # Find the tool class (should end with 'Tool')
                tool_class = None
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if name.endswith('Tool') and issubclass(obj, BaseTool) and obj != BaseTool:
                        tool_class = obj
                        break

                if not tool_class:
                    logger.error(f"No tool class found in {module_path}")
                    return None

                # Create instance
                return tool_class(
                    user=self.user,
                    db=self.db,
                    registry=tool_registry,
                    user_access=user_access
                )

            elif tool_registry.tool_type == ToolType.EXTERNAL:
                # Import external tool
                module_path = f"app.agents.personal_assistant.tools.external.{tool_registry.name}"
                module = importlib.import_module(module_path)

                # Find the tool class
                tool_class = None
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if name.endswith('Tool') and issubclass(obj, BaseTool) and obj != BaseTool:
                        tool_class = obj
                        break

                if not tool_class:
                    logger.error(f"No tool class found in {module_path}")
                    return None

                # Create instance
                return tool_class(
                    user=self.user,
                    db=self.db,
                    registry=tool_registry,
                    user_access=user_access
                )

        except ImportError as e:
            logger.error(f"Failed to import tool {tool_registry.name}: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to create tool instance {tool_registry.name}: {str(e)}")

        return None

    async def get_available_tools(self) -> List[ToolRegistry]:
        """Get list of tools available to the user."""
        available_tools = []

        for tool_name, tool_registry in self._tool_registry.items():
            # Check if user has access to this tool
            user_access = self._user_access.get(tool_name)

            # For builtin tools, always available
            # For external tools, check authorization
            if (tool_registry.tool_type == ToolType.BUILTIN or
                (user_access and user_access.is_authorized)):
                available_tools.append(tool_registry)

        return available_tools

    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        """
        Execute a tool with given parameters.

        Args:
            tool_name: Name of the tool to execute
            parameters: Parameters to pass to the tool

        Returns:
            Tool execution result

        Raises:
            ValueError: If tool not found or not authorized
            Exception: If tool execution fails
        """
        # Check if tool exists
        if tool_name not in self._tool_instances:
            raise ValueError(f"Tool '{tool_name}' not found or not available")

        tool_instance = self._tool_instances[tool_name]

        # Check authorization
        if not await tool_instance.is_authorized():
            raise ValueError(f"Tool '{tool_name}' not authorized for user")

        # Check rate limits
        if not await tool_instance.check_rate_limits():
            raise ValueError(f"Rate limit exceeded for tool '{tool_name}'")

        try:
            # Execute the tool
            result = await tool_instance.execute(parameters)

            # Update usage tracking
            await self._update_usage_tracking(tool_name)

            logger.info(f"Successfully executed tool {tool_name} for user {self.user.id}")
            return result

        except Exception as e:
            logger.error(f"Tool execution failed for {tool_name}: {str(e)}")
            raise

    async def _update_usage_tracking(self, tool_name: str) -> None:
        """Update usage tracking for a tool."""
        user_access = self._user_access.get(tool_name)
        if user_access:
            user_access.increment_usage()
            await self.db.commit()

    async def authorize_tool(self, tool_name: str) -> bool:
        """
        Authorize a tool for the user.

        Args:
            tool_name: Name of the tool to authorize

        Returns:
            True if authorization successful, False otherwise
        """
        if tool_name not in self._tool_registry:
            return False

        tool_registry = self._tool_registry[tool_name]

        # Get or create user access record
        user_access = self._user_access.get(tool_name)
        if not user_access:
            user_access = UserToolAccess(
                user_id=self.user.id,
                tool_id=tool_registry.id,
                is_authorized=False
            )
            self.db.add(user_access)
            self._user_access[tool_name] = user_access

        # For builtin tools, authorize immediately
        if tool_registry.tool_type == ToolType.BUILTIN:
            user_access.authorize()
            await self.db.commit()
            return True

        # For external tools, this would trigger OAuth flow
        # For now, just mark as authorized (OAuth implementation in next phase)
        user_access.authorize()
        await self.db.commit()
        return True

    async def revoke_tool_authorization(self, tool_name: str) -> bool:
        """
        Revoke authorization for a tool.

        Args:
            tool_name: Name of the tool to revoke

        Returns:
            True if revocation successful, False otherwise
        """
        user_access = self._user_access.get(tool_name)
        if user_access:
            user_access.revoke_authorization()
            await self.db.commit()
            return True

        return False

    def get_tool_schema(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get schema for a specific tool."""
        tool_registry = self._tool_registry.get(tool_name)
        return tool_registry.schema if tool_registry else None

    def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive information about a tool."""
        tool_registry = self._tool_registry.get(tool_name)
        user_access = self._user_access.get(tool_name)

        if not tool_registry:
            return None

        return {
            "name": tool_registry.name,
            "display_name": tool_registry.display_name,
            "description": tool_registry.description,
            "category": tool_registry.category,
            "tool_type": tool_registry.tool_type.value,
            "schema": tool_registry.schema,
            "is_authorized": user_access.is_authorized if user_access else False,
            "usage_count": user_access.usage_count if user_access else 0,
            "rate_limits": {
                "per_minute": tool_registry.rate_limit_per_minute,
                "per_day": tool_registry.rate_limit_per_day
            },
            "requires_oauth": tool_registry.requires_oauth(),
            "oauth_provider": tool_registry.oauth_provider
        }