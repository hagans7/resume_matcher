"""Integration tests for job management API endpoints."""

import pytest


class TestCreateJob:
    async def test_create_job_returns_201(self, client):
        response = await client.post(
            "/api/v1/jobs",
            json={
                "title": "Senior Python Developer",
                "description": "We need a Python expert with FastAPI and PostgreSQL skills.",
                "evaluation_mode": "standard",
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert body["success"] is True
        assert body["data"]["title"] == "Senior Python Developer"
        assert body["data"]["evaluation_mode"] == "standard"
        assert body["data"]["status"] == "active"
        assert "id" in body["data"]

    async def test_create_job_defaults_evaluation_mode(self, client):
        response = await client.post(
            "/api/v1/jobs",
            json={
                "title": "Data Analyst",
                "description": "Looking for a data analyst with SQL skills.",
            },
        )
        assert response.status_code == 201
        assert response.json()["data"]["evaluation_mode"] == "standard"

    async def test_create_job_invalid_mode_returns_422(self, client):
        response = await client.post(
            "/api/v1/jobs",
            json={
                "title": "Dev",
                "description": "Some description.",
                "evaluation_mode": "ultra",
            },
        )
        assert response.status_code == 422

    async def test_create_job_empty_title_returns_422(self, client):
        response = await client.post(
            "/api/v1/jobs",
            json={"title": "", "description": "Some description."},
        )
        assert response.status_code == 422

    async def test_create_job_short_description_returns_422(self, client):
        response = await client.post(
            "/api/v1/jobs",
            json={"title": "Dev", "description": "Short"},
        )
        assert response.status_code == 422


class TestListJobs:
    async def test_list_jobs_returns_200(self, client):
        response = await client.get("/api/v1/jobs")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert isinstance(body["data"], list)

    async def test_list_jobs_includes_created_job(self, client):
        # Create a job first
        await client.post(
            "/api/v1/jobs",
            json={"title": "ML Engineer", "description": "We need a machine learning engineer."},
        )
        response = await client.get("/api/v1/jobs")
        assert response.status_code == 200
        titles = [j["title"] for j in response.json()["data"]]
        assert "ML Engineer" in titles


class TestGetJob:
    async def test_get_job_returns_200(self, client):
        # Create job first
        create_resp = await client.post(
            "/api/v1/jobs",
            json={"title": "Backend Dev", "description": "Backend developer needed urgently."},
        )
        job_id = create_resp.json()["data"]["id"]

        response = await client.get(f"/api/v1/jobs/{job_id}")
        assert response.status_code == 200
        assert response.json()["data"]["id"] == job_id

    async def test_get_nonexistent_job_returns_404(self, client):
        response = await client.get("/api/v1/jobs/nonexistent-id")
        assert response.status_code == 404
