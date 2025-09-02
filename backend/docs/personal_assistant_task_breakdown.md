# Personal Assistant Agent - Detailed Task Breakdown

## Task 1: Database Schema & Models

### Acceptance Criteria
- [ ] All database models created with proper relationships
- [ ] Migration scripts generated and tested
- [ ] Models include proper validation and constraints
- [ ] Encrypted storage for OAuth tokens implemented

### Estimated Effort: 2-3 days

### Dependencies: None

### Subtasks

#### 1.1 Create Agent Configuration Model
- File: `backend/app/models/agent.py`
- Implement `AgentConfig` model with user relationship
- Add JSON field validation for config_data
- Include audit fields (created_at, updated_at)

#### 1.2 Create Tool Registry Models
- File: `backend/app/models/tool.py`
- Implement `ToolRegistry` and `UserToolAccess` models
- Add proper foreign key relationships
- Include tool schema validation

#### 1.3 Create OAuth Token Model
- File: `backend/app/models/oauth_token.py`
- Implement encrypted token storage
- Add token expiration handling
- Include scope management

#### 1.4 Create Database Migration
- File: `backend/alembic/versions/xxx_add_personal_assistant.py`
- Generate migration for all new tables
- Add proper indexes for performance
- Include data seeding for default tools

### Testing Requirements
- Unit tests for all model validations
- Integration tests for relationships
- Migration rollback testing

---

## Task 2: Core Agent Infrastructure

### Acceptance Criteria
- [ ] Personal Assistant agent follows existing AsyncNode patterns
- [ ] PocketFlow integration working correctly
- [ ] BAML functions integrated for LLM calls
- [ ] Agent can be instantiated alongside existing agents

### Estimated Effort: 3-4 days

### Dependencies: Task 1 (Database Models)

### Subtasks

#### 2.1 Create Base Agent Structure
- File: `backend/app/agents/personal_assistant/agent.py`
- Implement main PersonalAssistant class
- Follow existing chatbot_core patterns
- Add configuration management

#### 2.2 Implement AsyncNodes
- File: `backend/app/agents/personal_assistant/nodes.py`
- Create ThinkNode, ToolCallNode, ResponseNode
- Follow existing node patterns from chatbot_core
- Add proper error handling

#### 2.3 Create PocketFlow Workflow
- File: `backend/app/agents/personal_assistant/flow.py`
- Define agent workflow using AsyncFlow
- Connect nodes with proper transitions
- Add loop handling for multi-step tasks

#### 2.4 Add BAML Integration
- File: `backend/baml_src/personal_assistant.baml`
- Define BAML functions for PA operations
- Add structured output schemas
- Include streaming support

### Testing Requirements
- Unit tests for each node
- Integration tests for complete workflow
- BAML function testing
- Performance testing for streaming

---

## Task 3: Built-in Agent Capabilities

### Acceptance Criteria
- [ ] System prompt management working
- [ ] Planning tool can decompose complex requests
- [ ] Virtual file system operational
- [ ] Dynamic tool integration architecture complete

### Estimated Effort: 4-5 days

### Dependencies: Task 2 (Core Infrastructure)

### Subtasks

#### 3.1 System Prompt Management
- File: `backend/app/agents/personal_assistant/tools/builtin/system_prompt.py`
- Implement configurable system prompts
- Add context switching capabilities
- Include prompt templates

#### 3.2 Planning Tool
- File: `backend/app/agents/personal_assistant/tools/builtin/planning.py`
- Implement task decomposition
- Add dependency tracking
- Include priority management

#### 3.3 Virtual File System
- File: `backend/app/agents/personal_assistant/tools/builtin/virtual_fs.py`
- Implement in-memory file operations
- Add CRUD operations for temporary files
- Include session-based storage

#### 3.4 Tool Registry System
- File: `backend/app/agents/personal_assistant/tools/registry.py`
- Implement plugin architecture
- Add tool registration/deregistration
- Include schema validation

### Testing Requirements
- Unit tests for each built-in tool
- Integration tests for tool registry
- Performance tests for virtual file system
- Security tests for tool isolation

---

## Task 4: External Tool Integration

### Acceptance Criteria
- [ ] Google Calendar tool fully functional
- [ ] Gmail tool fully functional
- [ ] OAuth2 integration working
- [ ] Tools follow plugin architecture

### Estimated Effort: 5-6 days

### Dependencies: Task 3 (Built-in Capabilities)

### Subtasks

#### 4.1 Google Calendar Tool
- File: `backend/app/agents/personal_assistant/tools/external/google_calendar.py`
- Implement full CRUD operations for events
- Add availability checking functionality
- Include reminder and notification management
- Handle recurring events and exceptions

#### 4.2 Gmail Tool
- File: `backend/app/agents/personal_assistant/tools/external/gmail.py`
- Implement email reading and composition
- Add advanced search capabilities
- Include label and folder management
- Handle attachments and threading

