import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { 
  getDailyVocabulary, 
  submitMatch, 
  submitFillBlank, 
  completePracticeSession, 
  getVocabBank 
} from "@/lib/api/vocabulary";
import { 
  MatchSubmission, 
  FillBlankSubmission, 
  SessionCompleteRequest 
} from "@/lib/api/types";

export function useDailyVocabulary(day: number) {
  return useQuery({
    queryKey: ["vocabulary", "day", day],
    queryFn: () => getDailyVocabulary(day),
    enabled: !!day,
  });
}

export function useVocabBank(page = 1, perPage = 10, search?: string) {
  return useQuery({
    queryKey: ["vocabulary", "bank", page, perPage, search],
    queryFn: () => getVocabBank(page, perPage, search),
  });
}

export function useVocabularyMutations() {
  const queryClient = useQueryClient();

  const matchMutation = useMutation({
    mutationFn: (data: MatchSubmission) => submitMatch(data),
  });

  const fillBlankMutation = useMutation({
    mutationFn: (data: FillBlankSubmission) => submitFillBlank(data),
  });

  const completeSessionMutation = useMutation({
    mutationFn: (data: SessionCompleteRequest) => completePracticeSession(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["progress"] });
      queryClient.invalidateQueries({ queryKey: ["vocabulary"] });
    },
  });

  return {
    submitMatch: matchMutation.mutateAsync,
    isSubmittingMatch: matchMutation.isPending,

    submitFillBlank: fillBlankMutation.mutateAsync,
    isSubmittingFillBlank: fillBlankMutation.isPending,

    completeSession: completeSessionMutation.mutateAsync,
    isCompletingSession: completeSessionMutation.isPending,
  };
}
