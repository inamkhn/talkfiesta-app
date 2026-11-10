"use client";
import { createContext, useContext } from "react";
import { OnboardingState } from "@/lib/api/onboarding-state";

export const OnboardingStateContext = createContext<{
  state: OnboardingState;
  refresh: () => void;
  isRefreshing: boolean;
} | null>(null);

export function useOnboardingState() {
  const context = useContext(OnboardingStateContext);
  if (!context) throw new Error("Onboarding state requires an authenticated route guard.");
  return context;
}
