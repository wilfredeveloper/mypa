"""
Tool Entity Store System for Personal Assistant Agent.

This module provides persistent storage and management of entities extracted
from tool executions, enabling context-aware interactions and entity resolution
for ambiguous user references across conversation turns.
"""

from typing import Dict, Any, List, Optional, Union, TypeVar, Generic
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field, asdict
from enum import Enum
import json
import logging
import pickle
import os
import uuid
from pathlib import Path
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

T = TypeVar('T')


class EntityType(Enum):
    """Types of entities that can be stored in conversation memory."""
    CALENDAR_EVENT = "calendar_event"
    CONTACT = "contact"
    EMAIL = "email"
    DOCUMENT = "document"
    PLAN = "plan"
    TASK = "task"
    LOCATION = "location"
    SEARCH_RESULT = "search_result"
    GENERIC = "generic"


@dataclass
class EntityContext:
    """
    Represents a stored entity in conversation memory.
    
    This class stores detailed information about entities (events, contacts, etc.)
    that the agent has retrieved or discussed with the user.
    """
    entity_id: str  # Unique identifier (e.g., Google Calendar event ID)
    entity_type: EntityType
    display_name: str  # Human-readable name for the entity
    data: Dict[str, Any]  # Full entity data
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0
    
    # Context metadata
    source_tool: Optional[str] = None  # Tool that retrieved this entity
    user_references: List[str] = field(default_factory=list)  # How user referred to it
    confidence_score: float = 1.0  # Confidence in entity identification
    
    def __post_init__(self):
        """Ensure datetime objects are timezone-aware."""
        if self.created_at.tzinfo is None:
            self.created_at = self.created_at.replace(tzinfo=timezone.utc)
        if self.last_accessed.tzinfo is None:
            self.last_accessed = self.last_accessed.replace(tzinfo=timezone.utc)
    
    def access(self) -> None:
        """Mark this entity as accessed."""
        self.last_accessed = datetime.now(timezone.utc)
        self.access_count += 1
    
    def add_user_reference(self, reference: str) -> None:
        """Add a way the user has referenced this entity."""
        if reference not in self.user_references:
            self.user_references.append(reference)
    
    def matches_reference(self, reference: str) -> bool:
        """Check if a user reference matches this entity."""
        reference_lower = reference.lower()
        
        # Check display name
        if reference_lower in self.display_name.lower():
            return True
            
        # Check stored user references
        for user_ref in self.user_references:
            if reference_lower in user_ref.lower():
                return True
                
        # Check entity data for matches
        if self.entity_type == EntityType.CALENDAR_EVENT:
            summary = self.data.get('summary', '').lower()
            location = self.data.get('location', '').lower()
            if reference_lower in summary or reference_lower in location:
                return True
                
        return False
    
    def is_expired(self, max_age_minutes: int = 60) -> bool:
        """Check if this entity context has expired."""
        age = datetime.now(timezone.utc) - self.last_accessed
        return age > timedelta(minutes=max_age_minutes)


