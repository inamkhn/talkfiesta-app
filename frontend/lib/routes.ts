// Deny-by-default route policy, shared by AuthGuard (render-time protection)
// and the axios client (session-expiry redirects). Only these paths are
// reachable without a session; everything else requires authentication.
export const PUBLIC_PATHS = [
  "/",
  "/login",
  "/register",
  "/forgot-password",
  "/reset-password",
  "/verify-email",
  "/request-email-verification",
  "/design-preview", // Public sample UI; no account data or API requests.
];

export const isProtectedPath = (pathname: string | null | undefined): boolean =>
  !!pathname && !PUBLIC_PATHS.includes(pathname);
