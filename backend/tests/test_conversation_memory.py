"""
Test suite for the conversation memory system.

Tests cover context storage, retrieval, expiration, cross-interaction state preservation,
and the specific scenario described in the issue where the agent loses context between interactions.
"""

import pytest
import tempfile
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from app.agents.personal_assistant.memory import (
    ConversationMemory, EntityContext, EntityType, CalendarEventExtractor
)
from app.agents.personal_assistant.context_resolver import ContextResolver


class TestEntityContext:
    """Test EntityContext functionality."""
    
    def test_entity_creation(self):
        """Test basic entity creation and properties."""
        now = datetime.now(timezone.utc)
        entity = EntityContext(
            entity_id="test-event-123",
            entity_type=EntityType.CALENDAR_EVENT,
            display_name="Test Meeting",
            data={"summary": "Test Meeting", "start": "2025-09-12T13:00:00Z"},
            created_at=now,
            last_accessed=now,
            source_tool="google_calendar"
        )
        
        assert entity.entity_id == "test-event-123"
        assert entity.entity_type == EntityType.CALENDAR_EVENT
        assert entity.display_name == "Test Meeting"
        assert entity.source_tool == "google_calendar"
        assert entity.access_count == 0
    
    def test_entity_access_tracking(self):
        """Test entity access tracking."""
        now = datetime.now(timezone.utc)
        entity = EntityContext(
            entity_id="test-event-123",
            entity_type=EntityType.CALENDAR_EVENT,
            display_name="Test Meeting",
            data={},
            created_at=now,
            last_accessed=now
        )
        
        initial_access_time = entity.last_accessed
        initial_count = entity.access_count
        
        entity.access()
        
        assert entity.access_count == initial_count + 1
        assert entity.last_accessed > initial_access_time
    
    def test_entity_reference_matching(self):
        """Test entity reference matching."""
        entity = EntityContext(
            entity_id="nabulu-meeting-123",
            entity_type=EntityType.CALENDAR_EVENT,
            display_name="Nabulu coming to your place",
            data={"summary": "Nabulu coming to your place", "location": "Home"},
            created_at=datetime.now(timezone.utc),
            last_accessed=datetime.now(timezone.utc)
        )
        
        # Test various reference patterns
        assert entity.matches_reference("Nabulu")
        assert entity.matches_reference("nabulu")
        assert entity.matches_reference("coming to your place")
        assert entity.matches_reference("the meeting")
        assert not entity.matches_reference("unrelated text")
    
    def test_entity_expiration(self):
        """Test entity expiration logic."""
        old_time = datetime.now(timezone.utc) - timedelta(hours=2)
        entity = EntityContext(
            entity_id="test-event-123",
            entity_type=EntityType.CALENDAR_EVENT,
            display_name="Old Meeting",
            data={},
            created_at=old_time,
            last_accessed=old_time
        )
        
        # Should be expired with 60 minute default
        assert entity.is_expired(max_age_minutes=60)
        
        # Should not be expired with longer threshold
        assert not entity.is_expired(max_age_minutes=180)


class TestCalendarEventExtractor:
    """Test calendar event extraction from tool results."""
    
    def test_can_extract_calendar_events(self):
        """Test extractor can identify calendar tool results."""
        extractor = CalendarEventExtractor()
        
        # Positive cases
        assert extractor.can_extract("google_calendar", {"success": True, "data": {"events": []}})
        assert extractor.can_extract("google_calendar", {"success": True, "data": {"event": {}}})
        
        # Negative cases
        assert not extractor.can_extract("other_tool", {"success": True, "data": {"events": []}})
        assert not extractor.can_extract("google_calendar", {"success": False, "data": {"events": []}})
        assert not extractor.can_extract("google_calendar", {"success": True, "data": {}})
    
    def test_extract_single_event(self):
        """Test extraction of single event from tool result."""
        extractor = CalendarEventExtractor()
        result = {
            "success": True,
            "data": {
                "event": {
                    "id": "event-123",
                    "summary": "Test Meeting",
                    "start": "2025-09-12T13:00:00Z",
                    "end": "2025-09-12T14:00:00Z"
                }
            }
        }
        
        entities = extractor.extract_entities("google_calendar", result)
        
        assert len(entities) == 1
        entity = entities[0]
        assert entity.entity_id == "event-123"
        assert entity.display_name == "Test Meeting"
        assert entity.entity_type == EntityType.CALENDAR_EVENT
        assert entity.source_tool == "google_calendar"
    
    def test_extract_multiple_events(self):
        """Test extraction of multiple events from tool result."""
        extractor = CalendarEventExtractor()
        result = {
            "success": True,
            "data": {
                "events": [
                    {"id": "event-1", "summary": "Meeting 1"},
                    {"id": "event-2", "summary": "Meeting 2"}
                ]
            }
        }
        
        entities = extractor.extract_entities("google_calendar", result)
        
        assert len(entities) == 2
        assert entities[0].entity_id == "event-1"
        assert entities[1].entity_id == "event-2"


