#!/usr/bin/env python3
"""
Debug script to check OAuth state for Google Calendar and Gmail tools.
"""

import asyncio
import json
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.tool import ToolRegistry, UserToolAccess
from app.models.user import User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def debug_oauth_state():
    """Debug OAuth state for Google tools."""
    
    async with AsyncSessionLocal() as db:
        try:
            # Get user (assuming user ID 1)
            result = await db.execute(select(User).where(User.id == 1))
            user = result.scalar_one_or_none()
            if not user:
                logger.error("User 1 not found")
                return
            
            logger.info(f"🔍 Debugging OAuth state for user: {user.email}")
            
            # Get Google Calendar and Gmail tool registries
            result = await db.execute(select(ToolRegistry).where(ToolRegistry.name.in_(["google_calendar", "gmail"])))
            tools = {tool.name: tool for tool in result.scalars().all()}
            
            if "google_calendar" not in tools:
                logger.error("Google Calendar tool not found in registry")
                return
            if "gmail" not in tools:
                logger.error("Gmail tool not found in registry")
                return
            
            logger.info(f"📋 Found tools: {list(tools.keys())}")
            
            # Check UserToolAccess records for both tools
            for tool_name, tool in tools.items():
                result = await db.execute(
                    select(UserToolAccess)
                    .where(
                        UserToolAccess.user_id == user.id,
                        UserToolAccess.tool_id == tool.id
                    )
                )
                access = result.scalar_one_or_none()
                
                logger.info(f"\n🔧 {tool_name.upper()} TOOL ACCESS:")
                if not access:
                    logger.warning(f"  ❌ No UserToolAccess record found")
                    continue
                
                logger.info(f"  📊 Access ID: {access.id}")
                logger.info(f"  ✅ Is Authorized: {access.is_authorized}")
                logger.info(f"  📅 Authorization Date: {access.authorization_date}")
                logger.info(f"  📈 Usage Count: {access.usage_count}")
                logger.info(f"  🕒 Last Used: {access.last_used}")
                
                # Check config data
                config_data = access.config_data or {}
                logger.info(f"  🔑 Config Keys: {list(config_data.keys())}")
                
                # Check OAuth credentials
                google_oauth = config_data.get("google_oauth", {})
                google_calendar_oauth = config_data.get("google_calendar_oauth", {})
                
                logger.info(f"  🔐 google_oauth keys: {list(google_oauth.keys())}")
                logger.info(f"  🔐 google_calendar_oauth keys: {list(google_calendar_oauth.keys())}")
                
                # Check if tokens exist
                oauth_has_tokens = bool(google_oauth.get("refresh_token") or google_oauth.get("token"))
                calendar_oauth_has_tokens = bool(google_calendar_oauth.get("refresh_token") or google_calendar_oauth.get("token"))
                
                logger.info(f"  🎫 google_oauth has tokens: {oauth_has_tokens}")
                logger.info(f"  🎫 google_calendar_oauth has tokens: {calendar_oauth_has_tokens}")
                
                # Check scopes
                oauth_scopes = google_oauth.get("scopes", [])
                calendar_oauth_scopes = google_calendar_oauth.get("scopes", [])
                
                logger.info(f"  🎯 google_oauth scopes: {oauth_scopes}")
                logger.info(f"  🎯 google_calendar_oauth scopes: {calendar_oauth_scopes}")
                
                # Check token expiry
                oauth_expiry = google_oauth.get("expiry")
                calendar_oauth_expiry = google_calendar_oauth.get("expiry")
                
                logger.info(f"  ⏰ google_oauth expiry: {oauth_expiry}")
                logger.info(f"  ⏰ google_calendar_oauth expiry: {calendar_oauth_expiry}")
            
            logger.info(f"\n🎯 AUTHORIZATION ANALYSIS:")
            
            # Test authorization logic for both tools
            calendar_access = None
            gmail_access = None
            
            for tool_name, tool in tools.items():
                result = await db.execute(
                    select(UserToolAccess)
                    .where(
                        UserToolAccess.user_id == user.id,
                        UserToolAccess.tool_id == tool.id
                    )
                )
                access = result.scalar_one_or_none()
                
                if tool_name == "google_calendar":
                    calendar_access = access
                elif tool_name == "gmail":
                    gmail_access = access
                
                if access:
                    # Simulate the is_authorized check
                    is_authorized_db = access.is_authorized
                    config_data = access.config_data or {}
                    oauth_data = config_data.get("google_oauth", {})
                    has_tokens = bool(oauth_data.get("refresh_token") or oauth_data.get("token"))
                    
                    should_be_authorized = is_authorized_db and has_tokens
                    
                    logger.info(f"  {tool_name}: is_authorized={is_authorized_db}, has_tokens={has_tokens}, should_work={should_be_authorized}")
            
        except Exception as e:
            logger.error(f"Debug failed: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(debug_oauth_state())
