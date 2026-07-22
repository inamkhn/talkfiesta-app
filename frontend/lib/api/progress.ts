import apiClient from "./axios";
import { DashboardSummaryResponse, DailyProgressResponse, AchievementResponse, TrackProgressRequest } from "./types";

export const getDashboardSummary = async (): Promise<DashboardSummaryResponse> => {
  const response = await apiClient.get("/progress/dashboard");
  return response.data;
};

export const getProgressHistory = async (): Promise<DailyProgressResponse[]> => {
  const response = await apiClient.get("/progress/history");
  return response.data;
};

export const getAchievements = async (): Promise<AchievementResponse[]> => {
  const response = await apiClient.get("/progress/achievements");
  return response.data;
};

export const trackProgress = async (data: TrackProgressRequest): Promise<DailyProgressResponse> => {
  const response = await apiClient.post("/progress/track", data);
  return response.data;
};
