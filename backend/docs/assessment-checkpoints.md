# Durable assessment checkpoints

Scheduled cleanup for stalled jobs is now available; see
[retention cleanup](assessment-retention.md). That command supersedes the earlier
limitation below about indefinitely retained active-job checkpoints when deployed.

Completed transcription, writing evaluation, and speaking language evaluation
are checkpointed in `assessment_responses.grading.ai_checkpoints`. The existing
JSONB column is used, so no migration is required. There are at most two step
slots on the speaking response and one on writing; changed versions replace the
same slot rather than accumulating old output.

The worker supplies its live `JobClaim` to the evaluator. `CheckpointStore` checks
the active claim, active account, attempt, response question, finalized status,
and frozen revision before both reading and saving. It follows the runner's
user → attempt → job → response lock order. Provider calls run after the read
transaction closes; writes occur in a separate short transaction. A stale worker
cannot save its output after another execution has claimed the job.

## Reuse rules

A SHA-256 fingerprint includes the logical job, pinned content release, frozen
question/response evidence, configured model, prompt or transcription version,
rubric version, provider input, and output JSON schema. Every cache hit is
revalidated against the current Pydantic schema. Invalid/mismatched checkpoints
are recomputed, and failures/refusals are never cached as successful output.

Speaking language fingerprints include the actual transcript supplied for that
evaluation. Expired audio cannot use a cached transcript. The evidence loader
also removes expired/unavailable audio from the next snapshot, invalidating any
old audio-based fingerprint. Explicit skips and valid insufficient-evidence
outputs can be checkpointed without inventing scores.

The transcription version is `transcription-json-three-word-v1`; change it when
changing transcription behavior. Language prompt text and schemas automatically
participate in their fingerprints. Other semantic changes need a version bump.
Model aliases are matched by configured name, not by an unknowable provider-side
deployment revision; pin a model snapshot when exact model reproducibility matters.

## Example

1. Transcription finishes and its checkpoint commits.
2. Speaking evaluation finishes and its checkpoint commits.
3. Writing encounters a temporary provider failure.
4. The job retries under a new claim token.
5. Matching transcription and speaking checkpoints are reused; only writing calls
   the provider again.
6. Final feedback and placement commit together; temporary checkpoints are removed.

The claim token is deliberately excluded from the fingerprint so a new authorized
execution of the same logical job can reuse previous work.

## Retention and limitations

Checkpoint transcripts are private database data, never added to the learner API.
Successful completion removes both responses' temporary checkpoints while retaining
final language feedback. Terminal failure also removes checkpoints; retryable
failure preserves them. Existing attempt/account deletion handles record deletion.
An indefinitely stalled active job can retain checkpoint data until it is recovered
or deleted; this change does not add a scheduled retention sweeper. Audio retention
deadlines govern reuse, not automatic deletion of database rows.

Checkpoint database operational failures are retryable. A crash after a paid
provider response but before the checkpoint commits can still repeat that call.
This reduces repeat billing; it cannot provide exactly-once external billing.

Validation was limited to lint, imports, schema generation, and graph compilation.
No tests, live database execution, or paid provider calls were performed.
