'use client';

import { useEffect, useState } from 'react';
import { useAuthStore } from '@/store/authStore';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/lib/api/axios';

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const { setUser, setLoading } = useAuthStore();
  const queryClient = useQueryClient();
  const [mounted, setMounted] = useState(false);
  // Bumped by cross-tab storage events so `hasToken` is re-evaluated below.
  const [, bumpTokenVersion] = useState(0);

  // We check if we are on the client before reading localStorage
  const hasToken = typeof window !== 'undefined' ? !!localStorage.getItem('access_token') : false;

  const { data, isLoading, isError } = useQuery({
    queryKey: ['currentUser'],
    queryFn: async () => {
      const response = await apiClient.get('/auth/me');
      return response.data;
    },
    enabled: mounted && hasToken,
    retry: false,
  });

  useEffect(() => {
    setMounted(true);
  }, []);

  // Cross-tab session sync: `storage` events only fire in OTHER tabs, so a
  // login/logout performed elsewhere is mirrored here. Without this, a tab
  // left open after logging out in another tab keeps serving a dead session.
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      // key === null means localStorage.clear(); otherwise only token keys matter
      if (e.key !== null && e.key !== 'access_token' && e.key !== 'refresh_token') return;
      if (!localStorage.getItem('access_token')) {
        // Logged out (or storage cleared) in another tab
        useAuthStore.getState().logout();
        queryClient.clear();
      } else {
        // Logged in — possibly as a different account — in another tab
        queryClient.invalidateQueries({ queryKey: ['currentUser'] });
      }
      bumpTokenVersion((v) => v + 1); // re-render so `hasToken` is recomputed
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, [queryClient]);

  useEffect(() => {
    if (mounted) {
      if (!hasToken) {
        setLoading(false);
      }
    }
  }, [mounted, hasToken, setLoading]);

  useEffect(() => {
    if (data) {
      setUser(data);
      const { setLearningProfile } = useAuthStore.getState();
      setLearningProfile(data.learning_profile || null);
    } else if (isError) {
      // Interceptor handles the refresh attempt. If this query permanently fails, 
      // the token is truly invalid.
      setUser(null);
      const { setLearningProfile } = useAuthStore.getState();
      setLearningProfile(null);
    }
  }, [data, isError, setUser]);

  // Optionally, you can render a full-screen loading spinner here while `!mounted || (hasToken && isLoading)`
  // But for better UX, we'll let the layout render and components will check `isLoading` from Zustand.
  
  return <>{children}</>;
}
