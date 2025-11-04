export interface ReviewResponse {
  word_id: number;
  state: string;
  stability: number;
  difficulty: number;
  scheduled_days: number;
  next_review: string;
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

export type AnyReviewResponse = ReviewResponse | AnkiReviewResponse;
