import uuid
from httpx import AsyncClient, ASGITransport

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from typing import AsyncGenerator, Generator

from main import app
from src.core.database import get_db
from src.models.job import Job, JobStatus, JobType
from src.core.rate_limiter import limiter


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client for the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost") as client:
        yield client


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session for assertions."""
    async for session in get_db():
        yield session
        break  # Only need one session


@pytest.fixture(autouse=True)
def disable_rate_limiter() -> Generator[None, None, None]:
    """Disable rate limiting for tests."""
    limiter.enabled = False
    yield
    limiter.enabled = True


@pytest_asyncio.fixture
async def auth_token(async_client: AsyncClient) -> str:
    """Register a user and login to get a JWT access token."""
    # Register a unique user for this test
    test_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    test_password = "TestPass123!"

    # Register
    register_response = await async_client.post(
        "/auth/register",
        json={"email": test_email, "password": test_password},
    )
    assert register_response.status_code == 201, register_response.text

    # Login
    login_response = await async_client.post(
        "/auth/login",
        json={"email": test_email, "password": test_password},
    )
    assert login_response.status_code == 200, login_response.text

    token_data: dict[str, str] = login_response.json()
    return token_data["access_token"]


class TestJobEnqueueIntegration:
    """Integration tests for job enqueue via the API."""

    @pytest.mark.asyncio
    async def test_enqueue_email_job_creates_pending_job_in_db(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        auth_token: str,
    ) -> None:
        """
        Enqueue an email job and verify it's created with status 'pending' in PostgreSQL.
        """
        # Prepare email job payload
        email_payload = {
            "recipient": "test@example.com",
            "subject": "Test Email",
            "body": "This is a test email body.",
        }

        # Send request to enqueue email job
        response = await async_client.post(
            "/jobs/email",
            json=email_payload,
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        # Assert response is 202 Accepted
        assert response.status_code == 202, response.text

        response_data = response.json()
        assert "id" in response_data
        job_id = response_data["id"]
        assert uuid.UUID(job_id)  # Validate it's a valid UUID

        # Assert response contains expected fields
        assert response_data["job_type"] == "email"
        assert response_data["status"] == "pending"
        assert response_data["priority"] == 5
        assert response_data["retry_count"] == 0
        assert "created_at" in response_data
        assert "updated_at" in response_data

        # Query the database directly to confirm the job exists with status 'pending'
        db_job = await db_session.get(Job, uuid.UUID(job_id))
        assert db_job is not None, "Job should exist in database"

        assert db_job.job_type == JobType.EMAIL.value
        assert db_job.status == JobStatus.PENDING.value
        assert db_job.priority == 5
        assert db_job.retry_count == 0
        assert db_job.error_message is None
        assert db_job.result is None
        assert db_job.payload is not None
        assert db_job.payload["recipient"] == email_payload["recipient"]
        assert db_job.payload["subject"] == email_payload["subject"]
        assert db_job.payload["body"] == email_payload["body"]
        assert db_job.celery_task_id is not None  # Should be set after Celery enqueue

    @pytest.mark.asyncio
    async def test_enqueue_email_job_without_auth_returns_401(
        self,
        async_client: AsyncClient,
    ) -> None:
        """
        Enqueue an email job without authentication should return 401.
        """
        email_payload = {
            "recipient": "test@example.com",
            "subject": "Test Email",
            "body": "This is a test email body.",
        }

        response = await async_client.post(
            "/jobs/email",
            json=email_payload,
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_enqueue_email_job_with_invalid_payload_returns_422(
        self,
        async_client: AsyncClient,
        auth_token: str,
    ) -> None:
        """
        Enqueue an email job with invalid payload should return 422.
        """
        # Missing required fields
        email_payload = {
            "recipient": "not-an-email",
            "subject": "",
        }

        response = await async_client.post(
            "/jobs/email",
            json=email_payload,
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_enqueue_image_job_creates_pending_job_in_db(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        auth_token: str,
    ) -> None:
        """
        Enqueue an image job and verify it's created with status 'pending' in PostgreSQL.
        """
        # Note: This test assumes the file exists in tmp/uploads
        # In a real scenario, we'd need to upload a file first
        # For this test, we just verify the enqueue endpoint works
        image_payload = {
            "filename": "test_image.jpg",
            "operations": ["grayscale"],
            "output_format": "jpeg",
        }

        response = await async_client.post(
            "/jobs/image",
            json=image_payload,
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status_code == 202, response.text
        response_data = response.json()

        assert "id" in response_data
        job_id = response_data["id"]

        # Verify in database
        db_job = await db_session.get(Job, uuid.UUID(job_id))
        assert db_job is not None
        assert db_job.job_type == JobType.IMAGE.value
        assert db_job.status == JobStatus.PENDING.value

    @pytest.mark.asyncio
    async def test_enqueue_report_job_creates_pending_job_in_db(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        auth_token: str,
    ) -> None:
        """
        Enqueue a report job and verify it's created with status 'pending' in PostgreSQL.
        """
        report_payload = {
            "report_type": "csv",
            "dataset_id": "test_dataset",
            "filters": {"status": "active"},
        }

        response = await async_client.post(
            "/jobs/report",
            json=report_payload,
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status_code == 202, response.text
        response_data = response.json()

        assert "id" in response_data
        job_id = response_data["id"]

        # Verify in database
        db_job = await db_session.get(Job, uuid.UUID(job_id))
        assert db_job is not None
        assert db_job.job_type == JobType.REPORT.value
        assert db_job.status == JobStatus.PENDING.value

    @pytest.mark.asyncio
    async def test_get_job_status_returns_correct_data(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        auth_token: str,
    ) -> None:
        """
        Enqueue a job and then fetch its status via GET /jobs/{id}.
        """
        # First enqueue a job
        email_payload = {
            "recipient": "test@example.com",
            "subject": "Test Email for GET",
            "body": "Testing GET endpoint.",
        }

        enqueue_response = await async_client.post(
            "/jobs/email",
            json=email_payload,
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert enqueue_response.status_code == 202
        job_id = enqueue_response.json()["id"]

        # Now fetch the job status
        get_response = await async_client.get(
            f"/jobs/{job_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert get_response.status_code == 200
        job_data = get_response.json()

        assert job_data["id"] == job_id
        assert job_data["job_type"] == "email"
        assert job_data["status"] == "pending"
        assert job_data["priority"] == 5

    @pytest.mark.asyncio
    async def test_get_job_detail_returns_payload_and_result(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        auth_token: str,
    ) -> None:
        """
        Enqueue a job and fetch its detail via GET /jobs/{id}/detail.
        """
        email_payload = {
            "recipient": "detail@example.com",
            "subject": "Test Detail",
            "body": "Testing detail endpoint.",
        }

        enqueue_response = await async_client.post(
            "/jobs/email",
            json=email_payload,
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert enqueue_response.status_code == 202
        job_id = enqueue_response.json()["id"]

        # Fetch detail
        detail_response = await async_client.get(
            f"/jobs/{job_id}/detail",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert detail_response.status_code == 200
        detail_data = detail_response.json()

        assert detail_data["id"] == job_id
        assert detail_data["job_type"] == "email"
        assert detail_data["status"] == "pending"
        assert "payload" in detail_data
        assert detail_data["payload"]["recipient"] == email_payload["recipient"]
        assert detail_data["result"] is None  # Result is None for pending jobs
