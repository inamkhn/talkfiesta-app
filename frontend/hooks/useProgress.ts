import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getDashboardSummary, getProgressHistory, getAchievements, trackProgress } from "@/lib/api/progress";
import { TrackProgressRequest } from "@/lib/api/types";

export function useProgress() {
  const queryClient = useQueryClient();

  const dashboardQuery = useQuery({
    queryKey: ["dashboard"],
    queryFn: getDashboardSummary,
  });

  const historyQuery = useQuery({
    queryKey: ["progress", "history"],
    queryFn: getProgressHistory,
  });

  const achievementsQuery = useQuery({
    queryKey: ["progress", "achievements"],
    queryFn: getAchievements,
  });

  const trackMutation = useMutation({
    mutationFn: (data: TrackProgressRequest) => trackProgress(data),
    onSuccess: () => {
      // Invalidate dashboard and history to refetch latest progress
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["progress"] });
    },
  });

  return {
    // Queries
    dashboard: dashboardQuery.data,
    isLoadingDashboard: dashboardQuery.isLoading,
    isErrorDashboard: dashboardQuery.isError,

    history: historyQuery.data,
    isLoadingHistory: historyQuery.isLoading,

    achievements: achievementsQuery.data,
    isLoadingAchievements: achievementsQuery.isLoading,

    // Mutations
    trackProgress: trackMutation.mutate,
    isTracking: trackMutation.isPending,
  };
}
