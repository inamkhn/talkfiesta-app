import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { speakingApi } from "@/lib/api/speaking";
import { liveSpeakingApi } from "@/lib/api/live";
import { 
  SpeakingExerciseType, 
  SpeakingSubmissionCreate,
  LiveConversationSessionCreate,
  LiveConversationSessionEnd
} from "@/lib/api/types";

// --- Flow A: Scripted Speaking ---

export function useSpeakingExercise(cycle: number, day: number, exerciseType: SpeakingExerciseType = "CONVERSATIONAL") {
  return useQuery({
    queryKey: ["speakingExercise", cycle, day, exerciseType],
    queryFn: () => speakingApi.getExercise(cycle, day, exerciseType),
  });
}

export function useSubmitAudio() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: SpeakingSubmissionCreate) => speakingApi.submitAudio(data),
    onSuccess: (data) => {
      queryClient.setQueryData(["speakingSubmission", data.id], data);
    },
  });
}

export function useSpeakingSubmission(id: string) {
  return useQuery({
    queryKey: ["speakingSubmission", id],
    queryFn: () => speakingApi.getSubmission(id),
    enabled: !!id,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "PROCESSING" || status === "PENDING" ? 2000 : false;
    },
  });
}

export function useSpeakingProgress() {
  return useQuery({
    queryKey: ["speakingProgress"],
    queryFn: () => speakingApi.getProgress(),
  });
}

// --- Flow B: Live Conversation ---

export function useStartLiveSession() {
  return useMutation({
    mutationFn: (data: LiveConversationSessionCreate) => liveSpeakingApi.startSession(data),
  });
}

export function useEndLiveSession(sessionId: string) {
  return useMutation({
    mutationFn: (data: LiveConversationSessionEnd) => liveSpeakingApi.endSession(sessionId, data),
  });
}

export function useLiveSession(sessionId: string) {
  return useQuery({
    queryKey: ["liveSession", sessionId],
    queryFn: () => liveSpeakingApi.getSession(sessionId),
    enabled: !!sessionId,
    // Typically live sessions are active or ended. We can poll if we are waiting for submission completion.
  });
}
