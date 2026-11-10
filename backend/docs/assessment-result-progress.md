# Assessment result and progress response

`GET /api/v1/assessments/{id}/result` remains the owner-authorized polling endpoint.
It now adds `assessment_id`, an `evaluation` object, and
`placement.assessment_version`. Existing top-level `status`, `placement`,
`retry_after_seconds`, and `error` fields remain available.

## State mapping

| Attempt status | Public evaluation status | Frontend action |
|---|---|---|
| IN_PROGRESS | NOT_STARTED | Resume answering; evaluation has not started |
| SUBMITTED | QUEUED | Show waiting; poll after 3 seconds |
| PROCESSING | RUNNING | Show stage; poll after 3 seconds |
| FAILED_RETRYABLE | RETRY_SCHEDULED | Show retry message; poll after 5 seconds |
| COMPLETED | SUCCEEDED | Display placement; stop polling |
| FAILED_FINAL | FAILED_FINAL | Show failure; stop polling |

`retry_after_seconds` is a suggested polling interval, not an estimate of time
until completion or the scheduled retry time. The existing `Retry-After` header
matches it. `Cache-Control: no-store` remains set on successful responses.
Retries are performed by the deployed recovery/dispatch infrastructure; the GET
request does not run jobs or schedule retries itself.

Allowed stages are WAITING_FOR_WORKER, TRANSCRIBING_AUDIO, EVALUATING_LANGUAGE,
DETERMINING_PLACEMENT, SAVING_RESULTS, and DONE. Before submission stage is null.
For a scheduled retry or terminal failure, stage identifies the last saved work
stage, not currently running work. Unknown stages are projected as null. Stages
can repeat or move backward on retries; they are not percentage completion.

Example while running:

```json
{
  "assessment_id": "22222222-2222-4222-8222-222222222222",
  "status": "PROCESSING",
  "evaluation": {
    "job_id": "55555555-5555-4555-8555-555555555555",
    "status": "RUNNING",
    "stage": "TRANSCRIBING_AUDIO",
    "error": null
  },
  "placement": null,
  "retry_after_seconds": 3,
  "error": null
}
```

On failure, `evaluation.error` contains the same safe code/message/retryable
fields as the retained top-level `error`. `retryable: true` indicates an automatic
retry state; no manual retry endpoint is implemented by this change. Provider
errors, stack traces, model names, claim tokens, job metrics, checkpoint data,
transcripts, private rubric content, and trace identifiers are never projected.

## Consistency and provenance

The attempt and its latest owned ASSESSMENT job are loaded in one SELECT, avoiding
mixed snapshots while a worker changes both. Missing/inconsistent active jobs
produce 503 ASSESSMENT_PROGRESS_UNAVAILABLE rather than invented progress. Historical
completed/finally-failed attempts without a durable job may return null job_id.
Foreign and missing attempts both return 404.

New successful worker results persist `assessment_version: initial-assessment-v1`,
identifying the current four-grammar/four-vocabulary/writing/optional-speaking
blueprint. This is distinct from question content release, language rubric version,
and internal placement policy version. Historical results without a saved
assessment version return null. No historical result is rewritten and no version
is guessed from the currently deployed configuration.

Completed placement still includes explicit unassessed pronunciation. Speaking
skip checks use the frozen answer rather than the live media-upload FK, so later
audio retention deletion does not erase an already evaluated speaking result.
A contradicted speaking score is projected as unassessed with LOW confidence.

No database migration or deployment changes are needed. Validation is limited to
lint, imports, schema/OpenAPI generation, and graph compilation. No tests or live
service calls were run.
