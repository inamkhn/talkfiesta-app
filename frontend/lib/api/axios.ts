import axios, { type InternalAxiosRequestConfig } from "axios";
import { authApi } from "./auth";
import { useAuthStore } from "@/store/authStore";

const apiClient = axios.create({
  baseURL: "/api/v1",
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});

export async function withSessionLock<T>(operation: () => Promise<T>): Promise<T> {
  // Serialize rotation and logout across tabs sharing the refresh cookie.
  if (typeof navigator !== "undefined" && navigator.locks) {
    return await navigator.locks.request("talkfiesta-session", operation);
  }
  return operation();
}

apiClient.interceptors.request.use((config) => {
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  else config.headers.delete("Authorization");
  return config;
});

let refreshPromise: Promise<string> | null = null;
export function refreshAccessToken(failedToken: string | null): Promise<string> {
  if (!refreshPromise) {
    refreshPromise = withSessionLock(async () => {
      const current = localStorage.getItem("access_token");
      // Another request/tab may already have rotated the cookie.
      if (current && current !== failedToken) return current;
      if (failedToken && !current) throw new Error("Session ended while refreshing.");
      const data = await authApi.refresh();
      localStorage.setItem("access_token", data.access_token);
      localStorage.removeItem("refresh_token"); // Remove obsolete client-stored credentials.
      return data.access_token;
    }).finally(() => { refreshPromise = null; });
  }
  return refreshPromise;
}

export async function revokeSession(): Promise<void> {
  // Also coordinate in browsers without Web Locks.
  if (refreshPromise) await refreshPromise.catch(() => undefined);
  await withSessionLock(async () => {
    await authApi.logout();
    useAuthStore.getState().logout();
  });
}

apiClient.interceptors.response.use(response => response, async (error: unknown) => {
  if (!axios.isAxiosError(error)) return Promise.reject(error);
  const config = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined;
  const authEndpoint = config?.url?.startsWith("/auth/");
  if (error.response?.status !== 401 || !config || config._retry || authEndpoint || typeof window === "undefined") {
    return Promise.reject(error);
  }
  config._retry = true;
  const authorization = config.headers.Authorization;
  const failedToken = typeof authorization === "string" ? authorization.replace(/^Bearer /, "") : null;
  try {
    const token = await refreshAccessToken(failedToken);
    config.headers.Authorization = `Bearer ${token}`;
    return apiClient(config);
  } catch (refreshError) {
    // Keep the session on network/server failures so the user can retry.
    if (axios.isAxiosError(refreshError) && [401, 403].includes(refreshError.response?.status ?? 0)) {
      useAuthStore.getState().logout();
    }
    return Promise.reject(refreshError);
  }
});

export default apiClient;
