# Auth API module

`lib/api/auth.ts` is the typed transport for the backend auth routers, using the same-origin `/api/v1/auth` proxy with credentials enabled. It does not attach an access token, retry mutations, persist credentials or redirect. Responses are validated at runtime; 204 endpoints resolve to `void`. Axios errors remain intact for existing UI handling.

| Method | POST endpoint | Request | Response |
| --- | --- | --- | --- |
| register | /register | email, password, optional first_name | 201 session |
| login | /login | email, password | 200 session |
| refresh | /refresh | Cookie only | 200 session |
| logout | /logout | Cookie only | 204 |
| forgotPassword | /forgot-password | email | 202 message |
| resetPassword | /reset-password | token, new_password | 204 |
| requestEmailVerification | /request-email-verification | email | 202 message |
| verifyEmail | /verify-email | token | 204 |
| googleExchange | /google/exchange | id_token | 200 session |

Session responses contain `access_token`, `token_type`, `expires_in` and a user summary (`id`, `email`, nullable `first_name`, `roles`, `onboarding_completed`). This differs from `/users/me`; `useAuth` still hydrates the full current-user profile after authentication. Refresh credentials never appear in the response type or browser storage.

Use `useAuth` for login, registration, Google login, logout and password reset. It retains session locks, token storage, query-cache cleanup and onboarding redirects. Protected requests use `refreshAccessToken` in `lib/api/axios.ts` to deduplicate refreshes and serialize cookie rotation across tabs. Do not call the raw transport's refresh/logout directly from UI components.

Verification screens use the transport directly because those actions do not start or end a session. Successful verification re-fetches the current profile. Reset success clears local authentication, matching the backend's token-version increment and session revocation. Invalid/reused action tokens remain errors; they are not silently treated as success.

Email-request acknowledgements are generic: backend delivery occurs in a background task and a 202 does not prove account existence or successful SMTP delivery. Google exchange accepts an ID token, not an OAuth authorization code.

Backend remains authoritative for input validation (including password lengths, email normalization and first-name trimming), throttling, account eligibility and token validity. No changes to backend routes or recovery rules were needed.
