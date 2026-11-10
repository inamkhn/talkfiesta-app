import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  completeOnboarding,
  saveOnboardingPreferences,
  type SaveOnboardingPreferencesInput,
} from "@/lib/api/onboarding";
import { useRouter } from "next/navigation";

export function useOnboarding() {
  const router = useRouter();
  const queryClient = useQueryClient();

  const savePreferencesMutation = useMutation({
    mutationFn: (data: SaveOnboardingPreferencesInput) => saveOnboardingPreferences(data),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["onboarding-preferences"] });
      await queryClient.invalidateQueries({ queryKey: ["onboarding-state"] });
      router.replace("/onboarding");
    },
  });

  const completeOnboardingMutation = useMutation({
    mutationFn: (assessmentAttemptId: string) => completeOnboarding(assessmentAttemptId),
    onSuccess: async () => {
      router.replace("/learning-plan-ready");
      await queryClient.invalidateQueries({ queryKey: ["onboarding-state"] });
    },
  });

  return {
    savePreferences: savePreferencesMutation.mutate,
    isSavingPreferences: savePreferencesMutation.isPending,
    completeOnboarding: completeOnboardingMutation.mutate,
    isCompleting: completeOnboardingMutation.isPending,
  };
}

