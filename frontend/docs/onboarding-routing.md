# Onboarding resume routing

The route guard loads `GET /api/v1/onboarding/state` after authentication and when navigating to protected pages. The response is validated before selecting a destination. State queries are scoped to user ID and path, are canceled on account changes, and refresh on window focus.

| Server next_step | Frontend route |
| --- | --- |
| PREFERENCES | /goal-selection |
| ASSESSMENT | /level-assessment |
| ASSESSMENT_PROCESSING | /level-assessment/processing |
| ASSESSMENT_RESULT | /level-assessment/result |
| ASSESSMENT_RETRY | /level-assessment/retry |
| DASHBOARD | /dashboard |

- Login and signup use `/onboarding` as a guarded routing entry point. Authenticated visits to login/register also resume the saved step.
- Unfinished users cannot bypass onboarding by manually entering dashboard or lesson URLs. Completed users can navigate app pages normally; onboarding URLs redirect them to the dashboard.
- Preferences remain editable before an assessment exists. After saving, state is invalidated and the guarded entry point resolves the next step again.
- Processing state is polled every five seconds while the page is visible, including worker retry states. It moves to result/retry automatically when the server next_step changes.
- Failed/malformed state requests show a retry screen without creating, resetting or submitting an attempt.
- Public marketing, password recovery and design-preview routes remain accessible without this routing check.

This step implements routing and truthful resume status only. The live question and answer-saving flow is now connected at /level-assessment. Recording/upload and final review/submission are now connected. Result reports and learning-plan handoff are now connected. No assessment mutation or example placement is used by the resume screens. The saved attempt ID remains in the validated state context for that integration.

Validation: focused lint and TypeScript checks. No tests added and no live account requests made.
