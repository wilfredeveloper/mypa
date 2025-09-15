#!/usr/bin/env python3
"""
Migration script to authorize Gmail tool for users who already have Google Calendar authorized.

This script:
1. Finds all users with authorized Google Calendar access
2. Creates Gmail tool access records for them
3. Copies the OAuth credentials to the shared google_oauth key
4. Marks Gmail as authorized

Run this after deploying the Gmail tool integration.
"""

import asyncio
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.tool import ToolRegistry, UserToolAccess
from app.models.user import User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate_gmail_authorization():
    """Migrate existing Google Calendar authorizations to also include Gmail."""
    
    async with AsyncSessionLocal() as db:
        try:
            # Get Google Calendar and Gmail tool registries
            result = await db.execute(select(ToolRegistry).where(ToolRegistry.name == "google_calendar"))
            calendar_tool = result.scalar_one_or_none()
            if not calendar_tool:
                logger.error("Google Calendar tool not found in registry")
                return
            
            result = await db.execute(select(ToolRegistry).where(ToolRegistry.name == "gmail"))
            gmail_tool = result.scalar_one_or_none()
            if not gmail_tool:
                logger.error("Gmail tool not found in registry")
                return
            
            # Find all authorized Google Calendar users
            result = await db.execute(
                select(UserToolAccess)
                .where(
                    UserToolAccess.tool_id == calendar_tool.id,
                    UserToolAccess.is_authorized == True
                )
            )
            calendar_accesses = result.scalars().all()
            
            logger.info(f"Found {len(calendar_accesses)} authorized Google Calendar users")
            
            migrated_count = 0
            for calendar_access in calendar_accesses:
                try:
                    # Check if user already has Gmail access
                    result = await db.execute(
                        select(UserToolAccess)
                        .where(
                            UserToolAccess.user_id == calendar_access.user_id,
                            UserToolAccess.tool_id == gmail_tool.id
                        )
                    )
                    gmail_access = result.scalar_one_or_none()
                    
                    # Get OAuth credentials from Calendar access
                    calendar_config = calendar_access.config_data or {}
                    oauth_data = calendar_config.get("google_calendar_oauth") or calendar_config.get("google_oauth")
                    
                    if not oauth_data:
                        logger.warning(f"No OAuth data found for user {calendar_access.user_id}")
                        continue
                    
                    # Update Calendar access to include shared google_oauth key
                    if "google_oauth" not in calendar_config:
                        calendar_config["google_oauth"] = oauth_data
                        calendar_access.config_data = calendar_config
                    
                    # Create or update Gmail access
                    if not gmail_access:
                        gmail_access = UserToolAccess(
                            user_id=calendar_access.user_id,
                            tool_id=gmail_tool.id,
                            is_authorized=True,
                            config_data={"google_oauth": oauth_data}
                        )
                        db.add(gmail_access)
                        logger.info(f"Created Gmail access for user {calendar_access.user_id}")
                    else:
                        # Update existing Gmail access
                        gmail_config = gmail_access.config_data or {}
                        gmail_config["google_oauth"] = oauth_data
                        gmail_access.config_data = gmail_config
                        if not gmail_access.is_authorized:
                            gmail_access.authorize()
                        logger.info(f"Updated Gmail access for user {calendar_access.user_id}")
                    
                    migrated_count += 1
                    
                except Exception as e:
                    logger.error(f"Error migrating user {calendar_access.user_id}: {e}")
                    continue
            
            # Commit all changes
            await db.commit()
            logger.info(f"Successfully migrated {migrated_count} users to have Gmail access")
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            await db.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(migrate_gmail_authorization())
