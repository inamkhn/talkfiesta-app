import { useAuthStore } from "@/store/authStore";
import { useMutation } from "@tanstack/react-query";
import apiClient from "@/lib/api/axios";
import { useRouter } from "next/navigation";

export function useAuth() {
  const router = useRouter();
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

  const login = (data: any, options?: { onSuccess?: () => void; onError?: (error: any) => void }) => {
    loginMutation.mutate(data, {
      onSuccess: (response) => {
        localStorage.setItem("access_token", response.access_token);
        if (response.refresh_token) {
          localStorage.setItem("refresh_token", response.refresh_token);
        }
        options?.onSuccess?.();
        router.push("/dashboard");
      },
      onError: (err) => {
        options?.onError?.(err);
      },
    });
  };

  const register = (data: any, options?: { onSuccess?: () => void; onError?: (error: any) => void }) => {
    registerMutation.mutate(data, {
      onSuccess: (response) => {
        localStorage.setItem("access_token", response.access_token);
        if (response.refresh_token) {
          localStorage.setItem("refresh_token", response.refresh_token);
        }
        options?.onSuccess?.();
        router.push("/dashboard");
      },
      onError: (err) => {
        options?.onError?.(err);
      },
    });
  };

  const logout = () => {
    storeLogout();
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
