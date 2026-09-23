/**
 * WP-L10 — the rule card v2, as data.
 *
 * The server sends every authored language at once (`concept.rule_card`); the
 * card picks the learner's. French strings carry two marks: `[x]` is the part
 * that carries the rule (drawn red), `{x}` is written but silent (drawn grey).
 */

import type { ControlLanguage } from '@/types/daily-journey';

export type RuleCardShape = 'square' | 'circle' | 'circles' | 'triangle' | 'none';
export type Localized = Partial<Record<ControlLanguage, string>>;

export type RuleCardRow = { shape: RuleCardShape; label: string; fr: string };
export type RuleCardTableRow = { p: string; fr: string };

export type RuleCardPattern =
  | { kind: 'rows'; rows: RuleCardRow[] }
  | { kind: 'table'; verb: string; rows: RuleCardTableRow[]; note?: Localized };

export type RuleCardData = {
  speaker?: string | null;
  example: { fr: string; tr?: Localized };
  rule: Localized;
  pattern?: RuleCardPattern | null;
  contrast?: { wrong: string; right: string } | null;
  more?: Localized;
};

export type MarkedSegment = { text: string; tone: 'plain' | 'mark' | 'silent' };

/** «habit{e}» → plain «habit» + silent «e»; «[le] café» → mark «le» + plain « café». */
export function parseMarked(value: string | null | undefined): MarkedSegment[] {
  const text = String(value ?? '');
  const out: MarkedSegment[] = [];
  const pattern = /\[([^\]]*)\]|\{([^}]*)\}/g;
  let last = 0;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(text))) {
    if (match.index > last) out.push({ text: text.slice(last, match.index), tone: 'plain' });
    if (match[1] !== undefined) out.push({ text: match[1], tone: 'mark' });
    else out.push({ text: match[2] ?? '', tone: 'silent' });
    last = pattern.lastIndex;
  }
  if (last < text.length) out.push({ text: text.slice(last), tone: 'plain' });
  return out.filter((segment) => segment.text.length > 0);
}

/** The sentence as it is said: marks removed, for audio and the accessible name. */
export function plainText(value: string | null | undefined): string {
  return parseMarked(value).map((segment) => segment.text).join('');
}

/** The learner's language, else English (every authored card has English). */
export function pick(value: Localized | null | undefined, language: ControlLanguage): string {
  if (!value) return '';
  return (value[language] || value.en || '').trim();
}

/** A card is usable only with an example and a rule in some language. */
export function usableCard(card: unknown): card is RuleCardData {
  if (!card || typeof card !== 'object') return false;
  const data = card as RuleCardData;
  return Boolean(data.example?.fr && (data.rule?.en || data.rule?.de || data.rule?.fr));
}

/** Chrome for the card, in the learner's language (sentence case, no French labels over English text). */
export const RULE_CARD_COPY: Record<ControlLanguage, {
  eyebrow: string;
  translate: string;
  hideTranslation: string;
  listen: string;
  why: string;
  wrong: string;
  right: string;
  cahier: string;
  tryIt: string;
  back: string;
  pattern: string;
}> = {
  en: {
    eyebrow: "Today's rule",
    translate: 'Translate',
    hideTranslation: 'Hide translation',
    listen: 'Listen to the sentence',
    why: 'Why?',
    wrong: 'Wrong: ',
    right: 'Right: ',
    cahier: 'In your cahier ↗',
    tryIt: 'Essayer',
    back: 'Back to the exercise',
    pattern: 'The pattern',
  },
  de: {
    eyebrow: 'Regel des Tages',
    translate: 'Übersetzen',
    hideTranslation: 'Übersetzung ausblenden',
    listen: 'Satz anhören',
    why: 'Warum?',
    wrong: 'Falsch: ',
    right: 'Richtig: ',
    cahier: 'Im Cahier ↗',
    tryIt: 'Essayer',
    back: 'Zurück zur Übung',
    pattern: 'Das Muster',
  },
  fr: {
    eyebrow: 'La règle du jour',
    translate: 'Traduire',
    hideTranslation: 'Masquer la traduction',
    listen: 'Écouter la phrase',
    why: 'Pourquoi ?',
    wrong: 'Faux : ',
    right: 'Juste : ',
    cahier: 'Dans le cahier ↗',
    tryIt: 'Essayer',
    back: 'Retour à l’exercice',
    pattern: 'Le schéma',
  },
};
