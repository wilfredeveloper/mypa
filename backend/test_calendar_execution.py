#!/usr/bin/env python3
"""
Test script to verify Google Calendar tool execution after the fix.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.models.tool import ToolRegistry, UserToolAccess
from app.agents.personal_assistant.tools.external.google_calendar import GoogleCalendarTool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_calendar_execution():
    """Test Google Calendar tool execution."""
    async with AsyncSessionLocal() as db:
        try:
            # Get the user
            result = await db.execute(select(User).where(User.email == "pxumtech@gmail.com"))
            user = result.scalar_one_or_none()
            if not user:
                logger.error("User not found")
                return
            
            logger.info(f"🔍 Testing Google Calendar execution for user: {user.email}")
            
            # Get Google Calendar tool registry
            result = await db.execute(select(ToolRegistry).where(ToolRegistry.name == "google_calendar"))
            tool_registry = result.scalar_one_or_none()
            if not tool_registry:
                logger.error("Google Calendar tool not found in registry")
                return
            
            # Get user tool access
            result = await db.execute(
                select(UserToolAccess).where(
                    UserToolAccess.user_id == user.id,
                    UserToolAccess.tool_id == tool_registry.id
                )
            )
            user_access = result.scalar_one_or_none()
            if not user_access:
                logger.error("User tool access not found")
                return
            
            # Create Google Calendar tool instance
            calendar_tool = GoogleCalendarTool(
                registry=tool_registry,
                user=user,
                user_access=user_access,
                db=db
            )
            
            # Test authorization first
            is_authorized = await calendar_tool.is_authorized()
            logger.info(f"🎯 Google Calendar Tool is_authorized(): {is_authorized}")
            
            if not is_authorized:
                logger.error("❌ Tool is not authorized, cannot test execution")
                return
            
            # Test a simple calendar operation - list events for today
            logger.info("📅 Testing calendar event listing...")
            
            # Create parameters for listing events
            today = datetime.now()
            tomorrow = today + timedelta(days=1)
            
            parameters = {
                "action": "list",
                "time_min": today.isoformat(),
                "time_max": tomorrow.isoformat(),
                "max_results": 5
            }
            
            logger.info(f"📋 Parameters: {parameters}")
            
            # Execute the tool
            result = await calendar_tool.execute(parameters)
            logger.info(f"✅ Tool execution result: {result}")
            
            logger.info("🎉 SUCCESS: Google Calendar tool executed successfully!")
                
        except Exception as e:
            logger.error(f"Error testing execution: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_calendar_execution())
