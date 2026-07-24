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

export type CEFRLevel = "A1" | "A2" | "B1" | "B2" | "C1" | "C2";

export type OAuthProvider = "GOOGLE";

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
  oauth_provider?: OAuthProvider | null;
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
  target_cefr_level: CEFRLevel;
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
  target_cefr_level: CEFRLevel;
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

// ----------------------------------------------------------------------
// Vocabulary Types
// ----------------------------------------------------------------------

export interface ExerciseBankResponse {
  id: string;
  word_id: string;
  fill_blank_sentence: string;
  fill_blank_correct_answer: string;
  match_definition_distractor_1: string;
  match_definition_distractor_2: string;
  match_definition_distractor_3: string;
}

export interface WordWithExerciseResponse {
  id: string;
  word: string;
  phonetic?: string | null;
  part_of_speech?: string | null;
  definition: string;
  translation?: string | null;
  example_sentence?: string | null;
  audio_url?: string | null;
  exercise?: ExerciseBankResponse | null;
}

export interface DayWordsResponse {
  cycle: number;
  day: number;
  words: WordWithExerciseResponse[];
}

export interface MatchPair {
  word_id: string;
  selected_definition: string;
}

export interface MatchSubmission {
  pairs: MatchPair[];
}

export interface MatchPairResult {
  word_id: string;
  is_correct: boolean;
  correct_definition: string;
}

export interface MatchResult {
  pairs: MatchPairResult[];
  score: number;
}

export interface FillBlankSubmission {
  word_id: string;
  user_answer: string;
}

export interface FillBlankResult {
  word_id: string;
  is_correct: boolean;
  correct_answer: string;
}

export interface SessionCompleteRequest {
  cycle: number;
  day: number;
  words_learned: number;
  practice_seconds: number;
}

export interface SessionCompleteResponse {
  xp_gained: number;
  new_streak: number;
  achievements_unlocked: AchievementResponse[];
}

export type VocabWordStatus = "NEW" | "LEARNING" | "REVIEW" | "MASTERED";

export interface VocabBankItem {
  id: string;
  word: string;
  definition: string;
  part_of_speech?: string | null;
  status: VocabWordStatus;
  mastery_level: number;
  next_review_at?: string | null;
}

