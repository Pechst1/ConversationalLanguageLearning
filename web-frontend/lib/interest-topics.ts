/* The interest topics, once.
 *
 * The account stores English keys (`travel`, `food`) — the backend's article
 * seeding and the missions planner read them — while every screen of the
 * publication is French. Sign-up, Réglages and the «chosen» line all draw
 * from this list so the learner never meets a key, and a topic they typed
 * themselves is shown as they typed it.
 */

export type InterestTopic = { key: string; label: string };

export const INTEREST_TOPICS: readonly InterestTopic[] = [
  { key: 'technology', label: 'technologie' },
  { key: 'business', label: 'travail' },
  { key: 'travel', label: 'voyage' },
  { key: 'sports', label: 'sport' },
  { key: 'politics', label: 'politique' },
  { key: 'science', label: 'sciences' },
  { key: 'culture', label: 'culture' },
  { key: 'finance', label: 'économie' },
  { key: 'health', label: 'santé' },
  { key: 'food', label: 'cuisine' },
];

const BY_KEY = new Map(INTEREST_TOPICS.map((topic) => [topic.key, topic.label]));
const BY_LABEL = new Map(INTEREST_TOPICS.map((topic) => [topic.label, topic.key]));

/** The French label of a stored key; a custom topic reads as itself. */
export function interestTopicLabel(key: string): string {
  const normalized = String(key || '').trim().toLowerCase();
  return BY_KEY.get(normalized) ?? normalized;
}

/** The stored key for a label (accounts saved before this list stored the
 *  French word itself; they fold back to the key). */
export function interestTopicKey(value: string): string {
  const normalized = String(value || '').trim().toLowerCase();
  return BY_LABEL.get(normalized) ?? normalized;
}
