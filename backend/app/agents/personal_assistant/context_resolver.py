"""
Context-aware parameter resolution for Personal Assistant tools.

This module provides functionality to resolve ambiguous user references
to entities using conversation memory context.
"""

from typing import Dict, Any, List, Optional, Tuple
import logging
from datetime import datetime, timezone

from app.agents.personal_assistant.memory import ConversationMemory, EntityType, EntityContext

logger = logging.getLogger(__name__)


class ContextResolver:
    """
    Resolves ambiguous user references to entities using conversation memory.
    
    This class helps tools identify specific entities when users make
    ambiguous requests like "delete the event" or "call John".
    """
    
    def __init__(self, memory: ConversationMemory):
        self.memory = memory
    
    def resolve_calendar_event_reference(self, user_message: str, parameters: Dict[str, Any]) -> Optional[str]:
        """
        Resolve a calendar event reference from user message and parameters.
        
        Args:
            user_message: The user's original message
            parameters: Tool parameters that may contain partial event info
            
        Returns:
            Event ID if a unique event can be identified, None otherwise
        """
        # If event_id is already provided, use it
        if parameters.get("event_id"):
            return parameters["event_id"]
        
        # Look for recent calendar events
        recent_events = self.memory.get_recent_entities(EntityType.CALENDAR_EVENT, limit=10)
        if not recent_events:
            return None
        
        # Try to match based on user message content
        user_message_lower = user_message.lower()
        
        # Common deletion patterns
        deletion_patterns = [
            "delete the event", "remove the event", "cancel the event",
            "delete that event", "remove that event", "cancel that event",
            "delete it", "remove it", "cancel it"
        ]
        
        # If user is clearly referring to "the event" and there's only one recent event
        if any(pattern in user_message_lower for pattern in deletion_patterns):
            if len(recent_events) == 1:
                logger.info(f"Resolved 'the event' to: {recent_events[0].display_name}")
                return recent_events[0].entity_id
        
        # Try to match by event name/summary mentioned in the message
        for event in recent_events:
            if event.matches_reference(user_message):
                logger.info(f"Resolved event reference to: {event.display_name}")
                return event.entity_id
        
        # If user mentions a specific name that matches an event
        words = user_message_lower.split()
        for event in recent_events:
            event_words = event.display_name.lower().split()
            # Check if any significant words from event name appear in user message
            for event_word in event_words:
                if len(event_word) > 3 and event_word in words:  # Skip short words
                    logger.info(f"Resolved event by keyword '{event_word}': {event.display_name}")
                    return event.entity_id
        
        return None
    
    def resolve_contact_reference(self, user_message: str, parameters: Dict[str, Any]) -> Optional[str]:
        """
        Resolve a contact reference from user message and parameters.
        
        Args:
            user_message: The user's original message
            parameters: Tool parameters that may contain partial contact info
            
        Returns:
            Contact ID if a unique contact can be identified, None otherwise
        """
        # Look for recent contacts
        recent_contacts = self.memory.get_recent_entities(EntityType.CONTACT, limit=10)
        if not recent_contacts:
            return None
        
        # Try to match based on user message content
        for contact in recent_contacts:
            if contact.matches_reference(user_message):
                logger.info(f"Resolved contact reference to: {contact.display_name}")
                return contact.entity_id
        
        return None
    
    def enhance_tool_parameters(self, tool_name: str, parameters: Dict[str, Any], user_message: str) -> Dict[str, Any]:
        """
        Enhance tool parameters with context-resolved entity references.
        
        Args:
            tool_name: Name of the tool being called
            parameters: Original tool parameters
            user_message: User's original message
            
        Returns:
            Enhanced parameters with resolved entity references
        """
        logger.info(f"🔍 CONTEXT RESOLVER: Enhancing parameters for {tool_name}")
        logger.info(f"   📥 Original parameters: {parameters}")
        logger.info(f"   💬 User message: '{user_message}'")

        enhanced_params = parameters.copy()

        try:
            if tool_name == "google_calendar":
                action = parameters.get("action")
                
                if action == "delete":
                    # Try to resolve event reference for deletion
                    if not enhanced_params.get("event_id"):
                        resolved_event_id = self.resolve_calendar_event_reference(user_message, parameters)
                        if resolved_event_id:
                            enhanced_params["event_id"] = resolved_event_id
                            
                            # Add confirmation context
                            event = self.memory.get_entity(resolved_event_id)
                            if event:
                                enhanced_params["_context_info"] = {
                                    "resolved_entity": {
                                        "type": "calendar_event",
                                        "name": event.display_name,
                                        "id": resolved_event_id
                                    }
                                }
                
                elif action == "update":
                    # Try to resolve event reference for updates
                    if not enhanced_params.get("event_id"):
                        resolved_event_id = self.resolve_calendar_event_reference(user_message, parameters)
                        if resolved_event_id:
                            enhanced_params["event_id"] = resolved_event_id
            
            # Add similar logic for other tools as needed
            
        except Exception as e:
            logger.warning(f"Error enhancing parameters for {tool_name}: {str(e)}")

        logger.info(f"   📤 Enhanced parameters: {enhanced_params}")
        return enhanced_params
    
    def get_confirmation_context(self, tool_name: str, parameters: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get context information for generating confirmation messages.
        
        Args:
            tool_name: Name of the tool being called
            parameters: Tool parameters (potentially enhanced)
            
        Returns:
            Context information for confirmation messages
        """
        context_info = parameters.get("_context_info")
        if not context_info:
            return None
        
        resolved_entity = context_info.get("resolved_entity")
        if not resolved_entity:
            return None
        
        return {
            "entity_type": resolved_entity.get("type"),
            "entity_name": resolved_entity.get("name"),
            "entity_id": resolved_entity.get("id"),
            "action": parameters.get("action"),
            "tool": tool_name
        }
    
    def generate_confirmation_message(self, tool_name: str, parameters: Dict[str, Any], action: str) -> Optional[str]:
        """
        Generate a context-aware confirmation message.
        
        Args:
            tool_name: Name of the tool being called
            parameters: Tool parameters
            action: Action being performed
            
        Returns:
            Confirmation message if context is available
        """
        confirmation_context = self.get_confirmation_context(tool_name, parameters)
        if not confirmation_context:
            return None
        
        entity_name = confirmation_context.get("entity_name")
        entity_type = confirmation_context.get("entity_type")
        
        if tool_name == "google_calendar" and entity_type == "calendar_event":
            # Check if we have tool execution history for this entity
            entity_id = confirmation_context.get("entity_id")
            creation_context = None
            if entity_id:
                creation_context = self.memory.get_entity_creation_context(entity_id)

            if action == "delete":
                if creation_context:
                    return (f"I'll delete the '{entity_name}' event that we found "
                           f"when I {creation_context.user_intent or 'searched your calendar'} earlier.")
                else:
                    return f"I'll delete the '{entity_name}' event that we discussed earlier."
            elif action == "update":
                if creation_context:
                    return (f"I'll update the '{entity_name}' event that we found "
                           f"when I {creation_context.user_intent or 'searched your calendar'} earlier.")
                else:
                    return f"I'll update the '{entity_name}' event that we discussed earlier."

        return None

    def get_tool_execution_summary(self, tool_name: Optional[str] = None,
                                 limit: int = 5) -> List[str]:
        """Get a summary of recent tool executions for context."""
        executions = self.memory.get_recent_tool_executions(limit=limit, tool_name=tool_name)
        summaries = []

        for execution in executions:
            summary = f"{execution.tool_name}: {execution.get_summary()}"
            if execution.user_request:
                summary += f" (requested: '{execution.user_request[:30]}...')"
            summaries.append(summary)

        return summaries

    def find_related_executions(self, entity_id: str) -> List[str]:
        """Find tool executions related to a specific entity."""
        executions = self.memory.find_tool_executions_by_criteria(entity_id=entity_id)
        summaries = []

        for execution in executions:
            summary = f"{execution.timestamp.strftime('%H:%M')}: {execution.get_summary()}"
            summaries.append(summary)

        return summaries

    def get_execution_context_for_response(self, tool_name: str, action: str) -> Dict[str, Any]:
        """Get execution context to enhance agent responses."""
        recent_executions = self.memory.get_recent_tool_executions(
            limit=3, tool_name=tool_name, success_only=True
        )

        context = {
            "recent_executions": len(recent_executions),
            "last_execution_time": None,
            "entities_from_last_execution": 0
        }

        if recent_executions:
            last_execution = recent_executions[0]
            context["last_execution_time"] = last_execution.timestamp
            context["entities_from_last_execution"] = len(last_execution.extracted_entity_ids)

        return context


def create_context_resolver(memory: ConversationMemory) -> ContextResolver:
    """Create a context resolver instance."""
    return ContextResolver(memory)
