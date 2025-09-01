"""
FastAPI Backend Application Entry Point
"""

import uvicorn

from app.main import app
from app.core.config import settings


def main():
    """Run the FastAPI application with uvicorn."""
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD,
        log_level=settings.LOG_LEVEL.lower(),
    )


if __name__ == "__main__":
    main()
