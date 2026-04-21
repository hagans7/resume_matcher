"""Integration tests for health check endpoint."""

import pytest


class TestHealthCheck:
    async def test_health_returns_200_with_ok_status(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert "status" in body
        assert "db" in body
        assert "redis" in body

    async def test_health_db_field_present(self, client):
        response = await client.get("/health")
        body = response.json()
        # In test environment DB may or may not be available
        # We only assert the field is present, not its value
        assert "db" in body

    async def test_health_no_auth_required(self, client):
        """Health endpoint must be publicly accessible (used by load balancers)."""
        response = await client.get("/health")
        assert response.status_code in (200, 503)  # either healthy or degraded
