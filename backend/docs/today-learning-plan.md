# GET /api/v1/learning-plans/current/today

Authenticated, owner-scoped read of the next required lesson per enrollment.
No body is required. Responses use `Cache-Control: private, no-store`.

The response contains `plan_id`, `cycle`, `daily_target_minutes` from the saved
plan, the user's current `timezone`, and `activities` in Speaking, Vocabulary,
Writing order. Only enrolled modules appear. Today means the enrollment's
current curriculum day, not a calendar date or a daily unlock.

Each active activity contains module, day, content_item_id, title, description,
content_kind, estimated_minutes, activity_status, evaluation_status, and route
(for example `/speaking/day/2`). Description and estimated_minutes are optional
public metadata from the lesson body; absent metadata is returned as null.
No body, answer key, rubric, or evaluator guidance is exposed.

An owned draft for this exact progress and content item gives `IN_PROGRESS`;
otherwise the activity is `NOT_STARTED`. Evaluation status is null because
these are unfinished activities. Feedback for previously accepted work belongs
on the dashboard; it does not block the next curriculum day. A completed module
returns day 21, `COMPLETED`, and null content/metadata/route fields.

One PostgreSQL SELECT reads the plan, progress, completion counts, published
CORE lessons, timezone, and draft existence in a consistent statement snapshot.
Selection matches release, cycle, module, lesson kind, current day, CEFR and
goal variant exactly. The endpoint never changes progress or creates content.

Authentication and plan errors match GET /learning-plans/current. Additionally:

- `409 CURRICULUM_CONTENT_UNAVAILABLE`: a required lesson is missing or the
  enrollment is awaiting content. No release or goal fallback is used.
- `503 LEARNING_PLAN_UNAVAILABLE`: saved public metadata or plan state is invalid.

No migration or external provider is needed. Validation is limited to lint,
imports, PostgreSQL SQL compilation, and OpenAPI generation; no tests or live
database checks were run.
