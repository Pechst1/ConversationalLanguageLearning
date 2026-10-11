/**
 * WP-122 B · `/correcteur?mock=1` (DEV ONLY): an in-memory client over a draft the
 * backend made (`fixtures/mock-draft.json`: the grève evergreen at A2 for a learner
 * with no errata, so three «classiques»). `band=B1` drops the options. Grading is
 * `gradeLocally`, the port of the server's grader.
 */

import type { CorrecteurClient } from '@/lib/correcteur-api';
import { parseDraft, parseWeek, type CrDraft } from '@/lib/correcteur-types';

import { gradeLocally, type CrKey } from './correcteur-model';
import fixture from './fixtures/mock-draft.json';

type Options = { band?: string; latency?: number };

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export function mockKey(): CrKey[] {
  return (fixture.key as Array<Record<string, any>>).map((row) => ({
    sentenceIndex: row.sentence_index,
    span: [row.span[0], row.span[1]],
    wrongFr: row.wrong_fr,
    correctFr: row.correct_fr,
    grammarPoint: row.grammar_point,
    source: row.source === 'errata' ? 'errata' : 'classique',
  }));
}

export function mockDraft(band = 'A2'): CrDraft {
  const draft = parseDraft(fixture.draft as Record<string, any>);
  const lower = band === 'A1' || band === 'A2';
  return {
    ...draft,
    band,
    optionsEnabled: lower,
    units: lower ? draft.units : draft.units.map((unit) => ({ ...unit, options: null })),
  };
}

export function createMockCorrecteurClient({ band = 'A2', latency = 300 }: Options = {}): CorrecteurClient {
  const drafts = new Map<string, CrDraft>();
  return {
    async week() {
      await wait(latency);
      return { enabled: true, week: parseWeek(fixture.week as Record<string, any>) };
    },
    async draft() {
      await wait(latency);
      const draft = mockDraft(band);
      drafts.set(draft.id, draft);
      return draft;
    },
    async marks(correctionId, marks) {
      await wait(latency);
      const draft = drafts.get(correctionId) ?? mockDraft(band);
      return gradeLocally(draft, mockKey(), marks, fixture.romy_lines as Record<string, Record<string, string>>);
    },
  };
}
