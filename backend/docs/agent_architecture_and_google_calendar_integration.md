# 🤖 Personal Assistant Agent: State Management & Google Calendar Integration

This document explains how the Personal Assistant agent initializes, manages state, and integrates with Google Calendar using actual code from the codebase.

## 🚀 Agent Initialization Flow

The Personal Assistant agent follows a structured initialization process:

```python
def __init__(self, user: User, db: AsyncSession, config: Optional[AgentConfig] = None):
    """
    Initialize the Personal Assistant agent.

    Args:
        user: The user this agent belongs to
        db: Database session
        config: Optional agent configuration (will create default if None)
    """
    self.user = user
    self.db = db
    self.config = config
    self._baml_client: Optional[RateLimitedBAMLGeminiLLM] = None
    self._tool_registry: Optional[ToolRegistryManager] = None
    self._sessions: Dict[str, Dict[str, Any]] = {}

    # Initialize configuration
    self._pa_config = PersonalAssistantConfig()
```

### Initialization Steps

1. **Configuration Setup**: Load or create agent configuration
2. **BAML Client**: Initialize the AI reasoning client
3. **Tool Registry**: Set up available tools and permissions
4. **Session Storage**: Prepare conversation memory containers

```python
# Initialize tool registry
self._tool_registry = ToolRegistryManager(self.user, self.db)
await self._tool_registry.initialize()

# Log available tools right after registry initialization
available_tools = await self._tool_registry.get_available_tools()
tool_names = ", ".join([t.name for t in available_tools]) if available_tools else "none"
logger.info(
    f"Available tools at initialization for user {self.user.id}: [{tool_names}] (count={len(available_tools)})"
)
```

## 📊 Agent Initialization Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    AGENT INITIALIZATION                         │
└─────────────────────────────────────────────────────────────────┘

HTTP Request → Session Manager → Agent Instance
     │              │                    │
     │              │                    ├─ User Context
     │              │                    ├─ Database Session  
     │              │                    ├─ BAML Client (LLM)
     │              │                    ├─ Tool Registry
     │              │                    └─ Session Storage
     │              │
     │              ├─ Check Cache
     │              │   ├─ Found? → Reuse Agent ♻️
     │              │   └─ Not Found? → Create New 🆕
     │              │
     │              └─ Store in Cache

┌─────────────────────────────────────────────────────────────────┐
│                    AGENT COMPONENTS                             │
└─────────────────────────────────────────────────────────────────┘

PersonalAssistant Agent
├─ self.user: User                    # User context
├─ self.db: AsyncSession             # Database access
├─ self._baml_client: LLM            # AI reasoning
├─ self._tool_registry: Tools        # Available tools
└─ self._sessions: Dict              # Conversation memory
   └─ session_id: {
       ├─ "id": str
       ├─ "messages": List[Message]
       ├─ "memory": ConversationMemory  # 🧠 STATE STORAGE
       ├─ "tools_used": List[Tool]
       └─ "context": Dict
   }
```

## 🔄 Session Management Architecture

The session manager ensures agent instances are reused across requests to maintain conversation context:

```python
async def get_agent(self, user: User, db: AsyncSession) -> PersonalAssistant:
    """
    Get or create a Personal Assistant agent for the user.
    """
    user_id = user.id
    
    # Update last activity
    self._last_activity[user_id] = datetime.utcnow()
    
    # Return existing agent if available
    if user_id in self._agents:
        agent = self._agents[user_id]
        # Update the database session in case it's stale
        agent.db = db
        logger.info(f"♻️  SESSION MANAGER: Reusing EXISTING agent for user {user_id} (cached)")
        return agent
    
    # Create new agent
    logger.info(f"🆕 SESSION MANAGER: Creating NEW agent for user {user_id}")
    agent = PersonalAssistant(user, db)
    await agent.initialize()
```

### Session Initialization

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

    self._sessions[session_id] = {
        "id": session_id,
        "created_at": datetime.utcnow(),
        "messages": [],
        "context": context or {},
        "tools_used": [],
        "memory": memory
    }
```

## 📊 Session & State Management Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    SESSION MANAGEMENT                           │
└─────────────────────────────────────────────────────────────────┘

Request 1: "show my events"
┌─────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Browser   │───▶│ Session Manager  │───▶│ Agent Instance  │
│ session-123 │    │ Cache: {}        │    │ NEW ✨          │
└─────────────┘    └──────────────────┘    └─────────────────┘
                            │                        │
                            ▼                        ▼
                   ┌──────────────────┐    ┌─────────────────┐
                   │ Cache: {         │    │ ConversationMemory
                   │   user_1: agent  │    │ ├─ entities: []
                   │ }                │    │ ├─ tools: []
                   └──────────────────┘    │ └─ session-123
                                          └─────────────────┘

