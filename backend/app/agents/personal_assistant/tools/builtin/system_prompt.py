"""
System Prompt Management Tool for Personal Assistant.
"""

from typing import Dict, Any, List
from datetime import datetime
import logging

from sqlalchemy import select

from app.agents.personal_assistant.tools.base import BaseTool
from app.models.agent import AgentConfig
from app.agents.personal_assistant.config import PersonalAssistantConfig

logger = logging.getLogger(__name__)


class SystemPromptTool(BaseTool):
    """
    Tool for managing and switching between different system prompts.

    This tool allows users to:
    - Get the current system prompt
    - Set a new system prompt
    - List available prompt templates
    - Switch between different personality contexts
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pa_config = PersonalAssistantConfig()

        # Predefined prompt templates
        self.prompt_templates = {
            "professional": self.pa_config.get_system_prompt_for_personality("professional"),
            "casual": self.pa_config.get_system_prompt_for_personality("casual"),
            "friendly": self.pa_config.get_system_prompt_for_personality("friendly"),
            "task-focused": self.pa_config.get_system_prompt_for_personality("task-focused"),
            "default": self.pa_config.default_system_prompt
        }

    async def execute(self, parameters: Dict[str, Any]) -> Any:
        """
        Execute system prompt management action.

        Parameters:
            action (str): Action to perform - 'get', 'set', 'list', 'switch'
            prompt_name (str, optional): Name of prompt template for 'switch' action
            prompt_content (str, optional): Custom prompt content for 'set' action

        Returns:
            Result of the action
        """
        if not self.validate_parameters(parameters):
            return await self.handle_error(
                ValueError("Invalid parameters"),
                "Parameter validation failed"
            )

        action = parameters.get("action", "get").lower()

        try:
            if action == "get":
                return await self._get_current_prompt()
            elif action == "set":
                prompt_content = parameters.get("prompt_content")
                if not prompt_content:
                    return await self.handle_error(
                        ValueError("prompt_content is required for 'set' action"),
                        "Missing prompt content"
                    )
                return await self._set_custom_prompt(prompt_content)
            elif action == "list":
                return await self._list_available_prompts()
            elif action == "switch":
                prompt_name = parameters.get("prompt_name")
                if not prompt_name:
                    return await self.handle_error(
                        ValueError("prompt_name is required for 'switch' action"),
                        "Missing prompt name"
                    )
                return await self._switch_prompt_template(prompt_name)
            else:
                return await self.handle_error(
                    ValueError(f"Unknown action: {action}"),
                    "Invalid action"
                )

        except Exception as e:
            return await self.handle_error(e, f"Action: {action}")

    async def _get_current_prompt(self) -> Dict[str, Any]:
        """Get the current system prompt."""
        try:
            # Get user's agent config
            result = await self.db.execute(
                select(AgentConfig).where(
                    AgentConfig.user_id == self.user.id,
                    AgentConfig.agent_type == "personal_assistant",
                    AgentConfig.is_active == True
                )
            )
            config = result.scalar_one_or_none()

            if not config:
                return await self.create_success_response({
                    "current_prompt": self.pa_config.default_system_prompt,
                    "source": "default",
                    "personality": "professional"
                })

            # Determine the source of the current prompt
            current_prompt = config.system_prompt or self.pa_config.default_system_prompt
            personality = config.get_config_value("personality", "professional")

            # Check if it matches a template
            source = "custom"
            for template_name, template_content in self.prompt_templates.items():
                if current_prompt.strip() == template_content.strip():
                    source = f"template:{template_name}"
                    break

            return await self.create_success_response({
                "current_prompt": current_prompt,
                "source": source,
                "personality": personality,
                "length": len(current_prompt),
                "last_updated": config.updated_at.isoformat() if config.updated_at else None
            })

        except Exception as e:
            return await self.handle_error(e, "Getting current prompt")

    async def _set_custom_prompt(self, prompt_content: str) -> Dict[str, Any]:
        """Set a custom system prompt."""
        try:
            # Get or create user's agent config
            result = await self.db.execute(
                select(AgentConfig).where(
                    AgentConfig.user_id == self.user.id,
                    AgentConfig.agent_type == "personal_assistant",
                    AgentConfig.is_active == True
                )
            )
            config = result.scalar_one_or_none()

            if not config:
                # Create new config
                config = AgentConfig(
                    user_id=self.user.id,
                    agent_type="personal_assistant",
                    name=f"{self.user.full_name or self.user.email}'s Assistant",
                    system_prompt=prompt_content,
                    config_data=self.pa_config.get_default_config_for_user(),
                    is_active=True
                )
                self.db.add(config)
            else:
                # Update existing config
                config.system_prompt = prompt_content
                config.updated_at = datetime.utcnow()

            await self.db.commit()

            return await self.create_success_response({
                "message": "System prompt updated successfully",
                "prompt_length": len(prompt_content),
                "source": "custom",
                "updated_at": datetime.utcnow().isoformat()
            })

        except Exception as e:
            return await self.handle_error(e, "Setting custom prompt")

    async def _list_available_prompts(self) -> Dict[str, Any]:
        """List available prompt templates."""
        try:
            templates = []
            for name, content in self.prompt_templates.items():
                templates.append({
                    "name": name,
                    "description": self._get_template_description(name),
                    "length": len(content),
                    "preview": content[:100] + "..." if len(content) > 100 else content
                })

            return await self.create_success_response({
                "available_templates": templates,
                "total_count": len(templates),
                "current_personality": await self._get_current_personality()
            })

        except Exception as e:
            return await self.handle_error(e, "Listing available prompts")

    async def _switch_prompt_template(self, prompt_name: str) -> Dict[str, Any]:
        """Switch to a predefined prompt template."""
        try:
            if prompt_name not in self.prompt_templates:
                return await self.handle_error(
                    ValueError(f"Unknown prompt template: {prompt_name}"),
                    "Invalid template name"
                )

            new_prompt = self.prompt_templates[prompt_name]

            # Update the system prompt
            result = await self._set_custom_prompt(new_prompt)

            if result.get("success"):
                # Also update personality in config if it's a personality-based template
                if prompt_name in self.pa_config.personalities:
                    await self._update_personality(prompt_name)

                return await self.create_success_response({
                    "message": f"Switched to '{prompt_name}' prompt template",
                    "template_name": prompt_name,
                    "description": self._get_template_description(prompt_name),
                    "prompt_length": len(new_prompt),
                    "updated_at": datetime.utcnow().isoformat()
                })
            else:
                return result

        except Exception as e:
            return await self.handle_error(e, f"Switching to template: {prompt_name}")

    async def _update_personality(self, personality: str) -> None:
        """Update the personality setting in user config."""
        try:
            result = await self.db.execute(
                select(AgentConfig).where(
                    AgentConfig.user_id == self.user.id,
                    AgentConfig.agent_type == "personal_assistant",
                    AgentConfig.is_active == True
                )
            )
            config = result.scalar_one_or_none()

            if config:
                config.set_config_value("personality", personality)
                await self.db.commit()

        except Exception as e:
            logger.error(f"Failed to update personality: {str(e)}")

    async def _get_current_personality(self) -> str:
        """Get the current personality setting."""
        try:
            result = await self.db.execute(
                select(AgentConfig).where(
                    AgentConfig.user_id == self.user.id,
                    AgentConfig.agent_type == "personal_assistant",
                    AgentConfig.is_active == True
                )
            )
            config = result.scalar_one_or_none()

            if config:
                return config.get_config_value("personality", "professional")

            return "professional"

        except Exception as e:
            logger.error(f"Failed to get current personality: {str(e)}")
            return "professional"

    def _get_template_description(self, template_name: str) -> str:
        """Get description for a prompt template."""
        descriptions = {
            "professional": "Business-appropriate tone for professional interactions",
            "casual": "Relaxed, friendly tone for informal conversations",
            "friendly": "Warm and encouraging tone with personal touch",
            "task-focused": "Efficient, direct tone focused on getting things done",
            "default": "Balanced tone suitable for general assistance"
        }
        return descriptions.get(template_name, "Custom prompt template")