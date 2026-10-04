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
  /** QA-CLOSE: the server's verdict on `answer_text` (null for a self-rated card). */
  correct?: boolean | null;
  expected?: string | null;
  /** One short line in the learner's language: a forgiven slip, or why a near miss failed. */
  note_native?: string | null;
}

export type AnyReviewResponse = ReviewResponse | AnkiReviewResponse;
