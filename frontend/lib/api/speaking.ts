import apiClient from "./axios";
import {
  SpeakingExerciseResponse,
  SpeakingSubmissionCreate,
  SpeakingSubmissionResponse,
  SpeakingProgressResponse,
  SpeakingExerciseType
} from "./types";

export const speakingApi = {
  getExercise: async (
    cycle: number, 
    day: number, 
    exerciseType: SpeakingExerciseType = "CONVERSATIONAL"
  ): Promise<SpeakingExerciseResponse> => {
    const response = await apiClient.get(`/speaking/exercise/${cycle}/${day}`, {
      params: { exercise_type: exerciseType }
    });
    return response.data;
  },

  submitAudio: async (data: SpeakingSubmissionCreate): Promise<SpeakingSubmissionResponse> => {
    const response = await apiClient.post("/speaking/submit", data);
    return response.data;
  },

  getSubmission: async (id: string): Promise<SpeakingSubmissionResponse> => {
    const response = await apiClient.get(`/speaking/session/${id}`);
    return response.data;
  },

  getProgress: async (): Promise<SpeakingProgressResponse> => {
    const response = await apiClient.get("/speaking/progress");
    return response.data;
  },
};
