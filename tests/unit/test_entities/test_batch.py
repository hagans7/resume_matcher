"""Unit tests for Batch entity."""

from datetime import datetime, timezone

import pytest

from src.core.constants.app_constants import BATCH_STATUS_COMPLETED, BATCH_STATUS_PARTIAL_FAILURE
from src.entities.batch import Batch


def _make_batch(**kwargs) -> Batch:
    defaults = dict(
        id="b1",
        job_id="j1",
        total=10,
        succeeded=0,
        failed=0,
        status="processing",
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    return Batch(**defaults)


class TestBatchProgressPercent:
    def test_zero_when_total_zero(self):
        b = _make_batch(total=0)
        assert b.progress_percent() == 0

    def test_full_progress(self):
        b = _make_batch(total=10, succeeded=10)
        assert b.progress_percent() == 100

    def test_partial_progress(self):
        b = _make_batch(total=10, succeeded=5, failed=2)
        assert b.progress_percent() == 70

    def test_rounds_correctly(self):
        b = _make_batch(total=3, succeeded=1)
        assert b.progress_percent() == 33


class TestBatchIsComplete:
    def test_not_complete_when_pending(self):
        b = _make_batch(total=10, succeeded=5, failed=2)
        assert b.is_complete() is False

    def test_complete_all_succeeded(self):
        b = _make_batch(total=5, succeeded=5, failed=0)
        assert b.is_complete() is True

    def test_complete_with_failures(self):
        b = _make_batch(total=5, succeeded=3, failed=2)
        assert b.is_complete() is True


class TestBatchResolveFinalStatus:
    def test_completed_when_no_failures(self):
        b = _make_batch(total=5, succeeded=5, failed=0)
        assert b.resolve_final_status() == BATCH_STATUS_COMPLETED

    def test_partial_failure_when_some_failed(self):
        b = _make_batch(total=5, succeeded=3, failed=2)
        assert b.resolve_final_status() == BATCH_STATUS_PARTIAL_FAILURE

    def test_raises_when_not_complete(self):
        b = _make_batch(total=10, succeeded=5, failed=0)
        with pytest.raises(ValueError, match="not complete"):
            b.resolve_final_status()
