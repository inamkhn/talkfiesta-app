# GET /api/v1/speaking/today

Authenticated, owner-scoped read of the next assigned Speaking lesson. No body
is required. Successful responses use `Cache-Control: private, no-store`.

Returns module=SPEAKING, plan_id, module_progress_id, cycle, day, module_status,
activity and existing_draft_id. The activity contains id, kind, title,
exercise_type, topic, instructions, target_duration_seconds, target_cefr,
preparation_seconds and tips.

Selection reuses the learning plan's exact published CORE lesson lookup:
enrollment release, cycle, module, current day, CEFR and goal variant must match.
It never falls back to another release or generates content. Target CEFR comes
from the enrollment; the other instructional fields come from the versioned
lesson. The body must contain the six public fields exercise_type, topic,
instructions, target_duration_seconds, preparation_seconds and tips. Timing
values must be integers (positive target, nonnegative preparation), tips a list
of strings, and exercise_type CONVERSATIONAL, PUBLIC_SPEAKING or IMPROMPTU.
These are lesson targets, not upload-validation limits.

Only allowlisted JSON fields are selected. Raw body, evaluator notes, rubrics,
submission inputs, recordings and transcripts are never returned. The draft ID
must belong to this user, progress and content item, with mode RECORDED_SPEAKING
and status DRAFT. If historical duplicate drafts exist, the newest by created_at
and UUID is selected deterministically. This read does not create a draft.

A completed enrollment returns day=21, module_status=COMPLETED, activity=null,
existing_draft_id=null. Existing learning-plan validation requires all 21 credits.
Missing content in another enrolled module does not prevent this Speaking read.

All data comes from one PostgreSQL SELECT snapshot. No progress changes, provider
calls, uploads or evaluation jobs occur.

Errors use the application's existing problem response format:

- 401/403: invalid authentication or inactive account.
- 409 ONBOARDING_REQUIRED: incomplete onboarding.
- 404 ACTIVE_PLAN_NOT_FOUND: no active plan.
- 404 MODULE_NOT_ENROLLED: Speaking is not enrolled.
- 409 CURRICULUM_CONTENT_UNAVAILABLE: missing pinned published lesson or
  enrollment awaiting content.
- 503 LEARNING_PLAN_UNAVAILABLE: inconsistent plan/enrollment.
- 503 SPEAKING_LESSON_UNAVAILABLE: malformed public lesson fields.

No migration is required. Validation covers lint, imports, PostgreSQL query
compilation and OpenAPI generation; no tests or live database checks were run.