#### 4.3 OAuth Service Implementation
- File: `backend/app/services/oauth_service.py`
- Implement secure token storage and retrieval
- Add automatic token refresh mechanism
- Include permission revocation handling
- Add incremental authorization support

#### 4.4 Tool Base Classes
- File: `backend/app/agents/personal_assistant/tools/base.py`
- Define standardized tool interface
- Add authentication and authorization handling
- Include comprehensive error management
- Add rate limiting and retry logic

### Testing Requirements
- Unit tests for each external tool
- OAuth flow integration tests
- API rate limiting and error handling tests
- Security tests for token management

---

## Task 5: API Endpoints & Streaming

### Acceptance Criteria
- [ ] RESTful API endpoints implemented
- [ ] Server-Sent Events streaming working
- [ ] Mobile app compatibility ensured
- [ ] Proper error handling and status codes

### Estimated Effort: 3-4 days

### Dependencies: Task 4 (External Tools)

### Subtasks

#### 5.1 Core API Endpoints
- File: `backend/app/api/v1/endpoints/personal_assistant.py`
- Implement chat endpoints (streaming and non-streaming)
- Add tool management endpoints
- Include configuration endpoints
- Add session management

#### 5.2 OAuth API Endpoints
- File: `backend/app/api/v1/endpoints/oauth.py`
- Implement Google OAuth authorization flow
- Add callback handling
- Include token management endpoints
- Add permission checking endpoints

#### 5.3 Request/Response Schemas
- File: `backend/app/schemas/personal_assistant.py`
- Define all request and response models
- Add proper validation rules
- Include error response schemas
- Add streaming response formats

#### 5.4 Service Layer Integration
- File: `backend/app/services/personal_assistant.py`
- Implement main service class
- Add session management
- Include tool orchestration
- Add streaming response handling

### Testing Requirements
- API endpoint integration tests
- Streaming functionality tests
- Mobile compatibility tests
- Load testing for concurrent users

---

## Task 6: Security & OAuth Implementation

### Acceptance Criteria
- [ ] Google OAuth2 flow fully implemented
- [ ] Incremental authorization working
- [ ] Secure token storage and encryption
- [ ] Comprehensive security measures in place

### Estimated Effort: 3-4 days

### Dependencies: Task 5 (API Endpoints)

### Subtasks

#### 6.1 OAuth2 Flow Implementation
- File: `backend/app/core/oauth.py`
- Implement Google OAuth2 client setup
- Add authorization URL generation
- Include token exchange handling
- Add scope management

#### 6.2 Token Security
- File: `backend/app/core/security.py` (extend existing)
- Implement token encryption at rest
- Add secure token retrieval
- Include automatic token refresh
- Add token revocation handling

#### 6.3 Security Middleware
- Add rate limiting for tool usage
- Implement audit logging
- Add input validation and sanitization
- Include CORS and security headers

#### 6.4 Permission Management
- Implement incremental authorization
- Add scope-based access control
- Include permission checking middleware
- Add user consent management

### Testing Requirements
- OAuth flow security tests
- Token encryption/decryption tests
- Permission boundary tests
- Security vulnerability assessments

---

## Task 7: Testing & Documentation

### Acceptance Criteria
- [ ] Comprehensive test suite with >90% coverage
- [ ] API documentation complete
- [ ] Developer guides and examples ready
- [ ] Performance benchmarks established

### Estimated Effort: 2-3 days

### Dependencies: Task 6 (Security Implementation)

### Subtasks

#### 7.1 Unit Test Suite
- Tests for all models and services
- Tests for all tool implementations
- Tests for OAuth and security components
- Tests for API endpoints

#### 7.2 Integration Tests
- End-to-end workflow tests
- OAuth flow integration tests
- External API integration tests
- Mobile app compatibility tests

#### 7.3 API Documentation
- OpenAPI/Swagger documentation
- Request/response examples
- Authentication guides
- Error handling documentation

#### 7.4 Developer Documentation
- Setup and installation guides
- Tool development guidelines
- Architecture documentation
- Troubleshooting guides

### Testing Requirements
- Automated test execution
- Performance benchmarking
- Security testing
- Documentation accuracy verification

## Summary

**Total Estimated Effort: 19-25 days**

**Critical Path:**
1. Database Models → Core Infrastructure → Built-in Capabilities → External Tools → API Endpoints → Security → Testing

**Key Milestones:**
- Week 1: Database and core infrastructure complete
- Week 2: Built-in capabilities and external tools functional
- Week 3: API endpoints and security implementation
- Week 4: Testing, documentation, and deployment preparation

**Risk Mitigation:**
- OAuth integration complexity: Allocate extra time for Google API integration
- BAML streaming: Test streaming capabilities early in development
- Tool plugin architecture: Validate extensibility with sample tools
- Mobile compatibility: Test API responses across different mobile frameworks