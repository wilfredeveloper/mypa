"""
Database configuration and session management.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# Create async engine
async_engine = create_async_engine(
    str(settings.DATABASE_URL),
    echo=settings.DEBUG,
    future=True,
    pool_pre_ping=True,
)

# Create sync engine for migrations
# Convert async driver URLs to their sync equivalents
_db_url = str(settings.DATABASE_URL)
if _db_url.startswith("sqlite+aiosqlite"):
    _sync_url = _db_url.replace("+aiosqlite", "")
else:
    _sync_url = _db_url.replace("+asyncpg", "")

sync_engine = create_engine(
    _sync_url,
    echo=settings.DEBUG,
    pool_pre_ping=True,
)

# Create async session factory
AsyncSessionLocal = sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Create sync session factory for migrations
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=sync_engine,
)

# Base class for models
Base = declarative_base()


async def get_async_session() -> AsyncSession:
    """Dependency to get async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_sync_session():
    """Dependency to get sync database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
