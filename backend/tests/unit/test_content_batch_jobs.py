"""Unit tests for Phase 2 Content Factory batch jobs, outbox expansion, and lifecycle state."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.modules.jobs.content_runner import (
    create_content_generation_batch,
    default_release_key,
    derive_batch_status,
)
from app.modules.jobs.models import AiJob, OutboxEvent


class _FakeAsyncSession:
    """Minimal async session double to verify atomic batch + outbox creation."""

    def __init__(self, *, existing_parent: AiJob | None = None, existing_children=None):
        self.added: list[object] = []
        self.flushed = 0
        self.existing_parent = existing_parent
        self.existing_children = existing_children or []

    async def scalar(self, _stmt):
        return self.existing_parent

    async def scalars(self, _stmt):
        return list(self.existing_children)

    def add(self, obj: object) -> None:
        self.added.append(obj)

    def add_all(self, objs: list[object]) -> None:
        self.added.extend(objs)

    async def flush(self) -> None:
        self.flushed += 1


def test_default_release_key_format() -> None:
    assert (
        default_release_key("B1", 1, "GENERAL", "VOCABULARY")
        == "B1-C1-GENERAL-VOCABULARY-v1"
    )
    assert (
        default_release_key("B2", 2, "BUSINESS", "SPEAKING", version=3)
        == "B2-C2-BUSINESS-SPEAKING-v3"
    )


def test_derive_batch_status_all_states() -> None:
    def _jobs(*statuses: str):
        return [SimpleNamespace(status=s) for s in statuses]

    assert derive_batch_status(_jobs("PENDING", "PENDING")) == "PENDING"
    assert derive_batch_status(_jobs("SUCCEEDED", "RUNNING")) == "RUNNING"
    assert derive_batch_status(_jobs("SUCCEEDED", "RETRYABLE")) == "RUNNING"
    assert derive_batch_status(_jobs("SUCCEEDED", "FAILED")) == "GENERATION_FAILED"
    assert derive_batch_status(_jobs("SUCCEEDED", "SUCCEEDED")) == "GENERATION_COMPLETE"

    reviewer = uuid4()
    assert (
        derive_batch_status(
            _jobs("SUCCEEDED"),
            item_statuses=[("REVIEW", None), ("REVIEW", None)],
        )
        == "READY_FOR_REVIEW"
    )
    assert (
        derive_batch_status(
            _jobs("SUCCEEDED"),
            item_statuses=[("REVIEW", reviewer), ("REVIEW", None)],
        )
        == "AWAITING_APPROVAL"
    )
    assert (
        derive_batch_status(
            _jobs("SUCCEEDED"),
            item_statuses=[("REVIEW", reviewer), ("REVIEW", reviewer)],
        )
        == "READY_TO_PUBLISH"
    )
    assert (
        derive_batch_status(
            _jobs("SUCCEEDED"),
            item_statuses=[("PUBLISHED", reviewer), ("PUBLISHED", reviewer)],
        )
        == "PUBLISHED"
    )


async def test_create_content_generation_batch_expands_children_and_outbox() -> None:
    db = _FakeAsyncSession()
    admin_id = uuid4()

    parent, children = await create_content_generation_batch(
        db,  # type: ignore[arg-type]
        admin_user_id=admin_id,
        cefr_level="B1",
        cycle=1,
        modules=["VOCABULARY", "SPEAKING", "WRITING"],
        day_start=1,
        day_end=5,
        goal_variant="GENERAL",
        idempotency_key="admin-req-1",
        dry_run=True,
    )

    assert parent.job_type == "CONTENT_AUTHORING"
    assert parent.parent_job_id is None
    assert parent.generation_batch_key is not None
    assert len(children) == 15  # 3 modules x 5 days

    ai_jobs = [obj for obj in db.added if isinstance(obj, AiJob)]
    outbox = [obj for obj in db.added if isinstance(obj, OutboxEvent)]
    assert len(ai_jobs) == 16  # 1 parent + 15 children
    assert len(outbox) == 15
    assert all(ev.event_type == "CONTENT_GENERATION_REQUESTED" for ev in outbox)
    assert all(child.parent_job_id == parent.id for child in children)
    assert db.flushed == 2


async def test_create_content_generation_batch_is_idempotent_and_validates_range() -> (
    None
):
    admin_id = uuid4()
    existing_parent, original_children = await create_content_generation_batch(
        _FakeAsyncSession(),
        admin_user_id=admin_id,
        cefr_level="B1",
        cycle=1,
        modules=["VOCABULARY"],
        day_start=1,
        day_end=3,
        idempotency_key="replay-key",
    )
    existing_child = original_children[0]
    db = _FakeAsyncSession(
        existing_parent=existing_parent, existing_children=[existing_child]
    )

    parent, children = await create_content_generation_batch(
        db,  # type: ignore[arg-type]
        admin_user_id=admin_id,
        cefr_level="B1",
        cycle=1,
        modules=["VOCABULARY"],
        day_start=1,
        day_end=3,
        idempotency_key="replay-key",
    )
    assert parent.id == existing_parent.id
    assert len(children) == 1
    assert db.added == []

    with pytest.raises(ValueError, match="day_start and day_end"):
        await create_content_generation_batch(
            _FakeAsyncSession(),  # type: ignore[arg-type]
            admin_user_id=uuid4(),
            cefr_level="B1",
            cycle=1,
            modules=["VOCABULARY"],
            day_start=6,
            day_end=2,
            idempotency_key="bad-range",
        )