Request 2: "delete the Nabulu event" (SAME SESSION!)
┌─────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Browser   │───▶│ Session Manager  │───▶│ Agent Instance  │
│ session-123 │    │ Cache: {user_1}  │    │ REUSED ♻️       │
└─────────────┘    └──────────────────┘    └─────────────────┘
                            │                        │
                            ▼                        ▼
                   ┌──────────────────┐    ┌─────────────────┐
                   │ HIT! Return      │    │ ConversationMemory
                   │ cached agent     │    │ ├─ entities: [3]
                   │                  │    │ ├─ tools: [1]
                   └──────────────────┘    │ └─ session-123
                                          └─────────────────┘
```

## 🧠 Conversation Memory Structure

The conversation memory system stores entities and tool executions to maintain context:

```python
class ConversationMemory:
    """
    Manages conversation context and entity memory for the Personal Assistant.
    
    This class maintains a working context of entities that have been discussed
    or retrieved during the conversation, enabling stateful interactions.
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
            CalendarEventExtractor()
        ]
```

### Entity Types and Structure

```python
class EntityType(Enum):
    """Types of entities that can be stored in conversation memory."""
    CALENDAR_EVENT = "calendar_event"
    CONTACT = "contact"
    EMAIL = "email"
    DOCUMENT = "document"
    TASK = "task"
    LOCATION = "location"
    GENERIC = "generic"

@dataclass
class EntityContext:
    """
    Represents a stored entity in conversation memory.
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
```

## 📊 Memory Structure Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                  CONVERSATION MEMORY                            │
└─────────────────────────────────────────────────────────────────┘

ConversationMemory (session-123)
├─ session_id: "session-123"
├─ _entities: Dict[str, EntityContext]
│  ├─ "event-1": EntityContext {
│  │    ├─ entity_id: "event-1"
│  │    ├─ entity_type: CALENDAR_EVENT
│  │    ├─ display_name: "Nabulu coming to my place"
│  │    ├─ data: {summary, start, end, location...}
│  │    ├─ source_tool: "google_calendar"
│  │    └─ last_accessed: 2025-09-12T09:01:18Z
│  │  }
│  ├─ "event-2": EntityContext {...}
│  └─ "event-3": EntityContext {...}
│
├─ _entity_by_type: Dict[EntityType, List[str]]
│  └─ CALENDAR_EVENT: ["event-1", "event-2", "event-3"]
│
├─ _tool_executions: Dict[str, ToolExecutionContext]
│  └─ "exec-456": ToolExecutionContext {
│       ├─ tool_name: "google_calendar"
│       ├─ user_request: "show my events today"
│       ├─ parameters: {action: "list", time_range: "..."}
│       ├─ success: True
│       ├─ extracted_entity_ids: ["event-1", "event-2", "event-3"]
│       └─ timestamp: 2025-09-12T09:01:18Z
│     }
│
└─ _extractors: [CalendarEventExtractor()]
```

## 🔧 Google Calendar Integration

The Google Calendar tool provides comprehensive calendar management capabilities:

```python
class GoogleCalendarTool(ExternalTool):
    """
    Google Calendar integration tool for Personal Assistant.

    This tool provides:
    - List calendar events with filtering
    - Create new calendar events
    - Update existing events
    - Delete events
    - Check availability
    - Set reminders and notifications
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.calendar_service = None

        # Default calendar settings
        self.default_calendar_id = "primary"
        self.default_timezone = "UTC"

        # Context resolution
        self._context_resolver = None
        self._user_message = None

    def set_context(self, context_resolver: ContextResolver, user_message: Optional[str] = None):
        """Set context resolver and user message for context-aware operations."""
        self._context_resolver = context_resolver
        self._user_message = user_message
```

### OAuth Authorization

```python
async def is_authorized(self) -> bool:
    """Override to ensure tokens exist before use (refresh or access)."""
    try:
        if not self.user_access or not self.user_access.is_authorized:
            return False
        cfg = (self.user_access.config_data or {}).get("google_calendar_oauth", {})
        # Accept either refresh_token or current access token
        return bool(cfg.get("refresh_token") or cfg.get("token"))
    except Exception:
        return False
```

### Tool Execution with Context Enhancement

