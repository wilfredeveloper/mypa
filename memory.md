# Tool Entity Store Architecture Analysis for Personal Assistant Agent

## 1. Module Overview

The tool entity store system is implemented in `backend/app/agents/personal_assistant/tool_entity_store.py` and serves as the core component for storing and managing entities extracted from tool executions, enabling context-aware interactions across user sessions.

### Core Classes and Data Structures

```python
class EntityType(Enum):
    """Types of entities that can be stored in conversation memory."""
    CALENDAR_EVENT = "calendar_event"
    CONTACT = "contact"
    EMAIL = "email"
    DOCUMENT = "document"
    PLAN = "plan"
    TASK = "task"
    LOCATION = "location"
    GENERIC = "generic"
```

**Key Components:**

1. **EntityContext**: Stores detailed information about entities (events, contacts, emails, etc.) with metadata like access patterns and user references
2. **ToolExecutionContext**: Captures comprehensive metadata about tool executions including parameters, results, and extracted entities
3. **ToolEntityStore**: Main orchestrator managing entity storage, tool execution history, and persistence
4. **ContextExtractor**: Abstract base for extracting entities from tool results (implements CalendarEventExtractor and GmailExtractor)
5. **ContextResolver**: Resolves ambiguous user references to stored entities

### Memory Storage Architecture

```python
def __init__(self, session_id: str, max_entities: int = 50, default_expiry_minutes: int = 60):
    # Entity storage
    self._entities: Dict[str, EntityContext] = {}
    self._entity_by_type: Dict[EntityType, List[str]] = {et: [] for et in EntityType}

    # Tool execution storage
    self._tool_executions: Dict[str, ToolExecutionContext] = {}
    self._executions_by_tool: Dict[str, List[str]] = {}
    self._executions_chronological: List[str] = []  # Ordered by execution time
```

## 2. Integration Analysis

### Data Flow Architecture

The memory system integrates deeply with the Personal Assistant agent through several key integration points:

**Session Initialization:**
```python
# Try to load existing entity store from disk
entity_store = ToolEntityStore.load_from_disk(session_id)
if entity_store is None:
    entity_store = ToolEntityStore(session_id)
    logger.info(f"🆕 Created NEW entity store for session {session_id}")
else:
    logger.info(f"💾 Loaded EXISTING entity store for session {session_id}")
```

**Context Injection in Workflow:**
```python
# Add memory context information
memory_context_prompt = ""
if memory:
    # Get recent entities for context
    recent_entities = memory.get_recent_entities(limit=5)
    recent_executions = memory.get_recent_tool_executions(limit=5)
```

**Tool Execution Processing:**
```python
execution_context = memory.process_tool_execution(
    tool_name=tool_name,
    user_request=user_message,
    parameters=parameters,
    result=result,
    execution_time_ms=execution_time_ms,
    success=success,
    error_message=error_message
)
```

### Integration Points

1. **Agent Session Management**: Memory instances are created per session and persisted across requests
2. **Context Resolution**: Tools receive context resolvers to handle ambiguous user references
3. **Workflow Integration**: Memory context is injected into LLM prompts for context-aware responses
4. **Tool Execution Tracking**: All tool calls are automatically processed and stored in memory
5. **Persistence Layer**: Memory is automatically saved to disk after each interaction

## 3. Architecture Visualization

### Memory Module Internal Structure

