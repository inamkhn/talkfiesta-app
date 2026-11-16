"""Offline delivery, lease and recovery checks (no broker/provider/database)."""

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.modules.jobs import content_runner, outbox
from app.workers import dispatch_outbox, recover_jobs

NOW = datetime(2026, 11, 16, tzinfo=UTC)


def job(**overrides):
    values = {
        "id": uuid4(),
        "parent_job_id": uuid4(),
        "job_type": "CONTENT_AUTHORING",
        "generation_batch_key": "batch_test",
        "status": "PENDING",
        "attempts": 0,
        "lease_expires_at": None,
        "next_attempt_at": None,
        "cancel_requested_at": None,
        "created_at": NOW - timedelta(hours=1),
        "claim_token": None,
    }
    return SimpleNamespace(**(values | overrides))


def fake_session(monkeypatch, module, values):
    db = Mock()
    db.scalar.side_effect = values

    @contextmanager
    def begin():
        yield db

    monkeypatch.setattr(module, "SyncSessionLocal", SimpleNamespace(begin=begin))
    return db


@pytest.fixture(autouse=True)
def enable_content(monkeypatch):
    monkeypatch.setattr(content_runner.settings, "content_generation_enabled", True)


def test_dispatch_routes_only_job_id_to_content_queue(monkeypatch):
    claim = outbox.DispatchClaim(uuid4(), uuid4(), uuid4(), "CONTENT_AUTHORING")
    monkeypatch.setattr(dispatch_outbox, "require_handler", lambda: None)
    monkeypatch.setattr(dispatch_outbox, "claim_next", Mock(side_effect=[claim, None]))
    send = Mock()
    monkeypatch.setattr(dispatch_outbox.celery_app, "send_task", send)
    monkeypatch.setattr(dispatch_outbox, "mark_published", lambda _: True)
    assert dispatch_outbox.dispatch_batch() == 1
    assert send.call_args.args == ("talkfiesta.content.generate_unit",)
    assert send.call_args.kwargs["queue"] == "talkfiesta.content_generation"
    assert send.call_args.kwargs["args"] == [str(claim.job_id)]


@pytest.mark.parametrize("valid", [True, False])
def test_outbox_checks_parent_binding_and_orders_days(monkeypatch, valid):
    child = job()
    event = SimpleNamespace(
        id=uuid4(),
        ai_job_id=child.id,
        attempt_count=0,
        event_type="CONTENT_GENERATION_REQUESTED",
        payload={
            "job_id": str(child.id),
            "parent_job_id": str(child.parent_job_id if valid else uuid4()),
            "generation_batch_key": child.generation_batch_key,
        },
    )
    db = fake_session(monkeypatch, outbox, [NOW, event])
    db.get.return_value = child
    claim = outbox.claim_next()
    query = db.scalar.call_args_list[1].args[0]
    sql = str(query.compile(dialect=postgresql.dialect()))
    assert "EXISTS" in sql and "ai_jobs_1.attempts" in sql
    if valid:
        assert claim.job_type == "CONTENT_AUTHORING"
        assert event.attempt_count == 1
    else:
        assert claim is None
        assert event.last_error_code == "INVALID_EVALUATION_EVENT"


def test_claim_respects_global_active_slot(monkeypatch):
    child = job()
    fake_session(monkeypatch, content_runner, [child, NOW, uuid4()])
    assert content_runner.claim_job(child.id) is None
    assert child.attempts == 0


def test_claim_assigns_lease_and_counts_once(monkeypatch):
    child = job()
    fake_session(monkeypatch, content_runner, [child, NOW, None])
    claim = content_runner.claim_job(child.id)
    assert claim.job_id == child.id
    assert child.status == "RUNNING" and child.attempts == 1
    assert child.lease_expires_at > NOW


@pytest.mark.parametrize("exhausted", [False, True])
def test_expired_worker_retries_or_fails(monkeypatch, exhausted):
    attempts = content_runner.settings.content_job_max_attempts if exhausted else 1
    child = job(
        status="RUNNING",
        attempts=attempts,
        lease_expires_at=NOW - timedelta(seconds=1),
        claim_token=uuid4(),
    )
    db = fake_session(monkeypatch, content_runner, [child, NOW])
    assert content_runner.recover_job(child.id)
    assert child.status == ("FAILED" if exhausted else "RETRYABLE")
    assert child.claim_token is None
    db.add.assert_not_called()


def test_due_retry_creates_one_bound_event(monkeypatch):
    child = job(status="RETRYABLE", attempts=1, next_attempt_at=NOW)
    db = fake_session(monkeypatch, content_runner, [child, NOW, None, NOW])
    assert content_runner.recover_job(child.id)
    event = db.add.call_args.args[0]
    assert event.payload["parent_job_id"] == str(child.parent_job_id)
    assert event.payload["generation_batch_key"] == child.generation_batch_key
    assert child.status == "PENDING" and child.attempts == 1


def test_unpublished_or_quarantined_event_is_not_duplicated(monkeypatch):
    child = job(status="RETRYABLE", attempts=1)
    db = fake_session(monkeypatch, content_runner, [child, NOW, uuid4()])
    assert not content_runner.recover_job(child.id)
    db.add.assert_not_called()


@pytest.mark.parametrize("recent", [True, False])
def test_pending_redelivery_waits_visibility_deadline(monkeypatch, recent):
    child = job()
    published = NOW if recent else NOW - timedelta(hours=1)
    db = fake_session(monkeypatch, content_runner, [child, NOW, None, published])
    assert content_runner.recover_job(child.id) is not recent
    assert db.add.call_count == (0 if recent else 1)


def test_live_lease_and_terminal_success_are_untouched(monkeypatch):
    for child in [
        job(status="RUNNING", lease_expires_at=NOW + timedelta(minutes=1)),
        job(status="SUCCEEDED"),
    ]:
        db = fake_session(monkeypatch, content_runner, [child, NOW])
        assert not content_runner.recover_job(child.id)
        db.add.assert_not_called()


def test_recovery_scan_excludes_parent_jobs(monkeypatch):
    db = Mock()
    db.execute.return_value = []

    @contextmanager
    def session():
        yield db

    monkeypatch.setattr(recover_jobs, "SyncSessionLocal", session)
    assert recover_jobs.recover_batch() == 0
    sql = str(db.execute.call_args.args[0].compile(dialect=postgresql.dialect()))
    assert "ai_jobs.parent_job_id IS NOT NULL" in sql
    assert (
        recover_jobs.RECOVERY_HANDLERS["CONTENT_AUTHORING"]
        is content_runner.recover_job
    )
