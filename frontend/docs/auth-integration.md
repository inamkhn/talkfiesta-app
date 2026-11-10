# Authentication integration

The browser sends JSON login and registration requests to `/api/v1/auth/*` on the frontend origin. Next.js proxies `/api/v1/*` to `API_PROXY_ORIGIN` (default `http://127.0.0.1:8000`). Set this server-side variable to the backend origin, without `/api/v1`, and restart/rebuild Next.js when changing it. The shared Axios client no longer uses `NEXT_PUBLIC_API_URL`.

Refresh credentials stay in the backend's HttpOnly cookie. Only the short-lived access token is stored in localStorage. Existing client-stored refresh tokens are removed. Cookie security attributes are preserved by the proxy; use HTTPS in production and the backend's local-development cookie settings for local HTTP.

- Login posts `{email, password}`; registration posts `{email, password, first_name}`.
- Profile hydration uses `/users/me` and the current display-name/onboarding-status contract.
- Initial hydration can recover an access token from the cookie, including after access-token storage is lost.
- Protected requests retry at most once after refresh. Concurrent refreshes share one promise; Web Locks coordinate refresh/logout across tabs where supported.
- Transient refresh failures preserve local credentials for retry. Rejected refresh credentials clear the local session.
- Logout always calls the server, including when no local refresh token exists. Failure stays visible and retryable instead of claiming logout succeeded.
- Password recovery uses /auth/forgot-password (202 message) and /auth/reset-password (204), reads emailed fragment tokens, and clears the local session after reset. Google sign-in exchanges an ID token through /auth/google/exchange and uses the same session hydration and onboarding routing. Detailed routing now follows /onboarding/state; live assessment activities, submission, result reports and learning-plan handoff are now connected. Sample content is confined to /design-preview.

Validation: TypeScript and focused lint checks; no new tests or live account requests.

Email verification now has public `/verify-email` and `/request-email-verification` pages, fragment-token consumption, resend handling and a nonblocking reminder for unverified accounts. See [email verification](email-verification.md) for behavior and SMTP configuration.

## Google sign-in configuration

Set `NEXT_PUBLIC_GOOGLE_CLIENT_ID` in the frontend environment and `GOOGLE_CLIENT_ID` in the backend environment to the same Google OAuth web client ID. No client secret is used by this ID-token flow. Restart the backend and rebuild/restart the frontend after configuration changes; Next.js embeds public environment variables in the browser bundle.

In Google Cloud, configure the consent screen and authorize the frontend JavaScript origins, including the exact local port (for example `http://localhost:3000`) and production HTTPS origin. This popup callback flow does not use a redirect URI. See [Google's setup guide](https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid).

Login and registration load Google's official Identity Services script and button. Its credential callback posts `{id_token}` to `/api/v1/auth/google/exchange`; the backend validates the token, creates its refresh cookie, and returns the access token. The UI then hydrates `/users/me` and follows `/onboarding/state`. The Google ID token is not written to localStorage. Missing configuration, SDK load failures and exchange failures show email fallback or retry guidance. Concurrent email/Google exchanges are guarded within the mounted auth screen.

Live OAuth verification still requires a configured client, allowed origin and Google account. Check both new-account registration and existing-account login, canceled popups, rejected tokens, and saved onboarding routing before deployment. If deployment adds restrictive CSP or Cross-Origin-Opener-Policy headers, also follow Google's documented script/frame and popup requirements.
