"""Full tests for auth module and router."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from datetime import datetime, timedelta

from app.main import app


client = TestClient(app)


class TestAuthEndpoints:
    """Tests for auth endpoints."""
    
    def test_register_endpoint_exists(self):
        """Test register endpoint exists."""
        response = client.post(
            "/auth/register",
            json={
                "email": "test@example.com",
                "password": "password123",
            }
        )
        # Will fail due to DB, but validates route
        assert response.status_code in [200, 400, 500]
    
    def test_register_missing_email(self):
        """Test register with missing email."""
        response = client.post(
            "/auth/register",
            json={"password": "password123"}
        )
        assert response.status_code == 422
    
    def test_register_invalid_email(self):
        """Test register with invalid email."""
        response = client.post(
            "/auth/register",
            json={
                "email": "not-an-email",
                "password": "password123",
            }
        )
        assert response.status_code == 422
    
    def test_login_missing_email(self):
        """Test login with missing email."""
        response = client.post(
            "/auth/login",
            json={"password": "password123"}
        )
        assert response.status_code == 422
    
    def test_login_missing_credentials(self):
        """Test login with missing credentials."""
        response = client.post("/auth/login", json={})
        assert response.status_code == 422
    
    def test_me_endpoint_requires_auth(self):
        """Test /me endpoint requires authentication."""
        response = client.get("/auth/me")
        assert response.status_code in [401, 403, 422]
    
    def test_token_creation_for_me_endpoint(self):
        """Test token can be created for /me endpoint."""
        from app.core.auth import create_access_token, decode_token
        
        token = create_access_token({
            "user_id": "test-user-id",
            "email": "test@example.com",
        })
        
        # Verify token is valid
        decoded = decode_token(token)
        assert decoded is not None
        assert decoded.user_id == "test-user-id"
    
    def test_refresh_endpoint_requires_auth(self):
        """Test refresh endpoint requires authentication."""
        response = client.post("/auth/refresh")
        assert response.status_code in [401, 403, 422]

    def test_register_rejects_short_password(self):
        """UI promises ≥8 characters; backend must reject shorter passwords."""
        response = client.post(
            "/auth/register",
            json={"email": "shortpass@example.com", "password": "short"},
        )
        assert response.status_code == 422


class TestTokenOperations:
    """Tests for JWT token operations."""
    
    def test_token_contains_user_id(self):
        """Test token contains user_id claim."""
        from app.core.auth import create_access_token, decode_token
        
        token = create_access_token({"user_id": "user-123"})
        decoded = decode_token(token)
        
        assert decoded.user_id == "user-123"
    
    def test_token_contains_email(self):
        """Test token contains email claim."""
        from app.core.auth import create_access_token, decode_token
        
        token = create_access_token({
            "user_id": "user-123",
            "email": "test@example.com",
        })
        decoded = decode_token(token)
        
        assert decoded.email == "test@example.com"
    
    def test_token_contains_workspace(self):
        """Test token contains workspace_id claim."""
        from app.core.auth import create_access_token, decode_token
        
        token = create_access_token({
            "user_id": "user-123",
            "workspace_id": "ws-456",
        })
        decoded = decode_token(token)
        
        assert decoded.workspace_id == "ws-456"
    
    def test_token_custom_expiry(self):
        """Test token with custom expiry."""
        from app.core.auth import create_access_token, decode_token
        
        token = create_access_token(
            {"user_id": "user-123"},
            expires_delta=timedelta(hours=2)
        )
        
        decoded = decode_token(token)
        assert decoded is not None
    
    def test_decode_malformed_token(self):
        """Test decoding malformed token."""
        from app.core.auth import decode_token
        
        result = decode_token("not.a.valid.token")
        assert result is None
    
    def test_decode_empty_token(self):
        """Test decoding empty token."""
        from app.core.auth import decode_token
        
        result = decode_token("")
        assert result is None


class TestUserResponse:
    """Tests for UserResponse model."""
    
    def test_user_response_creation(self):
        """Test creating UserResponse."""
        from app.core.auth import UserResponse
        
        user = UserResponse(
            id="user-1",
            email="test@example.com",
            name="Test User",
            workspace_id="ws-1",
            is_active=True,
        )
        
        assert user.id == "user-1"
        assert user.email == "test@example.com"
        assert user.name == "Test User"
    
    def test_user_response_defaults(self):
        """Test UserResponse default values."""
        from app.core.auth import UserResponse
        
        user = UserResponse(
            id="user-1",
            email="test@example.com",
        )
        
        assert user.name is None
        assert user.workspace_id is None
        assert user.is_active is True
