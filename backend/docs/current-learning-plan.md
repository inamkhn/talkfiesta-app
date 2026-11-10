# GET /api/v1/learning-plans/current

Authenticated, owner-scoped, read-only retrieval of the active learning plan.
No request body or user_id parameter is required. Successful responses use
`Cache-Control: private, no-store`.

The response contains `plan` (id, cycle, ACTIVE status, provisional placement,
goals, focus areas, daily_target_minutes, created_at) and `modules` (module,
progress_id, status, current_day, completed_days, total_days=21, target_cefr,
prioritized). Modules are returned in Speaking, Vocabulary, Writing order,
including only actual enrollments. Plan preferences come from the saved plan
snapshot; daily_target_minutes maps from plan_config.daily_minutes.

One SELECT reads onboarding state, the active plan, enrollments, and correlated
completion counts. It does not increment progress or select/generate new content.
Completed days count distinct credited CORE curriculum days matching the pinned
release, cycle, module, lesson kind, goal variant, and CEFR. EXTRA activities and
foreign-user credits are excluded. Previously published, now archived lessons
retain earned credit. Counts are never inferred from current_day minus one.

Errors retain the application's existing application/problem+json format:

- 401: authentication missing or invalid.
- 403: inactive account.
- 409 ONBOARDING_REQUIRED: onboarding is incomplete.
- 404 ACTIVE_PLAN_NOT_FOUND: no ACTIVE plan, including after cycle completion;
  a reconciliation warning is logged.
- 503 LEARNING_PLAN_UNAVAILABLE: inconsistent/malformed saved plan or enrollment.

Only explicit public fields are mapped. Raw plan_config, curriculum bodies,
private rubrics, and completion-source details are not returned. No migration
is required. No tests or live database operations were run; lint, imports,
PostgreSQL query compilation, and OpenAPI generation are the validation scope.