```python
async def execute(self, parameters: Dict[str, Any]) -> Any:
    """Execute Google Calendar operations."""

    action = parameters.get("action", "list").lower()

    # Enhance parameters with context resolution if available
    if self._context_resolver and self._user_message:
        try:
            parameters = self._context_resolver.enhance_tool_parameters(
                "google_calendar", parameters, self._user_message
            )
            logger.debug("Enhanced parameters with context resolution")
        except Exception as e:
            logger.warning(f"Context resolution failed: {str(e)}")

    try:
        # Initialize calendar service if needed
        if not self.calendar_service:
            await self._initialize_calendar_service()

        if action == "list":
            time_range = parameters.get("time_range", {})
            calendar_id = parameters.get("calendar_id", self.default_calendar_id)
            return await self._list_events(calendar_id, time_range)

        elif action == "create":
            event_data = parameters.get("event_data")
            calendar_id = parameters.get("calendar_id", self.default_calendar_id)
            # ... create logic

        elif action == "delete":
            event_id = parameters.get("event_id")
            # ... delete logic
```

## 📊 Google Calendar Integration Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                GOOGLE CALENDAR INTEGRATION                      │
└─────────────────────────────────────────────────────────────────┘

User Request: "show my events today"
     │
     ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Personal        │───▶│ Context Resolver │───▶│ Google Calendar │
│ Assistant       │    │ enhance_tool_    │    │ Tool            │
│ Agent           │    │ parameters()     │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
     │                          │                        │
     │                          ▼                        ▼
     │                 ┌──────────────────┐    ┌─────────────────┐
     │                 │ Enhanced Params: │    │ OAuth Service   │
     │                 │ {                │    │ ├─ Access Token │
     │                 │   action: "list" │    │ ├─ Refresh Token│
     │                 │   time_range: {} │    │ └─ Credentials  │
     │                 │ }                │    └─────────────────┘
     │                 └──────────────────┘             │
     │                                                  ▼
     │                                        ┌─────────────────┐
     │                                        │ Google Calendar │
     │                                        │ API             │
     │                                        │ ├─ List Events  │
     │                                        │ ├─ Create Event │
     │                                        │ ├─ Update Event │
     │                                        │ └─ Delete Event │
     │                                        └─────────────────┘
     │                                                  │
     ▼                                                  ▼
┌─────────────────┐                          ┌─────────────────┐
│ Entity Extractor│◀─────────────────────────│ Tool Response   │
│ ├─ Parse Events │                          │ {               │
│ ├─ Create       │                          │   success: true │
│ │  EntityContext│                          │   result: {     │
│ └─ Store in     │                          │     events: []  │
│    Memory       │                          │   }             │
└─────────────────┘                          │ }               │
                                            └─────────────────┘
```

## 🔍 Context Resolution Process

The context resolver enables the agent to understand ambiguous references by leveraging stored conversation memory:

```python
# Context resolution for Google Calendar operations
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
```

### Confirmation Message Generation

```python
def generate_confirmation_message(self, tool_name: str, parameters: Dict[str, Any], action: str) -> Optional[str]:
    """
    Generate a context-aware confirmation message.
    """
    confirmation_context = self.get_confirmation_context(tool_name, parameters)
    if not confirmation_context:
        return None

    entity_name = confirmation_context.get("entity_name")
    entity_type = confirmation_context.get("entity_type")

    if entity_type == "calendar_event" and action == "delete":
        return f"I've deleted the '{entity_name}' event that we found when I searched your calendar earlier."
```

## 📊 Context Resolution Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    CONTEXT RESOLUTION                           │
└─────────────────────────────────────────────────────────────────┘

User: "delete the Nabulu event"
     │
     ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Context         │───▶│ Memory Search    │───▶│ Entity Match    │
│ Resolver        │    │ ├─ Parse "Nabulu"│    │ ├─ "Nabulu      │
│                 │    │ ├─ Search entities│    │ │   coming to   │
│                 │    │ └─ Match patterns │    │ │   my place"   │
└─────────────────┘    └──────────────────┘    │ ├─ ID: event-1  │
     │                                          │ └─ Type: EVENT  │
     ▼                                          └─────────────────┘
┌─────────────────┐                                     │
│ Enhanced Params │◀────────────────────────────────────┘
│ {               │
│   action: "delete"
│   event_id: "event-1"  ← RESOLVED!
│   _context_info: {
│     resolved_entity: {
│       type: "calendar_event"
│       name: "Nabulu coming to my place"
│       id: "event-1"
│     }
│   }
│ }
└─────────────────┘
```

## 🏷️ Entity Extraction from Tool Results

The CalendarEventExtractor automatically extracts calendar events from Google Calendar API responses:

```python
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
```

