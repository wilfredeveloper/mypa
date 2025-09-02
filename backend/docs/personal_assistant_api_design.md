# Personal Assistant Agent - API Design Document

## Overview

This document defines the RESTful API structure for the Personal Assistant agent, including endpoint specifications, authentication flows, streaming response formats, and mobile app integration patterns.

## Base Configuration

- **Base URL**: `/api/v1/personal-assistant`
- **Authentication**: JWT Bearer tokens (existing system)
- **Content Type**: `application/json`
- **Streaming**: Server-Sent Events (SSE) for real-time responses

## Core API Endpoints

### 1. Chat Endpoints

#### POST /chat
**Purpose**: Non-streaming chat interaction with Personal Assistant

**Request Schema**:
```json
{
  "message": "string (required)",
  "session_id": "string (optional)",
  "context": {
    "user_preferences": "object (optional)",
    "previous_context": "object (optional)"
  },
  "tools_enabled": ["string"] // Array of tool names
}
```

**Response Schema**:
```json
{
  "response": "string",
  "session_id": "string",
  "tools_used": [
    {
      "tool_name": "string",
      "action": "string",
      "parameters": "object",
      "result": "object",
      "execution_time_ms": "number"
    }
  ],
  "context": "object",
  "metadata": {
    "response_time_ms": "number",
    "token_usage": "object",
    "confidence_score": "number"
  }
}
```

**Error Responses**:
- `400`: Invalid request format
- `401`: Authentication required
- `403`: Insufficient permissions
- `429`: Rate limit exceeded
- `500`: Internal server error

#### POST /chat/stream
**Purpose**: Streaming chat with real-time responses via SSE

**Request Schema**: Same as `/chat`

**Response Format**: Server-Sent Events stream
```
event: message
data: {"type": "thinking", "content": "Analyzing your request..."}

event: message
data: {"type": "tool_call", "tool": "google_calendar", "action": "list_events"}

event: message
data: {"type": "tool_result", "tool": "google_calendar", "result": {...}}

event: message
data: {"type": "response", "content": "I found 3 events for today..."}

event: complete
data: {"session_id": "...", "tools_used": [...], "metadata": {...}}
```

**Stream Event Types**:
- `thinking`: Agent reasoning process
- `tool_call`: Tool execution started
- `tool_result`: Tool execution completed
- `response`: Partial or complete response
- `error`: Error occurred
- `complete`: Stream finished

### 2. Tool Management Endpoints

#### GET /tools
**Purpose**: List available tools for the authenticated user

**Response Schema**:
```json
{
  "tools": [
    {
      "name": "string",
      "display_name": "string",
      "description": "string",
      "category": "builtin|external",
      "schema": {
        "parameters": "object",
        "required": ["string"],
        "properties": "object"
      },
      "authorization_status": "authorized|unauthorized|pending",
      "permissions_required": ["string"],
      "rate_limits": {
        "requests_per_minute": "number",
        "requests_per_day": "number"
      }
    }
  ],
  "total_count": "number"
}
```

#### POST /tools/{tool_name}/authorize
**Purpose**: Initiate OAuth authorization for external tools

**Path Parameters**:
- `tool_name`: Name of the tool to authorize

**Request Schema**:
```json
{
  "scopes": ["string"], // Optional: specific scopes to request
  "redirect_uri": "string" // Optional: custom redirect URI
}
```

**Response Schema**:
```json
{
  "authorization_url": "string",
  "state": "string",
  "expires_at": "string (ISO 8601)",
  "scopes_requested": ["string"]
}
```

#### DELETE /tools/{tool_name}/authorize
**Purpose**: Revoke authorization for a tool

**Response Schema**:
```json
{
  "success": "boolean",
  "message": "string"
}
```

### 3. Configuration Endpoints

#### GET /config
**Purpose**: Get user's Personal Assistant configuration

**Response Schema**:
```json
{
  "agent_config": {
    "name": "string",
    "system_prompt": "string",
    "personality": "professional|casual|friendly",
    "response_style": "concise|detailed|conversational"
  },
  "enabled_tools": ["string"],
  "preferences": {
    "default_calendar": "string",
    "timezone": "string",
    "language": "string",
    "notification_settings": "object"
  },
  "limits": {
    "max_tools_per_request": "number",
    "max_session_duration_minutes": "number"
  }
}
```

