"""
Personal Assistant API schemas for request/response validation.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class PersonalAssistantChatRequest(BaseModel):
    """Request schema for standard Personal Assistant chat."""
    
    message: str = Field(..., description="User message to process")
    session_id: Optional[str] = Field(None, description="Optional session ID for conversation continuity")
    context: Optional[Dict[str, Any]] = Field(None, description="Optional context data")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Help me schedule a meeting for tomorrow",
                "session_id": "session_123",
                "context": {
                    "timezone": "UTC",
                    "preferred_time": "afternoon"
                }
            }
        }


class AutonomousChatRequest(BaseModel):
    """Request schema for autonomous Personal Assistant chat."""
    
    message: str = Field(..., description="User message to process autonomously")
    session_id: Optional[str] = Field(None, description="Optional session ID for conversation continuity")
    context: Optional[Dict[str, Any]] = Field(None, description="Optional context data")
    max_steps: Optional[int] = Field(10, description="Maximum number of autonomous steps to execute")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Research the challenges faced by TotalEnergies station managers and create a comprehensive report",
                "session_id": "session_123",
                "context": {
                    "research_depth": "comprehensive",
                    "output_format": "report"
                },
                "max_steps": 15
            }
        }


class ToolUsage(BaseModel):
    """Schema for tool usage information."""
    
    tool: str = Field(..., description="Name of the tool used")
    parameters: Dict[str, Any] = Field(..., description="Parameters passed to the tool")
    result: Any = Field(..., description="Result returned by the tool")
    success: bool = Field(..., description="Whether the tool execution was successful")
    timestamp: str = Field(..., description="ISO timestamp of tool execution")
    execution_time_ms: Optional[float] = Field(None, description="Tool execution time in milliseconds")


class PersonalAssistantChatResponse(BaseModel):
    """Response schema for standard Personal Assistant chat."""
    
    response: str = Field(..., description="Assistant's response to the user")
    session_id: str = Field(..., description="Session ID for conversation continuity")
    tools_used: List[ToolUsage] = Field(default_factory=list, description="List of tools used in processing")
    context: Dict[str, Any] = Field(default_factory=dict, description="Updated context data")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Response metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "response": "I've scheduled your meeting for tomorrow at 2 PM.",
                "session_id": "session_123",
                "tools_used": [
                    {
                        "tool": "google_calendar",
                        "parameters": {"action": "create_event", "title": "Meeting"},
                        "result": {"event_id": "evt_123"},
                        "success": True,
                        "timestamp": "2024-01-01T12:00:00Z"
                    }
                ],
                "context": {"last_action": "schedule_meeting"},
                "metadata": {
                    "message_count": 5,
                    "tools_count": 1,
                    "response_time_ms": 1500
                }
            }
        }


class AutonomousExecutionMetadata(BaseModel):
    """Metadata for autonomous execution."""
    
    message_count: int = Field(..., description="Total messages in session")
    tools_count: int = Field(..., description="Total tools used")
    steps_completed: int = Field(..., description="Number of autonomous steps completed")
    task_id: Optional[str] = Field(None, description="Unique task identifier")
    workspace_file: Optional[str] = Field(None, description="Workspace file name if created")
    session_duration_minutes: float = Field(..., description="Session duration in minutes")
    goal_achieved: bool = Field(False, description="Whether the original goal was achieved")


class AutonomousChatResponse(BaseModel):
    """Response schema for autonomous Personal Assistant chat."""
    
    response: str = Field(..., description="Comprehensive assistant response")
    session_id: str = Field(..., description="Session ID for conversation continuity")
    tools_used: List[ToolUsage] = Field(default_factory=list, description="List of all tools used during autonomous execution")
    context: Dict[str, Any] = Field(default_factory=dict, description="Updated context data")
    autonomous_execution: bool = Field(True, description="Indicates this was autonomous execution")
    metadata: AutonomousExecutionMetadata = Field(..., description="Autonomous execution metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "response": "I have completed comprehensive research on TotalEnergies station manager challenges and created a detailed report. The research covered operational challenges, regulatory compliance issues, customer service demands, and technology integration problems. All findings have been compiled into a structured report saved in your workspace.",
                "session_id": "session_123",
                "tools_used": [
                    {
                        "tool": "planning",
                        "parameters": {"action": "create", "task": "Research TotalEnergies challenges"},
                        "result": {"plan_created": True},
                        "success": True,
                        "timestamp": "2024-01-01T12:00:00Z"
                    },
                    {
                        "tool": "virtual_fs",
                        "parameters": {"action": "create", "filename": "workspace.md"},
                        "result": {"file_created": True},
                        "success": True,
                        "timestamp": "2024-01-01T12:01:00Z"
                    },
                    {
                        "tool": "tavily_search",
                        "parameters": {"query": "TotalEnergies station manager challenges"},
                        "result": {"results_found": 10},
                        "success": True,
                        "timestamp": "2024-01-01T12:02:00Z"
                    }
                ],
                "context": {"research_completed": True},
                "autonomous_execution": True,
                "metadata": {
                    "message_count": 3,
                    "tools_count": 8,
                    "steps_completed": 5,
                    "task_id": "task_abc123",
                    "workspace_file": "task_workspace_abc123.md",
                    "session_duration_minutes": 3.5,
                    "goal_achieved": True
                }
            }
        }


class ToolInfo(BaseModel):
    """Schema for tool information."""
    
    name: str = Field(..., description="Tool name")
    display_name: str = Field(..., description="Human-readable tool name")
    description: str = Field(..., description="Tool description")
    category: Optional[str] = Field(None, description="Tool category")
    authorized: bool = Field(..., description="Whether user is authorized to use this tool")
    schema: Dict[str, Any] = Field(default_factory=dict, description="Tool parameter schema")


class ConfigResponse(BaseModel):
    """Response schema for configuration endpoints."""
    
    agent_config: Dict[str, Any] = Field(..., description="Agent configuration")
    enabled_tools: List[str] = Field(..., description="List of enabled tool names")
    preferences: Dict[str, Any] = Field(..., description="User preferences")
    limits: Dict[str, Any] = Field(..., description="Usage limits and constraints")


class WorkspaceResponse(BaseModel):
    """Response schema for workspace endpoints."""
    
    task_id: str = Field(..., description="Task identifier")
    filename: str = Field(..., description="Workspace filename")
    content: str = Field(..., description="Workspace file content")
    created_at: datetime = Field(..., description="Workspace creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Workspace metadata")


class HealthResponse(BaseModel):
    """Response schema for health check endpoints."""
    
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="Service version")
    uptime_seconds: float = Field(..., description="Service uptime in seconds")
    tools_available: int = Field(..., description="Number of available tools")
    baml_client_status: str = Field(..., description="BAML client status")
    autonomous_mode_enabled: bool = Field(..., description="Whether autonomous mode is available")
