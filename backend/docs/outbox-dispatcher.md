# Transactional outbox dispatcher

This standalone process delivers EVALUATION_REQUESTED events from PostgreSQL to
the talkfiesta.assessments Celery queue. It sends only the persisted job UUID to
task `talkfiesta.assessment.execute`. Learner text and event payloads are not sent.

## Deployment

1. Apply `uv run alembic upgrade head` to the existing V4 database (new revision:
   20261101_outbox_delivery). No migration was run during implementation.
2. Implement/register the actual `talkfiesta.assessment.execute` worker task and
   deploy workers consuming talkfiesta.assessments. This handler is still pending.
3. Set OUTBOX_DISPATCH_ENABLED=true only once those workers are deployed.
4. From backend/, run separately from Celery:

```sh
uv run python -m app.workers.dispatch_outbox
```

For a single bounded batch use `--once`. The process checks both the enabled flag
and local task registration before claiming events. It does not remotely prove
worker availability; deployment must provide consumers using the same code.
Celery Beat is intentionally not required: the database dispatcher must remain
able to record/retry delivery while Redis is down.

## Delivery behavior

- Claim one eligible event under FOR UPDATE SKIP LOCKED; persist a unique claim
  token and lease, increment attempt_count, then commit before network I/O.
- Validate job kind, job/assessment references against the stored event. Invalid
  events are quarantined with failed_at and a sanitized error code.
- Publish once per claim. On confirmed client-side publish success, set
  published_at only if the claim token still matches. An older dispatcher cannot
  acknowledge or overwrite a newer claim.
- Failed publications clear the lease and schedule exponential backoff capped
  near five minutes, with jitter. Exhausted attempts are quarantined, not deleted.
- If the dispatcher dies after claiming, a later poll can reclaim the expired
  lease. If it dies after publishing but before acknowledging in PostgreSQL, the
  same event may be sent again. The task ID is stable but is NOT a Celery dedupe
  mechanism. The forthcoming job runner must claim jobs idempotently.
- PostgreSQL timestamps determine eligibility. No database transaction is held
  open while publishing to Redis. Other event types are left untouched.
- This implements at-least-once publication attempts, not exactly-once execution
  or guaranteed Redis durability. AOF-loss/stuck-job reconciliation remains part
  of the future job-recovery implementation.

Defaults: batch 20, poll every 2 seconds, lease 120 seconds, maximum 20 claims.
A crash counts as a claim attempt. Keep the lease longer than bounded publishing
time. A single corrupt/exhausted event may end that batch; the next poll advances
past it. Ctrl-C/SIGTERM stops after the current operation.

## Operations

Monitor unpublished events, expired leases and failed_at rows. Quarantine does
not discard assessment answers or alter their status. Until job-state recovery
is implemented, an undelivered assessment remains SUBMITTED.

After correcting a quarantined event's cause, an operator can reset failed_at,
attempt_count, next_attempt_at, claim_token, lease_expires_at and last_error_code
for that specific unpublished event. Never blindly replay published events or
reset live leases. No public retry/admin endpoint is introduced here.

No broker/database service was started, no events were published, and no tests
were added or run. The next step is the assessment job runner with durable
claims/leases, retry limits, stages and recovery before AI evaluation is enabled.
