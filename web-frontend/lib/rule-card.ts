/**
 * WP-L10 — the rule card v2, as data.
 *
 * The server sends every authored language at once (`concept.rule_card`); the
 * card picks the learner's. French strings carry two marks: `[x]` is the part
 * that carries the rule (drawn red), `{x}` is written but silent (drawn grey).
 *
 * F-1 (content program 2026-10-03): the v2+ card adds `how` (numbered steps),
 * `examples`, `traps` and `contrast_with`; every v2 unit also has an x-ray
 * sentence whose marked spans name what each part does. All optional: a v1
 * card has none of them and draws exactly as before.
 */

import { castIdFor } from '@/lib/cast-faces';
import type { ControlLanguage } from '@/types/daily-journey';

export type RuleCardShape = 'square' | 'circle' | 'circles' | 'triangle' | 'none';
export type Localized = Partial<Record<ControlLanguage, string>>;

export type RuleCardRow = { shape: RuleCardShape; label: string; fr: string };
export type RuleCardTableRow = { p: string; fr: string };

export type RuleCardPattern =
  | { kind: 'rows'; rows: RuleCardRow[] }
  | { kind: 'table'; verb: string; rows: RuleCardTableRow[]; note?: Localized };

export type RuleCardExample = { fr: string; tr?: Localized };
export type RuleCardTrap = { wrong: string; right: string; why?: Localized };
/** A partner unit; `title` ({en, de, fr}) is filled in by the server when it knows the unit. */
export type RuleCardPartner = { id: string; note?: Localized; title?: Localized | null };

export type RuleCardData = {
  speaker?: string | null;
  example: RuleCardExample;
  rule: Localized;
  pattern?: RuleCardPattern | null;
  contrast?: { wrong: string; right: string } | null;
  more?: Localized;
  /** v2+: how to build it, numbered steps separated by `\n`. */
  how?: Localized;
  /** v2+: 2–4 more marked examples. */
  examples?: RuleCardExample[];
  /** v2+: the real mistakes, ✗ → ✓ with the why. */
  traps?: RuleCardTrap[];
  /** v2+: the units to compare with. */
  contrast_with?: RuleCardPartner[];
};

export type MarkedSegment = { text: string; tone: 'plain' | 'mark' | 'silent' };

/* A mark holds no other bracket: «[a{b}c]» is read as plain «a», silent «b»,
   plain «c», and a stray bracket is dropped, never drawn. */
const MARKUP = /\[([^\[\]{}]*)\]|\{([^\[\]{}]*)\}/g;
const STRAY = /[\[\]{}]/g;

/**
 * «habit{e}» → plain «habit» + silent «e»; «[le] café» → mark «le» + plain « café».
 * Unbalanced markup never crashes and never prints: «Elle [est parti» is plain
 * «Elle est parti».
 */
export function parseMarked(value: string | number | null | undefined): MarkedSegment[] {
  if (typeof value !== 'string' && typeof value !== 'number') return [];
  const text = String(value);
  const out: MarkedSegment[] = [];
  const push = (segment: MarkedSegment) => {
    if (!segment.text) return;
    const previous = out[out.length - 1];
    if (previous && previous.tone === 'plain' && segment.tone === 'plain') previous.text += segment.text;
    else out.push(segment);
  };
  const pattern = new RegExp(MARKUP.source, 'g');
  let last = 0;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(text))) {
    if (match.index > last) push({ text: text.slice(last, match.index).replace(STRAY, ''), tone: 'plain' });
    if (match[1] !== undefined) push({ text: match[1], tone: 'mark' });
    else push({ text: match[2] ?? '', tone: 'silent' });
    last = pattern.lastIndex;
  }
  if (last < text.length) push({ text: text.slice(last).replace(STRAY, ''), tone: 'plain' });
  return out;
}

/** Which marks a set of French strings uses, for the card's colour key. */
export function markupTones(values: Array<string | null | undefined>): { mark: boolean; silent: boolean } {
  const tones = { mark: false, silent: false };
  values.forEach((value) => {
    parseMarked(value).forEach((segment) => {
      if (segment.tone === 'mark') tones.mark = true;
      if (segment.tone === 'silent') tones.silent = true;
    });
  });
  return tones;
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

/** «1. Check the verb.\n2. Put être…» → ['Check the verb.', 'Put être…'] (the list draws the numbers). */
export function howSteps(card: Pick<RuleCardData, 'how'> | null | undefined, language: ControlLanguage): string[] {
  return pick(card?.how, language)
    .split(/\n+/)
    .map((line) => line.replace(/^\s*(?:\d+\s*[.)]|[-–•])\s*/, '').trim())
    .filter(Boolean);
}

