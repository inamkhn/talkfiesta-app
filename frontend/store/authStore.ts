import { create } from 'zustand';
import type { UserResponse } from '@/lib/api/generated/schemas';

interface AuthState {
  user: UserResponse | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  setUser: (user: UserResponse | null) => void;
  setLoading: (loading: boolean) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true, // starts loading until hydration happens
  setUser: (user) => set({ user, isAuthenticated: !!user, isLoading: false }),
  setLoading: (loading) => set({ isLoading: loading }),
  logout: () => {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
    }
    set({ user: null, isAuthenticated: false, isLoading: false });
  },
}));
