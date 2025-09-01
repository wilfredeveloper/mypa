-- Database initialization script
-- This script runs when the PostgreSQL container starts

-- Create additional databases if needed
-- CREATE DATABASE fastapi_test;

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create indexes for better performance (will be created by Alembic migrations)
-- These are just examples of what might be useful

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE fastapi_db TO postgres;