@dataclass
class ToolExecutionContext:
    """
    Represents metadata about a tool execution in conversation memory.

    This class stores comprehensive information about tool calls including
    the user request, parameters used, output, timing, and related entities.
    """
    execution_id: str  # Unique identifier for this execution
    tool_name: str  # Name of the tool that was executed
    user_request: str  # Original user message that triggered this tool call
    parameters: Dict[str, Any]  # Parameters passed to the tool
    raw_output: Dict[str, Any]  # Raw output from the tool
    success: bool  # Whether the tool execution was successful
    execution_time_ms: float  # Execution time in milliseconds
    timestamp: datetime  # When the tool was executed

    # Context and relationships
    extracted_entity_ids: List[str] = field(default_factory=list)  # IDs of entities extracted from this call
    user_intent: Optional[str] = None  # Inferred user intent (e.g., "delete_event", "list_events")
    error_message: Optional[str] = None  # Error message if execution failed

    # Metadata
    session_id: str = ""  # Session this execution belongs to
    conversation_turn: int = 0  # Turn number in the conversation

    def __post_init__(self):
        """Ensure datetime objects are timezone-aware."""
        if self.timestamp.tzinfo is None:
            self.timestamp = self.timestamp.replace(tzinfo=timezone.utc)

        # Generate execution ID if not provided
        if not self.execution_id:
            self.execution_id = str(uuid.uuid4())

    def add_extracted_entity(self, entity_id: str) -> None:
        """Add an entity ID that was extracted from this tool execution."""
        if entity_id not in self.extracted_entity_ids:
            self.extracted_entity_ids.append(entity_id)

    def get_summary(self) -> str:
        """Get a human-readable summary of this tool execution."""
        status = "✅" if self.success else "❌"
        entity_count = len(self.extracted_entity_ids)

        summary = f"{status} {self.tool_name}"
        if self.user_intent:
            summary += f" ({self.user_intent})"

        if entity_count > 0:
            summary += f" → {entity_count} entities"

        if not self.success and self.error_message:
            summary += f" - {self.error_message}"

        return summary

    def matches_criteria(self, tool_name: Optional[str] = None,
                        success: Optional[bool] = None,
                        user_intent: Optional[str] = None,
                        entity_id: Optional[str] = None) -> bool:
        """Check if this execution matches the given criteria."""
        if tool_name and self.tool_name != tool_name:
            return False

        if success is not None and self.success != success:
            return False

        if user_intent and self.user_intent != user_intent:
            return False

        if entity_id and entity_id not in self.extracted_entity_ids:
            return False

        return True

    def is_recent(self, minutes: int = 30) -> bool:
        """Check if this execution is recent (within specified minutes)."""
        age = datetime.now(timezone.utc) - self.timestamp
        return age <= timedelta(minutes=minutes)


class ContextExtractor(ABC):
    """Abstract base class for extracting entity context from tool results."""
    
    @abstractmethod
    def can_extract(self, tool_name: str, result: Dict[str, Any]) -> bool:
        """Check if this extractor can handle the given tool result."""
        pass
    
    @abstractmethod
    def extract_entities(self, tool_name: str, result: Dict[str, Any]) -> List[EntityContext]:
        """Extract entity contexts from tool result."""
        pass


class CalendarEventExtractor(ContextExtractor):
    """Extracts calendar event entities from Google Calendar tool results."""
    
    def can_extract(self, tool_name: str, result: Dict[str, Any]) -> bool:
        """Check if this is a Google Calendar result with events."""
        if tool_name != "google_calendar" or not result.get("success", False):
            return False

        # The actual data is nested under "result" key
        data = result.get("result", {})
        return "events" in data or "event" in data
    
    def extract_entities(self, tool_name: str, result: Dict[str, Any]) -> List[EntityContext]:
        """Extract calendar event entities."""
        logger.info(f"🏷️  ENTITY EXTRACTOR: Attempting to extract from {tool_name}")
        logger.info(f"   📥 Tool result keys: {list(result.keys())}")

        entities = []
        # The actual data is nested under "result" key
        data = result.get("result", {})
        logger.info(f"   📊 Data keys: {list(data.keys())}")
        now = datetime.now(timezone.utc)
        
        # Handle single event (create/update operations)
        if "event" in data:
            event = data["event"]
            entity = EntityContext(
                entity_id=event.get("id", ""),
                entity_type=EntityType.CALENDAR_EVENT,
                display_name=event.get("summary", "Untitled Event"),
                data=event,
                created_at=now,
                last_accessed=now,
                source_tool=tool_name
            )
            entities.append(entity)
        
        # Handle multiple events (list operations)
        if "events" in data:
            events = data["events"]
            logger.info(f"   📋 Found {len(events)} events to extract")
            for event in events:
                entity = EntityContext(
                    entity_id=event.get("id", ""),
                    entity_type=EntityType.CALENDAR_EVENT,
                    display_name=event.get("summary", "Untitled Event"),
                    data=event,
                    created_at=now,
                    last_accessed=now,
                    source_tool=tool_name
                )
                entities.append(entity)
                logger.info(f"   ✅ Extracted entity: {entity.display_name} (ID: {entity.entity_id})")

        logger.info(f"   📤 Total entities extracted: {len(entities)}")
        return entities


