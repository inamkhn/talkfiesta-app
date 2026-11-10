# Landing-to-assessment design review

Reference: `TalkFiesta-Frontend-UX-Design-Landing-to-Assessment-V4.md`.

## Updated

- Landing page: warm off-white, green and orange accents; three equally weighted skills; four-step explanation; clearly labeled product and feedback examples.
- Removed unapproved prices, scarcity counters, trial/refund claims, invented learner proof and 21-day mastery claims from the rendered landing page.
- CTA links use real routes. Header includes an accessible mobile menu, Login, FAQ and skip link. Footer omits nonexistent policy/contact destinations.
- Login, registration and password recovery share the same light visual shell. Password visibility, accessible validation messages and pending-submit disabling were added.
- Preferences use multiple goals, skill focus, daily time, topics and speaking comfort instead of a self-selected CEFR level. Existing preferences load from GET /users/me; save uses PUT /onboarding/preferences. Errors preserve the current selections.
- Assessment screen design now covers welcome, choice questions, writing, optional speaking, review, processing and a provisional example result. Keyboard controls use native inputs; no fabricated score is presented as learner data.
- `/design-preview` is a public assessment design preview with no API calls or account data. `/level-assessment` and its processing/result/retry routes now display server-owned resume status; they do not display sample answers or scores.

## Integration still required

This is a design pass, not a completed end-to-end assessment client.

- Login/register, /users/me hydration, cookie refresh and logout now use the current backend contracts. Password recovery now uses the current endpoints and emailed fragment tokens. Returning-user routing now follows GET /onboarding/state, including direct protected navigation and completed-user redirects. Refresh requests are shared within a tab and serialized across tabs using Web Locks where available.
- Google sign-in is wired through the official button and backend token exchange; a matching frontend/backend Google client ID and allowed frontend origin are required.
- Email verification and resend are connected, with a nonblocking reminder for unverified signed-in accounts. Live email delivery needs configured backend SMTP.
- Assessment creation/resume, assigned questions, revision-aware choice/writing saves, draft restoration and optional speaking skip are now connected. Recording, audio upload/confirmation and speaking answer saves are now connected. Final review and submission are now connected. Real result reports and learning-plan handoff are now connected. Design-preview interactions never persist answers or create a plan.
- Real plan handoff now reads current-plan APIs after completion; placement never comes from the sample A2 card.
- Approved billing and legal content are still needed before adding payment or policy links.

Existing unused legacy landing components are not rendered by the new landing page. Dashboard and learning-module screens were outside this landing-to-assessment design pass.
