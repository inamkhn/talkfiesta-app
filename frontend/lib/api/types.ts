// Goal Enum
export enum Goal {
  FLUENCY = "FLUENCY",
  BUSINESS = "BUSINESS",
  EXAM = "EXAM",
  TRAVEL = "TRAVEL",
}

export enum AchievementModule {
  SPEAKING = "SPEAKING",
  VOCABULARY = "VOCABULARY",
  WRITING = "WRITING",
}

// ----------------------------------------------------------------------
// User & Auth Types
// ----------------------------------------------------------------------

export interface UserResponse {
  id: string;
  email: string;
  first_name?: string | null;
  last_name?: string | null;
  is_active: boolean;
  is_superuser: boolean;
  oauth_provider?: string | null;
  oauth_provider_id?: string | null;
  avatar_url?: string | null;
  onboarding_completed: boolean;
  created_at: string;
  updated_at: string;
  last_login_at?: string | null;
  learning_profile?: LearningProfileResponse | null;
}

export interface LearningProfileResponse {
  id: string;
  user_id: string;
  current_cycle: number;
  current_day: number;
  goal: Goal;
  target_cefr_level: string;
  native_language?: string | null;
  timezone: string;
  daily_reminder_enabled: boolean;
  created_at: string;
  updated_at: string;
}

// ----------------------------------------------------------------------
// Onboarding Types
// ----------------------------------------------------------------------

export interface LearningProfileCreate {
  goal: Goal;
  target_cefr_level: string;
  native_language?: string | null;
  timezone?: string;
  daily_reminder_enabled?: boolean;
}

export interface OnboardingCompleteResponse {
  user: UserResponse;
  learning_profile: LearningProfileResponse;
}

// ----------------------------------------------------------------------
// Progress & Dashboard Types
// ----------------------------------------------------------------------

export interface DailyProgressResponse {
  id: string;
  user_id: string;
  date: string;
  cycle: number;
  day: number;
  speaking_done: boolean;
  vocab_done: boolean;
  writing_done: boolean;
  total_practice_seconds: number;
}

export interface AchievementResponse {
  id: string;
  key: string;
  title: string;
  description: string;
  icon_url?: string | null;
  module?: AchievementModule | null;
  earned_at: string;
}

export interface DashboardSummaryResponse {
  today_progress: DailyProgressResponse;
  current_streak: number;
  longest_streak: number;
  total_xp: number;
  recent_achievements: AchievementResponse[];
}

export interface TrackProgressRequest {
  date: string; // YYYY-MM-DD
  module: AchievementModule;
  practice_seconds?: number;
  completed?: boolean;
}
