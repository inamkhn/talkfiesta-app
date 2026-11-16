"""Pilot bounds, request identity, authorization and transaction safety."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.api.deps import get_current_user, get_db
from app.core.exceptions import ConflictError
from app.main import app
from app.modules.content.admin_schemas import CreateBatchRequest
from app.modules.content.admin_service import ContentBatchService
from app.modules.jobs.content_runner import create_content_generation_batch
from app.modules.jobs.models import OutboxEvent
from tests.unit.test_content_batch_jobs import _FakeAsyncSession


@pytest.mark.parametrize(
    "fields",
    [
        {"day_start": 1, "day_end": 6},
        {"day_start": 5, "day_end": 1},
        {"day_start": 0, "day_end": 2},
        {"day_start": 20, "day_end": 22},
        {"day_start": True, "day_end": 2},
        {"day_start": 1, "day_end": 5, "module": "SPEAKING"},
        {"day_start": 1, "day_end": 5, "release_key": "other-release"},
    ],
)
def test_pilot_rejects_invalid_scope(fields):
    with pytest.raises(ValidationError):
        CreateBatchRequest(**fields)


def test_final_day_and_five_days_are_valid():
    assert CreateBatchRequest(day_start=21, day_end=21).day_start == 21
    assert CreateBatchRequest(day_start=1, day_end=5).day_end == 5


async def test_request_identity_is_scoped_and_payload_checked():
    admin = uuid4()
    args = {
        "admin_user_id": admin,
        "cefr_level": "B1",
        "cycle": 1,
        "modules": ["VOCABULARY"],
        "day_start": 1,
        "day_end": 5,
        "idempotency_key": "same",
    }
    parent, children = await create_content_generation_batch(
        _FakeAsyncSession(), **args
    )
    other, _ = await create_content_generation_batch(
        _FakeAsyncSession(), **{**args, "admin_user_id": uuid4()}
    )
    assert parent.idempotency_key != other.idempotency_key
    with pytest.raises(ConflictError):
        await create_content_generation_batch(
            _FakeAsyncSession(existing_parent=parent, existing_children=children),
            **{**args, "day_end": 4},
        )


async def test_overlap_rolls_back(monkeypatch):
    parent = SimpleNamespace(id=uuid4(), generation_batch_key="batch_test")
    monkeypatch.setattr(
        "app.modules.content.admin_service.create_content_generation_batch",
        AsyncMock(return_value=(parent, [])),
    )
    db = AsyncMock()
    db.scalar.side_effect = [uuid4(), None]
    with pytest.raises(ConflictError, match="already have"):
        await ContentBatchService(db).create(
            uuid4(), CreateBatchRequest(day_start=1, day_end=5), "key"
        )
    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()


async def test_learner_cannot_create_or_read_batches():
    async def unused_db():
        yield AsyncMock()

    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role="LEARNER")
    app.dependency_overrides[get_db] = unused_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            created = await client.post(
                "/api/v1/admin/content-generation/batches",
                json={"day_start": 1, "day_end": 5},
                headers={"Idempotency-Key": "test"},
            )
            read = await client.get(
                "/api/v1/admin/content-generation/batches/batch_test"
            )
        assert created.status_code == read.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_outbox_has_no_unmigrated_batch_columns():
    assert "job_context" not in OutboxEvent.__table__.columns
