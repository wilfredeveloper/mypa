"""
Tests for health check endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.core.config import settings


class TestHealthEndpoints:
    """Test health check endpoints."""
    
    def test_health_check(self, client: TestClient):
        """Test basic health check endpoint."""
        response = client.get(f"{settings.API_V1_STR}/health/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["version"] == settings.VERSION
        assert data["service"] == settings.PROJECT_NAME
    
    @pytest.mark.asyncio
    async def test_detailed_health_check(self, async_client: AsyncClient):
        """Test detailed health check endpoint."""
        response = await async_client.get(f"{settings.API_V1_STR}/health/detailed")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["version"] == settings.VERSION
        assert data["service"] == settings.PROJECT_NAME
        assert "checks" in data
        assert "database" in data["checks"]
        assert data["checks"]["database"] == "healthy"
    
    def test_readiness_check(self, client: TestClient):
        """Test readiness probe endpoint."""
        response = client.get(f"{settings.API_V1_STR}/health/ready")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "ready"
    
    def test_liveness_check(self, client: TestClient):
        """Test liveness probe endpoint."""
        response = client.get(f"{settings.API_V1_STR}/health/live")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "alive"
