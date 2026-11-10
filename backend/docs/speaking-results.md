# GET /api/v1/speaking/submissions/{submission_id}

Authenticated owner-scoped polling. Missing, foreign-owned and non-recorded-
speaking submissions all return the same 404. An active account is required;
an active plan is not, so earlier accepted submissions remain readable after
curriculum progression, plan replacement or audio retention cleanup.

200 returns submission_id, content_item_id, activity_status, evaluation,
transcript and feedback. Successful responses use Cache-Control: private,
no-store. One SELECT reads submission fields, the latest owned Speaking job,
and matching completion-credit existence in a consistent statement snapshot.
This endpoint does not claim/retry jobs, call providers, sign URLs or write data.

| Saved state | evaluation.status | evaluation.stage | Poll interval |
|---|---|---|---|
| Draft or rejected, no job/credit | NOT_REQUIRED | NOT_STARTED | Stop |
| Accepted, job PENDING | PENDING | WAITING_FOR_WORKER | 3 seconds |
| Accepted, job RUNNING | PROCESSING | TRANSCRIBING_AUDIO / EVALUATING_LANGUAGE / SAVING_RESULTS | 3 seconds |
| Accepted, job RETRYABLE | PENDING | RETRY_SCHEDULED | 5 seconds |
| Accepted, job SUCCEEDED | COMPLETED | DONE | Stop |
| Accepted, job FAILED | FAILED | FAILED | Stop |

The interval appears both in evaluation.retry_after_seconds and the Retry-After
header. Terminal/draft responses have no Retry-After header. The client should
stop its timer on completion/failure or when navigating away.

Accepted submissions retain activity_status=COMPLETED even if evaluation fails.
Drafts return IN_PROGRESS and rejected submissions REJECTED. No completion is
inferred from job status alone: the matching owned completion credit must exist.
Contradictory or incomplete saved states return 503 SPEAKING_RESULT_UNAVAILABLE.

While pending/running/retrying, transcript and feedback are null, even if the
worker has checkpointed its transcript. Completed evaluations expose the saved
original transcript, rubric_version and validated feedback. Corrections must
quote exact transcript substrings. No usable speech is still COMPLETED, with
reviewable=false, NO_USABLE_SPEECH and null scores. Pronunciation and pause count
remain null. Shared feedback contracts are independent of provider/worker imports.

Failed evaluations expose a saved original transcript if available and null
feedback. evaluation.error contains a fixed SPEAKING_EVALUATION_FAILED code,
safe message preserving activity credit and retry_allowed=false. There is no
manual retry endpoint yet; the flag does not promise an unsupported action.
Automatic retries remain PENDING/RETRY_SCHEDULED rather than terminal FAILED.

No S3 keys/URLs, upload checksums, private lesson body, submission input, worker
claim tokens, traces, metrics or provider error details are returned. Only the
typed public feedback contract is serialized; malformed or extra stored feedback
fields are rejected rather than leaked.

No migration is required. Checks: Ruff, imports, PostgreSQL query compilation,
OpenAPI generation and diff checks. No tests or live database/provider calls ran.
