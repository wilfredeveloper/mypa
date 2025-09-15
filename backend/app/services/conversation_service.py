"""
Conversation Service - Manages conversation sessions and message persistence.

This service handles creating, retrieving, and managing conversation sessions
and their associated messages in the database.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_, func
from sqlalchemy.orm import selectinload

from app.models.conversation import ConversationSession, ConversationMessage
from app.models.user import User

logger = logging.getLogger(__name__)


class ConversationService:
    """Service for managing conversation sessions and messages."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_session(
        self,
        user: User,
        session_id: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        context_data: Optional[Dict[str, Any]] = None
    ) -> ConversationSession:
        """
        Create a new conversation session.
        
        Args:
            user: The user who owns the session
            session_id: Optional custom session ID (will generate if None)
            title: Optional session title
            description: Optional session description
            context_data: Optional context data for the session
            
        Returns:
            The created ConversationSession
        """
        if session_id is None:
            session_id = ConversationSession.generate_session_id()
        
        session = ConversationSession(
            session_id=session_id,
            user_id=user.id,
            title=title,
            description=description,
            context_data=context_data or {},
            is_active=True
        )
        
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        
        logger.info(f"Created new conversation session {session_id} for user {user.id}")
        return session

    async def get_session(
        self,
        session_id: str,
        user: User,
        include_messages: bool = True
    ) -> Optional[ConversationSession]:
        """
        Get a conversation session by ID.
        
        Args:
            session_id: The session ID to retrieve
            user: The user who should own the session
            include_messages: Whether to include messages in the result
            
        Returns:
            The ConversationSession if found, None otherwise
        """
        query = select(ConversationSession).where(
            and_(
                ConversationSession.session_id == session_id,
                ConversationSession.user_id == user.id
            )
        )
        
        if include_messages:
            query = query.options(selectinload(ConversationSession.messages))
        
        result = await self.db.execute(query)
        session = result.scalar_one_or_none()
        
        if session:
            # Update last activity
            session.update_activity()
            await self.db.commit()
        
        return session

    async def get_or_create_session(
        self,
        user: User,
        session_id: Optional[str] = None,
        title: Optional[str] = None,
        context_data: Optional[Dict[str, Any]] = None
    ) -> ConversationSession:
        """
        Get an existing session or create a new one.
        
        Args:
            user: The user who owns the session
            session_id: Optional session ID to retrieve/create
            title: Optional title for new sessions
            context_data: Optional context data for new sessions
            
        Returns:
            The ConversationSession (existing or newly created)
        """
        if session_id:
            # Try to get existing session
            session = await self.get_session(session_id, user, include_messages=True)
            if session:
                logger.info(f"Retrieved existing session {session_id} for user {user.id}")
                return session
            
            logger.warning(f"Session {session_id} not found for user {user.id}, creating new session")
        
        # Create new session
        return await self.create_session(
            user=user,
            session_id=session_id,
            title=title,
            context_data=context_data
        )

    async def add_message(
        self,
        session: ConversationSession,
        role: str,
        content: str,
        tools_used: Optional[List[Dict[str, Any]]] = None,
        processing_time_ms: Optional[int] = None,
        token_count: Optional[int] = None,
        has_error: bool = False,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ConversationMessage:
        """
        Add a message to a conversation session.
        
        Args:
            session: The conversation session
            role: Message role ('user' or 'assistant')
            content: Message content
            tools_used: List of tools used (for assistant messages)
            processing_time_ms: Processing time in milliseconds
            token_count: Number of tokens in the message
            has_error: Whether the message has an error
            error_message: Error message if applicable
            metadata: Additional metadata
            
        Returns:
            The created ConversationMessage
        """
        message = ConversationMessage(
            session_id=session.session_id,
            role=role,
            content=content,
            tools_used=tools_used,
            processing_time_ms=processing_time_ms,
            token_count=token_count,
            has_error=has_error,
            error_message=error_message,
            message_metadata=metadata or {}
        )
        
        self.db.add(message)
        
        # Update session activity
        session.update_activity()
        
        await self.db.commit()
        await self.db.refresh(message)
        
        logger.debug(f"Added {role} message to session {session.session_id}")
        return message

    async def update_session_context(
        self,
        session: ConversationSession,
        context_data: Dict[str, Any]
    ) -> ConversationSession:
        """
        Update the context data for a conversation session.

        Args:
            session: The conversation session to update
            context_data: New context data to store

        Returns:
            The updated ConversationSession
        """
        # Update the context data
        session.context_data = context_data
        session.update_activity()

        # Commit the changes
        await self.db.commit()
        await self.db.refresh(session)

        logger.debug(f"Updated context for session {session.session_id}")
        return session

    async def get_user_sessions(
        self,
        user: User,
        limit: int = 50,
        include_inactive: bool = False
    ) -> List[ConversationSession]:
        """
        Get conversation sessions for a user.
        
        Args:
            user: The user whose sessions to retrieve
            limit: Maximum number of sessions to return
            include_inactive: Whether to include inactive sessions
            
        Returns:
            List of ConversationSession objects
        """
        query = select(ConversationSession).where(
            ConversationSession.user_id == user.id
        )
        
        if not include_inactive:
            query = query.where(ConversationSession.is_active == True)
        
        query = query.order_by(desc(ConversationSession.last_activity_at)).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()

    async def deactivate_session(self, session: ConversationSession) -> None:
        """
        Deactivate a conversation session.
        
        Args:
            session: The session to deactivate
        """
        session.is_active = False
        await self.db.commit()
        logger.info(f"Deactivated session {session.session_id}")

    async def delete_session(self, session: ConversationSession) -> None:
        """
        Delete a conversation session and all its messages.
        
        Args:
            session: The session to delete
        """
        session_id = session.session_id
        await self.db.delete(session)
        await self.db.commit()
        logger.info(f"Deleted session {session_id}")

    async def cleanup_old_sessions(
        self,
        user: User,
        days_old: int = 30,
        keep_minimum: int = 10
    ) -> int:
        """
        Clean up old inactive sessions for a user.
        
        Args:
            user: The user whose sessions to clean up
            days_old: Delete sessions older than this many days
            keep_minimum: Always keep at least this many recent sessions
            
        Returns:
            Number of sessions deleted
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        # Get sessions to potentially delete
        query = select(ConversationSession).where(
            and_(
                ConversationSession.user_id == user.id,
                ConversationSession.last_activity_at < cutoff_date,
                ConversationSession.is_active == False
            )
        ).order_by(desc(ConversationSession.last_activity_at))
        
        result = await self.db.execute(query)
        old_sessions = result.scalars().all()
        
        # Get total session count to ensure we keep minimum
        total_count_query = select(func.count(ConversationSession.id)).where(
            ConversationSession.user_id == user.id
        )
        total_result = await self.db.execute(total_count_query)
        total_sessions = total_result.scalar()
        
        # Calculate how many we can safely delete
        can_delete = max(0, total_sessions - keep_minimum)
        sessions_to_delete = old_sessions[:can_delete]
        
        # Delete the sessions
        deleted_count = 0
        for session in sessions_to_delete:
            await self.db.delete(session)
            deleted_count += 1
        
        if deleted_count > 0:
            await self.db.commit()
            logger.info(f"Cleaned up {deleted_count} old sessions for user {user.id}")
        
        return deleted_count
