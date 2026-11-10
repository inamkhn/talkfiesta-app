# GET /api/v1/speaking/submissions

Authenticated owner-scoped Speaking history, including earlier plans and
archived lesson titles. No active plan or onboarding-state check is required.
Results contain summaries only, with Cache-Control: private, no-store.

Query parameters:

- limit: integer 1–100, default 20.
- evaluation_status: optional NOT_REQUIRED, PENDING, PROCESSING, COMPLETED or FAILED.
- cursor: optional opaque signed continuation token returned by the preceding page.

200 contains items and next_cursor. Each item contains submission_id,
content_item_id, title, submitted_at, activity_status, evaluation_status and
grammar_score. Empty history returns items=[] and next_cursor=null. Grammar
score is returned only for completed, reviewable feedback; otherwise it is null.
Full transcript/feedback is available through the submission detail endpoint.
No raw input, media location, checksums, prompts or evaluator details are selected.

Only owned RECORDED_SPEAKING submissions are included. Accepted submissions need
a matching completion credit and show COMPLETED even if evaluation failed.
Drafts show IN_PROGRESS/NOT_REQUIRED; rejected records show REJECTED/NOT_REQUIRED.
Malformed saved state returns 503 SPEAKING_HISTORY_UNAVAILABLE.

Ordering is submitted_at DESC NULLS LAST, id DESC, with the UUID providing a
deterministic tie-break. Drafts without submitted_at appear after dated records,
ordered by UUID. One query fetches limit+1 records; the extra record determines
whether a next cursor is needed. There are no offset scans or per-item queries.

Cursors carry a version, timestamp/UUID boundary, authenticated owner, selected
status filter and expiration. HMAC-SHA256 uses the environment JWT signing secret
with a distinct Speaking-history context; a history cursor is not an access
token. The signature is compared in constant time. Cursors expire after 24 hours
and become invalid if the signing secret changes. Payloads are signed, not
encrypted: clients must treat them as opaque. Each query still enforces ownership.

Malformed, tampered, expired, foreign-user and filter-mismatched cursors return
422 INVALID_CURSOR. Invalid limit/status query values also return 422. Keep the
same status filter when continuing; limit may change. Restart without a cursor
when changing filters.

Pages are a live view, not a database snapshot across requests. New submissions
sort before a dated boundary; evaluation status changes or draft acceptance can
move records out of the remaining filtered results. Refresh the first page to
see new/changed items. Concurrent edits do not justify trusting client offsets.

Apply migration 20261105_speaking_history with `python -m alembic upgrade head`
from backend. It adds partial indexes for unfiltered and status-filtered Speaking
history. Existing V4 schema and prior migrations are prerequisites.

Checks: lint, imports, PostgreSQL query/index compilation, OpenAPI and Alembic
revision graph. No tests, live database operations or migrations were run.
