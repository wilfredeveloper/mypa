"""
Personal Assistant API endpoints with autonomous execution support.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer
import logging

from app.schemas.personal_assistant import (
    PersonalAssistantChatRequest, 
    PersonalAssistantChatResponse,
    AutonomousChatRequest,
    AutonomousChatResponse
)
from app.services.personal_assistant import personal_assistant_service
from app.api.deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer(auto_error=False)


@router.post("/chat", response_model=PersonalAssistantChatResponse)
async def chat_standard(
    request: PersonalAssistantChatRequest,
    background_tasks: BackgroundTasks,
    current_user: Optional[dict] = Depends(get_current_user)
):
    """
    Handle standard Personal Assistant chat requests.
    
    This endpoint processes a chat message using the standard single-tool execution mode.
    
    Args:
        request: The chat request containing message and optional context
        background_tasks: FastAPI background tasks for cleanup
        current_user: Optional authenticated user information
        
    Returns:
        PersonalAssistantChatResponse: Response with tools used and metadata
        
    Raises:
        HTTPException: If there's an error processing the request
    """
    try:
        logger.info(f"Received standard PA chat request from user: {current_user.id if current_user else 'anonymous'}")
        
        # Validate request
        if not request.message.strip():
            raise HTTPException(
                status_code=400,
                detail="Message cannot be empty"
            )
            
        # Process the chat request
        response = await personal_assistant_service.chat_standard(request, current_user)
        
        logger.info(f"Successfully processed standard PA chat request for session: {response.session_id}")
        return response
        
    except Exception as e:
        logger.error(f"Error in standard PA chat endpoint: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process chat request: {str(e)}"
        )


@router.post("/chat/autonomous", response_model=AutonomousChatResponse)
async def chat_autonomous(
    request: AutonomousChatRequest,
    background_tasks: BackgroundTasks,
    current_user: Optional[dict] = Depends(get_current_user)
):
    """
    Handle autonomous Personal Assistant chat requests.
    
    This endpoint processes a chat message using autonomous multi-step execution mode.
    The agent will:
    - Execute multiple tools sequentially as needed
    - Use virtual_fs as persistent workspace
    - Continue execution until the original goal is achieved
    - Maintain state and progress across tool calls
    
    Args:
        request: The autonomous chat request containing message and optional context
        background_tasks: FastAPI background tasks for cleanup
        current_user: Optional authenticated user information
        
    Returns:
        AutonomousChatResponse: Comprehensive response with workspace info and execution metadata
        
    Raises:
        HTTPException: If there's an error processing the request
    """
    try:
        logger.info(f"Received autonomous PA chat request from user: {current_user.id if current_user else 'anonymous'}")
        
        # Validate request
        if not request.message.strip():
            raise HTTPException(
                status_code=400,
                detail="Message cannot be empty"
            )
            
        # Process the autonomous chat request
        response = await personal_assistant_service.chat_autonomous(request, current_user)
        
        logger.info(f"Successfully processed autonomous PA chat request for session: {response.session_id}")
        logger.info(f"Autonomous execution completed {response.metadata.steps_completed} steps")
        
        return response
        
    except Exception as e:
        logger.error(f"Error in autonomous PA chat endpoint: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process autonomous chat request: {str(e)}"
        )


@router.get("/tools")
async def list_available_tools(
    current_user: Optional[dict] = Depends(get_current_user)
):
    """
    List available tools for the Personal Assistant.
    
    Returns:
        List of available tools with their descriptions and authorization status
    """
    try:
        tools = await personal_assistant_service.list_tools(current_user)
        return {"tools": tools}
        
    except Exception as e:
        logger.error(f"Error listing PA tools: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list tools: {str(e)}"
        )


@router.get("/config")
async def get_config(
    current_user: Optional[dict] = Depends(get_current_user)
):
    """
    Get Personal Assistant configuration for the current user.
    
    Returns:
        User's PA configuration including system prompt, enabled tools, and preferences
    """
    try:
        config = await personal_assistant_service.get_config(current_user)
        return config
        
    except Exception as e:
        logger.error(f"Error getting PA config: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get configuration: {str(e)}"
        )


@router.put("/config")
async def update_config(
    config_update: dict,
    current_user: Optional[dict] = Depends(get_current_user)
):
    """
    Update Personal Assistant configuration for the current user.
    
    Args:
        config_update: Configuration updates to apply
        
    Returns:
        Updated configuration
    """
    try:
        updated_config = await personal_assistant_service.update_config(config_update, current_user)
        return updated_config
        
    except Exception as e:
        logger.error(f"Error updating PA config: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update configuration: {str(e)}"
        )


@router.get("/workspace/{task_id}")
async def get_workspace(
    task_id: str,
    current_user: Optional[dict] = Depends(get_current_user)
):
    """
    Get workspace file content for a specific task.
    
    Args:
        task_id: The task ID to get workspace for
        
    Returns:
        Workspace file content and metadata
    """
    try:
        workspace = await personal_assistant_service.get_workspace(task_id, current_user)
        return workspace
        
    except Exception as e:
        logger.error(f"Error getting workspace: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get workspace: {str(e)}"
        )


@router.get("/health")
async def get_health():
    """
    Get Personal Assistant service health status.
    
    Returns:
        Health status and diagnostics
    """
    try:
        health = await personal_assistant_service.get_health()
        return health
        
    except Exception as e:
        logger.error(f"Error in PA health check: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Personal Assistant service is unhealthy"
        )
