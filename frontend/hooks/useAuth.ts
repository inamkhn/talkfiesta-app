import { useAuthStore } from "@/store/authStore";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/lib/api/axios";
import { useRouter } from "next/navigation";

interface TokenPair {
  access_token: string;
  refresh_token?: string;
}

export function useAuth() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user, isAuthenticated, isLoading, logout: storeLogout } = useAuthStore();

  const loginMutation = useMutation({
    mutationFn: async (data: any) => {
      const formData = new URLSearchParams();
      formData.append('username', data.username || data.email);
      formData.append('password', data.password);
      
      const response = await apiClient.post("/auth/login", formData, {
        headers: { "Content-Type": "application/x-www-form-urlencoded" }
      });
      return response.data;
    }
  });

  const registerMutation = useMutation({
    mutationFn: async (data: any) => {
      const response = await apiClient.post("/auth/register", data);
      return response.data;
    }
  });

  // Persist tokens, then hydrate the auth store BEFORE navigating so AuthGuard
  // never sees isAuthenticated=false on a protected route mid-login (which
  // would bounce a freshly logged-in user straight back to /login).
  const completeAuthentication = async (tokens: TokenPair) => {
    localStorage.setItem("access_token", tokens.access_token);
    if (tokens.refresh_token) {
      localStorage.setItem("refresh_token", tokens.refresh_token);
    }

    const { setUser, setLearningProfile, setLoading } = useAuthStore.getState();
    setLoading(true); // guard shows the spinner instead of redirecting
    // New users go to onboarding first; returning users land on the dashboard.
    let destination = "/dashboard";
    try {
      const me = await apiClient.get("/auth/me");
      setUser(me.data);
      setLearningProfile(me.data.learning_profile || null);
      // Seed the cache so AuthProvider doesn't refetch/flash on mount
      queryClient.setQueryData(["currentUser"], me.data);
      if (!me.data.onboarding_completed) {
        destination = "/goal-selection";
      }
    } catch {
      // Tokens are stored; keep isLoading=true and let AuthProvider's
      // /auth/me query settle the session (success -> setUser, failure ->
      // logged out). Either way the guard resolves without a race.
      queryClient.invalidateQueries({ queryKey: ["currentUser"] });
    }
    router.push(destination);
  };

  const login = (data: any, options?: { onSuccess?: () => void; onError?: (error: any) => void }) => {
    loginMutation.mutate(data, {
      onSuccess: async (response) => {
        options?.onSuccess?.();
        await completeAuthentication(response);
      },
      onError: (err) => {
        options?.onError?.(err);
      },
    });
  };

  const register = (data: any, options?: { onSuccess?: () => void; onError?: (error: any) => void }) => {
    registerMutation.mutate(data, {
      onSuccess: async (response) => {
        options?.onSuccess?.();
        await completeAuthentication(response);
      },
      onError: (err) => {
        options?.onError?.(err);
      },
    });
  };

  const logout = async () => {
    // Revoke the refresh token server-side BEFORE wiping local storage —
    // otherwise it stays valid for its full lifetime after "logout".
    const refreshToken =
      typeof window !== "undefined" ? localStorage.getItem("refresh_token") : null;
    if (refreshToken) {
      try {
        await apiClient.post("/auth/logout", { refresh_token: refreshToken });
      } catch {
        // Best-effort: revocation failure (offline, expired) must not block local logout.
      }
    }
    storeLogout();
    // Drop every cached query so the next account never sees this user's data.
    queryClient.clear();
    router.push("/login");
  };

  return {
    user,
    isAuthenticated,
    isLoading,
    login,
    isLoggingIn: loginMutation.isPending,
    loginError: loginMutation.error,
    register,
    isRegistering: registerMutation.isPending,
    registerError: registerMutation.error,
    logout,
  };
}