export interface VocabBankResponse {
  items: VocabBankItem[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

// ----------------------------------------------------------------------
// Writing Types
// ----------------------------------------------------------------------

export type WritingPromptType = "DESCRIPTIVE" | "NARRATIVE" | "ARGUMENTATIVE";
export type SubmissionStatus = "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED";

export interface WritingPromptResponse {
  id: string;
  cycle: number;
  day: number;
  type: WritingPromptType;
  difficulty_level: string;
  prompt_title: string;
  prompt_text: string;
  target_word_count: number;
  time_limit_minutes?: number | null;
  focus_areas?: unknown;
  writing_tips?: string | null;
  sample_outline?: string | null;
  sensitivity_flagged: boolean;
  created_at: string;
  updated_at: string;
}

export interface DraftSaveRequest {
  prompt_id: string;
  content: string;
}

export interface DraftSaveResponse {
  submission_id: string;
  status: SubmissionStatus;
  last_edited_at: string;
}

export interface SubmissionCreateRequest {
  prompt_id: string;
  content: string;
  word_count: number;
  time_spent_seconds?: number | null;
}

export interface SubmissionReviseRequest {
  content: string;
  word_count: number;
  time_spent_seconds?: number | null;
}

export interface GrammarIssue {
  type?: string | null;
  original_text: string;
  replacement_text: string;
  explanation: string;
}

export interface GrammarReport {
  score: number;
  issues: GrammarIssue[];
}

export interface StructureReport {
  score: number;
  notes: string[];
  suggestions: string[];
}

export interface VocabularySuggestion {
  original_word: string;
  suggested_word: string;
  context: string;
  explanation: string;
}

export interface VocabularyReport {
  score: number;
  suggestions: VocabularySuggestion[];
}

export interface CoherenceReport {
  score: number;
  notes: string[];
  topic_relevance: string;
}

export interface SupervisorReport {
  overall_score: number;
  grammar_score: number;
  structure_score: number;
  vocabulary_score: number;
  coherence_score: number;
  strengths: string[];
  improvements: string[];
  actionable_tips: string[];
  narrative_summary: string;
}

export interface AIFeedbackSchema {
  grammar?: GrammarReport | null;
  structure?: StructureReport | null;
  vocabulary?: VocabularyReport | null;
  coherence?: CoherenceReport | null;
  supervisor?: SupervisorReport | null;
}

export interface FixedIssue {
  description: string;
  original_text: string;
}

export interface FixedIssuesSchema {
  fixed_issues: FixedIssue[];
  still_present_issues: FixedIssue[];
  new_issues_introduced: FixedIssue[];
  error?: string | null;
}

export interface WritingSubmissionVersionResponse {
  id: string;
  submission_id: string;
  version_number: number;
  text_content: string;
  grammar_score?: number | null;
  structure_score?: number | null;
  vocabulary_score?: number | null;
  coherence_score?: number | null;
  overall_score?: number | null;
  ai_feedback?: AIFeedbackSchema | null;
  fixed_issues?: FixedIssuesSchema | null;
  created_at: string;
}

export interface WritingSubmissionResponse {
  id: string;
  user_id: string;
  prompt_id: string;
  daily_activity_id?: string | null;
  revision_count: number;
  word_count?: number | null;
  time_spent_seconds?: number | null;
  grammar_score?: number | null;
  structure_score?: number | null;
  vocabulary_score?: number | null;
  coherence_score?: number | null;
  overall_score?: number | null;
  status: SubmissionStatus;
  processing_job_id?: string | null;
  submitted_at: string;
  completed_at?: string | null;
  versions: WritingSubmissionVersionResponse[];
}

export interface WritingPortfolioResponse {
  submissions: WritingSubmissionResponse[];
}


// ----------------------------------------------------------------------
// Speaking Types
// ----------------------------------------------------------------------

export type SpeakingExerciseType = "CONVERSATIONAL" | "ROLEPLAY" | "DEBATE" | "PRESENTATION";
export type LiveSessionPersona = "INTERVIEWER" | "FRIEND" | "TEACHER" | "EXAMINER";
export type LiveSessionStatus = "ACTIVE" | "ENDED" | "ERROR";
export type ReviewStatus = "PENDING" | "REVIEWED" | "SKIPPED";

export interface SpeakingGrammarCorrection {
  original: string;
  corrected: string;
  explanation: string;
}

export interface SpeakingVocabularySuggestion {
  word_used: string;
  better_alternative: string;
  reason: string;
}

export interface SpeakingFeedback {
  fluency_feedback: string;
  grammar_feedback: string;
  vocabulary_feedback: string;
  overall_strengths: string;
  areas_for_improvement: string;
}

export interface SpeakingExerciseResponse {
  id: string;
  cycle: number;
  day: number;
  type: SpeakingExerciseType;
  topic: string;
  difficulty_level: string;
  prompt_text: string;
  target_duration_seconds: number;
  instructions?: string | null;
  target_cefr_level: string;
  goal_tags: Record<string, unknown>;
  review_status: ReviewStatus;
  created_at: string;
  updated_at: string;
}

export interface SpeakingSubmissionCreate {
  exercise_id: string;
  audio_url: string;
  daily_activity_id?: string | null;
}

export interface SpeakingSubmissionResponse {
  id: string;
  user_id: string;
  exercise_id?: string | null;
  audio_url: string;
  transcript?: string | null;
  duration_seconds?: number | null;
  word_count?: number | null;
  words_per_minute?: number | null;
  pause_count?: number | null;
  filler_words_count?: number | null;
  filler_words_list?: Record<string, number> | null;
  fluency_score?: number | null;
  grammar_score?: number | null;
  vocabulary_score?: number | null;
  pronunciation_score?: number | null;
  overall_score?: number | null;
  grammar_corrections?: SpeakingGrammarCorrection[] | null;
  vocabulary_suggestions?: SpeakingVocabularySuggestion[] | null;
  ai_feedback?: SpeakingFeedback | null;
  status: SubmissionStatus;
  processing_job_id?: string | null;
  submitted_at: string;
  completed_at?: string | null;
}

export interface LiveConversationSessionCreate {
  topic: string;
  persona: LiveSessionPersona;
  target_duration_seconds: number;
}

export interface LiveSessionTranscriptTurn {
  speaker: string;
  text: string;
  timestamp_ms: number;
}

export interface LiveConversationSessionEnd {
  actual_duration_seconds: number;
  transcript: LiveSessionTranscriptTurn[];
}

export interface LiveConversationSessionResponse {
  id: string;
  user_id: string;
  topic: string;
  persona: LiveSessionPersona;
  target_duration_seconds: number;
  actual_duration_seconds?: number | null;
  transcript_json?: Record<string, unknown>[] | null;
  turn_count?: number | null;
  avg_response_time_seconds?: number | null;
  avg_response_length_words?: number | null;
  topic_relevance_score?: number | null;
  status: LiveSessionStatus;
  submission_id?: string | null;
  ephemeral_token_issued_at?: string | null;
  started_at: string;
  ended_at?: string | null;
}

export interface LiveConversationSessionTokenResponse {
  session_id: string;
  ephemeral_token: string;
  ws_endpoint: string;
}

export interface SpeakingProgressResponse {
  total_submissions: number;
  average_overall_score: number;
  average_fluency_score: number;
  average_grammar_score: number;
  average_vocabulary_score: number;
}

