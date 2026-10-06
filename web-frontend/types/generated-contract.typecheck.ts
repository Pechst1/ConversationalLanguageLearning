/** Compile-time contract tests: an unused @ts-expect-error fails tsc. */
import type { AttemptBody, PublicStep, TodayEnvelope, StoryEpisode } from './daily-journey';
import type { EpisodeAudioManifest, VocabularyWord } from '@/services/api';

export function checkContract(
  today: TodayEnvelope, step: PublicStep, episode: StoryEpisode,
  audio: EpisodeAudioManifest, word: VocabularyWord,
) {
  if (step.kind === 'respond') {
    const line: string = step.prompt.character_line_fr;
    void line;
    // @ts-expect-error private grading keys never arrive in the public prompt
    void step.prompt.accepted_answers;
  }
  // @ts-expect-error no invented response property
  void today.e5_not_sent_by_the_api;
  // @ts-expect-error no grading field in the reader projection
  void episode.correct;
  // @ts-expect-error audio exposes clips, not provider secrets
  void audio.api_key;
  // @ts-expect-error vocabulary has no invented public field
  void word.e5_not_sent_by_the_api;
  const body: AttemptBody = {
    mutation_id: 'type-test', expected_revision: 1,
    // @ts-expect-error voice input needs text
    input: { mode: 'voice' },
  };
  void body;
}
