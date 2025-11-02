export type SessionStats = {
  totalReviews?: number;
  correctAnswers?: number;
  xpEarned?: number;
  sessionDuration?: number;
  newCards?: number;
  accuracy?: number;
  // API-derived fields
  xp_earned?: number;
  words_practiced?: number;
  words_reviewed?: number;
  correct_responses?: number;
  incorrect_responses?: number;
  accuracy_rate?: number;
  new_words_introduced?: number;
  status?: string;
  [key: string]: unknown;
};
