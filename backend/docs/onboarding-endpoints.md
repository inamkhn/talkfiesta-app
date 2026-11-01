# Onboarding state and preferences

Both endpoints require `Authorization: Bearer <access_token>`. They derive ownership
from the authenticated user and return `Cache-Control: no-store`.

## GET /api/v1/onboarding/state

```json
{
  "status": "ASSESSING",
  "next_step": "ASSESSMENT",
  "active_assessment_id": "22222222-2222-4222-8222-222222222222",
  "assessment_status": "IN_PROGRESS",
  "can_access_dashboard": false
}
```

The query reads user state and an owner-scoped INITIAL assessment in one database
snapshot. An active initial assessment takes precedence over historical attempts;
otherwise the latest initial attempt is used. Reassessments do not affect onboarding.
GET never writes state or creates an assessment.

| Persisted progress | Returned status | next_step |
| --- | --- | --- |
| User COMPLETED | COMPLETED | DASHBOARD |
| Initial assessment IN_PROGRESS | ASSESSING | ASSESSMENT |
| Initial assessment SUBMITTED / PROCESSING / FAILED_RETRYABLE | ASSESSING | ASSESSMENT_PROCESSING |
| Initial assessment COMPLETED with result and CEFR | RESULT_READY | ASSESSMENT_RESULT |
| Initial assessment FAILED_FINAL | ASSESSING | ASSESSMENT_RETRY |
| No attempt, user NOT_STARTED | NOT_STARTED | PREFERENCES |
| No attempt, user PREFERENCES_SAVED | PREFERENCES_SAVED | ASSESSMENT |

`active_assessment_id` identifies the attempt to resume, poll, view, or recover,
including a completed/failed attempt awaiting onboarding completion. It is null
before an assessment exists and after onboarding completion. `assessment_status`
lets the frontend distinguish processing from retryable failure. Missing attempts
for ASSESSING/RESULT_READY users, or completed attempts without usable result data,
return 409 `ONBOARDING_STATE_INCONSISTENT` rather than inventing progress.

Only persisted user status COMPLETED grants `can_access_dashboard=true`.
Assessment results alone never grant access or mark onboarding complete.

## PUT /api/v1/onboarding/preferences

All six fields are required. Unknown fields, duplicate selections, null values,
unsupported choices, invalid timezones, and non-integer minutes return 422.

```json
{
  "goals": ["BUSINESS"],
  "focus_areas": ["SPEAKING", "WRITING"],
  "daily_minutes": 15,
  "topics": ["DAILY_LIFE", "TRAVEL"],
  "self_reported_comfort": "SIMPLE",
  "timezone": "Asia/Riyadh"
}
```

| Field | Allowed values |
| --- | --- |
| goals | 1–4 unique values: FLUENCY, BUSINESS, EXAM, TRAVEL |
| focus_areas | 1–3 unique values: SPEAKING, VOCABULARY, WRITING |
| daily_minutes | 5, 10, 15, 20, 30, 45, 60 |
| topics | 0–8 unique values: DAILY_LIFE, TRAVEL, WORK, EDUCATION, TECHNOLOGY, CULTURE, HEALTH, HOBBIES |
| self_reported_comfort | BEGINNER, SIMPLE, COMFORTABLE, CONFIDENT |
| timezone | IANA name, for example UTC or Asia/Riyadh |

Goal choices match the existing frontend; the remaining explicit options are the
initial backend contract where the V4 proposal did not enumerate choices.

The service locks the user row, replaces the five learning-preference keys in
`users.preferences`, saves timezone in `users.timezone`, and advances NOT_STARTED
to PREFERENCES_SAVED in the same transaction. Unrelated preferences are preserved.
Repeating a request is safe; later onboarding states are never moved backward.
Changes after assessment/plan creation do not rewrite assessment evidence or an
existing learning plan.

Response: `{"status":"PREFERENCES_SAVED","saved":true}` (or the unchanged later
status). No new tables, migrations, assessment, AI job, or plan are created.

The existing `PATCH /users/me` still supports partial preference edits, but uses
the same validation for these five learning keys. It does not advance onboarding;
use this PUT endpoint to submit the full onboarding form.

## POST /api/v1/onboarding/complete

Body: `{"assessment_attempt_id":"<UUID>"}`. Returns 200:
`{"status":"COMPLETED","learning_plan_id":"<UUID>","next_path":"/dashboard"}`.

Requires an owned, completed INITIAL assessment with nonempty result evidence,
a usable A1–C2 placement, and validated saved learning preferences. Locks the user
and assessment, then creates the cycle-1 plan and exactly three ACTIVE module
progress rows at day 1. Updates current_cefr and onboarding status in the same
transaction. Focus areas mark priority; all three modules are enrolled.

Curriculum selection tries goals in saved order (FLUENCY maps to GENERAL), then
GENERAL as fallback. Each module independently pins a complete published release
with 21 CORE lessons at the placement level. Candidates are ordered by publication
time with deterministic tie breakers. Vocabulary requires ten distinct published
VOCAB_WORD references per lesson. Shared content locks prevent selected content
from changing before commit. Published content must remain immutable afterward.

Missing curriculum returns 503 CURRICULUM_UNAVAILABLE with no partial plan or
completion. Missing/unowned assessment returns 404. Incomplete assessment,
unavailable placement, missing preferences, or inconsistent saved state returns
409. Repeating the same assessment returns the original plan without resetting
progress, even if that plan is later paused or completed. A different assessment
cannot replace the original onboarding plan through this endpoint.

Completed assessments without placement can now reach ASSESSMENT_RESULT through
GET /state; POST /complete returns PLACEMENT_UNAVAILABLE until usable placement
exists. Assessment evaluation and later-cycle/reassessment workflows remain
separate responsibilities. No schema migration is needed.
