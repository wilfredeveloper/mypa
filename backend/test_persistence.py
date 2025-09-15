#!/usr/bin/env python3
"""
Test script to verify persistence mechanisms in Personal Assistant agent.

This script tests:
1. Session state persistence to database
2. Entity store persistence to disk
3. Tavily search integration with entity store
4. Plan persistence through entity store
"""

import asyncio
import os
import sys
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any

# Add the backend directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from app.agents.personal_assistant.tool_entity_store import (
    ToolEntityStore, 
    EntityType, 
    EntityContext,
    TavilySearchExtractor
)
from app.models.conversation import ConversationSession
from app.services.conversation_service import ConversationService
from app.core.database import AsyncSessionLocal
from app.models.user import User


async def test_entity_store_persistence():
    """Test entity store persistence to disk."""
    print("🧪 Testing Entity Store Persistence...")
    
    # Create temporary directory for testing
    temp_dir = Path(tempfile.mkdtemp())
    session_id = "test_session_123"
    
    try:
        # Create entity store with custom persistence directory
        entity_store = ToolEntityStore(session_id, max_entities=10)
        entity_store.persistence_dir = temp_dir
        
        # Add some test entities
        test_entity = EntityContext(
            entity_id="test_entity_1",
            entity_type=EntityType.GENERIC,
            display_name="Test Entity",
            data={"test": "data", "value": 42},
            created_at=datetime.now(timezone.utc),
            last_accessed=datetime.now(timezone.utc),
            source_tool="test_tool"
        )
        
        entity_store.store_entity(test_entity)
        
        # Save to disk
        success = entity_store.save_to_disk()
        assert success, "Failed to save entity store to disk"
        
        # Verify file exists
        memory_file = temp_dir / f"session_{session_id}.pkl"
        assert memory_file.exists(), "Memory file was not created"
        
        # Load from disk
        loaded_store = ToolEntityStore.load_from_disk(session_id, temp_dir)
        assert loaded_store is not None, "Failed to load entity store from disk"
        
        # Verify data integrity
        loaded_entity = loaded_store.get_entity("test_entity_1")
        assert loaded_entity is not None, "Entity not found in loaded store"
        assert loaded_entity.display_name == "Test Entity", "Entity data corrupted"
        assert loaded_entity.data["value"] == 42, "Entity data corrupted"
        
        print("✅ Entity Store Persistence: PASSED")
        
    finally:
        # Clean up
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_tavily_search_extractor():
    """Test Tavily search result extraction."""
    print("🧪 Testing Tavily Search Integration...")
    
    # Create extractor
    extractor = TavilySearchExtractor()
    
    # Test can_extract
    assert extractor.can_extract("tavily_search", {"result": {}}), "Should be able to extract from tavily_search"
    assert not extractor.can_extract("other_tool", {"result": {}}), "Should not extract from other tools"
    
    # Test entity extraction
    mock_result = {
        "result": {
            "query": "test query",
            "results": [
                {
                    "title": "Test Result 1",
                    "url": "https://example.com/1",
                    "content": "This is test content 1",
                    "score": 0.95,
                    "published_date": "2024-01-01"
                },
                {
                    "title": "Test Result 2",
                    "url": "https://example.com/2",
                    "content": "This is test content 2",
                    "score": 0.87
                }
            ]
        }
    }
    
    entities = extractor.extract_entities("tavily_search", mock_result)
    
    assert len(entities) == 2, f"Expected 2 entities, got {len(entities)}"
    
    # Check first entity
    entity1 = entities[0]
    assert entity1.entity_type == EntityType.SEARCH_RESULT, "Wrong entity type"
    assert entity1.display_name == "Search Result: Test Result 1", "Wrong display name"
    assert entity1.data["title"] == "Test Result 1", "Wrong title"
    assert entity1.data["url"] == "https://example.com/1", "Wrong URL"
    assert entity1.data["query"] == "test query", "Wrong query"
    
    print("✅ Tavily Search Integration: PASSED")


