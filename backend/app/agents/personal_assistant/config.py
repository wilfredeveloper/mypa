"""
Personal Assistant configuration and constants.
"""

from typing import Dict, Any, List
from dataclasses import dataclass


@dataclass
class PersonalAssistantConfig:
    """Configuration class for Personal Assistant agent."""

    # Default system prompt
    default_system_prompt: str = """You are a helpful Personal Assistant with access to various tools and capabilities.

Your role is to:
1. Understand user requests and break them down into actionable steps
2. Use available tools to accomplish tasks efficiently
3. Provide clear, helpful responses with context about what you've done
4. Maintain conversation context and remember user preferences
5. Ask for clarification when requests are ambiguous

Available capabilities:
- System prompt management for different contexts
- Task planning and decomposition
- Virtual file system for temporary data storage
- Google Calendar integration (when authorized)
- Gmail integration (when authorized)

Always be professional, helpful, and transparent about your actions and limitations."""

    # Default tool configurations
    default_enabled_tools: List[str] = None

    # Rate limiting defaults
    default_rate_limits: Dict[str, int] = None

    # Response style options
    response_styles: List[str] = None

    # Personality options
    personalities: List[str] = None

    def __post_init__(self):
        """Initialize default values after dataclass creation."""
        if self.default_enabled_tools is None:
            self.default_enabled_tools = [
                "system_prompt",
                "planning",
                "virtual_fs"
            ]

        if self.default_rate_limits is None:
            self.default_rate_limits = {
                "requests_per_minute": 60,
                "requests_per_day": 1000,
                "concurrent_sessions": 5
            }

        if self.response_styles is None:
            self.response_styles = [
                "concise",
                "detailed",
                "conversational",
                "professional"
            ]

        if self.personalities is None:
            self.personalities = [
                "professional",
                "casual",
                "friendly",
                "task-focused"
            ]

    def get_system_prompt_for_personality(self, personality: str) -> str:
        """Get system prompt customized for specific personality."""
        base_prompt = self.default_system_prompt

        personality_additions = {
            "professional": "\n\nMaintain a professional, business-appropriate tone in all interactions.",
            "casual": "\n\nUse a casual, friendly tone while remaining helpful and informative.",
            "friendly": "\n\nBe warm, encouraging, and personable in your responses.",
            "task-focused": "\n\nFocus on efficiency and getting tasks done quickly with minimal small talk."
        }

        addition = personality_additions.get(personality, "")
        return base_prompt + addition

    def get_default_config_for_user(self, user_preferences: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get default configuration dictionary for a user."""
        user_preferences = user_preferences or {}

        return {
            "personality": user_preferences.get("personality", "professional"),
            "response_style": user_preferences.get("response_style", "conversational"),
            "enabled_tools": user_preferences.get("enabled_tools", self.default_enabled_tools.copy()),
            "preferences": {
                "timezone": user_preferences.get("timezone", "UTC"),
                "language": user_preferences.get("language", "en"),
                "notification_settings": user_preferences.get("notification_settings", {
                    "email_notifications": True,
                    "task_reminders": True,
                    "calendar_alerts": True
                })
            },
            "limits": self.default_rate_limits.copy()
        }