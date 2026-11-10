# POST /api/v1/speaking/submissions

Creates or reuses a recording draft for the authenticated learner's current
Speaking lesson. Requires `Idempotency-Key` (1–128 letters, digits, `.`, `_`, `:`
or `-`) and JSON `{ "content_item_id": "<assigned lesson UUID>" }`.
Unknown body fields are rejected. Rate limit: 60 requests per user per hour,
using the existing Redis rate limiter.

Returns 201 for creation or 200 for an existing active draft. The response has
submission_id, mode=RECORDED_SPEAKING, status=DRAFT,
evaluation_status=NOT_REQUIRED, content_item_id, media_upload_id and created_at.
New drafts have input={}, revision_number=1 and no media. Reused drafts retain
their existing media reference. Responses use `Cache-Control: private, no-store`.

The transaction locks the user, active plan/Speaking progress, assigned published
content (shared lock), and existing draft in that order. Future speaking submit
and progress writers must follow this same order. It rechecks the account,
onboarding, enrollment, current pinned lesson, and existing activity credits.
No activity credit, progress advance, upload or AI job is created.

Durable per-user key hashes map to the requested content and returned submission.
The same key cannot be reused with another content ID. Different keys for the
same current activity reuse its active draft and are remembered too. Key and
draft writes commit together. Replays revalidate current eligibility: a completed
activity or stale assignment returns 409; a key pointing to an inactive draft
cannot silently allocate another draft. Creation failures roll back the entire
transaction.

Errors include the existing authentication/onboarding/plan/lesson errors, plus:

- 409 IDEMPOTENCY_KEY_REUSED: same key, different content.
- 409 ACTIVITY_ALREADY_COMPLETED: Speaking completed, or requested activity has
  an owned credit in the current Speaking enrollment.
- 409 ACTIVITY_NOT_CURRENT: requested content is not the current assignment.
- 409 DRAFT_NO_LONGER_ACTIVE: the key's original draft is no longer active.
- 422: missing/invalid key or payload.
- 429: request rate limit exceeded.

Migration `20261104_speaking_drafts` adds speaking_draft_requests and the partial
unique index uq_speaking_active_draft on progress/content for recording drafts.
Apply it with `python -m alembic upgrade head` from backend before using this
endpoint. It extends the existing V4 schema; it does not bootstrap an empty DB.
If historical duplicate active drafts exist, index creation fails rather than
silently deleting or changing learner records; reconcile those before migration.

Validation: lint, imports, OpenAPI, PostgreSQL table/index DDL compilation and
Alembic revision graph. No tests, live database checks or migrations were run.
