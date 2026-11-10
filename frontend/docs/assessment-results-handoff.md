# Placement report and learning-plan handoff

The processing, result and terminal-failure routes now render `AssessmentResult`, using GET `/assessments/{id}/result` scoped to the signed-in user and saved assessment ID.

## Processing and results

- Poll pending/retryable jobs at `retry_after_seconds` (five seconds if omitted), without background-tab polling. Stop timed polling at completed/final-failure states and on request errors; manual retry remains available.
- Show the backend's safe processing stage without invented percentages. Retryable evaluation failures remain on the existing job; no browser submission/restart is triggered automatically.
- Validate the public result projection. Display actual provisional CEFR, confidence, per-skill levels, strengths and improvement priorities. Missing evidence and skipped speaking show Not assessed, never zero. Pronunciation remains explicitly unassessed.
- Preserve previously confirmed data if a refresh fails. A completed result without an overall CEFR cannot initialize a plan.
- A final failure offers an explicit new-assessment action. Its per-user/failed-attempt request key is retained across uncertain retries; the original failed attempt is preserved by the backend.

## Plan creation and handoff

- Create my learning plan posts the completed assessment ID to `/onboarding/complete`. The backend makes repeated completion calls for the same attempt safe and rejects incomplete/inconsistent data.
- Failed confirmation keeps the result visible and allows retry. No new assessment or guessed placement is used.
- After completion, navigate to `/learning-plan-ready`. Its protected route is available only after the normal server-state guard confirms completed onboarding. Other unfinished users are redirected to their saved step.
- The handoff reads `/learning-plans/current` and `/learning-plans/current/today`, verifies matching plan IDs, and displays actual cycle, provisional placement, goals, focus areas, daily time and module activities.
- Missing content is shown explicitly; no lesson names, times or paid entitlements are invented. Modules progress independently. Go to my dashboard uses the existing authenticated dashboard route.
- Handoff load failures retry reading the existing plan rather than recreating it. The screen can be reloaded directly after completion.

Validation: TypeScript and targeted ESLint checks. No new tests, live assessment evaluations, plan creation or external service calls were performed during implementation. Browser-level end-to-end validation is still needed.
