# GET /api/v1/learning-plans/current/modules/{module}/timeline

Authenticated, owner-scoped, read-only timeline for the active plan. Module names
are case-insensitive: `speaking`, `vocabulary`, or `writing`. Responses use
`Cache-Control: private, no-store`.

Returns module, progress_id, cycle, current_day, status, completed_days,
total_days=21, and exactly 21 ordered entries in days. Each entry contains day,
state, completed_at, and title.

- COMPLETED requires an owned activity completion matching the enrollment and
  its pinned release, cycle, module, lesson kind, CEFR, goal variant and CORE slot.
  Archived credited lessons retain their completion and title. If multiple
  credited versions exist for one day, the earliest completion supplies its
  timestamp and title; the day counts only once.
- AVAILABLE requires an ACTIVE enrollment, its current day, published matching
  content, and no completion credit for that day.
- All other unfinished days are LOCKED. Missing future content has a null title.
  AWAITING_CONTENT enrollments expose no available day.

Day 21 stays at current_day=21 after completion. A COMPLETED enrollment must have
21 credited days; inconsistent saved state returns 503 rather than inventing
completion records. No calendar-based unlocks or writes occur.

One PostgreSQL SELECT reads the plan, all enrollments, the requested module's
public titles and owned credits in a consistent statement snapshot. No lesson
bodies, private rubrics, answer keys or other users' credits are returned.

Errors use the application's existing problem response format:

- 401/403: missing or invalid authentication / inactive account.
- 422: unknown module name.
- 409 ONBOARDING_REQUIRED: onboarding is incomplete.
- 404 ACTIVE_PLAN_NOT_FOUND: no active plan.
- 404 MODULE_NOT_ENROLLED: supported module absent from the active plan.
- 409 CURRICULUM_CONTENT_UNAVAILABLE: the active unfinished current day has no
  published matching lesson.
- 503 LEARNING_PLAN_UNAVAILABLE: malformed saved plan, enrollment or timeline.

No migration is required. Validation covers lint, imports, PostgreSQL query
compilation and OpenAPI generation. No tests or live database checks were run.