/** The extra examples the card can draw (a French sentence each). */
export function cardExamples(card: Pick<RuleCardData, 'examples'> | null | undefined): RuleCardExample[] {
  const list = Array.isArray(card?.examples) ? card!.examples : [];
  return list.filter((item): item is RuleCardExample => Boolean(item && plainText(item.fr).trim()));
}

/** The traps the card can draw: both sides present. */
export function cardTraps(card: Pick<RuleCardData, 'traps'> | null | undefined): RuleCardTrap[] {
  const list = Array.isArray(card?.traps) ? card!.traps : [];
  return list.filter((item): item is RuleCardTrap =>
    Boolean(item && plainText(item.wrong).trim() && plainText(item.right).trim()),
  );
}

export type CardPartner = { id: string; title: string; note: string; href: string };

/** Where a partner unit opens: the Cahier resolves the catalogue id. */
export function partnerHref(id: string): string {
  return `/grammar?unit=${encodeURIComponent(id)}`;
}

/**
 * «Compare with», by title: the French title first (unit titles are French on
 * every surface), else the learner's. A partner with no title is left out.
 */
export function cardPartners(
  card: Pick<RuleCardData, 'contrast_with'> | null | undefined,
  language: ControlLanguage,
): CardPartner[] {
  const list = Array.isArray(card?.contrast_with) ? card!.contrast_with : [];
  const out: CardPartner[] = [];
  list.forEach((partner) => {
    const id = typeof partner?.id === 'string' ? partner.id.trim() : '';
    const titles = partner?.title || null;
    const title = (titles?.fr || pick(titles, language)).trim();
    if (!id || !title) return;
    out.push({ id, title, note: pick(partner.note, language), href: partnerHref(id) });
  });
  return out;
}

/** Does the card have anything past the first view? */
export function cardHasDepth(card: RuleCardData, language: ControlLanguage): boolean {
  return Boolean(
    howSteps(card, language).length ||
      cardExamples(card).length ||
      cardTraps(card).length ||
      cardPartners(card, language).length,
  );
}

/* ---------------------------------------------------------------------------
 * F-1 — the x-ray sentence: each marked span says what it does.
 * ------------------------------------------------------------------------- */

export type XrayMark = { token: string; role?: string | null; explanation?: string | null };
export type XrayPayload = { sentence: string; marks: XrayMark[] };

/** The av2 roles the marks are underlined in, in order (red, blue, yellow, green, then again). */
export const XRAY_TONES = ['red', 'blue', 'yellow', 'green'] as const;
export type XrayTone = (typeof XRAY_TONES)[number];

export function xrayTone(index: number): XrayTone {
  return XRAY_TONES[((index % XRAY_TONES.length) + XRAY_TONES.length) % XRAY_TONES.length];
}

/** «agreement_marks» → «agreement marks»: the role key as words, never as a key. */
export function xrayRoleLabel(role: string | null | undefined): string {
  const words = String(role || '').replace(/[_-]+/g, ' ').replace(/\s+/g, ' ').trim();
  return words ? words.charAt(0).toUpperCase() + words.slice(1) : '';
}

/** «ne...que» → ['ne', 'que']. */
export function xrayPieces(token: string | null | undefined): string[] {
  return String(token || '')
    .split(/\s*(?:\.\.\.|…)\s*/)
    .map((piece) => piece.trim())
    .filter(Boolean);
}

const LETTER = /[A-Za-z0-9\u00C0-\u024F\u0152\u0153]/;
const fold = (value: string) => value.replace(/[\u2018\u2019\u02BC]/g, "'").toLowerCase();