## 🔄 Complete Integration Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                 COMPLETE INTEGRATION FLOW                       │
└─────────────────────────────────────────────────────────────────┘

REQUEST 1: "show my events today"
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Browser   │───▶│   Session   │───▶│   Agent     │───▶│   Memory    │
│ session-123 │    │  Manager    │    │ Instance    │    │ (empty)     │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                           │                   │                   │
                           ▼                   ▼                   ▼
                   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
                   │ Create NEW  │    │ Initialize  │    │ Load from   │
                   │ Agent       │    │ Tools       │    │ disk (none) │
                   └─────────────┘    └─────────────┘    └─────────────┘
                                              │
                                              ▼
                                      ┌─────────────┐
                                      │ Google Cal  │
                                      │ Tool.execute│
                                      │ (list)      │
                                      └─────────────┘
                                              │
                                              ▼
                                      ┌─────────────┐
                                      │ API Result: │
                                      │ 3 events    │
                                      └─────────────┘
                                              │
                                              ▼
                                      ┌─────────────┐
                                      │ Entity      │
                                      │ Extractor   │
                                      │ ├─ event-1  │
                                      │ ├─ event-2  │
                                      │ └─ event-3  │
                                      └─────────────┘
                                              │
                                              ▼
                                      ┌─────────────┐
                                      │ Memory      │
                                      │ ├─ 3 entities│
                                      │ ├─ 1 tool   │
                                      │ └─ Save disk│
                                      └─────────────┘

REQUEST 2: "delete the Nabulu event" (SAME SESSION!)
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Browser   │───▶│   Session   │───▶│   Agent     │───▶│   Memory    │
│ session-123 │    │  Manager    │    │ Instance    │    │ (3 entities)│
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                           │                   │                   │
                           ▼                   ▼                   ▼
                   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
                   │ REUSE       │    │ Context     │    │ Search for  │
                   │ Cached      │    │ Resolver    │    │ "Nabulu"    │
                   │ Agent ♻️    │    │ enhance()   │    │ → event-1   │
                   └─────────────┘    └─────────────┘    └─────────────┘
                                              │                   │
                                              ▼                   ▼
                                      ┌─────────────┐    ┌─────────────┐
                                      │ Enhanced    │    │ Found Match!│
                                      │ Params:     │    │ "Nabulu     │
                                      │ event_id:   │    │ coming to   │
                                      │ "event-1"   │    │ my place"   │
                                      └─────────────┘    └─────────────┘
                                              │
                                              ▼
                                      ┌─────────────┐
                                      │ Google Cal  │
                                      │ Tool.execute│
                                      │ (delete)    │
                                      └─────────────┘
                                              │
                                              ▼
                                      ┌─────────────┐
                                      │ Success!    │
                                      │ Event       │
                                      │ Deleted ✅  │
                                      └─────────────┘
```

## 🎯 Key Integration Points

### 1. Agent Session Management
```python
# Agent gets or creates session with persistent memory
if session_id not in self._sessions:
    memory = ConversationMemory.load_from_disk(session_id)
    if memory is None:
        memory = ConversationMemory(session_id)
```

### 2. Context-Enhanced Tool Execution
```python
# Context resolution enhances tool parameters
if self._context_resolver and self._user_message:
    parameters = self._context_resolver.enhance_tool_parameters(
        "google_calendar", parameters, self._user_message
    )
```

### 3. Entity Extraction from Results
```python
# Entity extraction from tool results
def can_extract(self, tool_name: str, result: Dict[str, Any]) -> bool:
    if tool_name != "google_calendar" or not result.get("success", False):
        return False
    data = result.get("result", {})
    return "events" in data or "event" in data
```

### 4. Context-Aware Parameter Resolution
```python
# Context-aware parameter resolution
if action == "delete":
    if not enhanced_params.get("event_id"):
        resolved_event_id = self.resolve_calendar_event_reference(user_message, parameters)
        if resolved_event_id:
            enhanced_params["event_id"] = resolved_event_id
```

## 🚀 Benefits of This Architecture

1. **Stateful Conversations**: The agent remembers what it has retrieved and can resolve ambiguous references
2. **Context Persistence**: Memory survives across requests and even agent restarts
3. **Intelligent Parameter Resolution**: Ambiguous user requests are automatically resolved using conversation history
4. **Comprehensive Logging**: Every step is logged for debugging and monitoring
5. **Scalable Design**: Session management allows multiple users with isolated contexts

This architecture enables **stateful conversations** where the agent remembers what it has retrieved and can resolve ambiguous references like "delete the Nabulu event" without asking for clarification! 🚀
```
