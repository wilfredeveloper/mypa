#!/usr/bin/env python3
"""
Test script to verify Google Calendar authorization after the fix.
"""

import asyncio
import logging
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.models.tool import ToolRegistry, UserToolAccess
from app.agents.personal_assistant.tools.external.google_calendar import GoogleCalendarTool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_calendar_auth():
    """Test Google Calendar authorization."""
    async with AsyncSessionLocal() as db:
        try:
            # Get the user
            result = await db.execute(select(User).where(User.email == "pxumtech@gmail.com"))
            user = result.scalar_one_or_none()
            if not user:
                logger.error("User not found")
                return
            
            logger.info(f"🔍 Testing authorization for user: {user.email}")
            
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
            
            logger.info(f"📊 User Access ID: {user_access.id}")
            logger.info(f"✅ Is Authorized (DB): {user_access.is_authorized}")
            
            # Check config data
            config_data = user_access.config_data or {}
            google_oauth_cfg = config_data.get("google_oauth", {})
            legacy_cfg = config_data.get("google_calendar_oauth", {})
            
            logger.info(f"🔑 google_oauth has tokens: {bool(google_oauth_cfg.get('refresh_token') or google_oauth_cfg.get('token'))}")
            logger.info(f"🔑 google_calendar_oauth has tokens: {bool(legacy_cfg.get('refresh_token') or legacy_cfg.get('token'))}")
            
            # Create Google Calendar tool instance
            calendar_tool = GoogleCalendarTool(
                registry=tool_registry,
                user=user,
                user_access=user_access,
                db=db
            )
            
            # Test authorization
            is_authorized = await calendar_tool.is_authorized()
            logger.info(f"🎯 Google Calendar Tool is_authorized(): {is_authorized}")
            
            if is_authorized:
                logger.info("✅ SUCCESS: Google Calendar tool is now properly authorized!")
            else:
                logger.error("❌ FAILED: Google Calendar tool is still not authorized")
                
        except Exception as e:
            logger.error(f"Error testing authorization: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_calendar_auth())