function findPiece(haystack: string, needle: string, from: number): number {
  let first = -1;
  let index = haystack.indexOf(needle, from);
  while (index >= 0) {
    if (first < 0) first = index;
    const before = index > 0 ? haystack.charAt(index - 1) : '';
    const after = haystack.charAt(index + needle.length);
    const startOk = !before || !LETTER.test(before) || !LETTER.test(needle.charAt(0));
    const endOk = !after || !LETTER.test(after) || !LETTER.test(needle.charAt(needle.length - 1));
    if (startOk && endOk) return index;
    index = haystack.indexOf(needle, index + 1);
  }
  return first;
}

/**
 * Where each mark sits in the sentence: one `[start, end)` range per piece, in
 * order (a discontinuous mark's pieces are found left to right). A mark whose
 * pieces are not all found gets no range, and is listed but not drawn.
 */
export function locateXray(sentence: string, marks: XrayMark[]): Array<Array<[number, number]>> {
  const haystack = fold(String(sentence || ''));
  return (marks || []).map((mark) => {
    const ranges: Array<[number, number]> = [];
    let cursor = 0;
    const pieces = xrayPieces(mark?.token);
    for (let i = 0; i < pieces.length; i += 1) {
      const needle = fold(pieces[i]);
      const at = findPiece(haystack, needle, cursor);
      if (at < 0) return [];
      ranges.push([at, at + needle.length]);
      cursor = at + needle.length;
    }
    return ranges;
  });
}

export type XraySegment = { text: string; marks: number[] };

/** The sentence cut at every mark edge; each piece lists the marks that cover it (overlaps allowed). */
export function xraySegments(sentence: string, marks: XrayMark[]): XraySegment[] {
  const text = String(sentence || '');
  if (!text) return [];
  const located = locateXray(text, marks);
  const edges = [0, text.length];
  located.forEach((ranges) => ranges.forEach(([start, end]) => edges.push(start, end)));
  const cuts = edges
    .filter((edge, index) => edges.indexOf(edge) === index)
    .sort((a, b) => a - b);
  const out: XraySegment[] = [];
  for (let i = 0; i < cuts.length - 1; i += 1) {
    const start = cuts[i];
    const end = cuts[i + 1];
    if (end <= start) continue;
    const covering: number[] = [];
    located.forEach((ranges, markIndex) => {
      if (ranges.some(([a, b]) => a <= start && end <= b)) covering.push(markIndex);
    });
    const previous = out[out.length - 1];
    if (previous && previous.marks.join(',') === covering.join(',')) previous.text += text.slice(start, end);
    else out.push({ text: text.slice(start, end), marks: covering });
  }
  return out;
}

/** A usable x-ray: a sentence and at least one mark found in it. */
export function usableXray(xray: unknown): xray is XrayPayload {
  if (!xray || typeof xray !== 'object') return false;
  const data = xray as XrayPayload;
  if (typeof data.sentence !== 'string' || !data.sentence.trim() || !Array.isArray(data.marks)) return false;
  return locateXray(data.sentence, data.marks).some((ranges) => ranges.length > 0);
}

/**
 * Tapping a piece covered by several marks: the next of them after the one
 * selected, else the narrowest (the most specific).
 */
