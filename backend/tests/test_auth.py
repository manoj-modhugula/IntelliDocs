"""Tests for authentication module."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

from app.core.auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_token,
    TokenData,
)


class TestPasswordHashing:
    """Tests for password hashing."""
    
    def test_hash_password_returns_hash(self):
        """Test that hash_password returns a hash."""
        password = "mypassword123"  # Keep under 72 bytes for bcrypt
        hashed = hash_password(password)
        
        assert hashed != password
        assert len(hashed) > 20
    
    def test_hash_password_different_each_time(self):
        """Test that same password produces different hashes."""
        password = "testpass456"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        
        assert hash1 != hash2  # bcrypt uses random salt
    
    def test_verify_password_correct(self):
        """Test verify_password with correct password."""
        password = "correcthorse"
        hashed = hash_password(password)
        
        assert verify_password(password, hashed) is True
    
    def test_verify_password_incorrect(self):
        """Test verify_password with incorrect password."""
        password = "rightpass"
        hashed = hash_password(password)
        
        assert verify_password("wrongpass", hashed) is False


class TestJWTTokens:
    """Tests for JWT token creation and validation."""
    
    def test_create_access_token_returns_string(self):
        """Test that create_access_token returns a string."""
        token = create_access_token({"user_id": "123", "email": "test@example.com"})
        
        assert isinstance(token, str)
        assert len(token) > 50
    
    def test_create_access_token_with_expiry(self):
        """Test token creation with custom expiry."""
        token = create_access_token(
            {"user_id": "123"},
            expires_delta=timedelta(hours=1)
        )
        
        assert isinstance(token, str)
    
    def test_decode_token_valid(self):
        """Test decoding a valid token."""
        token = create_access_token({
            "user_id": "user-123",
            "email": "test@example.com",
        })
        
        decoded = decode_token(token)
        
        assert decoded is not None
        assert decoded.user_id == "user-123"
        assert decoded.email == "test@example.com"
    
    def test_decode_token_invalid(self):
        """Test decoding an invalid token."""
        decoded = decode_token("invalid.token.here")
        
        assert decoded is None
    
    def test_decode_token_expired(self):
        """Test decoding an expired token."""
        token = create_access_token(
            {"user_id": "123"},
            expires_delta=timedelta(seconds=-1)  # Already expired
        )
        
        decoded = decode_token(token)
        
        assert decoded is None
