// Deny-by-default route policy, shared by AuthGuard (render-time protection)
// and the axios client (session-expiry redirects). Only these paths are
// reachable without a session; everything else requires authentication.
export const PUBLIC_PATHS = [
  "/",
  "/login",
  "/register",
  "/forgot-password",
  "/reset-password",
];

export const isProtectedPath = (pathname: string | null | undefined): boolean =>
  !!pathname && !PUBLIC_PATHS.includes(pathname);
