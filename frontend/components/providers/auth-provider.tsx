'use client';

import { useEffect, useState } from 'react';
import { useAuthStore } from '@/store/authStore';
import { useQuery } from '@tanstack/react-query';
import apiClient from '@/lib/api/axios';

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const { setUser, setLoading } = useAuthStore();
  const [mounted, setMounted] = useState(false);

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
