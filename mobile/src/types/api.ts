export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
  tokenType: string;
}

export interface UserProfile {
  id: string;
  email: string;
  full_name: string | null;
  native_language: string;
  target_language: string;
  proficiency_level: string;
  daily_goal_minutes: number;
  notifications_enabled: boolean;
  preferred_session_time: string | null;
  is_active: boolean;
  is_verified: boolean;
  subscription_tier: string;
  subscription_expires_at: string | null;
  total_xp: number;
  level: number;
  current_streak: number;
  longest_streak: number;
  last_activity_date: string | null;
}

export interface AnkiStageSlice {
  stage: string;
  value: number;
}

export interface AnkiDirectionSummary {
  direction: string;
  total: number;
  due_today: number;
  stage_counts: Record<string, number>;
}

export interface AnkiProgressSummary {
  total_cards: number;
  due_today: number;
  stage_totals: Record<string, number>;
  chart: AnkiStageSlice[];
  directions: Record<string, AnkiDirectionSummary>;
}

export interface AnkiWordProgress {
  word_id: number;
  word: string;
  language: string;
  direction?: string | null;
  french_translation?: string | null;
  german_translation?: string | null;
  deck_name?: string | null;
  difficulty_level?: number | null;
  english_translation?: string | null;
  learning_stage: string;
  state: string;
  progress_difficulty?: number | null;
  ease_factor?: number | null;
  interval_days?: number | null;
  due_at?: string | null;
  next_review?: string | null;
  last_review?: string | null;
  reps: number;
  lapses: number;
  proficiency_score: number;
  scheduler?: string | null;
}

export interface QueueWord {
  word_id: number;
  word: string;
  language: string;
  english_translation?: string | null;
  part_of_speech?: string | null;
  difficulty_level?: number | null;
  state: string;
  next_review?: string | null;
  scheduled_days?: number | null;
  is_new: boolean;
  scheduler?: string | null;
}

export interface AnkiReviewResponse {
  word_id: number;
  scheduler: string;
  phase?: string | null;
  ease_factor?: number | null;
  interval_days?: number | null;
  due_at?: string | null;
  next_review?: string | null;
}
