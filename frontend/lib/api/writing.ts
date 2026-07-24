import apiClient from "./axios";
import {
  WritingPromptResponse,
  DraftSaveRequest,
  DraftSaveResponse,
  SubmissionCreateRequest,
  WritingSubmissionResponse,
  SubmissionReviseRequest,
  WritingPortfolioResponse,
} from "./types";

export const writingApi = {
  getDailyPrompt: async (day: number): Promise<WritingPromptResponse> => {
    const response = await apiClient.get(`/writing/prompt/${day}`);
    return response.data;
  },

  saveDraft: async (data: DraftSaveRequest): Promise<DraftSaveResponse> => {
    const response = await apiClient.post("/writing/draft/save", data);
    return response.data;
  },

  submitWriting: async (data: SubmissionCreateRequest): Promise<WritingSubmissionResponse> => {
    const response = await apiClient.post("/writing/submit", data);
    return response.data;
  },

  getSubmission: async (id: string): Promise<WritingSubmissionResponse> => {
    const response = await apiClient.get(`/writing/submission/${id}`);
    return response.data;
  },

  reviseSubmission: async (id: string, data: SubmissionReviseRequest): Promise<WritingSubmissionResponse> => {
    const response = await apiClient.post(`/writing/submission/${id}/revise`, data);
    return response.data;
  },

  getPortfolio: async (): Promise<WritingPortfolioResponse> => {
    const response = await apiClient.get("/writing/portfolio");
    return response.data;
  },
};