#### PUT /config
**Purpose**: Update Personal Assistant configuration

**Request Schema**:
```json
{
  "agent_config": {
    "name": "string (optional)",
    "system_prompt": "string (optional)",
    "personality": "string (optional)",
    "response_style": "string (optional)"
  },
  "enabled_tools": ["string"] // Optional
  "preferences": "object (optional)"
}
```

**Response Schema**: Same as GET /config

### 4. Session Management

#### GET /sessions
**Purpose**: List user's chat sessions

**Query Parameters**:
- `limit`: Number of sessions to return (default: 20)
- `offset`: Pagination offset (default: 0)
- `status`: Filter by status (active|completed|expired)

**Response Schema**:
```json
{
  "sessions": [
    {
      "session_id": "string",
      "created_at": "string (ISO 8601)",
      "updated_at": "string (ISO 8601)",
      "status": "active|completed|expired",
      "message_count": "number",
      "tools_used": ["string"],
      "summary": "string"
    }
  ],
  "total_count": "number",
  "has_more": "boolean"
}
```

#### GET /sessions/{session_id}
**Purpose**: Get detailed session information

**Response Schema**:
```json
{
  "session_id": "string",
  "created_at": "string (ISO 8601)",
  "updated_at": "string (ISO 8601)",
  "status": "string",
  "messages": [
    {
      "id": "string",
      "timestamp": "string (ISO 8601)",
      "role": "user|assistant",
      "content": "string",
      "tools_used": ["object"],
      "metadata": "object"
    }
  ],
  "context": "object",
  "summary": "string"
}
```

#### DELETE /sessions/{session_id}
**Purpose**: Delete a chat session

**Response Schema**:
```json
{
  "success": "boolean",
  "message": "string"
}
```

## OAuth2 Integration Endpoints

### 1. Google OAuth Flow

#### GET /oauth/google/authorize
**Purpose**: Initiate Google OAuth2 authorization flow

**Query Parameters**:
- `service`: Required. Service to authorize (`calendar`, `gmail`, or `both`)
- `scopes`: Optional. Comma-separated list of specific scopes
- `redirect_uri`: Optional. Custom redirect URI for mobile apps

**Response**: HTTP 302 Redirect to Google OAuth consent screen

#### GET /oauth/google/callback
**Purpose**: Handle OAuth2 callback from Google

**Query Parameters**:
- `code`: Authorization code from Google
- `state`: State parameter for CSRF protection
- `error`: Error code if authorization failed

**Success Response**:
```json
{
  "success": true,
  "services_authorized": ["calendar", "gmail"],
  "scopes_granted": ["string"],
  "expires_at": "string (ISO 8601)"
}
```

**Error Response**:
```json
{
  "success": false,
  "error": "string",
  "error_description": "string"
}
```

#### GET /oauth/google/status
**Purpose**: Check OAuth authorization status for Google services

**Response Schema**:
```json
{
  "calendar": {
    "authorized": "boolean",
    "scopes": ["string"],
    "expires_at": "string (ISO 8601)",
    "last_refresh": "string (ISO 8601)"
  },
  "gmail": {
    "authorized": "boolean",
    "scopes": ["string"],
    "expires_at": "string (ISO 8601)",
    "last_refresh": "string (ISO 8601)"
  }
}
```

#### POST /oauth/google/refresh
**Purpose**: Manually refresh OAuth tokens

**Request Schema**:
```json
{
  "service": "calendar|gmail|both"
}
```

**Response Schema**:
```json
{
  "success": "boolean",
  "services_refreshed": ["string"],
  "expires_at": "string (ISO 8601)"
}
```

#### DELETE /oauth/google/revoke
**Purpose**: Revoke Google OAuth authorization

**Request Schema**:
```json
{
  "service": "calendar|gmail|both"
}
```

**Response Schema**:
```json
{
  "success": "boolean",
  "services_revoked": ["string"],
  "message": "string"
}
```

## Mobile App Integration Patterns

### 1. Authentication Flow for Mobile

**Step 1**: Mobile app authenticates user with existing JWT system
```http
POST /api/v1/auth/login
Authorization: Bearer <jwt_token>
```

**Step 2**: Mobile app checks PA configuration
```http
GET /api/v1/personal-assistant/config
Authorization: Bearer <jwt_token>
```

