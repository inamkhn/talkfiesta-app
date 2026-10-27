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
  draft: (promptId: string) => [...writingKeys.all, "draft", promptId] as const,
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

export const useWritingDraft = (promptId: string | undefined) => {
  return useQuery({
    queryKey: writingKeys.draft(promptId || ""),
    queryFn: () => writingApi.getDraft(promptId!),
    enabled: !!promptId,
  });
};

export const useSaveDraft = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: DraftSaveRequest) => writingApi.saveDraft(data),
    onSuccess: (_data, variables) => {
      // Keep the restorable draft in sync with what was just persisted.
      queryClient.invalidateQueries({ queryKey: writingKeys.draft(variables.prompt_id) });
    },
  });
};

export const useSubmitWriting = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: SubmissionCreateRequest) => writingApi.submitWriting(data),
    onSuccess: (data) => {
      queryClient.setQueryData(writingKeys.submission(data.id), data);
      queryClient.invalidateQueries({ queryKey: writingKeys.portfolio() });
      // The draft was promoted to a PROCESSING submission; drop the stale copy.
      queryClient.invalidateQueries({ queryKey: writingKeys.draft(data.prompt_id) });
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
