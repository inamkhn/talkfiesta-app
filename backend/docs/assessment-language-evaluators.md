# Writing and speaking evaluator integration

The existing LangGraph now carries both the placement feedback and the full
validated language evaluation for each productive skill.

- Writing uses the frozen prompt, rubric, and finalized learner text.
- Speaking uses the verified audio transcription step and its explicit unavailable
  reasons. Only usable transcripts trigger a language evaluation call.
- User-message payloads are JSON. System instructions treat submissions as data,
  require evidence-based feedback, and prohibit acoustic judgments from text.
- The configured language model uses explicit strict JSON-schema structured output.
  Application validation still checks cross-field consistency.

## Failure behavior

One provider call is attempted per skill per job execution. SDK retries remain
disabled. Network failures, HTTP 408/409/429/5xx, truncated output, and schema
parsing/validation failures use the job runner's finite retry budget. Explicit
refusals/content filtering are terminal evaluation errors, not learner scores.
Other configuration/authentication/request failures remain terminal.

A valid insufficient-writing assessment cannot create a successful placement.
Optional insufficient speaking is unassessed and lowers the placement confidence
according to the existing policy. No new placement algorithm or calibration is
introduced.

## Persistence

The evaluator returns `AssessmentEvaluation`: a strict placement plus exactly one
writing and one speaking `ResponseEvaluation`. IDs, question references, and
revisions come from the worker snapshot, never from model output. Each response's
assessed status/level/reason must agree with both its detailed language output
and the final placement.

`finish()` revalidates the complete envelope, obtains the live worker claim, and
locks the matching response rows. It verifies attempt ownership through the
claimed attempt, response question/revision, answer kind, and finalized/skip
status. It then writes:

- `assessment_responses.grading.evaluation`: skill, revision, placement, and
  language criteria/feedback (or null language for a skipped/unavailable recording).
- `grading.model` and `grading.rubric_version`: evaluation metadata.
- The placement, attempt completion, job success, and onboarding result-ready state.

All writes share one transaction. Any mismatch or lost lease rolls back the whole
completion. Objective grades and frozen answers/revisions are left intact.
Existing JSONB columns are used; no migration is needed. The learner result API
continues returning only its explicit placement projection.

With the default learner-text redaction setting, the configured LangSmith client
hides complete input/output payloads, including feedback that may quote a learner.
Operational trace metadata remains available. Keep redaction enabled in production.

Durable step checkpoints now reuse completed provider work on retries; see
`assessment-checkpoints.md`. Transcripts are temporarily stored in private response
grading and removed on success or terminal failure. The provider-to-checkpoint
commit gap can still repeat paid calls. No live provider
or database execution was performed, and no tests were added or run. Local lint,
imports, schema generation, and graph compilation are the validation scope.

Provider edge cases follow the
[OpenAI structured output documentation](https://developers.openai.com/api/docs/guides/structured-outputs).
