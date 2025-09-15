#!/usr/bin/env python3
"""
Check Gmail tool authorization status in the database.
"""

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models.tool import ToolRegistry, UserToolAccess
from app.models.user import User
from sqlalchemy import select

async def check_gmail_auth():
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Get user (assuming user ID 1)
        user_result = await session.execute(select(User).where(User.id == 1))
        user = user_result.scalar_one_or_none()
        if not user:
            print('No user found with ID 1')
            return
            
        print(f'User: {user.email}')
        
        # Get Gmail tool from registry
        gmail_tool_result = await session.execute(
            select(ToolRegistry).where(ToolRegistry.name == 'gmail')
        )
        gmail_tool = gmail_tool_result.scalar_one_or_none()
        if not gmail_tool:
            print('Gmail tool not found in registry')
            return
            
        print(f'Gmail tool: {gmail_tool.name}, enabled: {gmail_tool.is_enabled}')
        
        # Get user access for Gmail
        access_result = await session.execute(
            select(UserToolAccess).where(
                UserToolAccess.user_id == user.id,
                UserToolAccess.tool_id == gmail_tool.id
            )
        )
        access = access_result.scalar_one_or_none()
        if not access:
            print('No user access record found for Gmail')
            return
            
        print(f'User access: authorized={access.is_authorized}')
        print(f'Config data: {access.config_data}')
        
        # Check OAuth data specifically
        if access.config_data:
            oauth_data = access.config_data.get('google_oauth', {})
            print(f'OAuth token present: {bool(oauth_data.get("token"))}')
            print(f'OAuth refresh_token present: {bool(oauth_data.get("refresh_token"))}')
            print(f'OAuth scopes: {oauth_data.get("scopes", [])}')
            if oauth_data.get('expiry'):
                print(f'OAuth expiry: {oauth_data.get("expiry")}')

if __name__ == "__main__":
    asyncio.run(check_gmail_auth())