export function pickXrayMark(covering: number[], selected: number | null, sentence: string, marks: XrayMark[]): number | null {
  if (!covering.length) return selected;
  if (selected != null && covering.indexOf(selected) >= 0 && covering.length > 1) {
    return covering[(covering.indexOf(selected) + 1) % covering.length];
  }
  const located = locateXray(sentence, marks);
  const width = (index: number) => (located[index] || []).reduce((sum, [a, b]) => sum + (b - a), 0);
  return covering.slice().sort((a, b) => width(a) - width(b) || a - b)[0];
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
  /** WP-92: the tiny label over the scene's own line. */
  fromScene: string;
  /** F-1: the expansion of a v2+ card (a v1 card keeps «why»). */
  more: string;
  how: string;
  examples: string;
  showTranslations: string;
  hideTranslations: string;
  traps: string;
  compare: string;
  /** The colour key: «red = carries the rule · grey = written, not said». */
  keyLabel: string;
  keyRed: string;
  keyRedMeans: string;
  keyGrey: string;
  keyGreyMeans: string;
  xray: string;
  xrayHint: string;
  xrayMarks: string;
  /** WP-129 (D7): a rule met earlier, seen again in the page just read. */
  reviewEyebrow: string;
  reviewDone: string;
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
    fromScene: 'in today’s scene',
    more: 'More',
    how: 'How to build it',
    examples: 'More examples',
    showTranslations: 'Show translations',
    hideTranslations: 'Hide translations',
    traps: 'Watch out',
    compare: 'Compare with',
    keyLabel: 'Colour key',
    keyRed: 'red',
    keyRedMeans: 'carries the rule',
    keyGrey: 'grey',
    keyGreyMeans: 'written, not said',
    xray: 'The sentence, x-rayed',
    xrayHint: 'Tap a coloured part to see what it does.',
    xrayMarks: 'The marked parts',
    reviewEyebrow: 'A rule you know, in today’s page',
    reviewDone: 'Continue',
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
    fromScene: 'in der heutigen Szene',
    more: 'Mehr',
    how: 'So baust du es',
    examples: 'Weitere Beispiele',
    showTranslations: 'Übersetzungen zeigen',
    hideTranslations: 'Übersetzungen ausblenden',
    traps: 'Vorsicht',
    compare: 'Vergleiche mit',
    keyLabel: 'Farbschlüssel',
    keyRed: 'rot',
    keyRedMeans: 'trägt die Regel',
    keyGrey: 'grau',
    keyGreyMeans: 'geschrieben, nicht gesprochen',
    xray: 'Der Satz unter der Lupe',
    xrayHint: 'Tippe auf einen farbigen Teil: Was macht er?',
    xrayMarks: 'Die markierten Teile',
    reviewEyebrow: 'Eine bekannte Regel, auf der heutigen Seite',
    reviewDone: 'Weiter',
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
    fromScene: 'dans la scène d’aujourd’hui',
    more: 'Pourquoi ?',
    how: 'Comment la construire',
    examples: 'D’autres exemples',
    showTranslations: 'Afficher les traductions',
    hideTranslations: 'Masquer les traductions',
    traps: 'Attention',
    compare: 'À comparer avec',
    keyLabel: 'Légende des couleurs',
    keyRed: 'rouge',
    keyRedMeans: 'porte la règle',
    keyGrey: 'gris',
    keyGreyMeans: 's’écrit, ne se dit pas',
    xray: 'La phrase aux rayons X',
    xrayHint: 'Touchez une partie colorée : à quoi sert-elle ?',
    xrayMarks: 'Les parties marquées',
    reviewEyebrow: 'Une règle déjà vue, dans la page du jour',
    reviewDone: 'Continuer',
  },
};

/**
 * WP-92 — the card's first anchor: a line of today's scene that uses the rule,
 * said by the cast member who said it there.
 */
export type RuleSceneAnchor = {
  fr: string;
  /** The drawn cast member (`lib/cast-faces` id), or null for anyone without a face. */
  castId: string | null;
  /** The name printed beside the face; empty when the payload named nobody. */
  name: string;
};

const ANCHOR_NAMES: Record<string, string> = {
  margaux_barman: 'Margaux',
  marin_leveque: 'Marin',
  romy_tremblay: 'Romy',
  lila_bonnet: 'Lila',
  augustin_de_roncourt: 'Gus',
  landlord_marchand: 'M. Marchand',
};

/**
 * The scene anchor from a RULE step's prompt, or `null` when the prompt has
 * none (an older payload, or a scene that did not carry the form) — the card
 * is then exactly what it was. The speaker may be a cast id («margaux_barman»,
 * «margaux») or a display name; an unknown one keeps its own spelling.
 */
export function ruleSceneAnchor(
  prompt: { scene_example_fr?: string | null; scene_example_speaker?: string | null } | null | undefined,
): RuleSceneAnchor | null {
  const fr = typeof prompt?.scene_example_fr === 'string' ? prompt.scene_example_fr.trim() : '';
  if (!plainText(fr).trim()) return null;
  const speaker = typeof prompt?.scene_example_speaker === 'string' ? prompt.scene_example_speaker.trim() : '';
  const castId = speaker ? castIdFor(speaker) : null;
  const name = castId
    ? ANCHOR_NAMES[castId] ?? speaker
    : speaker
      ? speaker.charAt(0).toUpperCase() + speaker.slice(1).replace(/_/g, ' ')
      : '';
  return { fr, castId, name };
}
