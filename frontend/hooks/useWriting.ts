import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { writingApi } from "@/lib/api/writing";
import {
  DraftSaveRequest,
  SubmissionCreateRequest,
  SubmissionReviseRequest,
} from "@/lib/api/types";

export const writingKeys = {
  all: ["writing"] as const,
  dailyPrompt: (day: number) => [...writingKeys.all, "prompt", day] as const,
  submission: (id: string) => [...writingKeys.all, "submission", id] as const,
  portfolio: () => [...writingKeys.all, "portfolio"] as const,
};

export const useDailyPrompt = (day: number) => {
  return useQuery({
    queryKey: writingKeys.dailyPrompt(day),
    queryFn: () => writingApi.getDailyPrompt(day),
    enabled: day > 0,
  });
};

export const useSaveDraft = () => {
  return useMutation({
    mutationFn: (data: DraftSaveRequest) => writingApi.saveDraft(data),
  });
};

export const useSubmitWriting = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: SubmissionCreateRequest) => writingApi.submitWriting(data),
    onSuccess: (data) => {
      queryClient.setQueryData(writingKeys.submission(data.id), data);
      queryClient.invalidateQueries({ queryKey: writingKeys.portfolio() });
    },
  });
};

export const useSubmission = (id: string) => {
  return useQuery({
    queryKey: writingKeys.submission(id),
    queryFn: () => writingApi.getSubmission(id),
    enabled: !!id,
    // Polling if processing
    refetchInterval: (query) => {
      if (query.state.data?.status === "PROCESSING" || query.state.data?.status === "PENDING") {
        return 2000; // Poll every 2 seconds
      }
      return false;
    },
  });
};

export const useReviseSubmission = (id: string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: SubmissionReviseRequest) => writingApi.reviseSubmission(id, data),
    onSuccess: (data) => {
      queryClient.setQueryData(writingKeys.submission(id), data);
      queryClient.invalidateQueries({ queryKey: writingKeys.portfolio() });
    },
  });
};

export const useWritingPortfolio = () => {
  return useQuery({
    queryKey: writingKeys.portfolio(),
    queryFn: () => writingApi.getPortfolio(),
  });
};
