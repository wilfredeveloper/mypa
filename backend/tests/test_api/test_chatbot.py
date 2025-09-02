"""
Tests for chatbot API endpoints.
"""

import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from datetime import datetime

from app.main import app
from app.schemas.chatbot import (
    ChatRequest, ChatResponse, ConversationMessage, ThoughtStep,
    ChatHealthCheck, UsageStats, ConversationSummary
)


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def sample_chat_request():
    """Sample chat request for testing."""
    return {
        "message": "Hello, how are you?",
        "conversation_history": [
            {
                "role": "user",
                "content": "Hi there!",
                "timestamp": "2024-01-01T12:00:00"
            },
            {
                "role": "assistant", 
                "content": "Hello! How can I help you today?",
                "timestamp": "2024-01-01T12:00:01"
            }
        ],
        "stream": False,
        "session_id": "test-session-123"
    }


class TestChatbotEndpoints:
    """Test class for chatbot API endpoints."""
    
    @patch('app.services.chatbot.chatbot_service.chat_non_streaming')
    def test_chat_non_streaming_success(self, mock_chat_service, client, sample_chat_request):
        """Test successful non-streaming chat request."""
        # Setup mock response
        mock_response = {
            "response": "I'm doing well, thank you!",
            "session_id": "test-session-123",
            "thoughts": [],
            "observations": [],
            "metadata": {"processing_time_ms": 1500.0},
            "usage_stats": {"total_tokens": 45}
        }
        mock_chat_service.return_value = mock_response
        
        # Make request
        response = client.post("/api/v1/chatbot/chat", json=sample_chat_request)
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        mock_chat_service.assert_called_once()
    
    def test_chat_non_streaming_empty_message(self, client):
        """Test chat request with empty message."""
        request_data = {
            "message": "",
            "conversation_history": [],
            "stream": False
        }
        
        response = client.post("/api/v1/chatbot/chat", json=request_data)
        
        assert response.status_code == 400
        assert "Message cannot be empty" in response.json()["detail"]
    
    @patch('app.services.chatbot.chatbot_service.get_health_check')
    def test_health_check(self, mock_health_check, client):
        """Test health check endpoint."""
        mock_health_check.return_value = {
            "status": "healthy",
            "baml_available": True,
            "rate_limit_status": {},
            "last_successful_call": None,
            "error_details": None
        }
        
        response = client.get("/api/v1/chatbot/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["baml_available"] is True