class GmailExtractor(ContextExtractor):
    """Extracts email and contact entities from Gmail tool results."""

    def can_extract(self, tool_name: str, result: Dict[str, Any]) -> bool:
        """Check if this is a Gmail result with messages."""
        if tool_name != "gmail" or not result.get("success", False):
            return False

        # The actual data is nested under "result" key
        data = result.get("result", {})
        return "messages" in data or "message" in data

    def extract_entities(self, tool_name: str, result: Dict[str, Any]) -> List[EntityContext]:
        """Extract email entities from Gmail results."""
        logger.info(f"🏷️  GMAIL EXTRACTOR: Attempting to extract from {tool_name}")
        logger.info(f"   📥 Tool result keys: {list(result.keys())}")

        entities = []
        # The actual data is nested under "result" key
        data = result.get("result", {})
        logger.info(f"   📊 Data keys: {list(data.keys())}")
        now = datetime.now(timezone.utc)

        # Handle single message (send/reply operations)
        if "message" in data:
            message = data["message"]
            entity = EntityContext(
                entity_id=message.get("id", ""),
                entity_type=EntityType.EMAIL,
                display_name=f"Email: {message.get('subject', 'No Subject')}",
                data=message,
                created_at=now,
                last_accessed=now,
                source_tool=tool_name
            )
            entities.append(entity)

            # Extract contact from sender
            sender = message.get("from", "")
            if sender:
                contact_entity = self._create_contact_entity(sender, now, tool_name)
                if contact_entity:
                    entities.append(contact_entity)

        # Handle multiple messages (read/search operations)
        if "messages" in data:
            messages = data["messages"]
            logger.info(f"   📋 Found {len(messages)} messages to extract")
            for message in messages:
                entity = EntityContext(
                    entity_id=message.get("id", ""),
                    entity_type=EntityType.EMAIL,
                    display_name=f"Email: {message.get('subject', 'No Subject')}",
                    data=message,
                    created_at=now,
                    last_accessed=now,
                    source_tool=tool_name
                )
                entities.append(entity)
                logger.info(f"   ✅ Extracted email: {entity.display_name} (ID: {entity.entity_id})")

                # Extract contacts from email addresses
                for field in ["from", "to", "cc"]:
                    email_addresses = message.get(field, "")
                    if email_addresses:
                        # Handle multiple addresses separated by commas
                        for addr in email_addresses.split(","):
                            addr = addr.strip()
                            if addr:
                                contact_entity = self._create_contact_entity(addr, now, tool_name)
                                if contact_entity:
                                    entities.append(contact_entity)

        logger.info(f"   📤 Total entities extracted: {len(entities)}")
        return entities

    def _create_contact_entity(self, email_address: str, timestamp: datetime, source_tool: str) -> Optional[EntityContext]:
        """Create a contact entity from an email address."""
        if not email_address or "@" not in email_address:
            return None

        # Extract name and email from formats like "John Doe <john@example.com>" or just "john@example.com"
        import re
        match = re.match(r'^(.+?)\s*<(.+?)>$', email_address.strip())
        if match:
            name = match.group(1).strip().strip('"')
            email = match.group(2).strip()
        else:
            email = email_address.strip()
            name = email.split("@")[0]  # Use part before @ as name

        return EntityContext(
            entity_id=email,  # Use email as unique ID
            entity_type=EntityType.CONTACT,
            display_name=f"{name} ({email})" if name != email else email,
            data={
                "email": email,
                "name": name,
                "source": "gmail"
            },
            created_at=timestamp,
            last_accessed=timestamp,
            source_tool=source_tool
        )


