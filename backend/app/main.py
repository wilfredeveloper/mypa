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


async def _seed_tool_registry(session) -> None:
    """Seed the tool registry with all required tools."""
    from sqlalchemy import select
    from app.models.tool import ToolRegistry, ToolType
    from app.agents.personal_assistant.tools.schemas import (
        GOOGLE_CALENDAR_SCHEMA,
        GMAIL_SCHEMA,
        SYSTEM_PROMPT_SCHEMA,
        PLANNING_SCHEMA,
        VIRTUAL_FS_SCHEMA,
        TAVILY_SEARCH_SCHEMA
    )

    # Define all tools to be seeded
    tools_to_seed = [
        {
            "name": "system_prompt",
            "display_name": "System Prompt Manager",
            "description": "Manage and switch between different system prompts for the Personal Assistant",
            "tool_type": ToolType.BUILTIN,
            "category": "configuration",
            "schema_data": SYSTEM_PROMPT_SCHEMA,
            "rate_limit_per_minute": 60,
            "rate_limit_per_day": 1000,
        },
        {
            "name": "planning",
            "display_name": "Task Planning",
            "description": "Break down complex requests into actionable steps with dependency tracking",
            "tool_type": ToolType.BUILTIN,
            "category": "productivity",
            "schema_data": PLANNING_SCHEMA,
            "rate_limit_per_minute": 30,
            "rate_limit_per_day": 500,
        },
        {
            "name": "virtual_fs",
            "display_name": "Virtual File System",
            "description": "Create and manage temporary files during task execution with in-memory storage",
            "tool_type": ToolType.BUILTIN,
            "category": "utility",
            "schema_data": VIRTUAL_FS_SCHEMA,
            "rate_limit_per_minute": 120,
            "rate_limit_per_day": 2000,
        },
        {
            "name": "tavily_search",
            "display_name": "Tavily Web Search",
            "description": "Perform web searches using the Tavily Search API with structured results",
            "tool_type": ToolType.BUILTIN,
            "category": "research",
            "schema_data": TAVILY_SEARCH_SCHEMA,
            "rate_limit_per_minute": 30,
            "rate_limit_per_day": 500,
        },
        {
            "name": "google_calendar",
            "display_name": "Google Calendar",
            "description": (
                "Manage Google Calendar: list, create, update, delete events, and check availability. "
                "Requires Google OAuth (offline access) to operate."
            ),
            "tool_type": ToolType.EXTERNAL,
            "category": "productivity",
            "schema_data": GOOGLE_CALENDAR_SCHEMA,
            "permissions_required": ["https://www.googleapis.com/auth/calendar"],
            "oauth_provider": "google",
            "rate_limit_per_minute": 60,
            "rate_limit_per_day": 1000,
        },
        {
            "name": "gmail",
            "display_name": "Gmail",
            "description": (
                "Manage Gmail: read inbox, send emails, reply to messages, search emails, and manage labels. "
                "Requires Google OAuth with Gmail permissions to operate."
            ),
            "tool_type": ToolType.EXTERNAL,
            "category": "communication",
            "schema_data": GMAIL_SCHEMA,
            "permissions_required": [
                "https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/gmail.send",
                "https://www.googleapis.com/auth/gmail.compose",
                "https://www.googleapis.com/auth/gmail.modify"
            ],
            "oauth_provider": "google",
            "rate_limit_per_minute": 30,
            "rate_limit_per_day": 500,
        }
    ]

    # Seed or update each tool
    for tool_config in tools_to_seed:
        result = await session.execute(
            select(ToolRegistry).where(ToolRegistry.name == tool_config["name"])
        )
        existing_tool = result.scalar_one_or_none()

        if not existing_tool:
            # Create new tool
            new_tool = ToolRegistry(
                name=tool_config["name"],
                display_name=tool_config["display_name"],
                description=tool_config["description"],
                tool_type=tool_config["tool_type"],
                category=tool_config["category"],
                schema_data=tool_config["schema_data"],
                permissions_required=tool_config.get("permissions_required"),
                oauth_provider=tool_config.get("oauth_provider"),
                rate_limit_per_minute=tool_config.get("rate_limit_per_minute", 60),
                rate_limit_per_day=tool_config.get("rate_limit_per_day", 1000),
                is_enabled=True,
            )
            session.add(new_tool)
            logger.info(f"Seeded ToolRegistry entry: {tool_config['name']}")
        else:
            # Update existing tool to ensure schema stays in sync
            existing_tool.display_name = tool_config["display_name"]
            existing_tool.description = tool_config["description"]
            existing_tool.tool_type = tool_config["tool_type"]
            existing_tool.category = tool_config["category"]
            existing_tool.schema_data = tool_config["schema_data"]
            existing_tool.permissions_required = tool_config.get("permissions_required")
            existing_tool.oauth_provider = tool_config.get("oauth_provider")
            existing_tool.rate_limit_per_minute = tool_config.get("rate_limit_per_minute", 60)
            existing_tool.rate_limit_per_day = tool_config.get("rate_limit_per_day", 1000)
            existing_tool.is_enabled = True
            logger.info(f"Updated ToolRegistry entry: {tool_config['name']}")

    await session.commit()
    logger.info(f"Tool registry seeding completed. Seeded/updated {len(tools_to_seed)} tools.")


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
            from app.agents.personal_assistant.tools.schemas import (
                GOOGLE_CALENDAR_SCHEMA,
                GMAIL_SCHEMA,
                SYSTEM_PROMPT_SCHEMA,
                PLANNING_SCHEMA,
                VIRTUAL_FS_SCHEMA,
                TAVILY_SEARCH_SCHEMA
            )

            if db_url.startswith("sqlite"):
                logger.info("Auto-creating SQLite tables if not present")
                await asyncio.to_thread(Base.metadata.create_all, bind=sync_engine)

            # Seed ToolRegistry with all tools if missing (dev convenience)
            session = AsyncSessionLocal()
            try:
                await _seed_tool_registry(session)
            except Exception as se:
                logger.error(f"ToolRegistry seed failed: {se}")
            finally:
                await session.close()
        except Exception as e:
            logger.error(f"DB auto-create/seed failed: {e}")

    @app.on_event("shutdown")
    async def shutdown_event():
        """Application shutdown event."""
        logger.info("Shutting down FastAPI application")

        # Shutdown agent session manager
        try:
            from app.services.agent_session_manager import get_agent_session_manager
            session_manager = await get_agent_session_manager()
            await session_manager.shutdown()
        except Exception as e:
            logger.error(f"Failed to shutdown agent session manager: {e}")
    
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
