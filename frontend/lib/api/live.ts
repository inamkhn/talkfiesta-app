import apiClient from "./axios";
import {
  LiveConversationSessionCreate,
  LiveConversationSessionTokenResponse,
  LiveConversationSessionEnd,
  LiveConversationSessionResponse
} from "./types";

export const liveSpeakingApi = {
  startSession: async (data: LiveConversationSessionCreate): Promise<LiveConversationSessionTokenResponse> => {
    const response = await apiClient.post("/live/session", data);
    return response.data;
  },

  endSession: async (sessionId: string, data: LiveConversationSessionEnd): Promise<LiveConversationSessionResponse> => {
    const response = await apiClient.post(`/live/session/${sessionId}/end`, data);
    return response.data;
  },

  getSession: async (sessionId: string): Promise<LiveConversationSessionResponse> => {
    const response = await apiClient.get(`/live/session/${sessionId}`);
    return response.data;
  },
};
