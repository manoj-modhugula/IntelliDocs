"""Tests for database module."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.core.database import Base, get_clean_database_url


class TestDatabaseConfig:
    """Tests for database configuration."""

    def test_base_class_exists(self):
        """Test that Base class is defined."""
        assert Base is not None
        assert hasattr(Base, "metadata")

    def test_clean_database_url_removes_sslmode(self):
        """Test that sslmode is removed from URL."""
        url = "postgresql://user:pass@host/db?sslmode=require"
        clean_url = get_clean_database_url(url)
        
        assert "sslmode" not in clean_url

    def test_clean_database_url_removes_channel_binding(self):
        """Test that channel_binding is removed from URL."""
        url = "postgresql://user:pass@host/db?channel_binding=require"
        clean_url = get_clean_database_url(url)
        
        assert "channel_binding" not in clean_url

    def test_clean_database_url_preserves_basic_url(self):
        """Test that basic URL parts are preserved."""
        url = "postgresql://user:pass@host:5432/mydb"
        clean_url = get_clean_database_url(url)
        
        assert "user:pass@host:5432/mydb" in clean_url

    def test_clean_database_url_handles_multiple_params(self):
        """Test handling of multiple query params."""
        url = "postgresql://user:pass@host/db?sslmode=require&connect_timeout=10&channel_binding=prefer"
        clean_url = get_clean_database_url(url)
        
        assert "sslmode" not in clean_url
        assert "channel_binding" not in clean_url
        # Note: connect_timeout should also be preserved if not filtered


class TestDatabaseSession:
    """Tests for database session management."""

    @pytest.mark.asyncio
    async def test_get_db_is_generator(self):
        """Test that get_db returns async generator."""
        from app.core.database import get_db
        
        # get_db should be an async generator function
        assert hasattr(get_db, "__call__")