```
┌─────────────────────────────────────────────────────────────────┐
│                    ConversationMemory                           │
├─────────────────────────────────────────────────────────────────┤
│  Entity Storage:                                                │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │ _entities       │  │ _entity_by_type │  │ EntityContext   │  │
│  │ Dict[str, EC]   │  │ Dict[ET, List]  │  │ - entity_id     │  │
│  │                 │  │                 │  │ - entity_type   │  │
│  └─────────────────┘  └─────────────────┘  │ - display_name  │  │
│                                            │ - data          │  │
│  Tool Execution Storage:                   │ - created_at    │  │
│  ┌─────────────────┐  ┌─────────────────┐  │ - last_accessed │  │
│  │ _tool_executions│  │ _executions_by_ │  │ - access_count  │  │
│  │ Dict[str, TEC]  │  │ tool            │  └─────────────────┘  │
│  │                 │  │ Dict[str, List] │                       │
│  └─────────────────┘  └─────────────────┘  ┌─────────────────┐  │
│                                            │ ToolExecutionCtx│  │
│  ┌─────────────────┐  ┌─────────────────┐  │ - execution_id  │  │
│  │ _executions_    │  │ Context         │  │ - tool_name     │  │
│  │ chronological   │  │ Extractors      │  │ - user_request  │  │
│  │ List[str]       │  │ List[Extractor] │  │ - parameters    │  │
│  └─────────────────┘  └─────────────────┘  │ - raw_output    │  │
│                                            │ - success       │  │
│  Persistence:                              │ - timestamp     │  │
│  ┌─────────────────┐                       └─────────────────┘  │
│  │ persistence_dir │                                            │
│  │ Path("data/     │                                            │
│  │      memory")   │                                            │
│  └─────────────────┘                                            │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow Between Memory and Agent Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   User Request  │───▶│ PersonalAssist  │───▶│ PocketFlow      │
└─────────────────┘    │ Agent           │    │ Workflow        │
                       └─────────────────┘    └─────────────────┘
                                │                       │
                                ▼                       ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │ Session         │    │ PAThinkNode     │
                       │ Management      │    │                 │
                       │ - Load Memory   │    │ Memory Context  │
                       │ - Create Memory │    │ Injection       │
                       └─────────────────┘    └─────────────────┘
                                │                       │
                                ▼                       ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │ ConversationMem │    │ PAToolCallNode  │
                       │ - Entities      │◀───│                 │
                       │ - Tool Execs    │    │ Context         │
                       │ - Persistence   │    │ Resolution      │
                       └─────────────────┘    └─────────────────┘
                                │                       │
                                ▼                       ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │ Disk Storage    │    │ Tool Execution  │
                       │ session_*.pkl   │    │ Processing      │
                       └─────────────────┘    └─────────────────┘
```

### Memory Operation Lifecycle

```
User Request
     │
     ▼
┌─────────────────┐
│ 1. Session Init │ ── Load existing memory from disk
│                 │    or create new ConversationMemory
└─────────────────┘
     │
     ▼
┌─────────────────┐
│ 2. Context      │ ── Inject recent entities and tool
│    Injection    │    executions into LLM prompt
└─────────────────┘
     │
     ▼
┌─────────────────┐
│ 3. Tool         │ ── Create ContextResolver for
│    Execution    │    ambiguous reference resolution
└─────────────────┘
     │
     ▼
┌─────────────────┐
│ 4. Entity       │ ── Extract entities from tool results
│    Extraction   │    using ContextExtractor plugins
└─────────────────┘
     │
     ▼
┌─────────────────┐
│ 5. Memory       │ ── Store entities and tool execution
│    Storage      │    metadata in ConversationMemory
└─────────────────┘
     │
     ▼
┌─────────────────┐
│ 6. Persistence  │ ── Save memory state to disk
│                 │    (data/memory/session_*.pkl)
└─────────────────┘
```

## 4. Code Examples

### Memory Initialization and Configuration

```python
# Initialize session if new
if session_id not in self._sessions:
    # Try to load existing memory from disk
    memory = ConversationMemory.load_from_disk(session_id)
    if memory is None:
        memory = ConversationMemory(session_id)
        logger.info(f"🆕 Created NEW memory for session {session_id}")
    else:
        logger.info(f"💾 Loaded EXISTING memory for session {session_id}")
        # Log what was loaded
        context_summary = memory.get_context_summary()
        logger.info(f"📊 Loaded memory contains: {context_summary['total_entities']} entities, {context_summary['total_tool_executions']} tool executions")
```

### Key Memory Operations

