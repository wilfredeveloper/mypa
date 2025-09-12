# Tool Metadata System Documentation

## Overview

The Tool Metadata System is an advanced enhancement to the Personal Assistant's conversation memory that captures, stores, and utilizes comprehensive metadata about every tool execution. This system enables the agent to maintain rich context about not just what entities were discussed, but how they were obtained, when they were accessed, and what operations were performed on them.

## Key Features

### 1. Comprehensive Tool Execution Tracking
- **Request Context**: Stores the original user request that triggered each tool call
- **Parameter Logging**: Records all parameters passed to tools
- **Output Capture**: Saves complete tool outputs for future reference
- **Timing Information**: Tracks execution time for performance insights
- **Success/Failure Status**: Records whether operations succeeded or failed
- **Error Details**: Captures error messages for failed operations

### 2. Entity-Tool Correlation
- **Creation Context**: Links entities to the tool executions that created them
- **Modification History**: Tracks which tools modified which entities
- **Access Patterns**: Records when and how entities were accessed
- **Relationship Mapping**: Correlates related entities across tool calls

### 3. Context-Aware Responses
- **Historical References**: Agent can reference previous tool executions in responses
- **Execution-Based Confirmations**: Confirmations include context about how entities were originally obtained
- **Tool History Integration**: Recent tool executions are included in agent prompts
- **Smart Parameter Resolution**: Uses tool history to resolve ambiguous references

## Architecture

### Core Components

#### ToolExecutionContext Class
```python
@dataclass
class ToolExecutionContext:
    execution_id: str              # Unique identifier
    tool_name: str                 # Name of executed tool
    user_request: str              # Original user message
    parameters: Dict[str, Any]     # Tool parameters
    raw_output: Dict[str, Any]     # Complete tool output
    success: bool                  # Success/failure status
    execution_time_ms: float       # Execution duration
    timestamp: datetime            # When executed
    extracted_entity_ids: List[str] # Related entities
    user_intent: Optional[str]     # Inferred intent
    error_message: Optional[str]   # Error details
```

#### Enhanced ConversationMemory
- **Tool Execution Storage**: Maintains indexed storage of all tool executions
- **Chronological Ordering**: Keeps executions sorted by timestamp
- **Tool-Based Indexing**: Enables fast queries by tool name
- **Entity Correlation**: Links executions to extracted entities
- **Automatic Cleanup**: Manages memory usage with intelligent expiration

#### Context-Aware Resolution
- **Historical Context**: Uses tool execution history for entity resolution
- **Enhanced Confirmations**: Generates confirmations that reference tool history
- **Query Interface**: Provides methods to search and filter tool executions

## Usage Examples

### Basic Tool Metadata Capture

```python
# After a tool execution, process with metadata
execution_context = memory.process_tool_execution(
    tool_name="google_calendar",
    user_request="show me my meetings tomorrow",
    parameters={"action": "list", "date": "2025-09-13"},
    result=calendar_result,
    execution_time_ms=250.5,
    success=True,
    user_intent="list_calendar_events"
)
```

### Context-Aware Entity Resolution

```python
# When user says "delete the event", resolver uses tool history
user_message = "delete the event"
delete_params = {"action": "delete"}

# Enhance parameters with context from tool history
enhanced_params = resolver.enhance_tool_parameters(
    "google_calendar", delete_params, user_message
)

# Result includes event_id resolved from recent tool executions
# enhanced_params = {
#     "action": "delete",
#     "event_id": "meeting-789",
#     "_context_info": {
#         "resolved_entity": {
#             "type": "calendar_event",
#             "name": "Team standup",
#             "id": "meeting-789"
#         }
#     }
# }
```

### Historical Context in Responses

```python
# Generate confirmation that references tool history
confirmation = resolver.generate_confirmation_message(
    "google_calendar", enhanced_params, "delete"
)

# Result: "I'll delete the 'Team standup' event that we found 
#          when I list_calendar_events earlier."
```

### Querying Tool History

```python
# Get recent tool executions
recent_executions = memory.get_recent_tool_executions(
    limit=5, tool_name="google_calendar"
)

# Find executions related to specific entity
related_executions = memory.find_tool_executions_by_criteria(
    entity_id="meeting-789"
)

# Get execution that created an entity
creation_context = memory.get_entity_creation_context("meeting-789")
```

## Integration Points

### 1. Agent Workflow Integration
- **PAToolCallNode**: Automatically captures metadata after each tool execution
- **PAThinkNode**: Includes tool history in system prompts
- **Session Management**: Loads and saves tool metadata with conversation memory

### 2. Tool Enhancement
- **Context Setting**: Tools receive context resolvers for enhanced operations
- **Parameter Enhancement**: Tools get pre-resolved parameters based on history
- **Confirmation Generation**: Tools can generate context-aware confirmations

### 3. Memory Persistence
- **Disk Storage**: Tool metadata survives agent restarts
- **Session Recovery**: Tool history is restored when sessions resume
- **Cleanup Management**: Automatic cleanup of old executions

## Benefits

### 1. Enhanced User Experience
- **Seamless Interactions**: No need to repeat information already provided
- **Context Continuity**: Agent remembers how information was obtained
- **Intelligent References**: Understands ambiguous references like "the event"
- **Historical Awareness**: Can reference previous operations in responses

### 2. Improved Agent Capabilities
- **Smarter Responses**: Responses include relevant historical context
- **Better Error Handling**: Can reference previous successful operations
- **Performance Insights**: Execution timing helps optimize operations
- **Debugging Support**: Complete execution history aids troubleshooting

### 3. Extensible Architecture
- **Tool Agnostic**: Works with any tool that follows the interface
- **Scalable Storage**: Efficient indexing and cleanup mechanisms
- **Query Flexibility**: Rich query interface for various use cases
- **Integration Ready**: Easy to integrate with new tools and features

## Configuration

### Memory Limits
```python
# Configure memory limits
memory = ConversationMemory(
    session_id="user-session",
    max_entities=50,           # Maximum entities to store
    default_expiry_minutes=60  # Default entity expiration
)

# Tool executions are limited to max_entities * 2
# Oldest executions are automatically cleaned up
```

### Persistence Settings
```python
# Configure persistence directory
memory.persistence_dir = Path("/path/to/memory/storage")

# Save and load operations
memory.save_to_disk()
loaded_memory = ConversationMemory.load_from_disk(session_id)
```

## Best Practices

### 1. Tool Implementation
- Always call `process_tool_execution` after tool operations
- Provide meaningful `user_intent` values for better context
- Include comprehensive error messages for failed operations
- Use consistent parameter naming across similar tools

### 2. Context Resolution
- Check for existing context before asking for clarification
- Use tool history to enhance confirmation messages
- Provide fallback behavior when context resolution fails
- Log context resolution decisions for debugging

### 3. Memory Management
- Configure appropriate memory limits for your use case
- Implement regular cleanup of expired entities and executions
- Monitor memory usage in production environments
- Use persistence for important long-term contexts

## Future Enhancements

- **Cross-Session Context**: Share context across user sessions
- **Tool Performance Analytics**: Detailed performance monitoring
- **Context Prediction**: Predict likely next actions based on history
- **Advanced Query Language**: SQL-like queries for tool history
- **Context Visualization**: Visual representation of tool execution flows
