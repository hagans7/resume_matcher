"""Unit tests for CancelBatchService."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from src.core.constants.app_constants import (
    BATCH_STATUS_CANCELLED,
    BATCH_STATUS_COMPLETED,
    BATCH_STATUS_PARTIAL_FAILURE,
    BATCH_STATUS_PROCESSING,
    BATCH_STATUS_QUEUED,
)
from src.core.exceptions.app_exceptions import BatchNotFoundError, ValidationError
from src.entities.batch import Batch
from src.services.cancel_batch import CancelBatchService


def _make_batch(status=BATCH_STATUS_PROCESSING) -> Batch:
    return Batch(
        id="batch-001",
        job_id="job-001",
        total=5,
        status=status,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def batch_repo():
    repo = AsyncMock()
    repo.get_by_id.return_value = _make_batch()
    repo.update_status.return_value = None
    return repo


@pytest.fixture
def svc(batch_repo):
    return CancelBatchService(batch_repo=batch_repo)


class TestCancelBatchSuccess:
    async def test_cancels_queued_batch(self, svc, batch_repo):
        batch_repo.get_by_id.return_value = _make_batch(BATCH_STATUS_QUEUED)
        await svc.execute("batch-001")
        batch_repo.update_status.assert_called_once_with("batch-001", BATCH_STATUS_CANCELLED)

    async def test_cancels_processing_batch(self, svc, batch_repo):
        batch_repo.get_by_id.return_value = _make_batch(BATCH_STATUS_PROCESSING)
        await svc.execute("batch-001")
        batch_repo.update_status.assert_called_once_with("batch-001", BATCH_STATUS_CANCELLED)


class TestCancelBatchNotFound:
    async def test_raises_when_batch_not_found(self, svc, batch_repo):
        batch_repo.get_by_id.return_value = None
        with pytest.raises(BatchNotFoundError):
            await svc.execute("nonexistent-batch")

    async def test_no_status_update_when_not_found(self, svc, batch_repo):
        batch_repo.get_by_id.return_value = None
        with pytest.raises(BatchNotFoundError):
            await svc.execute("nonexistent-batch")
        batch_repo.update_status.assert_not_called()


class TestCancelBatchInvalidStatus:
    @pytest.mark.parametrize("terminal_status", [
        BATCH_STATUS_COMPLETED,
        BATCH_STATUS_PARTIAL_FAILURE,
        BATCH_STATUS_CANCELLED,
    ])
    async def test_cannot_cancel_terminal_batch(self, svc, batch_repo, terminal_status):
        batch_repo.get_by_id.return_value = _make_batch(terminal_status)
        with pytest.raises(ValidationError) as exc_info:
            await svc.execute("batch-001")
        assert "cannot be cancelled" in exc_info.value.message
        assert terminal_status in exc_info.value.message

    async def test_validation_error_mentions_valid_statuses(self, svc, batch_repo):
        batch_repo.get_by_id.return_value = _make_batch(BATCH_STATUS_COMPLETED)
        with pytest.raises(ValidationError) as exc_info:
            await svc.execute("batch-001")
        msg = exc_info.value.message
        assert BATCH_STATUS_QUEUED in msg or BATCH_STATUS_PROCESSING in msg