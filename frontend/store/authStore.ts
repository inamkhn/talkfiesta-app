import { create } from "zustand";
import { UserResponse, LearningProfileResponse } from "@/lib/api/types";

interface AuthState {
  user: UserResponse | null;
  learningProfile: LearningProfileResponse | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  
  setUser: (user: UserResponse | null) => void;
  setLearningProfile: (profile: LearningProfileResponse | null) => void;
  setLoading: (loading: boolean) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  learningProfile: null,
  isAuthenticated: false,
  isLoading: true, // starts loading until hydration happens
  
  setUser: (user) => set({ user, isAuthenticated: !!user, isLoading: false }),
  setLearningProfile: (profile) => set({ learningProfile: profile }),
  setLoading: (loading) => set({ isLoading: loading }),
  
  logout: () => {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
    }
    set({ user: null, learningProfile: null, isAuthenticated: false, isLoading: false });
  },
}));
