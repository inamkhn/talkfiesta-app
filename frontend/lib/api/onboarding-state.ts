import { z } from "zod";
import apiClient from "./axios";

const stateSchema = z.object({
  status: z.enum(["NOT_STARTED", "PREFERENCES_SAVED", "ASSESSING", "RESULT_READY", "COMPLETED"]),
  next_step: z.enum(["PREFERENCES", "ASSESSMENT", "ASSESSMENT_PROCESSING", "ASSESSMENT_RESULT", "ASSESSMENT_RETRY", "DASHBOARD"]),
  active_assessment_id: z.string().uuid().nullable(),
  assessment_status: z.enum(["IN_PROGRESS", "SUBMITTED", "PROCESSING", "COMPLETED", "FAILED_RETRYABLE", "FAILED_FINAL"]).nullable(),
  can_access_dashboard: z.boolean(),
}).refine(state => {
  if (state.next_step === "DASHBOARD") return state.can_access_dashboard && state.status === "COMPLETED";
  if (state.can_access_dashboard || state.status === "COMPLETED") return false;
  if (["ASSESSMENT_PROCESSING", "ASSESSMENT_RESULT", "ASSESSMENT_RETRY"].includes(state.next_step)) return !!state.active_assessment_id;
  return true;
}, "The saved onboarding state is inconsistent.");

export type OnboardingState = z.infer<typeof stateSchema>;
export async function getOnboardingState(signal?: AbortSignal): Promise<OnboardingState> {
  const response = await apiClient.get<unknown>("/onboarding/state", { signal });
  return stateSchema.parse(response.data);
}

export function onboardingDestination(state: OnboardingState): string {
  switch (state.next_step) {
    case "PREFERENCES": return "/goal-selection";
    case "ASSESSMENT": return "/level-assessment";
    case "ASSESSMENT_PROCESSING": return "/level-assessment/processing";
    case "ASSESSMENT_RESULT": return "/level-assessment/result";
    case "ASSESSMENT_RETRY": return "/level-assessment/retry";
    case "DASHBOARD": return "/dashboard";
  }
}

export function isOnboardingPath(pathname: string): boolean {
  return pathname === "/onboarding" || pathname === "/goal-selection" || pathname === "/level-assessment" || pathname.startsWith("/level-assessment/");
}
