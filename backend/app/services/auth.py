"""
Authentication service for business logic operations.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.models.user import User


class AuthService:
    """Service class for authentication-related operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def authenticate_user(
        self, 
        email: str, 
        password: str
    ) -> Optional[User]:
        """Authenticate user with email and password."""
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return None
        
        if not user.is_active:
            return None
        
        if not verify_password(password, user.hashed_password):
            return None
        
        # Update last login timestamp
        await self.update_last_login(user.id)
        
        return user
    
    async def update_last_login(self, user_id: int) -> None:
        """Update user's last login timestamp."""
        await self.db.execute(
            update(User)
            .where(User.id == user_id)
            .values(last_login=datetime.utcnow())
        )
        await self.db.commit()
    
    async def verify_user_email(self, user_id: int) -> Optional[User]:
        """Mark user email as verified."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return None
        
        user.is_verified = True
        await self.db.commit()
        await self.db.refresh(user)
        return user
