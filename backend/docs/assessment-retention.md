# Audio and checkpoint retention

From backend/, inspect candidates without deleting anything:

```sh
uv run python -m app.workers.cleanup_retention --limit 100
```

Apply the bounded batch:

```sh
uv run python -m app.workers.cleanup_retention --apply --limit 100
```

Schedule the apply command periodically using your deployment scheduler, for example
every five minutes. Scheduling and actual deletion have not been performed here.

Audio cleanup uses persisted delete_after deadlines, skips DELETED records and
recordings referenced by assessments with live worker leases, and waits until the
signed upload URL has expired plus a 15-minute grace period. Each exact stored S3
key is deleted without holding a database transaction. Only successful S3 deletion
allows the row to become DELETED. Failures are logged with upload ID and error type
and retried on subsequent runs. Missing objects are safe to delete again. Concurrent
cleanup processes may repeat deletion of the same immutable key.

The S3 role needs DeleteObject permission. For versioned buckets, DeleteObject
does not purge old versions: configure noncurrent-version expiration through S3
lifecycle. Lifecycle is also required for orphaned objects whose database records
were deleted through account deletion and for late/incomplete uploads. This command
does not enumerate the bucket or delete arbitrary object prefixes. NULL retention
deadlines are not guessed; legacy records need an explicit retention policy.

Checkpoint cleanup uses ASSESSMENT_CHECKPOINT_RETENTION_DAYS (default 7), measured
from assessment submission. It selects old assessment jobs containing checkpoints,
locks user → attempt → job → responses, rechecks age and all live job leases, and
removes only grading.ai_checkpoints. Final evaluations, objective grades, answers,
and placement records are preserved. A resumed job can recompute removed steps;
cleanup does not cancel jobs or alter their status. Success/terminal failure also
continue to remove checkpoints immediately through the existing runner.

Each category processes at most --limit candidates per invocation. Large backlogs
need repeated runs. Expired live leases are not extended by cleanup; recovery
remains a separate service. Checkpoint candidates require an associated owned
assessment job, as created by the normal submission path.

No live cleanup, S3 calls, database mutations, or tests were run during implementation.
Local lint, imports, and SQL compilation are structural checks only.
