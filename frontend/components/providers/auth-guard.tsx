"use client";
import { useCallback, useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { isProtectedPath } from "@/lib/routes";
import {
  getOnboardingState,
  isOnboardingPath,
  onboardingDestination,
} from "@/lib/api/onboarding-state";
import { OnboardingStateContext } from "./onboarding-state-context";
import { EmailVerificationReminder } from "@/components/auth/EmailVerificationReminder";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, isAuthenticated, isLoading } = useAuthStore();
  const protectedPage = isProtectedPath(pathname);
  const authEntry = pathname === "/login" || pathname === "/register";
  const checkOnboarding =
    isAuthenticated && !isLoading && (protectedPage || authEntry);
  const onboarding = useQuery({
    // Recheck on route navigation; never share onboarding data across accounts.
    queryKey: ["onboarding-state", user?.id, pathname],
    queryFn: ({ signal }) => getOnboardingState(signal),
    enabled: checkOnboarding,
    retry: false,
    staleTime: 0,
    refetchOnWindowFocus: true,
    refetchInterval: (query) =>
      query.state.data?.next_step === "ASSESSMENT_PROCESSING" ? 5000 : false,
  });
  const { refetch: refetchOnboarding } = onboarding;
  const refreshOnboarding = useCallback(() => {
    void refetchOnboarding();
  }, [refetchOnboarding]);
  let destination: string | null = null;
  if (!isLoading && !isAuthenticated && protectedPage) destination = "/login";
  if (checkOnboarding && onboarding.data && !onboarding.isError) {
    const state = onboarding.data;
    if (state.can_access_dashboard) {
      if (
        authEntry ||
        (isOnboardingPath(pathname) && pathname !== "/learning-plan-ready")
      )
        destination = "/dashboard";
    } else {
      // Allow editing preferences before an assessment exists. Once an attempt
      // exists, its server-owned state chooses the appropriate resume screen.
      const editingPreferences =
        pathname === "/goal-selection" &&
        state.next_step === "ASSESSMENT" &&
        !state.active_assessment_id;
      if (!editingPreferences) destination = onboardingDestination(state);
    }
    if (destination === pathname) destination = null;
  }
  useEffect(() => {
    if (destination) router.replace(destination);
  }, [destination, router]);

  if (checkOnboarding && onboarding.isError && !onboarding.data) {
    return (
      <main className="journey-theme flex min-h-screen flex-col items-center justify-center gap-5 p-6">
        <h1 className="text-xl font-semibold">
          We couldn’t load your saved progress.
        </h1>
        <p role="alert" className="max-w-md text-center text-sm">
          Please try again. We haven’t changed your preferences or assessment.
        </p>
        <button
          className="journey-primary"
          disabled={onboarding.isFetching}
          onClick={() => onboarding.refetch()}
        >
          Retry
        </button>
      </main>
    );
  }
  if (
    (protectedPage && (isLoading || !isAuthenticated)) ||
    (checkOnboarding && onboarding.isPending) ||
    destination
  ) {
    return (
      <div
        role="status"
        className="journey-theme flex min-h-screen items-center justify-center p-6"
      >
        Loading your saved progress…
      </div>
    );
  }
  if (checkOnboarding && onboarding.data) {
    return (
      <OnboardingStateContext.Provider
        value={{
          state: onboarding.data,
          refresh: refreshOnboarding,
          isRefreshing: onboarding.isFetching,
        }}
      >
        {onboarding.isError && (
          <div
            role="alert"
            className="journey-theme border-b border-orange-200 p-4 text-center text-sm"
          >
            We couldn’t refresh your progress. Your open activity is still here.{" "}
            <button className="underline" onClick={refreshOnboarding}>
              Retry status check
            </button>
          </div>
        )}
        {protectedPage && <EmailVerificationReminder />}
        {children}
      </OnboardingStateContext.Provider>
    );
  }
  return <>{children}</>;
}
