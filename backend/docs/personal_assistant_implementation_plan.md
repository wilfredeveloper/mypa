# Personal Assistant Agent Implementation Plan

## Overview

This document outlines the comprehensive implementation plan for a Personal Assistant agent with tool calling capabilities, built following the existing `chatbot_core` architecture and `pocketflow` design patterns.

## Architecture Analysis

### Existing Patterns Identified

1. **AsyncNode Structure**: All agents use `AsyncNode` base class with `prep_async`, `exec_async`, and `post_async` methods
2. **BAML Integration**: Streaming and non-streaming LLM calls via `RateLimitedBAMLGeminiLLM`
3. **Service Layer**: Clean separation with services in `app/services/` directory
4. **API Structure**: RESTful endpoints with FastAPI, JWT authentication, and streaming support
5. **Database Models**: SQLAlchemy async models with proper relationships
6. **Tool Patterns**: Modular tool architecture seen in PocketFlow cookbooks

### Key Integration Points

- **PocketFlow**: `AsyncFlow` orchestration with node connections
- **BAML**: Structured LLM calls with streaming capabilities
- **FastAPI**: RESTful APIs with SSE support for mobile integration
- **SQLAlchemy**: Async database operations with proper models
- **JWT Auth**: Existing authentication system for user management

## File Structure

```
backend/
├── app/
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── personal_assistant/
│   │   │   ├── __init__.py
│   │   │   ├── agent.py              # Main PA agent class
│   │   │   ├── nodes.py              # PA-specific AsyncNodes
│   │   │   ├── flow.py               # PA workflow definition
│   │   │   ├── tools/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py           # Base tool interface
│   │   │   │   ├── registry.py       # Tool registration system
│   │   │   │   ├── builtin/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── system_prompt.py
│   │   │   │   │   ├── planning.py
│   │   │   │   │   └── virtual_fs.py
│   │   │   │   └── external/
│   │   │   │       ├── __init__.py
│   │   │   │       ├── google_calendar.py
│   │   │   │       └── gmail.py
│   │   │   └── config.py             # PA configuration
│   ├── api/v1/endpoints/
│   │   └── personal_assistant.py     # PA API endpoints
│   ├── models/
│   │   ├── agent.py                  # Agent configuration models
│   │   ├── tool.py                   # Tool registration models
│   │   └── oauth_token.py            # OAuth token storage
│   ├── schemas/
│   │   ├── personal_assistant.py     # PA request/response schemas
│   │   ├── tool.py                   # Tool schemas
│   │   └── oauth.py                  # OAuth schemas
│   ├── services/
│   │   ├── personal_assistant.py     # PA service layer
│   │   ├── tool_registry.py          # Tool management service
│   │   └── oauth_service.py          # OAuth token management
│   └── core/
│       └── oauth.py                  # OAuth utilities
├── baml_src/
│   └── personal_assistant.baml       # PA-specific BAML functions
└── alembic/versions/
    └── xxx_add_personal_assistant.py # Database migration
```

## Database Schema Changes

### New Models Required

1. **Agent Configuration**
   ```python
   class AgentConfig(Base):
       id: int (PK)
       user_id: int (FK to users.id)
       agent_type: str  # 'personal_assistant'
       name: str
       system_prompt: str
       config_data: JSON  # Agent-specific configuration
       is_active: bool
       created_at: datetime
       updated_at: datetime
   ```

2. **Tool Registry**
   ```python
   class ToolRegistry(Base):
       id: int (PK)
       name: str (unique)
       tool_type: str  # 'builtin' or 'external'
       schema_data: JSON  # Tool schema definition
       is_enabled: bool
       created_at: datetime
   ```

3. **User Tool Access**
   ```python
   class UserToolAccess(Base):
       id: int (PK)
       user_id: int (FK to users.id)
       tool_id: int (FK to tool_registry.id)
       is_authorized: bool
       config_data: JSON  # User-specific tool config
       created_at: datetime
   ```

4. **OAuth Tokens**
   ```python
   class OAuthToken(Base):
       id: int (PK)
       user_id: int (FK to users.id)
       provider: str  # 'google'
       service: str   # 'calendar', 'gmail'
       access_token: str (encrypted)
       refresh_token: str (encrypted)
       expires_at: datetime
       scope: str
       created_at: datetime
       updated_at: datetime
   ```

## API Endpoint Specifications

### Core Endpoints

1. **POST /api/v1/personal-assistant/chat**
   - Non-streaming chat with PA
   - Request: `{message: str, session_id?: str, context?: dict}`
   - Response: `{response: str, session_id: str, tools_used: list}`

2. **POST /api/v1/personal-assistant/chat/stream**
   - Streaming chat with SSE
   - Same request format
   - Response: SSE stream with partial responses

3. **GET /api/v1/personal-assistant/tools**
   - List available tools for user
   - Response: `{tools: [{name, description, schema, authorized}]}`

4. **POST /api/v1/personal-assistant/tools/{tool_name}/authorize**
   - Initiate OAuth flow for external tools
   - Response: `{auth_url: str, state: str}`

5. **GET /api/v1/personal-assistant/config**
   - Get user's PA configuration
   - Response: `{system_prompt, enabled_tools, preferences}`

6. **PUT /api/v1/personal-assistant/config**
   - Update PA configuration
   - Request: `{system_prompt?, enabled_tools?, preferences?}`

### OAuth Endpoints

1. **GET /api/v1/oauth/google/authorize**
   - Start Google OAuth flow
   - Query params: `service` (calendar|gmail), `scopes`
   - Response: Redirect to Google OAuth

2. **GET /api/v1/oauth/google/callback**
   - Handle OAuth callback
   - Exchange code for tokens
   - Response: Success/error status

## Integration Points

### BAML Functions Required

1. **PersonalAssistantThinking**: Analyze user request and plan actions
2. **PersonalAssistantToolCall**: Execute tool calls with proper parameters
3. **PersonalAssistantResponse**: Generate final response with context
4. **PersonalAssistantPlanning**: Break down complex requests into steps

### Mobile App Integration

- All endpoints support JSON responses
- SSE streaming for real-time updates
- Proper error handling with HTTP status codes
- JWT authentication for secure access
- Offline capability considerations

## Security Implementation

### OAuth2 Flow

1. **Incremental Authorization**: Request permissions only when needed
2. **Scope Separation**: Calendar and Gmail permissions independent
3. **Token Encryption**: Store tokens encrypted at rest
4. **Token Refresh**: Automatic token renewal
5. **Revocation Handling**: Graceful handling of revoked permissions

### Security Best Practices

- HTTPS for all external API calls
- Input validation and sanitization
- Rate limiting on tool usage
- Audit logging for tool executions
- Secure token storage with encryption

## Success Criteria

1. ✅ PA agent instantiates alongside existing agents
2. ✅ Users authenticate with Google services seamlessly
3. ✅ New tools added without core agent code changes
4. ✅ Web and mobile app compatibility
5. ✅ Real-time streaming responses work correctly
6. ✅ Comprehensive error handling and fallbacks
7. ✅ Horizontal scalability with stateless operations
8. ✅ Backward compatibility with existing functionality

## Next Steps

1. Implement database models and migrations
2. Create base agent infrastructure
3. Build tool registry and plugin system
4. Implement OAuth integration
5. Create API endpoints with streaming
6. Add comprehensive testing
7. Create documentation and examples