class TestConversationMemory:
    """Test ConversationMemory functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.memory = ConversationMemory("test-session-123")
        self.test_entity = EntityContext(
            entity_id="nabulu-meeting-123",
            entity_type=EntityType.CALENDAR_EVENT,
            display_name="Nabulu coming to your place",
            data={
                "summary": "Nabulu coming to your place",
                "start": "2025-09-12T13:00:00Z",
                "end": "2025-09-12T14:00:00Z"
            },
            created_at=datetime.now(timezone.utc),
            last_accessed=datetime.now(timezone.utc),
            source_tool="google_calendar"
        )
    
    def test_store_and_retrieve_entity(self):
        """Test basic entity storage and retrieval."""
        self.memory.store_entity(self.test_entity)
        
        retrieved = self.memory.get_entity("nabulu-meeting-123")
        assert retrieved is not None
        assert retrieved.display_name == "Nabulu coming to your place"
        assert retrieved.access_count == 1  # Should be incremented by get_entity
    
    def test_find_entities_by_reference(self):
        """Test finding entities by user reference."""
        self.memory.store_entity(self.test_entity)
        
        # Test various reference patterns
        matches = self.memory.find_entities_by_reference("Nabulu")
        assert len(matches) == 1
        assert matches[0].entity_id == "nabulu-meeting-123"
        
        matches = self.memory.find_entities_by_reference("the event")
        assert len(matches) == 1
        
        matches = self.memory.find_entities_by_reference("unrelated")
        assert len(matches) == 0
    
    def test_process_tool_result(self):
        """Test processing tool results for entity extraction."""
        tool_result = {
            "success": True,
            "data": {
                "events": [
                    {
                        "id": "extracted-event-123",
                        "summary": "Extracted Meeting",
                        "start": "2025-09-12T15:00:00Z"
                    }
                ]
            }
        }
        
        entities = self.memory.process_tool_result("google_calendar", tool_result)
        
        assert len(entities) == 1
        assert entities[0].entity_id == "extracted-event-123"
        
        # Verify entity was stored
        retrieved = self.memory.get_entity("extracted-event-123")
        assert retrieved is not None
    
    def test_cleanup_expired_entities(self):
        """Test cleanup of expired entities."""
        # Create an old entity
        old_time = datetime.now(timezone.utc) - timedelta(hours=2)
        old_entity = EntityContext(
            entity_id="old-event-123",
            entity_type=EntityType.CALENDAR_EVENT,
            display_name="Old Meeting",
            data={},
            created_at=old_time,
            last_accessed=old_time
        )
        
        self.memory.store_entity(old_entity)
        self.memory.store_entity(self.test_entity)  # Recent entity
        
        assert len(self.memory._entities) == 2
        
        # Cleanup with 60 minute threshold
        cleaned_count = self.memory.cleanup_expired_entities()
        
        assert cleaned_count == 1
        assert len(self.memory._entities) == 1
        assert "old-event-123" not in self.memory._entities
        assert "nabulu-meeting-123" in self.memory._entities


class TestContextResolver:
    """Test ContextResolver functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.memory = ConversationMemory("test-session-123")
        self.resolver = ContextResolver(self.memory)
        
        # Add a test event to memory
        self.test_entity = EntityContext(
            entity_id="nabulu-meeting-123",
            entity_type=EntityType.CALENDAR_EVENT,
            display_name="Nabulu coming to your place",
            data={
                "summary": "Nabulu coming to your place",
                "start": "2025-09-12T13:00:00Z",
                "end": "2025-09-12T14:00:00Z"
            },
            created_at=datetime.now(timezone.utc),
            last_accessed=datetime.now(timezone.utc),
            source_tool="google_calendar"
        )
        self.memory.store_entity(self.test_entity)
    
    def test_resolve_calendar_event_reference(self):
        """Test resolving calendar event references."""
        # Test explicit deletion request
        event_id = self.resolver.resolve_calendar_event_reference(
            "delete the event", {}
        )
        assert event_id == "nabulu-meeting-123"
        
        # Test name-based reference
        event_id = self.resolver.resolve_calendar_event_reference(
            "cancel the Nabulu meeting", {}
        )
        assert event_id == "nabulu-meeting-123"
        
        # Test no match
        event_id = self.resolver.resolve_calendar_event_reference(
            "delete something else", {}
        )
        assert event_id is None
    
    def test_enhance_tool_parameters(self):
        """Test enhancing tool parameters with context."""
        original_params = {
            "action": "delete"
        }
        
        enhanced_params = self.resolver.enhance_tool_parameters(
            "google_calendar", original_params, "delete the event"
        )
        
        assert enhanced_params["event_id"] == "nabulu-meeting-123"
        assert "_context_info" in enhanced_params
        assert enhanced_params["_context_info"]["resolved_entity"]["name"] == "Nabulu coming to your place"
    
    def test_generate_confirmation_message(self):
        """Test generating context-aware confirmation messages."""
        parameters = {
            "action": "delete",
            "event_id": "nabulu-meeting-123",
            "_context_info": {
                "resolved_entity": {
                    "type": "calendar_event",
                    "name": "Nabulu coming to your place",
                    "id": "nabulu-meeting-123"
                }
            }
        }
        
        message = self.resolver.generate_confirmation_message(
            "google_calendar", parameters, "delete"
        )
        
        assert message is not None
        assert "Nabulu coming to your place" in message
        assert "delete" in message.lower()


