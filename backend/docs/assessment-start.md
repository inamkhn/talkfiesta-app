# POST /api/v1/assessments

Requires Bearer authentication and `Idempotency-Key` (1–128 ASCII letters,
digits, dots, underscores, colons, or hyphens; UUID strings work).
Body: `{"kind":"INITIAL"}`. Reassessment and unknown fields return 422.

201 for creation, 200 for resume/replay:

```json
{"id":"<UUID>","status":"IN_PROGRESS","content_release":"placement-bank-v1","estimated_minutes":7,"resumed":false}
```

Resume returns the attempt's current status and `resumed:true`; it does not reset
answers, content release, or processing. SUBMITTED, PROCESSING, and FAILED_RETRYABLE
attempts remain active. GET/item selection/submission endpoints are separate work;
this endpoint creates no questions and calls no AI provider. Seven minutes is the
initial blueprint's approximate duration, not a measured completion time.

New starts require saved, validated preferences and timezone. A completed initial
result returns 409 ASSESSMENT_ALREADY_COMPLETED with its result URL in Location.
Completed onboarding rejects new keys with 409. FAILED_FINAL can be replaced with
a new key, subject to ASSESSMENT_STARTS_PER_DAY (default 3 in a rolling 24 hours).
Resuming/replaying does not consume that limit.

User locking serializes starts; the existing partial unique index additionally
enforces one active initial attempt. The attempt, onboarding transition, and
durable key record commit together. Keys are scoped by user, stored as SHA-256
hashes, and linked to the original attempt even when the request only resumed it.
An old key always returns that original attempt's current state, including after
completion/failure. A retry that should create a replacement needs a new key.
No keys are recorded for unsuccessful requests. Payload mismatches return 409.

## Database deployment

Apply `uv run alembic upgrade head` against the existing V4 database before using
the endpoint. The repository previously contained no migration revisions; the
new root revision is explicitly additive and requires users/assessment_attempts
to exist. It does not bootstrap an empty database. Fresh metadata-created V4
databases already include the new table and should stamp this revision instead
of running its create-table operation. Do not stamp an existing database that
has not acquired the new table. No database migration was executed by this change.

The schema now includes `assessment_start_requests` in addition to the previous
15 tables. Existing checks asserting exactly 15 tables will need updating when
test work is resumed.

## Initial question-bank contract

Configure ASSESSMENT_CONTENT_RELEASE (default placement-bank-v1). Only PUBLISHED
ASSESSMENT_QUESTION rows from this release are considered. The initial blueprint
requires at least one valid MCQ for each GRAMMAR/VOCABULARY × A1–C2 combination,
one writing prompt, and one speaking prompt (speaking is optional for the learner).
This is a starting coverage rule, not a calibrated CEFR assessment instrument.

MCQ body:
`{"skill":"GRAMMAR","kind":"MULTIPLE_CHOICE","prompt":"...","choices":[{"id":"a","text":"..."},{"id":"b","text":"..."}],"correct_choice_id":"b"}`.
CEFR comes from the row's cefr_level column. Choices need 2–6 unique nonempty IDs
and nonblank text, and correct_choice_id must identify one choice.

Writing/speaking bodies use skill WRITING/SPEAKING, kind SHORT_WRITING/
RECORDED_SPEAKING, a nonblank prompt, and a nonempty rubric object. Invalid rows
do not count toward coverage. Incomplete banks return 503
ASSESSMENT_CONTENT_UNAVAILABLE without creating an attempt. Rows are share-locked
during validation; published releases must remain immutable afterward. No sample
questions were fabricated or seeded. Future selection/evaluation must share this
body contract and never expose correct choices or rubrics to learners.

## POST /api/v1/assessments/{id}/items/next

Requires Bearer authentication; no request body or idempotency key. The persisted
ASSIGNED row makes retries safe. Returns 201 for a new item, 200 for the existing
unanswered item, or an empty 204 after all ten items are finalized. Submission
is separate. Missing/unowned attempts return 404; non-IN_PROGRESS attempts return
409 ASSESSMENT_NOT_EDITABLE. Only INITIAL assessments are supported.

Initial selection policy: four GRAMMAR MCQs, four VOCABULARY MCQs, one
SHORT_WRITING prompt, then one optional RECORDED_SPEAKING prompt. Each objective
skill starts at A2. Subsequent questions target one band above/below the previous
question for a correct/incorrect answer, bounded at A1/C2. Select the nearest
available unused band, breaking ties by question UUID. Writing/speech ties are
also broken by UUID. This deterministic initial policy is not CEFR calibration.

The answer-saving implementation must retain status ASSIGNED for drafts, set
ANSWERED only on finalization, and store objective `grading.correct` as a boolean.
Missing objective grading blocks adaptive progression with 409
ANSWER_GRADING_REQUIRED. SKIPPED is allowed only for speaking. Answer writers
must use the same user -> assessment lock order. The next-item endpoint neither
saves nor grades answers.

New assignments explicitly start at revision 0. Public responses include only
response_id, position, skill, kind, prompt, choices (MCQ only), revision, and
optional. Choice objects expose only id/text. Answer keys, rubrics, grading and
other private content fields are never serialized. The assessment and published
content are locked until assignment is committed. Selection uses only the pinned
release and excludes already assigned questions. Missing or unusable required
content returns 503; it is not mistaken for successful completion.

No schema migration or test files were added for this endpoint. Existing legacy
assignments keep their stored revision and must conform to the documented sequence;
inconsistent assignment histories return 409 instead of silently skipping items.

## PUT /api/v1/assessments/{id}/responses/{response_id}

Requires Bearer authentication. Returns 200 with response_id, status, revision,
and saved:true. Ownership and assignment are checked; missing/unowned resources
return 404. Submitted assessments reject writes with 409 ASSESSMENT_NOT_EDITABLE.

