# POST /api/v1/speaking/submissions/{submission_id}/submit

Requires Bearer authentication, Idempotency-Key and JSON
`{ "media_upload_id": "<currently attached verified upload UUID>" }`.
Unknown body fields are rejected. Rate limit: 60 requests/hour/user.

202 returns submission_id, activity_status=COMPLETED, evaluation_status=PENDING,
job_id, credited_day, next_speaking_day and submission_url. It sets Location to
submission_url and Cache-Control to private, no-store. At day 21,
next_speaking_day is null; current_day stays 21 and module status becomes COMPLETED.

## Acceptance transaction

1. Lock and recheck the user; resolve only an owned recorded-speaking submission.
2. Check durable idempotency receipts. Equivalent accepted retries return the
   original receipt, including after progress moves or audio retention expires.
   New keys for the same accepted recording are also remembered. Changed media
   or a key reused for another request returns 409 IDEMPOTENCY_CONFLICT.
3. For new acceptance, use the same user -> plan/progress -> content -> draft ->
   upload lock order as allocation/confirmation. Require an active current draft,
   the pinned published lesson, and no existing activity credit.
4. Validate exact upload binding, owner, purpose SPEAKING, status VERIFIED,
   verified timestamp, unexpired retention, WebM MIME, recorded size/checksum
   metadata, and current Speaking size/duration limits. Reject audio already
   attached to any other ACCEPTED submission.
5. Require credited pinned days to be exactly 1 through current_day minus one.
   Refuse inconsistent progress instead of manufacturing missing credits.
6. Set ACCEPTED/PENDING, submitted_at and server-controlled recording/content
   metadata. Insert one completion credit using the user's current timezone and
   acceptance timestamp. Duration is floored to whole seconds for the integer
   completion duration column; the exact decimal remains on media and input.
7. Advance only Speaking, or mark it COMPLETED at day 21. Other modules and the
   plan lifecycle remain unchanged. No next cycle or content is generated here.
8. Insert one SPEAKING_FEEDBACK AI job, one SPEAKING_FEEDBACK_REQUESTED outbox
   event, and the durable response receipt. Commit once; any failure rolls back
   acceptance, credit, progress, job, event and receipt together.

Existing unique completion constraints prevent duplicate progress credits; the
job key is speaking:<submission_id>:feedback:v1. Network provider calls are not
made in this transaction. The response is an immutable acceptance receipt, not
live evaluation status; a retry still returns its original PENDING receipt.

## Integration status

The dispatcher routes SPEAKING_FEEDBACK_REQUESTED to the Speaking worker when
SPEAKING_EXECUTION_ENABLED=true. See speaking-worker.md for deployment and
recovery. When disabled these events remain unpublished. Poll submission_url
using the owner-scoped GET endpoint documented in speaking-results.md.

Migration 20261104_speaking_submit adds durable acceptance receipts. Apply
`python -m alembic upgrade head` from backend before using this endpoint. Media
UUIDs in receipts deliberately have no FK so retention cannot invalidate an
acceptance receipt. Existing V4 schema and prior migrations are prerequisites.

Checks: lint, imports, OpenAPI, PostgreSQL receipt-table DDL compilation and
Alembic revision graph. No tests, live database operations or migrations ran.
