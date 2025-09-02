"""
Base tool interface for Personal Assistant tools.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.tool import ToolRegistry, UserToolAccess

logger = logging.getLogger(__name__)


class BaseTool(ABC):
    """
    Abstract base class for all Personal Assistant tools.

    This class defines the standard interface that all tools must implement,
    providing a consistent plugin architecture for the Personal Assistant.
    """

    def __init__(self, user: User, db: AsyncSession, registry: ToolRegistry,
                 user_access: Optional[UserToolAccess] = None):
        """
        Initialize the base tool.

        Args:
            user: The user this tool belongs to
            db: Database session
            registry: Tool registry information
            user_access: User's access record for this tool
        """
        self.user = user
        self.db = db
        self.registry = registry
        self.user_access = user_access
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")

    @abstractmethod
    async def execute(self, parameters: Dict[str, Any]) -> Any:
        """
        Execute the tool with given parameters.

        Args:
            parameters: Tool-specific parameters

        Returns:
            Tool execution result

        Raises:
            ValueError: If parameters are invalid
            Exception: If execution fails
        """
        pass

    async def is_authorized(self) -> bool:
        """
        Check if the user is authorized to use this tool.

        Returns:
            True if authorized, False otherwise
        """
        # Builtin tools are always authorized
        if self.registry.tool_type.value == "builtin":
            return True

        # External tools require explicit authorization
        return self.user_access and self.user_access.is_authorized

    async def check_rate_limits(self) -> bool:
        """
        Check if the user has exceeded rate limits for this tool.

        Returns:
            True if within limits, False if exceeded
        """
        if not self.user_access:
            return True

        # Check daily limit
        if self.user_access.daily_usage_count >= self.registry.rate_limit_per_day:
            # Check if we need to reset daily counter
            if (self.user_access.daily_usage_reset and
                datetime.utcnow() - self.user_access.daily_usage_reset.replace(tzinfo=None) > timedelta(days=1)):
                self.user_access.reset_daily_usage()
                await self.db.commit()
            else:
                return False

        # For minute-based rate limiting, we'd need more sophisticated tracking
        # For now, we'll rely on daily limits
        return True

    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """
        Validate parameters against the tool's schema.

        Args:
            parameters: Parameters to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            schema = self.registry.schema
            if not schema:
                return True

            # Basic validation - in production, use jsonschema library
            required_fields = schema.get("required", [])
            for field in required_fields:
                if field not in parameters:
                    self.logger.error(f"Missing required parameter: {field}")
                    return False

            return True

        except Exception as e:
            self.logger.error(f"Parameter validation error: {str(e)}")
            return False

    async def get_user_config(self, key: str, default: Any = None) -> Any:
        """
        Get user-specific configuration for this tool.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value
        """
        if not self.user_access or not self.user_access.config_data:
            return default

        return self.user_access.config_data.get(key, default)

    async def set_user_config(self, key: str, value: Any) -> None:
        """
        Set user-specific configuration for this tool.

        Args:
            key: Configuration key
            value: Configuration value
        """
        if not self.user_access:
            return

        if not self.user_access.config_data:
            self.user_access.config_data = {}

        self.user_access.config_data[key] = value
        await self.db.commit()

    def get_tool_info(self) -> Dict[str, Any]:
        """
        Get information about this tool.

        Returns:
            Dictionary containing tool information
        """
        return {
            "name": self.registry.name,
            "display_name": self.registry.display_name,
            "description": self.registry.description,
            "category": self.registry.category,
            "tool_type": self.registry.tool_type.value,
            "schema": self.registry.schema,
            "requires_oauth": self.registry.requires_oauth(),
            "oauth_provider": self.registry.oauth_provider
        }

    async def handle_error(self, error: Exception, context: str = "") -> Dict[str, Any]:
        """
        Handle tool execution errors consistently.

        Args:
            error: The exception that occurred
            context: Additional context about the error

        Returns:
            Standardized error response
        """
        error_msg = f"Tool {self.registry.name} error"
        if context:
            error_msg += f" ({context})"
        error_msg += f": {str(error)}"

        self.logger.error(error_msg, exc_info=True)

        return {
            "success": False,
            "error": str(error),
            "error_type": type(error).__name__,
            "tool": self.registry.name,
            "context": context,
            "timestamp": datetime.utcnow().isoformat()
        }

    async def create_success_response(self, result: Any, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Create a standardized success response.

        Args:
            result: The tool execution result
            metadata: Optional metadata about the execution

        Returns:
            Standardized success response
        """
        response = {
            "success": True,
            "result": result,
            "tool": self.registry.name,
            "timestamp": datetime.utcnow().isoformat()
        }

        if metadata:
            response["metadata"] = metadata

        return response


class ExternalTool(BaseTool):
    """
    Base class for external tools that require OAuth authentication.
    """

    async def is_authorized(self) -> bool:
        """Check OAuth authorization for external tools."""
        if not self.user_access or not self.user_access.is_authorized:
            return False

        # Check if OAuth tokens are available and valid
        return await self.check_oauth_tokens()

    async def check_oauth_tokens(self) -> bool:
        """
        Check if OAuth tokens are available and valid.

        Returns:
            True if tokens are valid, False otherwise
        """
        # This will be implemented in the OAuth phase
        # For now, assume tokens are valid if user is authorized
        return self.user_access and self.user_access.is_authorized

    async def get_oauth_token(self) -> Optional[str]:
        """
        Get valid OAuth access token for this tool.

        Returns:
            Access token if available, None otherwise
        """
        # This will be implemented in the OAuth phase
        return None

    async def refresh_oauth_token(self) -> bool:
        """
        Refresh OAuth token if needed.

        Returns:
            True if refresh successful, False otherwise
        """
        # This will be implemented in the OAuth phase
        return False