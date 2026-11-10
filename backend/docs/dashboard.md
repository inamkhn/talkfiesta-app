# GET /api/v1/dashboard

Authenticated, read-only learner home summary. No body or user ID parameter.
Successful responses use `Cache-Control: private, no-store`.

The response contains:

- `learner`: display_name, current timezone, provisional_cefr from the active plan.
- `learning_plan`: id, cycle, daily_target_minutes, completed_required_activities,
  total_required_activities and overall_completion_percent rounded to one decimal.
  The denominator is 21 times the actual number of enrolled modules. Only pinned
  CORE lesson day credits count toward completion, never optional activities.
- `modules`: module, completed_days, total_days=21, current_day.
- `streak`: current_days, longest_days, last_active_local_date.
- `practice`: total_seconds, today_seconds, mastered_words.
- `today_preview`: module, day, title, content_item_id in Speaking, Vocabulary,
  Writing order. Completed modules keep day 21 with null title/content_item_id.
- `pending_feedback`: latest five ACCEPTED submissions whose evaluation_status
  is PENDING or PROCESSING, with submission_id, module, evaluation_status and
  submitted_at. `pending_feedback_count` includes all matching submissions.
- `recent_achievements`: latest five stored achievement_key/earned_at pairs,
  matching the V4 response example. No achievements are awarded by this read.

One SQL statement loads the plan, pinned current lessons and aggregates in one
PostgreSQL snapshot, preventing concurrent practice acceptance from mixing old
progress with new statistics. The dashboard reuses the learning query service's
public projections. No HTTP calls, provider calls, database writes, or raw lesson
bodies, recordings, submission inputs, transcripts, feedback or badge context
are exposed.

Practice totals, streaks, pending feedback and achievements span all of this
learner's plans. Current plan completion and today's preview use the active plan.
Mastered words count owned user_vocabulary rows with status MASTERED.

Streaks count distinct credited local_practice_date values. Consecutive dates
ending today or yesterday keep the current streak alive; otherwise it is zero.
No activity means zero counts and a null last-active date. Multiple completions
on one date count once for streaks, but all credited durations contribute to
practice totals. Today is calculated using the database clock in users.timezone.
Timezone changes never rewrite historical credited dates. Dates ahead of today's
local date (possible after a timezone change) remain in history and total time,
but do not extend current/longest streak calculations until that date arrives.

Errors retain existing learning-plan behavior: 401/403 authentication/account,
409 ONBOARDING_REQUIRED, 404 ACTIVE_PLAN_NOT_FOUND,
409 CURRICULUM_CONTENT_UNAVAILABLE for missing current lessons, and
503 LEARNING_PLAN_UNAVAILABLE for invalid saved plan state. Malformed dashboard
aggregate records return 503 DASHBOARD_UNAVAILABLE.

No migration is required. Lint, imports, PostgreSQL SQL compilation and OpenAPI
generation are the validation scope; no tests or live database checks were run.
