import type { ControlLanguage } from '@/types/daily-journey';

/** Stored classification labels are answer keys. Translate display only. */
const LABELS: Record<string, { fr: string; de: string }> = {
  'present condition': { fr: 'condition au présent', de: 'Bedingung im Präsens' },
  'future result': { fr: 'conséquence au futur', de: 'Folge im Futur' },
  'imperative result': { fr: 'conséquence à l’impératif', de: 'Folge im Imperativ' },
  'background/habit': { fr: 'contexte ou habitude', de: 'Hintergrund oder Gewohnheit' },
  'bounded event': { fr: 'événement achevé', de: 'Abgeschlossenes Ereignis' },
  'article changes': { fr: 'l’article change', de: 'Der Artikel ändert sich' },
};

export function classificationCopy(value: string, language: ControlLanguage): string {
  if (language === 'en') return value;
  let display = value;
  for (const [key, labels] of Object.entries(LABELS)) {
    display = display.split(key).join(labels[language]);
  }
  return display;
}

export function classificationGoal(language: ControlLanguage): string {
  return { en: 'Classify this form.', de: 'Ordne die Form zu.', fr: 'Classez cette forme.' }[language];
}

/**
 * QA-FORGE (2026-10-03) — a judgement item («Correct» / «À corriger» are answer
 * keys) asks one question in the learner's language and offers two answers in
 * that same language: never an English label next to a French one, never a
 * drop zone. The server sends `label_l10n` and the question as `goal_native`;
 * this table is the floor for a stored item that has neither.
 */
const JUDGEMENT_LABELS: Record<ControlLanguage, Record<string, string>> = {
  en: { correct: 'Correct', 'à corriger': 'Needs fixing' },
  de: { correct: 'Stimmt so', 'à corriger': 'Muss korrigiert werden' },
  fr: { correct: 'Correcte', 'à corriger': 'À corriger' },
};

const JUDGEMENT_QUESTION: Record<ControlLanguage, string> = {
  en: 'Is this sentence correct?',
  de: 'Ist der Satz richtig?',
  fr: 'Cette phrase est-elle correcte ?',
};

function judgementKey(label: string): string {
  return label.normalize('NFC').trim().toLowerCase();
}

/** True when the labels are the judgement's two keys. */
export function isJudgementLabels(labels: unknown): boolean {
  if (!Array.isArray(labels) || labels.length !== 2) return false;
  const keys = labels.map((label) => judgementKey(String(label))).sort();
  return keys[0] === 'correct' && keys[1] === 'à corriger';
}

/** «À corriger» → «Muss korrigiert werden» (the item's own table first). */
export function judgementLabel(
  label: string,
  language: ControlLanguage,
  table?: Record<string, Record<string, string> | null | undefined> | null,
): string {
  const own = table?.[language]?.[label];
  if (typeof own === 'string' && own.trim()) return own.trim();
  return JUDGEMENT_LABELS[language]?.[judgementKey(label)] ?? label;
}

export function judgementQuestion(language: ControlLanguage): string {
  return JUDGEMENT_QUESTION[language] ?? JUDGEMENT_QUESTION.en;
}