class TavilySearchExtractor(ContextExtractor):
    """Extract search result entities from Tavily web search results."""

    def can_extract(self, tool_name: str, result: Dict[str, Any]) -> bool:
        """Check if this extractor can handle the tool result."""
        return tool_name == "tavily_search" and "result" in result

    def extract_entities(self, tool_name: str, result: Dict[str, Any]) -> List[EntityContext]:
        """Extract search result entities from Tavily search results."""
        logger.info(f"🏷️  TAVILY EXTRACTOR: Attempting to extract from {tool_name}")
        logger.info(f"   📥 Tool result keys: {list(result.keys())}")

        entities = []
        # The actual data is nested under "result" key
        data = result.get("result", {})
        logger.info(f"   📊 Data keys: {list(data.keys())}")
        now = datetime.now(timezone.utc)

        # Extract search query information
        query = data.get("query", "")
        search_results = data.get("results", [])

        logger.info(f"   🔍 Search query: '{query}'")
        logger.info(f"   📋 Found {len(search_results)} search results to extract")

        # Create entities for each search result
        for i, search_result in enumerate(search_results):
            try:
                # Generate unique ID for this search result
                result_id = f"search_{hash(search_result.get('url', '') + query)}_{i}"

                # Extract relevant information
                title = search_result.get("title", "").strip()
                url = search_result.get("url", "").strip()
                content = search_result.get("content", "").strip()
                score = search_result.get("score", 0.0)
                published_date = search_result.get("published_date")

                if not title or not url:
                    logger.debug(f"   ⚠️  Skipping search result {i} - missing title or URL")
                    continue

                # Create display name
                display_name = f"Search Result: {title}"

                # Create entity data
                entity_data = {
                    "title": title,
                    "url": url,
                    "content": content,
                    "score": score,
                    "published_date": published_date,
                    "query": query,
                    "search_timestamp": now.isoformat(),
                    "result_index": i
                }

                entity = EntityContext(
                    entity_id=result_id,
                    entity_type=EntityType.SEARCH_RESULT,
                    display_name=display_name,
                    data=entity_data,
                    created_at=now,
                    last_accessed=now,
                    source_tool=tool_name
                )

                entities.append(entity)
                logger.debug(f"   ✅ Extracted search result: {title}")

            except Exception as e:
                logger.warning(f"   ❌ Failed to extract search result {i}: {str(e)}")
                continue

        logger.info(f"   📤 Total search result entities extracted: {len(entities)}")
        return entities


