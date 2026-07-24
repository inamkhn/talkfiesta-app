import apiClient from "./axios";
import { 
  DayWordsResponse, 
  FillBlankSubmission, 
  FillBlankResult, 
  MatchSubmission, 
  MatchResult, 
  SessionCompleteRequest, 
  SessionCompleteResponse, 
  VocabBankResponse 
} from "./types";

export const getDailyVocabulary = async (day: number): Promise<DayWordsResponse> => {
  const response = await apiClient.get(`/vocabulary/day/${day}`);
  return response.data;
};

export const submitFillBlank = async (data: FillBlankSubmission): Promise<FillBlankResult> => {
  const response = await apiClient.post("/vocabulary/exercise/fill-blank/submit", data);
  return response.data;
};

export const submitMatch = async (data: MatchSubmission): Promise<MatchResult> => {
  const response = await apiClient.post("/vocabulary/exercise/match/submit", data);
  return response.data;
};

export const completePracticeSession = async (data: SessionCompleteRequest): Promise<SessionCompleteResponse> => {
  const response = await apiClient.post("/vocabulary/session/complete", data);
  return response.data;
};

export const getVocabBank = async (page = 1, perPage = 10, search?: string): Promise<VocabBankResponse> => {
  const response = await apiClient.get("/vocabulary/bank", {
    params: { page, per_page: perPage, search: search || undefined }
  });
  return response.data;
};
