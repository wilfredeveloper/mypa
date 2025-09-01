"""
Tests for user service.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.services.user import UserService


class TestUserService:
    """Test user service operations."""
    
    @pytest.mark.asyncio
    async def test_create_user(self, db_session: AsyncSession):
        """Test creating a new user."""
        user_service = UserService(db_session)
        user_data = UserCreate(
            email="test@example.com",
            username="testuser",
            full_name="Test User",
            password="TestPassword123!",
        )
        
        user = await user_service.create(user_data)
        
        assert user.id is not None
        assert user.email == "test@example.com"
        assert user.username == "testuser"
        assert user.full_name == "Test User"
        assert user.is_active is True
        assert user.hashed_password != "TestPassword123!"  # Should be hashed
    
    @pytest.mark.asyncio
    async def test_get_user_by_id(self, db_session: AsyncSession, test_user: User):
        """Test getting user by ID."""
        user_service = UserService(db_session)
        
        user = await user_service.get_by_id(test_user.id)
        
        assert user is not None
        assert user.id == test_user.id
        assert user.email == test_user.email
    
    @pytest.mark.asyncio
    async def test_get_user_by_email(self, db_session: AsyncSession, test_user: User):
        """Test getting user by email."""
        user_service = UserService(db_session)
        
        user = await user_service.get_by_email(test_user.email)
        
        assert user is not None
        assert user.id == test_user.id
        assert user.email == test_user.email
    
    @pytest.mark.asyncio
    async def test_update_user(self, db_session: AsyncSession, test_user: User):
        """Test updating user information."""
        user_service = UserService(db_session)
        update_data = UserUpdate(
            full_name="Updated Name",
            bio="Updated bio"
        )
        
        updated_user = await user_service.update(test_user.id, update_data)
        
        assert updated_user is not None
        assert updated_user.full_name == "Updated Name"
        assert updated_user.bio == "Updated bio"
        assert updated_user.email == test_user.email  # Unchanged
    
    @pytest.mark.asyncio
    async def test_get_multi_users(self, db_session: AsyncSession):
        """Test getting multiple users with pagination."""
        user_service = UserService(db_session)
        
        # Create multiple users
        for i in range(5):
            user_data = UserCreate(
                email=f"user{i}@example.com",
                username=f"user{i}",
                password="Password123!",
            )
            await user_service.create(user_data)
        
        users = await user_service.get_multi(skip=0, limit=3)
        
        assert len(users) == 3
        
        users_page_2 = await user_service.get_multi(skip=3, limit=3)
        assert len(users_page_2) == 2
    
    @pytest.mark.asyncio
    async def test_activate_deactivate_user(self, db_session: AsyncSession, test_user: User):
        """Test activating and deactivating user."""
        user_service = UserService(db_session)
        
        # Deactivate user
        deactivated_user = await user_service.deactivate(test_user.id)
        assert deactivated_user is not None
        assert deactivated_user.is_active is False
        
        # Activate user
        activated_user = await user_service.activate(test_user.id)
        assert activated_user is not None
        assert activated_user.is_active is True
