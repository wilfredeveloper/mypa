# FastAPI Backend

A professional FastAPI backend application with modern architecture, following best practices for scalability, maintainability, and production readiness.

## Features

- **FastAPI Framework**: Modern, fast web framework for building APIs
- **Async/Await Support**: Full asynchronous support with SQLAlchemy 2.0
- **JWT Authentication**: Secure authentication with access and refresh tokens
- **Database Integration**: PostgreSQL with SQLAlchemy ORM and Alembic migrations
- **API Versioning**: Structured API versioning with `/api/v1/` prefix
- **Comprehensive Testing**: Unit, integration, and API tests with pytest
- **Docker Support**: Full containerization with docker-compose
- **Logging**: Structured logging with configurable formats
- **Security**: CORS, trusted hosts, and security best practices
- **Documentation**: Auto-generated OpenAPI/Swagger documentation

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL (or use Docker)
- Redis (optional, for caching)

### Installation

1. **Clone and navigate to the backend directory**:
   ```bash
   cd backend
   ```

2. **Create and activate virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -e .[dev]
   ```

4. **Set up environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Run with Docker (Recommended)**:
   ```bash
   docker-compose up -d
   ```

   Or run locally:
   ```bash
   # Start database and Redis
   docker-compose up -d db redis

   # Run migrations
   alembic upgrade head

   # Start the application
   python main.py
   ```

### API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8000/api/v1/docs
- **ReDoc**: http://localhost:8000/api/v1/redoc
- **Health Check**: http://localhost:8000/api/v1/health/

## Development

### Database Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test types
pytest -m unit
pytest -m integration
pytest -m e2e
```

## Authentication

The API uses JWT tokens for authentication:

1. **Register**: `POST /api/v1/auth/register`
2. **Login**: `POST /api/v1/auth/login`
3. **Refresh**: `POST /api/v1/auth/refresh`

Include the access token in requests:
```
Authorization: Bearer <access_token>
```