import { useMutation, useQueryClient } from "@tanstack/react-query";
import { configureLearningProfile, completeOnboarding } from "@/lib/api/onboarding";
import { useAuthStore } from "@/store/authStore";
import { LearningProfileCreate } from "@/lib/api/types";
import { useRouter } from "next/navigation";

export function useOnboarding() {
  const router = useRouter();
  const { setLearningProfile, setUser } = useAuthStore();

  const configureProfileMutation = useMutation({
    mutationFn: (data: LearningProfileCreate) => configureLearningProfile(data),
    onSuccess: (data) => {
      setLearningProfile(data);
    },
  });

  const completeOnboardingMutation = useMutation({
    mutationFn: completeOnboarding,
    onSuccess: (data) => {
      setUser(data.user);
      setLearningProfile(data.learning_profile);
      router.push("/dashboard");
    },
  });

  return {
    configureProfile: configureProfileMutation.mutate,
    isConfiguring: configureProfileMutation.isPending,
    
    completeOnboarding: completeOnboardingMutation.mutate,
    isCompleting: completeOnboardingMutation.isPending,
  };
}