**Step 3**: Mobile app initiates chat session
```http
POST /api/v1/personal-assistant/chat
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "message": "Schedule a meeting for tomorrow",
  "context": {
    "device_type": "mobile",
    "app_version": "1.0.0"
  }
}
```

### 2. OAuth Flow for Mobile Apps

**Custom URI Scheme**: `mypa://oauth/callback`

**Step 1**: Request authorization URL
```http
POST /api/v1/personal-assistant/tools/google_calendar/authorize
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "redirect_uri": "mypa://oauth/callback"
}
```

**Step 2**: Open authorization URL in system browser
```json
{
  "authorization_url": "https://accounts.google.com/oauth/authorize?...",
  "state": "mobile_app_state_token"
}
```

**Step 3**: Handle callback in mobile app
```
mypa://oauth/callback?code=auth_code&state=mobile_app_state_token
```

**Step 4**: Exchange code for tokens (handled automatically by backend)

### 3. Streaming Responses for Mobile

**EventSource Implementation**:
```javascript
const eventSource = new EventSource('/api/v1/personal-assistant/chat/stream', {
  headers: {
    'Authorization': 'Bearer ' + jwt_token
  }
});

eventSource.onmessage = function(event) {
  const data = JSON.parse(event.data);
  handleStreamingResponse(data);
};
```

**Native Mobile Streaming**:
- iOS: Use `URLSessionDataTask` with streaming delegate
- Android: Use `OkHttp` with `EventSource` library
- React Native: Use `react-native-sse` package

### 4. Offline Capability Considerations

**Cached Responses**:
```json
{
  "response": "string",
  "cached_at": "string (ISO 8601)",
  "expires_at": "string (ISO 8601)",
  "offline_available": "boolean"
}
```

**Offline Queue**:
- Queue requests when offline
- Sync when connection restored
- Provide offline status indicators

## Error Handling

### Standard Error Response Format

```json
{
  "error": {
    "code": "string",
    "message": "string",
    "details": "object (optional)",
    "timestamp": "string (ISO 8601)",
    "request_id": "string"
  }
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `INVALID_REQUEST` | 400 | Malformed request |
| `UNAUTHORIZED` | 401 | Authentication required |
| `FORBIDDEN` | 403 | Insufficient permissions |
| `NOT_FOUND` | 404 | Resource not found |
| `RATE_LIMITED` | 429 | Rate limit exceeded |
| `TOOL_UNAVAILABLE` | 503 | External tool service unavailable |
| `OAUTH_EXPIRED` | 401 | OAuth token expired |
| `OAUTH_REVOKED` | 403 | OAuth authorization revoked |
| `INTERNAL_ERROR` | 500 | Internal server error |

### Streaming Error Format

```
event: error
data: {
  "error": {
    "code": "TOOL_UNAVAILABLE",
    "message": "Google Calendar service is temporarily unavailable",
    "recoverable": true,
    "retry_after": 30
  }
}
```

## Rate Limiting

### Rate Limit Headers

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
X-RateLimit-Retry-After: 60
```

### Rate Limits by Endpoint

| Endpoint | Limit | Window |
|----------|-------|--------|
| `/chat` | 60 requests | per minute |
| `/chat/stream` | 10 concurrent | per user |
| `/tools/*` | 100 requests | per hour |
| `/oauth/*` | 20 requests | per hour |

## Security Considerations

### Request Validation
- All inputs validated against schemas
- SQL injection prevention
- XSS protection for user content
- CSRF protection for state parameters

### Token Security
- OAuth tokens encrypted at rest
- Automatic token rotation
- Secure token transmission (HTTPS only)
- Token scope validation

### API Security
- CORS configuration for web clients
- Request signing for sensitive operations
- Audit logging for all tool executions
- IP-based rate limiting

## Performance Specifications

### Response Time Targets
- Non-streaming chat: < 2 seconds (95th percentile)
- Streaming first token: < 500ms (95th percentile)
- Tool authorization: < 1 second (95th percentile)
- Configuration updates: < 200ms (95th percentile)

### Throughput Targets
- 1000 concurrent users
- 10,000 requests per minute
- 100 concurrent streaming connections per server
- 99.9% uptime SLA

### Caching Strategy
- Configuration data: 5 minutes TTL
- Tool schemas: 1 hour TTL
- OAuth status: 30 seconds TTL
- Session data: In-memory with Redis backup