class TestMemoryPersistence:
    """Test memory persistence functionality."""
    
    def setup_method(self):
        """Set up test fixtures with temporary directory."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.memory = ConversationMemory("test-session-123")
        self.memory.persistence_dir = self.temp_dir
        
        # Add test entity
        self.test_entity = EntityContext(
            entity_id="test-event-123",
            entity_type=EntityType.CALENDAR_EVENT,
            display_name="Test Meeting",
            data={"summary": "Test Meeting"},
            created_at=datetime.now(timezone.utc),
            last_accessed=datetime.now(timezone.utc)
        )
        self.memory.store_entity(self.test_entity)
    
    def teardown_method(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir)
    
    def test_save_and_load_memory(self):
        """Test saving and loading memory from disk."""
        # Save memory
        success = self.memory.save_to_disk()
        assert success
        
        # Verify file exists
        memory_file = self.temp_dir / "session_test-session-123.pkl"
        assert memory_file.exists()
        
        # Load memory
        loaded_memory = ConversationMemory.load_from_disk("test-session-123", self.temp_dir)
        assert loaded_memory is not None
        assert loaded_memory.session_id == "test-session-123"
        assert len(loaded_memory._entities) == 1
        
        # Verify entity was restored
        entity = loaded_memory.get_entity("test-event-123")
        assert entity is not None
        assert entity.display_name == "Test Meeting"


class TestStateManagementScenario:
    """Test the specific state management scenario described in the issue."""
    
    def setup_method(self):
        """Set up the scenario test."""
        self.memory = ConversationMemory("scenario-session")
        self.resolver = ContextResolver(self.memory)
    
    def test_nabulu_meeting_scenario(self):
        """Test the specific Nabulu meeting scenario from the issue."""
        # Step 1: Agent retrieves calendar events (simulating list operation)
        calendar_result = {
            "success": True,
            "data": {
                "events": [
                    {
                        "id": "nabulu-event-456",
                        "summary": "Nabulu coming to your place",
                        "start": "2025-09-12T13:00:00Z",
                        "end": "2025-09-12T14:00:00Z",
                        "location": "Home"
                    }
                ]
            }
        }
        
        # Process the tool result (this should store the event in memory)
        extracted_entities = self.memory.process_tool_result("google_calendar", calendar_result)
        assert len(extracted_entities) == 1
        assert extracted_entities[0].display_name == "Nabulu coming to your place"
        
        # Step 2: User asks to delete "the event" (ambiguous reference)
        user_message = "delete the event"
        
        # The context resolver should identify the Nabulu event
        resolved_event_id = self.resolver.resolve_calendar_event_reference(user_message, {})
        assert resolved_event_id == "nabulu-event-456"
        
        # Step 3: Enhance parameters with context
        delete_params = {"action": "delete"}
        enhanced_params = self.resolver.enhance_tool_parameters(
            "google_calendar", delete_params, user_message
        )
        
        assert enhanced_params["event_id"] == "nabulu-event-456"
        assert enhanced_params["_context_info"]["resolved_entity"]["name"] == "Nabulu coming to your place"
        
        # Step 4: Generate confirmation message
        confirmation = self.resolver.generate_confirmation_message(
            "google_calendar", enhanced_params, "delete"
        )
        
        assert confirmation is not None
        assert "Nabulu coming to your place" in confirmation
        
        # This demonstrates that the agent maintains context and can resolve
        # ambiguous references without asking for clarification
