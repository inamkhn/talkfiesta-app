# Assessment job execution and recovery

Implemented the execution-control layer. The real evaluator is still pending.
Keep ASSESSMENT_EXECUTION_ENABLED=false and OUTBOX_DISPATCH_ENABLED=false until
the pipeline is implemented and workers are deployed. Enabling execution without
callable `evaluate_assessment` fails registration instead of consuming jobs with
a placeholder handler.

## Evaluator integration contract

The future synchronous function in assessment/ai/evaluators.py receives
`evaluate_assessment(job_id: UUID, report_stage: Callable)` and returns a validated
PublicPlacement or a dictionary matching that schema. It loads frozen evidence
by job ID. Provider calls must have bounded timeouts. It reports only:
TRANSCRIBING_AUDIO, EVALUATING_LANGUAGE, DETERMINING_PLACEMENT, SAVING_RESULTS.

Raise RetryableEvaluationError for transient failures safe to retry. Unexpected
exceptions and invalid output are terminal; raw exception messages and learner
content are not logged. Soft timeouts are retryable. Persistent step outputs,
provider usage accounting, detailed response-level evidence, pronunciation and
the richer result-progress contract are future evaluator integration work.

## Durable execution

User -> assessment -> job row locks serialize claims and commits. Claiming changes
PENDING/RETRYABLE to RUNNING, increments attempts, records a token/lease, and sets
the assessment PROCESSING. A live competing claim or terminal job is ignored.
No transaction spans evaluator calls. Stage updates and result/failure writes
require the current unexpired claim token. A stale worker's result is discarded.

The fixed lease defaults to 360 seconds and must exceed Celery's hard time limit
(300 seconds). Stages do not extend it. Defaults permit three executions; retries
have exponential backoff with jitter. Worker termination consumes an attempt.
Recovery of an expired lease first schedules a retry or marks terminal failure.

Success validates required writing evidence and atomically writes assessment
result/CEFR/confidence/completed_at, job SUCCEEDED/DONE, and RESULT_READY on the
user unless onboarding is already complete or a newer initial attempt exists.
No learning plan is created here. Lost-claim fencing prevents a prior execution
from overwriting a later execution's output. Database failure before commit leaves
the lease for recovery.

## Recovery process

Apply migration 20261101_job_execution after 20261101_outbox_delivery. It adds
job execution metadata, not a new table. No migration has been executed here.

Schedule this standalone command roughly every 15–30 seconds through the host's
process scheduler (no scheduler was installed/configured by this change):

```sh
uv run python -m app.workers.recover_jobs --limit 100
```

It scans a bounded eligible batch and rechecks each job under locks. Due retries
get a fresh outbox event for the same logical job. Pending jobs whose published
delivery remains unclaimed beyond the broker visibility timeout get redelivery.
Existing unpublished events, including quarantined delivery failures, are left
for dispatch/operator review. Concurrent recovery processes cannot create duplicate
recovery events for a job. Run the outbox dispatcher separately.

Celery task ID is not a deduplication guarantee. Late acknowledgement and database
claims provide replay-safe state transitions, not exactly-once external billing.
A crash after a provider response can require another paid call; step persistence
is needed to reduce that window. All worker processes must enforce hard runtime
limits; the Windows solo development pool is unsuitable for production execution.

This change does not yet add progress stages to the public result response. No
services were started, jobs executed, or tests added/run. Static checks and module
loading are the only verification performed.