class ToolEntityStore:
    """
    Stores and manages entities extracted from tool executions for the Personal Assistant.

    This class maintains a store of entities (calendar events, emails, contacts, etc.)
    that have been extracted from tool results, enabling context-aware interactions
    and entity resolution for ambiguous user references.
    """
    
    def __init__(self, session_id: str, max_entities: int = 50, default_expiry_minutes: int = 60):
        self.session_id = session_id
        self.max_entities = max_entities
        self.default_expiry_minutes = default_expiry_minutes
        
        # Entity storage
        self._entities: Dict[str, EntityContext] = {}
        self._entity_by_type: Dict[EntityType, List[str]] = {et: [] for et in EntityType}

        # Tool execution storage
        self._tool_executions: Dict[str, ToolExecutionContext] = {}
        self._executions_by_tool: Dict[str, List[str]] = {}
        self._executions_chronological: List[str] = []  # Ordered by execution time

        # Context extractors
        self._extractors: List[ContextExtractor] = [
            CalendarEventExtractor(),
            GmailExtractor(),
            TavilySearchExtractor()
        ]
        
        # Memory metadata
        self.created_at = datetime.now(timezone.utc)
        self.last_cleanup = datetime.now(timezone.utc)

        # Persistence settings
        self.persistence_enabled = True
        self.persistence_dir = Path("data/memory")
        self.persistence_dir.mkdir(parents=True, exist_ok=True)
    
    def store_entity(self, entity: EntityContext) -> None:
        """Store an entity in the entity store."""
        # Update existing entity or add new one
        if entity.entity_id in self._entities:
            existing = self._entities[entity.entity_id]
            existing.data.update(entity.data)
            existing.access()
            logger.debug(f"Updated existing entity: {entity.display_name}")
        else:
            self._entities[entity.entity_id] = entity
            self._entity_by_type[entity.entity_type].append(entity.entity_id)
            logger.debug(f"Stored new entity: {entity.display_name}")
        
        # Cleanup if we exceed max entities
        if len(self._entities) > self.max_entities:
            self._cleanup_old_entities()
    
    def get_entity(self, entity_id: str) -> Optional[EntityContext]:
        """Retrieve an entity by ID."""
        entity = self._entities.get(entity_id)
        if entity:
            entity.access()
        return entity
    
    def find_entities_by_reference(self, reference: str, entity_type: Optional[EntityType] = None) -> List[EntityContext]:
        """Find entities that match a user reference."""
        matches = []
        
        # Filter by type if specified
        entities_to_search = []
        if entity_type:
            entity_ids = self._entity_by_type.get(entity_type, [])
            entities_to_search = [self._entities[eid] for eid in entity_ids if eid in self._entities]
        else:
            entities_to_search = list(self._entities.values())
        
        # Find matches
        for entity in entities_to_search:
            if entity.matches_reference(reference):
                entity.access()
                matches.append(entity)
        
        # Sort by access count and recency
        matches.sort(key=lambda e: (e.access_count, e.last_accessed), reverse=True)
        return matches
    
    def get_recent_entities(self, entity_type: Optional[EntityType] = None, limit: int = 10) -> List[EntityContext]:
        """Get recently accessed entities."""
        entities = []
        
        if entity_type:
            entity_ids = self._entity_by_type.get(entity_type, [])
            entities = [self._entities[eid] for eid in entity_ids if eid in self._entities]
        else:
            entities = list(self._entities.values())
        
        # Sort by last accessed time
        entities.sort(key=lambda e: e.last_accessed, reverse=True)
        return entities[:limit]
    
    def process_tool_result(self, tool_name: str, result: Dict[str, Any],
                          user_request: str = "", parameters: Dict[str, Any] = None,
                          execution_time_ms: float = 0) -> List[EntityContext]:
        """Process a tool result and extract entities for storage."""
        extracted_entities = []

        for extractor in self._extractors:
            if extractor.can_extract(tool_name, result):
                entities = extractor.extract_entities(tool_name, result)
                for entity in entities:
                    self.store_entity(entity)
                    extracted_entities.append(entity)
                break

        return extracted_entities

    def process_tool_execution(self, tool_name: str, user_request: str,
                             parameters: Dict[str, Any], result: Dict[str, Any],
                             execution_time_ms: float, success: bool = True,
                             error_message: Optional[str] = None,
                             user_intent: Optional[str] = None) -> ToolExecutionContext:
        """
        Process a complete tool execution and store both metadata and extracted entities.

        This is the main method to call after a tool execution to capture all context.
        """
        # Create tool execution context
        execution = ToolExecutionContext(
            execution_id=str(uuid.uuid4()),
            tool_name=tool_name,
            user_request=user_request,
            parameters=parameters.copy() if parameters else {},
            raw_output=result.copy() if isinstance(result, dict) else {"output": result},
            success=success,
            execution_time_ms=execution_time_ms,
            timestamp=datetime.now(timezone.utc),
            error_message=error_message,
            user_intent=user_intent,
            session_id=self.session_id
        )

        # Extract entities if successful
        extracted_entities = []
        if success and isinstance(result, dict):
            extracted_entities = self.process_tool_result(tool_name, result, user_request, parameters, execution_time_ms)

            # Link extracted entities to this execution
            for entity in extracted_entities:
                execution.add_extracted_entity(entity.entity_id)

        # Store the execution
        self.store_tool_execution(execution)

        logger.info(f"Processed tool execution: {execution.get_summary()}")
        return execution

    def store_tool_execution(self, execution: ToolExecutionContext) -> None:
        """Store a tool execution in conversation memory."""
        # Store the execution
        self._tool_executions[execution.execution_id] = execution

        # Update tool index
        if execution.tool_name not in self._executions_by_tool:
            self._executions_by_tool[execution.tool_name] = []
        self._executions_by_tool[execution.tool_name].append(execution.execution_id)

        # Update chronological index
        self._executions_chronological.append(execution.execution_id)

        # Keep chronological list sorted and limited
        self._executions_chronological.sort(
            key=lambda eid: self._tool_executions[eid].timestamp
        )

        # Limit to most recent executions to prevent memory bloat
        max_executions = self.max_entities * 2  # Allow more executions than entities
        if len(self._executions_chronological) > max_executions:
            # Remove oldest executions
            to_remove = self._executions_chronological[:-max_executions]
            for exec_id in to_remove:
                execution_to_remove = self._tool_executions.pop(exec_id, None)
                if execution_to_remove:
                    # Remove from tool index
                    tool_list = self._executions_by_tool.get(execution_to_remove.tool_name, [])
                    if exec_id in tool_list:
                        tool_list.remove(exec_id)

            self._executions_chronological = self._executions_chronological[-max_executions:]

        logger.debug(f"Stored tool execution: {execution.get_summary()}")

    def get_tool_execution(self, execution_id: str) -> Optional[ToolExecutionContext]:
        """Retrieve a tool execution by ID."""
        return self._tool_executions.get(execution_id)

    def get_recent_tool_executions(self, limit: int = 10,
                                  tool_name: Optional[str] = None,
                                  success_only: bool = False) -> List[ToolExecutionContext]:
        """Get recent tool executions, optionally filtered by tool name and success status."""
        executions = []

        # Get execution IDs to consider
        if tool_name:
            exec_ids = self._executions_by_tool.get(tool_name, [])
            # Sort by timestamp (most recent first)
            exec_ids = sorted(exec_ids,
                            key=lambda eid: self._tool_executions[eid].timestamp,
                            reverse=True)
        else:
            # Use chronological list (reverse for most recent first)
            exec_ids = list(reversed(self._executions_chronological))

        # Filter and collect executions
        for exec_id in exec_ids:
            execution = self._tool_executions.get(exec_id)
            if execution:
                if success_only and not execution.success:
                    continue
                executions.append(execution)
                if len(executions) >= limit:
                    break

        return executions

    def find_tool_executions_by_criteria(self,
                                       tool_name: Optional[str] = None,
                                       success: Optional[bool] = None,
                                       user_intent: Optional[str] = None,
                                       entity_id: Optional[str] = None,
                                       since_minutes: Optional[int] = None) -> List[ToolExecutionContext]:
        """Find tool executions matching specific criteria."""
        matches = []

        for execution in self._tool_executions.values():
            # Check time filter first (most selective)
            if since_minutes is not None and not execution.is_recent(since_minutes):
                continue

            # Check other criteria
            if execution.matches_criteria(tool_name, success, user_intent, entity_id):
                matches.append(execution)

        # Sort by timestamp (most recent first)
        matches.sort(key=lambda e: e.timestamp, reverse=True)
        return matches

    def get_entity_creation_context(self, entity_id: str) -> Optional[ToolExecutionContext]:
        """Get the tool execution that created/extracted a specific entity."""
        for execution in self._tool_executions.values():
            if entity_id in execution.extracted_entity_ids:
                return execution
        return None

    def correlate_entities_with_executions(self, entity_ids: List[str]) -> Dict[str, ToolExecutionContext]:
        """Get the tool executions that created/extracted the given entities."""
        correlations = {}
        for entity_id in entity_ids:
            execution = self.get_entity_creation_context(entity_id)
            if execution:
                correlations[entity_id] = execution
        return correlations
    
    def cleanup_expired_entities(self) -> int:
        """Remove expired entities from memory."""
        expired_ids = []
        
        for entity_id, entity in self._entities.items():
            if entity.is_expired(self.default_expiry_minutes):
                expired_ids.append(entity_id)
        
        for entity_id in expired_ids:
            entity = self._entities.pop(entity_id)
            # Remove from type index
            if entity_id in self._entity_by_type[entity.entity_type]:
                self._entity_by_type[entity.entity_type].remove(entity_id)
        
        self.last_cleanup = datetime.now(timezone.utc)
        logger.debug(f"Cleaned up {len(expired_ids)} expired entities")
        return len(expired_ids)
    
    def _cleanup_old_entities(self) -> None:
        """Remove oldest entities when max capacity is exceeded."""
        if len(self._entities) <= self.max_entities:
            return
        
        # Sort entities by last accessed time (oldest first)
        entities_by_age = sorted(
            self._entities.items(),
            key=lambda x: x[1].last_accessed
        )
        
        # Remove oldest entities
        entities_to_remove = len(self._entities) - self.max_entities + 5  # Remove a few extra
        for i in range(entities_to_remove):
            if i < len(entities_by_age):
                entity_id, entity = entities_by_age[i]
                self._entities.pop(entity_id)
                if entity_id in self._entity_by_type[entity.entity_type]:
                    self._entity_by_type[entity.entity_type].remove(entity_id)
        
        logger.debug(f"Cleaned up {entities_to_remove} old entities due to capacity limit")
    
    def get_context_summary(self) -> Dict[str, Any]:
        """Get a summary of current entity store contents."""
        recent_executions = self.get_recent_tool_executions(limit=5)

        return {
            "session_id": self.session_id,
            "total_entities": len(self._entities),
            "total_tool_executions": len(self._tool_executions),
            "entities_by_type": {et.value: len(ids) for et, ids in self._entity_by_type.items() if ids},
            "executions_by_tool": {tool: len(ids) for tool, ids in self._executions_by_tool.items() if ids},
            "recent_entities": [
                {
                    "id": entity.entity_id,
                    "type": entity.entity_type.value,
                    "name": entity.display_name,
                    "last_accessed": entity.last_accessed.isoformat()
                }
                for entity in self.get_recent_entities(limit=5)
            ],
            "recent_tool_executions": [
                {
                    "id": execution.execution_id,
                    "tool": execution.tool_name,
                    "summary": execution.get_summary(),
                    "timestamp": execution.timestamp.isoformat(),
                    "entities_extracted": len(execution.extracted_entity_ids)
                }
                for execution in recent_executions
            ]
        }

    def save_to_disk(self) -> bool:
        """Save entity store to disk."""
        if not self.persistence_enabled:
            return False

        try:
            # Create session-specific file
            memory_file = self.persistence_dir / f"session_{self.session_id}.pkl"

            # Prepare entities data for serialization
            entities_data = {}
            for eid, entity in self._entities.items():
                entity_dict = asdict(entity)
                # Convert datetime objects to ISO strings
                entity_dict["created_at"] = entity.created_at.isoformat()
                entity_dict["last_accessed"] = entity.last_accessed.isoformat()
                entity_dict["entity_type"] = entity.entity_type.value
                entities_data[eid] = entity_dict

            # Prepare tool executions data for serialization
            executions_data = {}
            for exec_id, execution in self._tool_executions.items():
                exec_dict = asdict(execution)
                # Convert datetime objects to ISO strings
                exec_dict["timestamp"] = execution.timestamp.isoformat()
                executions_data[exec_id] = exec_dict

            memory_data = {
                "session_id": self.session_id,
                "max_entities": self.max_entities,
                "default_expiry_minutes": self.default_expiry_minutes,
                "entities": entities_data,
                "entity_by_type": {et.value: ids for et, ids in self._entity_by_type.items()},
                "tool_executions": executions_data,
                "executions_by_tool": self._executions_by_tool,
                "executions_chronological": self._executions_chronological,
                "created_at": self.created_at.isoformat(),
                "last_cleanup": self.last_cleanup.isoformat()
            }

            # Save to disk
            with open(memory_file, 'wb') as f:
                pickle.dump(memory_data, f)

            logger.debug(f"Saved entity store for session {self.session_id} to disk")
            return True

        except Exception as e:
            logger.error(f"Failed to save entity store to disk: {str(e)}")
            return False

    @classmethod
    def load_from_disk(cls, session_id: str, persistence_dir: Optional[Path] = None) -> Optional['ToolEntityStore']:
        """Load tool entity store from disk."""
        try:
            if persistence_dir is None:
                persistence_dir = Path("data/memory")

            memory_file = persistence_dir / f"session_{session_id}.pkl"
            if not memory_file.exists():
                return None

            # Load data from disk
            with open(memory_file, 'rb') as f:
                memory_data = pickle.load(f)

            # Create new instance
            entity_store = cls(
                session_id=memory_data["session_id"],
                max_entities=memory_data.get("max_entities", 50),
                default_expiry_minutes=memory_data.get("default_expiry_minutes", 60)
            )

            # Restore entities
            for eid, entity_data in memory_data.get("entities", {}).items():
                # Convert datetime strings back to datetime objects
                if isinstance(entity_data["created_at"], str):
                    entity_data["created_at"] = datetime.fromisoformat(entity_data["created_at"])
                if isinstance(entity_data["last_accessed"], str):
                    entity_data["last_accessed"] = datetime.fromisoformat(entity_data["last_accessed"])
                if isinstance(entity_data["entity_type"], str):
                    entity_data["entity_type"] = EntityType(entity_data["entity_type"])

                entity = EntityContext(**entity_data)
                entity_store._entities[eid] = entity

            # Restore type index
            for et_value, ids in memory_data.get("entity_by_type", {}).items():
                et = EntityType(et_value)
                entity_store._entity_by_type[et] = ids

            # Restore tool executions
            for exec_id, exec_data in memory_data.get("tool_executions", {}).items():
                # Convert datetime strings back to datetime objects
                if isinstance(exec_data["timestamp"], str):
                    exec_data["timestamp"] = datetime.fromisoformat(exec_data["timestamp"])

                execution = ToolExecutionContext(**exec_data)
                entity_store._tool_executions[exec_id] = execution

            # Restore tool execution indices
            entity_store._executions_by_tool = memory_data.get("executions_by_tool", {})
            entity_store._executions_chronological = memory_data.get("executions_chronological", [])

            # Restore metadata
            entity_store.created_at = datetime.fromisoformat(memory_data.get("created_at", datetime.now(timezone.utc).isoformat()))
            entity_store.last_cleanup = datetime.fromisoformat(memory_data.get("last_cleanup", datetime.now(timezone.utc).isoformat()))

            logger.debug(f"Loaded entity store for session {session_id} from disk")
            return entity_store

        except Exception as e:
            logger.error(f"Failed to load entity store from disk: {str(e)}")
            return None

    def cleanup_disk_files(self, max_age_days: int = 7) -> int:
        """Clean up old memory files from disk."""
        if not self.persistence_enabled:
            return 0

        try:
            cleaned_count = 0
            cutoff_time = datetime.now(timezone.utc) - timedelta(days=max_age_days)

            for memory_file in self.persistence_dir.glob("session_*.pkl"):
                try:
                    # Check file modification time
                    file_mtime = datetime.fromtimestamp(memory_file.stat().st_mtime, tz=timezone.utc)
                    if file_mtime < cutoff_time:
                        memory_file.unlink()
                        cleaned_count += 1
                        logger.debug(f"Cleaned up old memory file: {memory_file.name}")
                except Exception as e:
                    logger.warning(f"Failed to clean up memory file {memory_file.name}: {str(e)}")

            return cleaned_count

        except Exception as e:
            logger.error(f"Failed to cleanup disk files: {str(e)}")
            return 0

    def get_context_summary(self) -> Dict[str, Any]:
        """Get a summary of the current conversation context for logging."""
        entity_counts = {}
        for entity_type in EntityType:
            count = len(self._entity_by_type[entity_type])
            if count > 0:
                entity_counts[entity_type.value] = count

        tool_counts = {}
        for tool_name, execution_ids in self._executions_by_tool.items():
            tool_counts[tool_name] = len(execution_ids)

        recent_entities = []
        for entity in list(self._entities.values())[-3:]:  # Last 3 entities
            recent_entities.append({
                "type": entity.entity_type.value,
                "name": entity.display_name,
                "id": entity.entity_id
            })

        recent_tools = []
        for execution in self.get_recent_tool_executions(limit=3):
            recent_tools.append({
                "tool": execution.tool_name,
                "success": execution.success,
                "timestamp": execution.timestamp.isoformat(),
                "entities_created": len(execution.extracted_entity_ids)
            })

        return {
            "session_id": self.session_id,
            "total_entities": len(self._entities),
            "total_tool_executions": len(self._tool_executions),
            "entity_counts_by_type": entity_counts,
            "tool_counts": tool_counts,
            "recent_entities": recent_entities,
            "recent_tool_executions": recent_tools
        }
