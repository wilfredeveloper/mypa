"""
Agent Session Manager - Manages Personal Assistant agent instances across HTTP requests.

This service ensures that agent instances are properly cached and reused across
requests to maintain conversation memory and session state.
"""

import asyncio
import logging
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.agents.personal_assistant.agent import PersonalAssistant

logger = logging.getLogger(__name__)


class AgentSessionManager:
    """
    Manages Personal Assistant agent instances to maintain session continuity.
    
    This singleton service caches agent instances per user to ensure that
    conversation memory and session state are preserved across HTTP requests.
    """
    
    _instance: Optional['AgentSessionManager'] = None
    _lock = asyncio.Lock()
    
    def __init__(self):
        # Cache of agent instances by user_id
        self._agents: Dict[int, PersonalAssistant] = {}
        
        # Track last activity for cleanup
        self._last_activity: Dict[int, datetime] = {}
        
        # Configuration
        self.max_idle_minutes = 60  # Clean up agents after 1 hour of inactivity
        self.cleanup_interval_minutes = 15  # Run cleanup every 15 minutes
        
        # Start cleanup task
        self._cleanup_task = None
        self._start_cleanup_task()
        
        logger.info("Agent Session Manager initialized")
    
    @classmethod
    async def get_instance(cls) -> 'AgentSessionManager':
        """Get singleton instance of AgentSessionManager."""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    async def get_agent(self, user: User, db: AsyncSession) -> PersonalAssistant:
        """
        Get or create a Personal Assistant agent for the user.
        
        Args:
            user: The user requesting the agent
            db: Database session
            
        Returns:
            PersonalAssistant instance for the user
        """
        user_id = user.id
        
        # Update last activity
        self._last_activity[user_id] = datetime.utcnow()
        
        # Return existing agent if available
        if user_id in self._agents:
            agent = self._agents[user_id]
            # Update the database session in case it's stale
            agent.db = db
            logger.info(f"♻️  SESSION MANAGER: Reusing EXISTING agent for user {user_id} (cached)")
            return agent
        
        # Create new agent
        logger.info(f"🆕 SESSION MANAGER: Creating NEW agent for user {user_id}")
        agent = PersonalAssistant(user, db)
        await agent.initialize()

        # Cache the agent
        self._agents[user_id] = agent

        logger.info(f"💾 SESSION MANAGER: Cached new agent for user {user_id}")
        return agent
    
    async def remove_agent(self, user_id: int) -> bool:
        """
        Remove an agent from the cache.
        
        Args:
            user_id: ID of the user whose agent to remove
            
        Returns:
            True if agent was removed, False if not found
        """
        if user_id in self._agents:
            del self._agents[user_id]
            if user_id in self._last_activity:
                del self._last_activity[user_id]
            logger.info(f"Removed agent for user {user_id}")
            return True
        return False
    
    async def cleanup_idle_agents(self) -> int:
        """
        Clean up agents that have been idle for too long.
        
        Returns:
            Number of agents cleaned up
        """
        now = datetime.utcnow()
        idle_threshold = now - timedelta(minutes=self.max_idle_minutes)
        
        idle_users = []
        for user_id, last_activity in self._last_activity.items():
            if last_activity < idle_threshold:
                idle_users.append(user_id)
        
        # Remove idle agents
        cleaned_count = 0
        for user_id in idle_users:
            if await self.remove_agent(user_id):
                cleaned_count += 1
        
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} idle agents")
        
        return cleaned_count
    
    def _start_cleanup_task(self):
        """Start the background cleanup task."""
        async def cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(self.cleanup_interval_minutes * 60)
                    await self.cleanup_idle_agents()
                except asyncio.CancelledError:
                    logger.info("Agent cleanup task cancelled")
                    break
                except Exception as e:
                    logger.error(f"Error in agent cleanup task: {str(e)}")
        
        self._cleanup_task = asyncio.create_task(cleanup_loop())
    
    async def shutdown(self):
        """Shutdown the session manager and cleanup resources."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Clear all agents
        self._agents.clear()
        self._last_activity.clear()
        
        logger.info("Agent Session Manager shutdown complete")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the session manager."""
        return {
            "active_agents": len(self._agents),
            "users_with_activity": len(self._last_activity),
            "max_idle_minutes": self.max_idle_minutes,
            "cleanup_interval_minutes": self.cleanup_interval_minutes
        }


# Global instance getter
async def get_agent_session_manager() -> AgentSessionManager:
    """Get the global agent session manager instance."""
    return await AgentSessionManager.get_instance()


# FastAPI dependency
async def get_personal_assistant_agent(
    user: User,
    db: AsyncSession
) -> PersonalAssistant:
    """
    FastAPI dependency to get a Personal Assistant agent.
    
    This dependency ensures that agent instances are properly cached
    and reused across requests for the same user.
    """
    session_manager = await get_agent_session_manager()
    return await session_manager.get_agent(user, db)
