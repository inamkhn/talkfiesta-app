import apiClient from "./axios";
import { completeOnboarding as completeOnboardingAssessment } from "./assessment-result";
import { getOnboardingState, type OnboardingState } from "./onboarding-state";

export interface SaveOnboardingPreferencesInput {
  goals: string[];
  focus_areas: string[];
  topics: string[];
  daily_minutes: number;
  self_reported_comfort: string;
  timezone: string;
}

export const fetchOnboardingState = async (signal?: AbortSignal): Promise<OnboardingState> => {
  return getOnboardingState(signal);
};

export const saveOnboardingPreferences = async (
  data: SaveOnboardingPreferencesInput
): Promise<{ status: string }> => {
  const response = await apiClient.put<{ status: string }>("/onboarding/preferences", data);
  return response.data;
};

export const completeOnboarding = async (
  assessmentAttemptId: string
): Promise<{ learning_plan_id: string }> => {
  return completeOnboardingAssessment(assessmentAttemptId);
};

