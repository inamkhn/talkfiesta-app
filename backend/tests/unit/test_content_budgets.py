"""Offline budget and manual-retry checks, without event-loop sockets."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from pydantic import BaseModel

from app.core.exceptions import ConflictError
from app.modules.content.admin_schemas import RetryBatchRequest
from app.modules.content.admin_service import ContentBatchService
from app.modules.content.budget import (
    ContentBudgetExceeded,
    remaining_calls,
    reserve_metrics,
)


class Output(BaseModel):
    text: str


def immediate(coro):
    # Session doubles complete immediately; no real asynchronous I/O is permitted.
    try:
        coro.send(None)
    except StopIteration as result:
        return result.value
    finally:
        coro.close()
    raise AssertionError("Unexpected I/O in an offline test")


def test_reservations_survive_new_attempts_and_never_exceed_cap():
    job = SimpleNamespace(job_context={}, metrics={}, attempts=1)
    for _ in range(6):
        assert reserve_metrics(job, Output, "system", "user") == 6000
        job.attempts += 1
    assert remaining_calls(job) == 0
    with pytest.raises(ContentBudgetExceeded):
        reserve_metrics(job, Output, "system", "user")
    assert job.metrics["provider_calls_reserved"] == 6


def test_oversized_input_does_not_reserve_call():
    job = SimpleNamespace(job_context={}, metrics={})
    with pytest.raises(ContentBudgetExceeded):
        reserve_metrics(job, Output, "x" * 60001, "")
    assert job.metrics == {}


def fixture():
    parent = SimpleNamespace(
        id=uuid4(),
        generation_batch_key="batch_x",
        metrics={},
        job_context={"release_keys": {"VOCABULARY": "release"}, "dry_run": False},
    )
    child = SimpleNamespace(
        id=uuid4(),
        status="FAILED",
        attempts=1,
        cancel_requested_at=None,
        metrics={"provider_calls_reserved": 2},
        job_context={"day": 1},
        stage="FAILED",
        last_error_code="GENERATION_FAILED",
        result_summary=None,
    )
    db = AsyncMock()
    db.add = Mock()
    db.scalar.side_effect = [parent, None]
    db.scalars.return_value = [child]
    return parent, child, db


def test_retry_preserves_usage_and_replay_does_not_duplicate_delivery():
    parent, child, db = fixture()
    admin = uuid4()
    request = RetryBatchRequest(
        child_job_ids=[child.id], reason="Provider configuration fixed"
    )
    service = ContentBatchService(db)
    result = immediate(service.retry(admin, "batch_x", request, "key"))
    assert result.children[0].status == "PENDING"
    assert child.attempts == 1 and child.metrics["provider_calls_reserved"] == 2
    assert db.add.call_count == 1
    db.scalar.side_effect = [parent]
    immediate(service.retry(admin, "batch_x", request, "key"))
    assert db.add.call_count == 1
    db.scalar.side_effect = [parent]
    with pytest.raises(ConflictError):
        immediate(
            service.retry(
                admin,
                "batch_x",
                RetryBatchRequest(child_job_ids=[child.id], reason="different"),
                "key",
            )
        )


@pytest.mark.parametrize(
    "status,calls,attempts",
    [
        ("SUCCEEDED", 2, 1),
        ("RUNNING", 2, 1),
        ("RETRYABLE", 2, 1),
        ("FAILED", 6, 1),
        ("FAILED", 2, 100),
    ],
)
def test_ineligible_jobs_cannot_be_requeued(status, calls, attempts):
    _, child, db = fixture()
    child.status, child.attempts = status, attempts
    child.metrics["provider_calls_reserved"] = calls
    with pytest.raises(ConflictError):
        immediate(
            ContentBatchService(db).retry(
                uuid4(),
                "batch_x",
                RetryBatchRequest(child_job_ids=[child.id], reason="Retry"),
                "key",
            )
        )
    db.add.assert_not_called()
    db.commit.assert_not_awaited()
    db.rollback.assert_awaited_once()
