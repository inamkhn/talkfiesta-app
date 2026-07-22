import apiClient from "./axios";
import { LearningProfileCreate, LearningProfileResponse, OnboardingCompleteResponse } from "./types";

export const configureLearningProfile = async (data: LearningProfileCreate): Promise<LearningProfileResponse> => {
  const response = await apiClient.post("/auth/onboarding/learning-profile", data);
  return response.data;
};

export const completeOnboarding = async (): Promise<OnboardingCompleteResponse> => {
  const response = await apiClient.post("/auth/onboarding/complete");
  return response.data;
};
