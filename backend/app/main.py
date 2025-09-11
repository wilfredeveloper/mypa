"""
FastAPI application factory and main application setup.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import os
from dotenv import load_dotenv

# Load environment variables from .env.local and .env files
# This ensures BAML can access the API keys from environment variables
load_dotenv(".env.local")
load_dotenv(".env")

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.logging import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger(__name__)


def create_application() -> FastAPI:
    """Create and configure FastAPI application."""
    
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="Professional FastAPI backend with modern architecture",
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url=f"{settings.API_V1_STR}/docs",
        redoc_url=f"{settings.API_V1_STR}/redoc",
    )
    
    # Set up CORS
    if settings.BACKEND_CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    # Add trusted host middleware for security
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"] if settings.DEBUG else ["localhost", "127.0.0.1"]
    )
    
    # Include API router
    app.include_router(api_router, prefix=settings.API_V1_STR)

    # Mount static files
    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # Add startup and shutdown event handlers
    @app.on_event("startup")
    async def startup_event():
        """Application startup event."""
        logger.info("Starting up FastAPI application",
                   version=settings.VERSION,
                   debug=settings.DEBUG)

        # Development convenience: auto-create tables for SQLite if missing and seed default tools
        try:
            db_url = str(settings.DATABASE_URL or "")
            import asyncio
            # Ensure models are imported so metadata knows all tables
            import app.models.user  # noqa: F401
            import app.models.agent  # noqa: F401
            import app.models.tool  # noqa: F401
            import app.models.oauth_token  # noqa: F401
            from app.core.database import Base, sync_engine, AsyncSessionLocal
            from sqlalchemy import select
            from app.models.tool import ToolRegistry, ToolType
            from app.agents.personal_assistant.tools.schemas import GOOGLE_CALENDAR_SCHEMA

            if db_url.startswith("sqlite"):
                logger.info("Auto-creating SQLite tables if not present")
                await asyncio.to_thread(Base.metadata.create_all, bind=sync_engine)

            # Seed ToolRegistry with google_calendar if missing (dev convenience)
            async with AsyncSessionLocal() as session:
                try:
                    result = await session.execute(select(ToolRegistry).where(ToolRegistry.name == "google_calendar"))
                    tool = result.scalar_one_or_none()
                    if not tool:
                        tool = ToolRegistry(
                            name="google_calendar",
                            display_name="Google Calendar",
                            description=(
                                "Manage Google Calendar: list, create, update, delete events, and check availability. "
                                "Requires Google OAuth (offline access) to operate."
                            ),
                            tool_type=ToolType.EXTERNAL,
                            category="productivity",
                            schema_data=GOOGLE_CALENDAR_SCHEMA,
                            permissions_required=["https://www.googleapis.com/auth/calendar"],
                            oauth_provider="google",
                            is_enabled=True,
                        )
                        session.add(tool)
                        await session.commit()
                        logger.info("Seeded ToolRegistry entry: google_calendar")
                    else:
                        # Update existing entry to ensure schema stays in sync with tool implementation
                        tool.display_name = "Google Calendar"
                        tool.description = (
                            "Manage Google Calendar: list, create, update, delete events, and check availability. "
                            "Requires Google OAuth (offline access) to operate."
                        )
                        tool.tool_type = ToolType.EXTERNAL
                        tool.category = "productivity"
                        tool.schema_data = GOOGLE_CALENDAR_SCHEMA
                        tool.oauth_provider = "google"
                        tool.is_enabled = True
                        await session.commit()
                        logger.info("Updated ToolRegistry entry: google_calendar")
                except Exception as se:
                    logger.error(f"ToolRegistry seed failed: {se}")
        except Exception as e:
            logger.error(f"DB auto-create/seed failed: {e}")

    @app.on_event("shutdown")
    async def shutdown_event():
        """Application shutdown event."""
        logger.info("Shutting down FastAPI application")
    
    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        """Global exception handler for unhandled exceptions."""
        logger.error("Unhandled exception occurred", 
                    error=str(exc), 
                    path=request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"}
        )
    
    return app


# Create application instance
app = create_application()
