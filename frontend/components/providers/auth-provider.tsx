"use client";
import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { isAxiosError } from "axios";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { isProtectedPath } from "@/lib/routes";
import { UserResponse } from "@/lib/api/types";
import apiClient from "@/lib/api/axios";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const pathname = usePathname();
  const { setUser, setLoading } = useAuthStore();
  const session = useQuery<UserResponse | null>({
    queryKey: ["currentUser"],
    queryFn: async ({ signal }) => (await apiClient.get<UserResponse>("/users/me", { signal })).data,
    retry: false,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });
  const rejected = isAxiosError(session.error) && [401, 403].includes(session.error.response?.status ?? 0);

  useEffect(() => {
    if (session.isSuccess) setUser(session.data);
    else if (rejected) setUser(null);
  }, [session.isSuccess, session.data, rejected, setUser]);

  useEffect(() => {
    localStorage.removeItem("refresh_token");
    const onStorage = (event: StorageEvent) => {
      if (event.key !== null && event.key !== "access_token") return;
      // Cancel old-account requests before exposing the next account's data.
      void queryClient.cancelQueries().then(() => {
        queryClient.removeQueries({ predicate: query => query.queryKey[0] !== "currentUser" });
        if (!localStorage.getItem("access_token")) {
          setUser(null);
          queryClient.setQueryData(["currentUser"], null);
        } else {
          setLoading(true);
          void queryClient.invalidateQueries({ queryKey: ["currentUser"] });
        }
      });
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [queryClient, setLoading, setUser]);

  if (session.isError && !rejected && isProtectedPath(pathname)) {
    return <main className="journey-theme flex min-h-screen flex-col items-center justify-center gap-5 p-6"><p role="alert">We couldn’t check your session. Please try again.</p><button className="journey-primary" disabled={session.isFetching} onClick={() => session.refetch()}>Retry connection</button></main>;
  }
  return <>{children}</>;
}
