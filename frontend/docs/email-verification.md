# Email verification

`/verify-email` is a public route matching the backend's default `EMAIL_VERIFICATION_URL`. Emailed links use `#token=...`; legacy query tokens are also accepted. Tokens are read in the browser and are not logged or persisted by this UI. A different token resets the page's state.

The user explicitly presses **Verify email** to POST `{token}` to `/api/v1/auth/verify-email`. Rendering the route does not consume a single-use token. A 204 displays success; a 401/INVALID_ACTION_TOKEN displays an invalid, expired or already-used link state. Rate limits and uncertain network failures have retry guidance. Duplicate submissions are blocked while a request is pending. Verification never signs the user in or changes the current session.

After success, `/users/me` is invalidated and refetched through the session provider. The UI does not optimistically mark the signed-in user verified: the emailed link might belong to a different account. Continue goes through the guarded `/onboarding` entry for authenticated users or `/login` otherwise.

`/request-email-verification` is public and posts `{email}` to `/api/v1/auth/request-email-verification`. Signed-in users get their email prefilled. The 202 acknowledgement is generic and does not claim delivery or disclose account existence. The form allows another request and handles rate limits, validation and service/network failures. Backend throttling remains authoritative.

An unverified signed-in user sees a reminder on protected onboarding/dashboard pages; login also links to the request form. Verification does not block learning, consistent with the existing backend. Registration does not automatically send an email; users request it through the reminder.

Configure backend SMTP and set `EMAIL_VERIFICATION_URL` to the deployed frontend's `/verify-email` URL. No new email library or backend endpoint is introduced. Delivery remains the backend's existing best-effort background SMTP task. Verification in another open tab appears after that tab reloads its profile.

Validation: TypeScript and focused ESLint checks; no tests added. Live SMTP delivery and browser verification with real accounts remain deployment checks.
