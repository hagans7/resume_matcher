"""Unit tests for atomic batch completion — Fix 1 race condition."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, call

import pytest

from src.core.constants.app_constants import (
    BATCH_STATUS_COMPLETED,
    BATCH_STATUS_PARTIAL_FAILURE,
    BATCH_STATUS_PROCESSING,
)
from src.entities.batch import Batch


def _make_batch(succeeded=0, failed=0, total=3) -> Batch:
    return Batch(
        id="batch-001",
        job_id="job-001",
        total=total,
        succeeded=succeeded,
        failed=failed,
        status=BATCH_STATUS_PROCESSING,
        created_at=datetime.now(timezone.utc),
    )


class TestAtomicIncrementInterface:
    """Verify atomic_increment_and_finalize is called instead of separate increment + check."""

    async def test_evaluate_single_calls_atomic_not_separate_increment(self):
        """evaluate_single_task must use atomic_increment_and_finalize, not increment_succeeded."""
        import inspect
        from src.tasks import evaluate_single_task
        source = inspect.getsource(evaluate_single_task)

        # Must use atomic method
        assert "atomic_increment_and_finalize" in source, (
            "Fix 1 regression: evaluate_single_task must use atomic_increment_and_finalize"
        )

    async def test_mark_failed_calls_atomic_not_separate_increment(self):
        """_mark_failed must use atomic_increment_and_finalize, not increment_failed."""
        import inspect
        from src.tasks import evaluate_single_task
        source = inspect.getsource(evaluate_single_task._mark_failed)

        assert "atomic_increment_and_finalize" in source, (
            "Fix 1 regression: _mark_failed must use atomic_increment_and_finalize"
        )

    async def test_no_python_level_completion_check_in_task(self):
        """Completion check must be in SQL, not in Python after increment."""
        import inspect
        from src.tasks import evaluate_single_task
        source = inspect.getsource(evaluate_single_task._run_evaluation)

        # Should NOT call the old separate methods
        assert "increment_succeeded" not in source, (
            "Fix 1 regression: increment_succeeded called separately (use atomic instead)"
        )
        assert "increment_failed" not in source, (
            "Fix 1 regression: increment_failed called separately (use atomic instead)"
        )
        assert "_check_batch_complete" not in source, (
            "Fix 1 regression: _check_batch_complete is Python-level check — removed in Fix 1"
        )


class TestBatchEntityCompletion:
    """Verify Batch entity logic is consistent with SQL atomic logic."""

    def test_completed_when_all_succeed(self):
        b = _make_batch(succeeded=3, failed=0, total=3)
        assert b.resolve_final_status() == BATCH_STATUS_COMPLETED

    def test_partial_failure_when_some_fail(self):
        b = _make_batch(succeeded=2, failed=1, total=3)
        assert b.resolve_final_status() == BATCH_STATUS_PARTIAL_FAILURE

    def test_not_complete_when_pending(self):
        b = _make_batch(succeeded=1, failed=0, total=3)
        assert not b.is_complete()

    def test_complete_when_all_processed(self):
        b = _make_batch(succeeded=2, failed=1, total=3)
        assert b.is_complete()


class TestAsyncEngineSharing:
    """Fix 2: verify shared engine is not recreated per task."""

    def test_module_level_engine_exists(self):
        from src.tasks.evaluate_single_task import _async_engine, _async_session_factory
        assert _async_engine is not None
        assert _async_session_factory is not None

    def test_process_batch_imports_shared_factory(self):
        """process_batch_task must import shared factory, not create its own engine."""
        import inspect
        from src.tasks import process_batch_task
        source = inspect.getsource(process_batch_task)

        assert "create_async_engine" not in source, (
            "Fix 2 regression: process_batch_task creates its own async engine"
        )
        assert "_async_session_factory" in source, (
            "Fix 2 regression: process_batch_task must use shared _async_session_factory"
        )

    def test_evaluate_single_no_per_task_engine_creation_in_helpers(self):
        """_mark_failed must not create new engines — uses shared factory."""
        import inspect
        from src.tasks.evaluate_single_task import _mark_failed
        source = inspect.getsource(_mark_failed)

        assert "create_async_engine" not in source, (
            "Fix 2 regression: _mark_failed creates its own engine per call"
        )
        assert "_async_session_factory" in source
