"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuthStore } from "@/store/authStore";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { isAuthenticated, isLoading } = useAuthStore();

  useEffect(() => {
    // We do a simple client-side check since we are using localStorage for MVP.
    // In a production app with SSR, we would use httpOnly cookies and Next.js middleware.
    if (!isLoading && !isAuthenticated) {
      // Redirect to login if trying to access a protected route
      if (pathname?.startsWith("/dashboard") || pathname?.startsWith("/onboarding")) {
        router.push("/login");
      }
    }
  }, [isLoading, isAuthenticated, pathname, router]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-950">
        <div className="flex flex-col items-center space-y-4">
          <svg className="animate-spin h-8 w-8 text-indigo-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <span className="text-slate-400">Verifying session...</span>
        </div>
      </div>
    );
  }

  // If not authenticated and trying to access protected route, render nothing (will redirect)
  if (!isAuthenticated && (pathname?.startsWith("/dashboard") || pathname?.startsWith("/onboarding"))) {
    return null;
  }

  return <>{children}</>;
}