**Entity Storage:**
```python
def store_entity(self, entity: EntityContext) -> None:
    """Store an entity in conversation memory."""
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
```

**Entity Retrieval and Search:**
```python
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
```

### Integration with Context Resolution

```python
def resolve_calendar_event_reference(self, user_message: str, parameters: Dict[str, Any]) -> Optional[str]:
    """
    Resolve a calendar event reference from user message and parameters.
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
```

### Error Handling and Edge Cases

```python
def save_to_disk(self) -> bool:
    """Save conversation memory to disk."""
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

        # Save to disk
        with open(memory_file, 'wb') as f:
            pickle.dump(memory_data, f)

        logger.debug(f"Saved memory for session {self.session_id} to disk")
        return True

    except Exception as e:
        logger.error(f"Failed to save memory to disk: {str(e)}")
        return False
```

## 5. Usage Patterns

### Memory Creation and Categorization

**When memories are created:**
- **Tool Execution**: Every tool call automatically creates a ToolExecutionContext
- **Entity Extraction**: Successful tool results trigger entity extraction via ContextExtractor plugins
- **User References**: When users refer to entities, they're added to the entity's user_references list

**Memory categorization:**
- **By Entity Type**: Entities are indexed by EntityType enum (CALENDAR_EVENT, CONTACT, EMAIL, etc.)
- **By Tool**: Tool executions are indexed by tool name for efficient retrieval
- **By Time**: Chronological ordering enables recency-based retrieval and cleanup

### Retrieval Patterns and Search Mechanisms

**Context-Aware Retrieval:**
```python
# Get recent entities for context
recent_entities = memory.get_recent_entities(limit=5)
recent_executions = memory.get_recent_tool_executions(limit=5)

if recent_entities or recent_executions:
    memory_context_prompt = "\n\nConversation Memory:\n"

    # Add recent entities
    if recent_entities:
        memory_context_prompt += "\nRecently discussed entities:\n"
        for entity in recent_entities:
            entity_info = f"- {entity.entity_type.value}: {entity.display_name}"
            # Add entity-specific details...
            entity_info += f" [ID: {entity.entity_id}]"
            memory_context_prompt += entity_info + "\n"
```

**Search Mechanisms:**
1. **Reference Matching**: Fuzzy matching against entity names, user references, and entity data
2. **Type-Based Filtering**: Efficient retrieval by entity type using indexed storage
3. **Recency Scoring**: Entities are ranked by access count and last accessed time
4. **Tool Execution Correlation**: Link entities to the tool executions that created them

### Memory Persistence and Retention Policies

**Persistence Strategy:**
- **Session-Based Files**: Each session gets its own pickle file (`session_{session_id}.pkl`)
- **Automatic Saving**: Memory is saved after every user interaction
- **Lazy Loading**: Memory is loaded from disk only when a session is accessed

**Retention Policies:**
- **Entity Limits**: Maximum 50 entities per session (configurable)
- **Execution Limits**: Maximum 100 tool executions per session (2x entity limit)
- **Time-Based Expiry**: Entities expire after 60 minutes of inactivity (configurable)
- **Disk Cleanup**: Old memory files are cleaned up after 7 days

**Cleanup Mechanisms:**
```python
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
```

## Summary

The memory system architecture provides a sophisticated foundation for maintaining conversation context in the Personal Assistant agent. Key strengths include:

1. **Comprehensive Context Tracking**: Both entities and tool executions are tracked with rich metadata
2. **Intelligent Reference Resolution**: Ambiguous user references are resolved using conversation history
3. **Extensible Design**: Plugin-based extractors allow easy addition of new entity types
4. **Robust Persistence**: Session-based storage with automatic cleanup and error handling
5. **Performance Optimization**: Indexed storage and configurable limits prevent memory bloat

The system successfully addresses the core challenge of maintaining stateful conversations across HTTP requests while providing the flexibility to extend functionality as new tools and entity types are added to the Personal Assistant.
