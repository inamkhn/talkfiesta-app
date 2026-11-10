import { useRef } from "react";
import { useAuthStore } from "@/store/authStore";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import apiClient, { revokeSession, withSessionLock } from "@/lib/api/axios";
import { UserResponse } from "@/lib/api/types";
import { useRouter } from "next/navigation";

import { authApi, type AuthSessionResponse, type LoginInput, type RegisterInput, type GoogleInput, type ResetPasswordInput } from "@/lib/api/auth";
type AuthOptions = { onSuccess?: () => void; onError?: (error: unknown) => void };

export function useAuth() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user, isAuthenticated, isLoading } = useAuthStore();

  const authenticationInFlight = useRef(false);
  const authenticate = async (request: () => Promise<AuthSessionResponse>) => {
    if (authenticationInFlight.current) throw new Error("Sign-in is already in progress.");
    authenticationInFlight.current = true;
    try {
      const token = await withSessionLock(async () => {
        const data = await request();
        await queryClient.cancelQueries();
        localStorage.setItem("access_token", data.access_token);
        localStorage.removeItem("refresh_token");
        return data.access_token;
      });
      queryClient.removeQueries({ predicate: query => query.queryKey[0] !== "currentUser" });
      useAuthStore.getState().setLearningProfile(null);
      const me = await apiClient.get<UserResponse>("/users/me");
      if (localStorage.getItem("access_token") !== token) throw new Error("The session changed. Please sign in again.");
      queryClient.setQueryData(["currentUser"], me.data);
      useAuthStore.getState().setUser(me.data);
      return me.data;
    } finally { authenticationInFlight.current = false; }
  };

  const loginMutation = useMutation({ mutationFn: (data: LoginInput) => authenticate(() => authApi.login(data)) });
  const registerMutation = useMutation({ mutationFn: (data: RegisterInput) => authenticate(() => authApi.register(data)) });
  const googleMutation = useMutation({ mutationFn: (data: GoogleInput) => authenticate(() => authApi.googleExchange(data)) });
  const afterAuthentication = () => {
    // The guarded entry point loads /onboarding/state before choosing a screen.
    router.replace("/onboarding");
  };
  const login = (data: LoginInput, options?: AuthOptions) => loginMutation.mutate(data, {
    onSuccess: () => { afterAuthentication(); options?.onSuccess?.(); },
    onError: error => options?.onError?.(error),
  });
  const register = (data: RegisterInput, options?: AuthOptions) => registerMutation.mutate(data, {
    onSuccess: () => { afterAuthentication(); options?.onSuccess?.(); },
    onError: error => options?.onError?.(error),
  });
  const googleLogin = (idToken: string, options?: AuthOptions) => googleMutation.mutate({ id_token: idToken }, {
    onSuccess: () => { afterAuthentication(); options?.onSuccess?.(); },
    onError: error => options?.onError?.(error),
  });
  const logout = async () => {
    // Preserve the session if revocation fails; do not report a false logout.
    await revokeSession();
    await queryClient.cancelQueries();
    queryClient.removeQueries({ predicate: query => query.queryKey[0] !== "currentUser" });
    queryClient.setQueryData(["currentUser"], null);
    router.replace("/login");
  };

  const forgotPasswordMutation = useMutation({
    mutationFn: async (email: string) => authApi.forgotPassword({ email }),
  });
  const resetPasswordMutation = useMutation({
    mutationFn: async (data: ResetPasswordInput) => {
      await withSessionLock(async () => {
        await authApi.resetPassword(data);
        // The server revokes sessions and clears its cookie on 204. Discard
        // in-flight profile loads before they can restore obsolete user data.
        await queryClient.cancelQueries();
        useAuthStore.getState().logout();
        queryClient.removeQueries({ predicate: query => query.queryKey[0] !== "currentUser" });
        queryClient.setQueryData(["currentUser"], null);
      });
    },
  });

  const requestPasswordReset = (
    email: string,
    options?: {
      onSuccess?: (data: { message: string }) => void;
      onError?: (error: unknown) => void;
    }
  ) => {
    forgotPasswordMutation.mutate(email, {
      onSuccess: (data) => options?.onSuccess?.(data),
      onError: (err) => options?.onError?.(err),
    });
  };

  const resetPassword = (
    data: ResetPasswordInput,
    options?: { onSuccess?: () => void; onError?: (error: unknown) => void }
  ) => {
    resetPasswordMutation.mutate(data, {
      onSuccess: () => options?.onSuccess?.(),
      onError: (err) => options?.onError?.(err),
    });
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
    googleLogin,
    isGoogleLoggingIn: googleMutation.isPending,
    requestPasswordReset,
    isRequestingReset: forgotPasswordMutation.isPending,
    resetPassword,
    isResettingPassword: resetPasswordMutation.isPending,
  };
}
