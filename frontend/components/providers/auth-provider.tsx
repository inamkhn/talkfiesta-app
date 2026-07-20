'use client';

import { useEffect, useState } from 'react';
import { useAuthStore } from '@/store/authStore';
import { useReadCurrentUserApiV1AuthMeGet } from '@/lib/api/generated/authentication/authentication';

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const { setUser, setLoading } = useAuthStore();
  const [mounted, setMounted] = useState(false);

  // We check if we are on the client before reading localStorage
  const hasToken = typeof window !== 'undefined' ? !!localStorage.getItem('access_token') : false;

  const { data, isLoading, isError } = useReadCurrentUserApiV1AuthMeGet({
    query: {
      enabled: mounted && hasToken,
      retry: false,
    }
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
    } else if (isError) {
      // Interceptor handles the refresh attempt. If this query permanently fails, 
      // the token is truly invalid.
      setUser(null);
    }
  }, [data, isError, setUser]);

  // Optionally, you can render a full-screen loading spinner here while `!mounted || (hasToken && isLoading)`
  // But for better UX, we'll let the layout render and components will check `isLoading` from Zustand.
  
  return <>{children}</>;
}
