#!/usr/bin/env python3
"""
Simple test script to verify the conversation memory implementation.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.agents.personal_assistant.memory import ConversationMemory, EntityContext, EntityType
from app.agents.personal_assistant.context_resolver import ContextResolver
from datetime import datetime, timezone

def test_basic_memory():
    """Test basic memory functionality."""
    print("🧪 Testing basic memory functionality...")
    
    memory = ConversationMemory('test-session')
    print(f"✓ Created memory for session: {memory.session_id}")
    
    # Create test entity
    entity = EntityContext(
        entity_id='test-event-123',
        entity_type=EntityType.CALENDAR_EVENT,
        display_name='Test Meeting',
        data={'summary': 'Test Meeting'},
        created_at=datetime.now(timezone.utc),
        last_accessed=datetime.now(timezone.utc)
    )
    
    # Store and retrieve
    memory.store_entity(entity)
    retrieved = memory.get_entity('test-event-123')
    assert retrieved is not None
    assert retrieved.display_name == 'Test Meeting'
    print(f"✓ Stored and retrieved entity: {retrieved.display_name}")
    
    # Test reference matching
    matches = memory.find_entities_by_reference('Test Meeting')
    assert len(matches) == 1
    print(f"✓ Found {len(matches)} matches for reference")
    
    print("✅ Basic memory test passed!\n")

def test_nabulu_scenario():
    """Test the specific Nabulu meeting scenario."""
    print("🧪 Testing Nabulu meeting scenario...")
    
    memory = ConversationMemory('scenario-session')
    resolver = ContextResolver(memory)
    
    # Step 1: Simulate calendar event retrieval
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
    
    # Process the tool result
    extracted_entities = memory.process_tool_result("google_calendar", calendar_result)
    assert len(extracted_entities) == 1
    assert extracted_entities[0].display_name == "Nabulu coming to your place"
    print("✓ Processed calendar result and extracted event")
    
    # Step 2: Test ambiguous reference resolution
    user_message = "delete the event"
    resolved_event_id = resolver.resolve_calendar_event_reference(user_message, {})
    assert resolved_event_id == "nabulu-event-456"
    print(f"✓ Resolved '{user_message}' to event ID: {resolved_event_id}")
    
    # Step 3: Test parameter enhancement
    delete_params = {"action": "delete"}
    enhanced_params = resolver.enhance_tool_parameters(
        "google_calendar", delete_params, user_message
    )
    assert enhanced_params["event_id"] == "nabulu-event-456"
    assert "_context_info" in enhanced_params
    print("✓ Enhanced parameters with context resolution")
    
    # Step 4: Test confirmation message generation
    confirmation = resolver.generate_confirmation_message(
        "google_calendar", enhanced_params, "delete"
    )
    assert confirmation is not None
    assert "Nabulu coming to your place" in confirmation
    print(f"✓ Generated confirmation: {confirmation}")
    
    print("✅ Nabulu scenario test passed!\n")

def test_memory_persistence():
    """Test memory persistence functionality."""
    print("🧪 Testing memory persistence...")
    
    import tempfile
    from pathlib import Path
    
    # Create temporary directory
    temp_dir = Path(tempfile.mkdtemp())
    print(f"✓ Using temp directory: {temp_dir}")
    
    # Create memory with test entity
    memory = ConversationMemory('persist-test')
    memory.persistence_dir = temp_dir
    
    entity = EntityContext(
        entity_id='persist-event-123',
        entity_type=EntityType.CALENDAR_EVENT,
        display_name='Persistent Meeting',
        data={'summary': 'Persistent Meeting'},
        created_at=datetime.now(timezone.utc),
        last_accessed=datetime.now(timezone.utc)
    )
    memory.store_entity(entity)
    
    # Save to disk
    success = memory.save_to_disk()
    assert success
    print("✓ Saved memory to disk")
    
    # Load from disk
    loaded = ConversationMemory.load_from_disk('persist-test', temp_dir)
    assert loaded is not None
    retrieved = loaded.get_entity('persist-event-123')
    assert retrieved is not None
    assert retrieved.display_name == 'Persistent Meeting'
    print(f"✓ Loaded entity from disk: {retrieved.display_name}")
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir)
    print("✓ Cleaned up temp directory")
    
    print("✅ Persistence test passed!\n")

def test_tool_metadata_system():
    """Test the comprehensive tool metadata system."""
    print("🧪 Testing tool metadata system...")

    memory = ConversationMemory('metadata-session')
    resolver = ContextResolver(memory)

    # Step 1: Process a tool execution with metadata
    calendar_result = {
        "success": True,
        "data": {
            "events": [
                {
                    "id": "meeting-789",
                    "summary": "Team standup",
                    "start": "2025-09-13T09:00:00Z",
                    "end": "2025-09-13T09:30:00Z"
                }
            ]
        }
    }

    execution_context = memory.process_tool_execution(
        tool_name="google_calendar",
        user_request="show me my meetings tomorrow",
        parameters={"action": "list", "date": "2025-09-13"},
        result=calendar_result,
        execution_time_ms=250.5,
        success=True,
        user_intent="list_calendar_events"
    )

    assert execution_context.tool_name == "google_calendar"
    assert execution_context.success == True
    assert execution_context.execution_time_ms == 250.5
    assert len(execution_context.extracted_entity_ids) == 1
    print("✓ Processed tool execution with metadata")

    # Step 2: Test tool execution retrieval
    retrieved_execution = memory.get_tool_execution(execution_context.execution_id)
    assert retrieved_execution is not None
    assert retrieved_execution.user_request == "show me my meetings tomorrow"
    print("✓ Retrieved tool execution by ID")

    # Step 3: Test recent executions query
    recent_executions = memory.get_recent_tool_executions(limit=5)
    assert len(recent_executions) == 1
    assert recent_executions[0].tool_name == "google_calendar"
    print("✓ Queried recent tool executions")

    # Step 4: Test entity-execution correlation
    entity_id = execution_context.extracted_entity_ids[0]
    creation_context = memory.get_entity_creation_context(entity_id)
    assert creation_context is not None
    assert creation_context.execution_id == execution_context.execution_id
    print("✓ Correlated entity with creating tool execution")

    # Step 5: Test context-aware confirmation with tool history
    # First enhance parameters to include context info
    delete_params = {"action": "delete"}
    user_message = "delete the event"  # Use pattern that resolver recognizes
    enhanced_params = resolver.enhance_tool_parameters(
        "google_calendar", delete_params, user_message
    )

    confirmation = resolver.generate_confirmation_message(
        "google_calendar", enhanced_params, "delete"
    )

    assert confirmation is not None
    assert "Team standup" in confirmation
    print(f"✓ Generated context-aware confirmation: {confirmation}")

    # Step 6: Test tool execution summaries
    summaries = resolver.get_tool_execution_summary(tool_name="google_calendar")
    assert len(summaries) == 1
    assert "google_calendar" in summaries[0]
    print("✓ Generated tool execution summaries")

    print("✅ Tool metadata system test passed!\n")

def main():
    """Run all tests."""
    print("🚀 Starting conversation memory implementation tests...\n")

    try:
        test_basic_memory()
        test_nabulu_scenario()
        test_memory_persistence()
        test_tool_metadata_system()

        print("🎉 All tests passed! The conversation memory system is working correctly.")
        print("\n📋 Summary:")
        print("- ✅ Basic entity storage and retrieval")
        print("- ✅ Context-aware reference resolution")
        print("- ✅ Parameter enhancement with stored context")
        print("- ✅ Context-aware confirmation messages")
        print("- ✅ Memory persistence and recovery")
        print("- ✅ Tool execution metadata storage and correlation")
        print("- ✅ Tool history-aware context resolution")
        print("- ✅ Enhanced confirmations with execution context")
        print("\n🔧 The agent will now maintain comprehensive context including tool execution history!")

    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