MCQ: `{"kind":"MULTIPLE_CHOICE","selected_choice_id":"b","expected_revision":0}`.
The option must belong to the question. Correctness is stored privately as
`grading.correct` for adaptive selection, never returned in the save response.

Writing draft: `{"kind":"SHORT_WRITING","text":"My draft","finalize":false,"expected_revision":0}`.
Drafts remain ASSIGNED, so next-item returns the same prompt. Finalize with true
(the default) and the latest revision. Final text must not be blank; the limit
is 10,000 characters. Drafts may be empty. Text is preserved as submitted.

Speaking skip: `{"kind":"RECORDED_SPEAKING","skipped":true,"skip_reason":"MIC_UNAVAILABLE","expected_revision":0}`.
Other reasons: DECLINED, TECHNICAL_ISSUE. Audio and skip are mutually exclusive.

Speaking audio: `{"kind":"RECORDED_SPEAKING","media_upload_id":"<UUID>","expected_revision":0}`.
Requires an owner-scoped VERIFIED ASSESSMENT upload with verified_at populated,
not past delete_after, already bound to this response through media_upload_id.
The future upload-confirmation endpoint must establish that binding using the
same user -> assessment -> response -> upload lock order. Until that endpoint
exists, recorded-audio attachment is not a complete end-to-end flow; skipping is.

Every accepted write increments revision. A stale revision returns 409
VERSION_CONFLICT, except an identical immediate retry (same normalized payload
and expected_revision exactly one behind) which returns the saved result without
another write. Finalized answers cannot be edited (409 ANSWER_FINALIZED), keeping
adaptive history stable. Draft autosaves must be serialized by the frontend.
All updates to answer, grading, media, status, timestamp and revision commit
atomically. No new tables or migrations are required.

## POST /api/v1/assessments/{id}/submit

Requires Bearer authentication and Idempotency-Key with the same format as start.
No body is needed. Returns 202 with attempt_id, current status, job_id, and
result_url. The first successful call returns SUBMITTED; PROCESSING is reserved
for a worker that actually starts evaluation.

Submission locks user then assessment then responses. All ten positions must
exist, match their pinned published questions and skill sequence, and contain
valid finalized payloads. Objective grades must match their saved choice and
private answer key. Writing drafts are rejected. Speaking requires an explicit
valid skip or owner-scoped verified, bound, unexpired audio. Invalid/incomplete
answers return 409 ASSESSMENT_INCOMPLETE; unusable audio returns 409
ASSESSMENT_AUDIO_UNAVAILABLE. Unknown/unowned attempts return 404.

The SUBMITTED transition, submitted_at, PENDING ASSESSMENT job, unpublished
EVALUATION_REQUESTED outbox event and submission-key record commit together.
No answer can be edited afterward. The event carries only job/attempt IDs.
A deterministic job idempotency key enforces one evaluation job per attempt.
Same-key and new-key retries return that job without creating more events/jobs;
reusing a submission key for another assessment returns 409 IDEMPOTENCY_KEY_REUSED.
Failed evaluation never silently creates a replacement job. Retry responses expose
the current attempt status, which may already be COMPLETED or failed.

Apply the new 20261101_submit_keys migration after 20261031_start_keys before
using this route. No migration was executed during implementation. The model
registry is loaded at API startup so all job foreign-key targets are registered.
This additional table brings the current metadata to 17 tables.

Submission requests are throttled at 60/user/hour using the existing Redis helper
(which fails open when Redis is unavailable). Durable keys have no automatic
expiry; define retention before long-term public operation.

IMPORTANT: dispatch_outbox.py and assessment_tasks.py are still scaffolds, and
GET /assessments/{id}/result is not implemented. This endpoint durably schedules
work in PostgreSQL; it does not yet deliver messages to Celery, call AI, or produce
results. Implement dispatcher delivery/retry and worker idempotent job claiming
before enabling the complete assessment experience. Audio must be revalidated by
the worker before use because storage/retention may change after submission.

## GET /api/v1/assessments/{id}/result

Now implemented (supersedes the earlier note that this route was pending).
Requires Bearer authentication and checks attempt ownership; missing/unowned IDs
return the same 404. Always read-only: no job dispatch, retries, or state changes.
All successful responses are 200 with Cache-Control: no-store.

IN_PROGRESS returns placement:null without polling guidance. SUBMITTED/PROCESSING
return placement:null and retry_after_seconds:3, also in Retry-After. Retryable
failure returns a generic EVALUATION_RETRYABLE error and a five-second polling
hint; final failure returns EVALUATION_FAILED with no polling hint. Neither case
exposes provider errors or creates a new job.

COMPLETED returns a provisional placement. Future workers must write top-level
result keys skills, strengths, improvement_priorities, rubric_version, and the
attempt's placement_cefr/confidence columns. Skills must contain grammar,
vocabulary, writing, speaking; each contains level, assessed, and an optional
reason. Unassessed skills require null level and a reason (MIC_UNAVAILABLE,
DECLINED, TECHNICAL_ISSUE, INSUFFICIENT_EVIDENCE, AUDIO_UNAVAILABLE, NOT_ASSESSED).
Assessed skills require A1–C2 and no reason. Overall CEFR may be null when evidence
is insufficient; onboarding completion still requires a valid placement.

Only explicitly typed public fields are returned. Skipped/missing speaking
responses are forced to unassessed rather than exposing a hallucinated score.
Malformed completed results return 503 ASSESSMENT_RESULT_UNAVAILABLE instead of
fabricating a placement. The worker must commit result, placement, confidence,
and COMPLETED status atomically. Dispatcher and evaluation worker remain pending;
this endpoint can poll stored state but does not itself generate results.
No migration or test files were added for this route.