async def test_session_context_persistence():
    """Test session context persistence to database."""
    print("🧪 Testing Session Context Persistence...")

    async with AsyncSessionLocal() as db:
        try:
            # Create a test user with required password hash
            from app.core.security import get_password_hash
            test_user = User(
                email="test@example.com",
                username="testuser",
                full_name="Test User",
                hashed_password=get_password_hash("testpassword"),
                is_active=True
            )
            db.add(test_user)
            await db.commit()
            await db.refresh(test_user)
            
            # Create conversation service
            conversation_service = ConversationService(db)
            
            # Create session with initial context
            initial_context = {"test_key": "test_value", "counter": 1}
            session = await conversation_service.create_session(
                user=test_user,
                title="Test Session",
                context_data=initial_context
            )
            
            # Verify initial context
            assert session.context_data == initial_context, "Initial context not saved correctly"
            
            # Update context
            updated_context = {"test_key": "updated_value", "counter": 2, "new_key": "new_value"}
            updated_session = await conversation_service.update_session_context(
                session=session,
                context_data=updated_context
            )
            
            # Verify update
            assert updated_session.context_data == updated_context, "Context not updated correctly"
            
            # Retrieve session again to verify persistence
            retrieved_session = await conversation_service.get_session(
                session_id=session.session_id,
                user=test_user
            )
            
            assert retrieved_session is not None, "Session not found"
            assert retrieved_session.context_data == updated_context, "Context not persisted correctly"
            
            print("✅ Session Context Persistence: PASSED")
            
        except Exception as e:
            print(f"❌ Session Context Persistence: FAILED - {str(e)}")
            raise
        finally:
            # Clean up test data
            try:
                await db.delete(test_user)
                await db.commit()
            except Exception:
                pass


async def test_integrated_persistence():
    """Test integrated persistence across all systems."""
    print("🧪 Testing Integrated Persistence...")
    
    # Create temporary directory for entity store
    temp_dir = Path(tempfile.mkdtemp())
    session_id = "integrated_test_session"
    
    try:
        # Create entity store
        entity_store = ToolEntityStore(session_id)
        entity_store.persistence_dir = temp_dir
        
        # Test Tavily search result processing
        mock_tavily_result = {
            "result": {
                "query": "Python programming",
                "results": [
                    {
                        "title": "Python.org",
                        "url": "https://python.org",
                        "content": "The official Python website",
                        "score": 0.99
                    }
                ]
            }
        }
        
        # Process tool result (this should extract entities)
        extracted_entities = entity_store.process_tool_result(
            tool_name="tavily_search",
            result=mock_tavily_result,
            user_request="Search for Python programming",
            parameters={"query": "Python programming"},
            execution_time_ms=150.0
        )
        
        assert len(extracted_entities) == 1, "Should extract 1 search result entity"
        assert extracted_entities[0].entity_type == EntityType.SEARCH_RESULT, "Wrong entity type"
        
        # Save to disk
        success = entity_store.save_to_disk()
        assert success, "Failed to save entity store"
        
        # Load from disk and verify
        loaded_store = ToolEntityStore.load_from_disk(session_id, temp_dir)
        assert loaded_store is not None, "Failed to load entity store"
        
        # Verify search result entity persisted
        search_entities = loaded_store.get_recent_entities(EntityType.SEARCH_RESULT, limit=10)
        assert len(search_entities) == 1, "Search result entity not persisted"

        search_entity = search_entities[0]
        assert search_entity.data["title"] == "Python.org", "Search result data corrupted"
        assert search_entity.data["query"] == "Python programming", "Search query not preserved"
        
        print("✅ Integrated Persistence: PASSED")
        
    finally:
        # Clean up
        shutil.rmtree(temp_dir, ignore_errors=True)


async def main():
    """Run all persistence tests."""
    print("🚀 Starting Personal Assistant Persistence Tests\n")
    
    try:
        # Test individual components
        await test_entity_store_persistence()
        test_tavily_search_extractor()
        await test_session_context_persistence()
        await test_integrated_persistence()
        
        print("\n🎉 All persistence tests PASSED!")
        return True
        
    except Exception as e:
        print(f"\n💥 Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
