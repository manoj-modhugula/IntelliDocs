"""
Tests for health endpoint.
"""

import pytest


@pytest.mark.asyncio
async def test_health_endpoint(async_client):
    """Test that health endpoint returns healthy status."""
    response = await async_client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "intellidocs-api"


@pytest.mark.asyncio
async def test_health_endpoint_returns_json(async_client):
    """Test that health endpoint returns JSON content type."""
    response = await async_client.get("/health")
    
    assert "application/json" in response.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_ready_endpoint(async_client):
    """Test readiness check returns database status."""
    response = await async_client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "checks" in data
    assert "database" in data["checks"]
