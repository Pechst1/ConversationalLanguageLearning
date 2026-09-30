/**
 * Story-engine episode → reader stages (WP-14E, frontend side).
 *
 * `GET /story-engine/episodes` is a read-only projection of the canonical daily
 * story (ENGINE-FRONTEND-CONTRACT.md). This module turns one such episode into
 * the paged reader's stage list so the existing immersive reader renders it
 * unchanged. Pure: no fetch, no React, unit-tested with `node --test`.
 *
 * Rules kept here, not in the component:
 *   * every stage comes from a server panel; nothing is synthesised;
 *   * a panel with no art is `missing`, never a placeholder illustration;
 *   * reused location art is `setting_reference` and is labelled as such —
 *     it is not claimed to be a newly generated illustration;
 *   * a panel's own drawing is `panel_art`; while it is on its way the panel
 *     shows the plate (`rendering`, `artPending`) and the journey controller
 *     polls (`shouldPollStoryArt`, WP-90) — so the poll survives the step;
 *   * the generated ending is exposed only when the server exposes it
 *     (`resolution` is null until the exchange actually settles).
 */

import type { ControlLanguage, GrammarFocus, StoryEpisode, StoryPanel } from '@/types/daily-journey';
import { lineMarkRanges } from '@/components/feuilleton/reader/grammar-marks';
import {
  readerCharacterKey,
  type ReaderLine,
  type ReaderResolutionStage,
  type ReaderStage,
} from '@/components/feuilleton/reader/panel-model';
import { castIdFor, expressionForMood } from '@/lib/cast-faces';
import type { PortraitMood } from '@/lib/onboarding-portraits';

/**
 * One dialogue line as the engine actually sends it.
 *
 * `character_name` was ratified additively on 2026-09-06 (ENGINE-FRONTEND-
 * CONTRACT.md, "Verified in a browser"): it is the display name from the
 * owning thread's world bible, or `null` when the thread has none. The shared
 * `StoryPanel` type in `@/types/daily-journey` is owned by the engine side and
 * does not carry the field yet, so it is read structurally here — which is also
 * what an older server, sending no such field, needs.
 */
type StoryDialogueLine = StoryPanel['dialogue'][number] & {
  character_name?: string | null;
  /** WP-90: the director's face for this line — neutral | happy | cross | moved. */
  mood?: string | null;
  /** WP-90: the line in the learner's language, sent for learners up to A2. */
  text_native?: string | null;
};

/**
 * WP-90: a panel as the engine sends it now, read structurally — an older
 * server sends none of these, and the shared type (owned by the engine side)
 * need not know them for the reader to use them.
 */
type StoryPanelSource = StoryPanel & {
  /** One sentence describing the picture, in the learner's language. */
  alt_native?: string | null;
  overlay_payload?: { alt_native?: string | null } | null;
};

const CHARACTER_NAMES: Record<string, string> = {
  romy: 'Romy',
  marin: 'Marin',
  lila: 'Lila',
  gus: 'Gus',
  margaux: 'Margaux',
  marchand: 'Monsieur Marchand',
  toi: 'Vous',
  learner: 'Vous',
  you: 'Vous',
};

/**
 * The name to print above a line.
 *
 * The server's own `character_name` wins whenever it sent one: it comes from
 * the thread's world bible and is the only source that knows a generated cast.
 * Only when the field is absent or null does the local table stand in, and an
 * id it does not know keeps its own spelling — which is how a generated id such
 * as `marin_leveque` used to reach the reader as "Marin_leveque".
 */
export function storyCharacterName(
  characterId: string | null | undefined,
  characterName?: string | null,
): string {
  const given = String(characterName ?? '').trim();
  if (given) return given;
  const id = String(characterId || '').trim();
  if (!id) return '';
  const key = id.toLowerCase();
  if (CHARACTER_NAMES[key]) return CHARACTER_NAMES[key];
  return id.charAt(0).toUpperCase() + id.slice(1);
}

/**
 * Narration as the learner should read it (WP-44).
 *
 * Some producers number the beat inside the sentence — «Panneau 1 : la fuite a
 * inondé la cave.» The number is production scaffolding: the reader already
 * says which plate this is, twice (the rail and the dots), and the prefix reads
 * as a caption in a storyboard rather than as a line of a story. Stripped at
 * the edge of the projection so every surface that reads narration — reader,
 * radio lines, the season page — is free of it, and so a producer that stops
 * emitting it needs no second change here.
 */
export function stripPanelPrefix(text: string | null | undefined): string {
  return String(text ?? '')
    .replace(/^\s*panneau\s*n?[°º]?\s*\d+\s*[:.\-–—]\s*/i, '')
    .trim();
}

/**
 * WP-77: the story's live mood for one character, when the payload carries it.
 *
 * The living story keeps `moods: { [character_id]: { mood: -2…2 } }`. The
 * episode projection does not publish it yet, so it is read structurally —
 * from the episode or from one line — and a payload without it is a neutral
 * face, never an invented one.
 */
export function storyMoodFor(
  episode: StoryEpisode | null | undefined,
  characterId: string | null | undefined,
  line?: Record<string, unknown> | null,
): PortraitMood {
  const own = line ? (line.mood ?? line.expression) : undefined;
  if (own != null) return expressionForMood(own);
  const moods = (episode as unknown as { moods?: Record<string, { mood?: unknown } | number> } | null)?.moods;
  const id = String(characterId || '');
  if (!moods || !id) return 'neutral';
  const entry = moods[id];
  return expressionForMood(typeof entry === 'object' && entry ? entry.mood : entry);
}

function panelLines(panel: StoryPanel, episode?: StoryEpisode | null): ReaderLine[] {
  return ((panel.dialogue || []) as StoryDialogueLine[])
    // The raw index is kept before filtering: it is the line's audio key.
    .map((line, rawIndex) => ({ line, rawIndex }))
    .filter(({ line }) => line && String(line.text_fr || '').trim())
    .map(({ line, rawIndex }, index) => ({
      key: `${panel.id}-l${index}`,
      who: storyCharacterName(line.character_id, line.character_name),
      fr: String(line.text_fr).trim(),
      // WP-90: the director's translation for ≤A2 learners brings back
      // «Traduire la case»; a line without one stays French-only.
      en: storyLineNative(line),
      audioKey: `${panel.id}:l${rawIndex}`,
      speakerId: line.character_id ? String(line.character_id) : null,
      // The visual accent stays keyed to the canonical id, so a renamed
      // character keeps its colour; the display name is only a fallback seed.
      character: readerCharacterKey(line.character_id) || readerCharacterKey(line.character_name) || '',
      // WP-77: a face beside every line a drawn character speaks.
      faceId: castIdFor(line.character_id, line.character_name),
      faceMood: storyMoodFor(episode, line.character_id, line as unknown as Record<string, unknown>),
      // WP-92: the day's rule in this line, for «Rayons X» (the focus unit only).
      ...lineMarks(line, episode),
    }));
}

function lineMarks(line: StoryDialogueLine, episode?: StoryEpisode | null): { marks?: ReaderLine['marks'] } {
  const marks = lineMarkRanges(line.text_fr, line.grammar_marks, storyGrammarFocus(episode)?.unit_id ?? null);
  return marks.length ? { marks } : {};
}

/**
 * WP-92: the rule this page was written around, read defensively — an older
 * payload has none, and a focus without a title cannot be named in a legend.
 */
// UI state preserves unknown weaving on older pages; the current wire sends a boolean.
type ReaderGrammarFocus = Omit<GrammarFocus, 'woven'> & { woven: boolean | null };
export function storyGrammarFocus(episode: StoryEpisode | null | undefined): ReaderGrammarFocus | null {
  const focus = (episode as { grammar_focus?: unknown } | null | undefined)?.grammar_focus;
  if (!focus || typeof focus !== 'object') return null;
  const value = focus as Partial<GrammarFocus>;
  const titleFr = typeof value.title_fr === 'string' ? value.title_fr.trim() : '';
  const titleNative = typeof value.title_native === 'string' ? value.title_native.trim() : '';
  if (!titleFr && !titleNative) return null;
  return {
    unit_id: value.unit_id ?? '',
    title_fr: titleFr,
    title_native: titleNative,
    woven: typeof value.woven === 'boolean' ? value.woven : null,
  };
}

/**
 * WP-92 «Rayons X»: the rule's name for the legend, in the reader's chrome
 * language — the learner's up to A2 (`title_native`), French from B1. `null`
 * when the page has no focus or no line carries a mark: then there is no
 * toggle at all.
 */
export function storyRayonsTitle(
  episode: StoryEpisode | null | undefined,
  language: ControlLanguage | null | undefined,
): string | null {
  const focus = storyGrammarFocus(episode);
  if (!focus) return null;
  const marked = buildStoryStages(episode).some(
    (stage) => stage.kind === 'panel' && stage.lines.some((line) => (line.marks?.length ?? 0) > 0),
  );
  if (!marked) return null;
  const french = !language || language === 'fr';
  return (french ? focus.title_fr || focus.title_native : focus.title_native || focus.title_fr) || null;
}

/** WP-90: a line's translation for the learner, when the director sent one. */
export function storyLineNative(line: Record<string, unknown> | null | undefined): string {
  const native = line ? line.text_native : null;
  return typeof native === 'string' ? native.trim() : '';
}

/**
 * WP-90: what the panel's picture shows, for its `alt`.
 *
 * The director's one-sentence description in the learner's language, read
 * from the panel or from its payload; failing that the narration, which at
 * least says where we are. Empty only when the panel has neither.
 */
export function storyPanelAlt(panel: StoryPanel | null | undefined): string {
  if (!panel) return '';
  const source = panel as StoryPanelSource;
  for (const value of [source.alt_native, source.overlay_payload?.alt_native]) {
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return stripPanelPrefix(panel.narration_fr);
}

/** The reader's stage list for one story-engine episode, in panel order. */
export function buildStoryStages(episode: StoryEpisode | null | undefined): ReaderStage[] {
  if (!episode) return [];
  const panels = [...(episode.panels || [])].sort((a, b) => a.index - b.index);
  const stages: ReaderStage[] = panels.map((panel, ordinal) => {
    const lines = panelLines(panel, episode);
    const character = lines.map((line) => line.character).find(Boolean) || '';
    return {
      kind: 'panel',
      key: `panel:${panel.id}`,
      ordinal: ordinal + 1,
      panelId: panel.id,
      panelIndex: panel.index,
      title: '',
      beat: '',
      imageUrl: panelShowsArt(panel) ? panel.image_url || '' : '',
      artStatus: panelShowsArt(panel) ? 'ready' : 'missing',
      // WP-90: the plate is standing in while the drawing is on the press.
      artPending: panelShowsArt(panel) && panel.image_status === 'rendering',
      imageAlt: storyPanelAlt(panel),
      character,
      lines,
      caption: stripPanelPrefix(panel.narration_fr),
      tasks: [],
    };
  });

  // The ending exists only once the server says the exchange has settled.
  if (episode.resolution && (episode.resolution.text_fr || episode.resolution.summary_native)) {
    stages.push({
      kind: 'resolution',
      key: `resolution:${episode.id}`,
      ordinal: stages.length + 1,
      character: 'toi',
      hookQuestion: String(episode.resolution.text_fr || '').trim(),
      hookBeat: String(episode.resolution.summary_native || '').trim(),
      tasks: [],
    });
  }
  return stages;
}

const SHOWN_ART = new Set(['panel_art', 'rendering', 'setting_reference']);

/** A panel with art to show: its own drawing, or the plate (also while drawing). */
function panelShowsArt(panel: StoryPanel): boolean {
  return Boolean(panel.image_url) && SHOWN_ART.has(panel.image_status);
}

/** Which panels reuse setting art, so the reader can say so. */
export function storyUsesSettingArt(episode: StoryEpisode | null | undefined): boolean {
  return Boolean(
    episode?.panels?.some(
      (panel) =>
        (panel.image_status === 'setting_reference' || panel.image_status === 'rendering') &&
        panel.image_url,
    ),
  );
}

/** True while any panel's own drawing is still on its way. */
export function storyArtRendering(episode: StoryEpisode | null | undefined): boolean {
  return Boolean(episode?.panels?.some((panel) => panel.image_status === 'rendering'));
}

// ---------------------------------------------------------------------------
// WP-90 — the panel-art poll, owned by the journey controller
// ---------------------------------------------------------------------------

/** Panel art takes about a minute a scene; re-read the episode every 6 s… */
export const STORY_ART_POLL_MS = 6000;
/** …for at most five minutes. A panel still rendering after that keeps its plate. */
export const STORY_ART_POLL_LIMIT = 50;

/**
 * Should the controller re-read the episode once more? Only while a panel is
 * still drawing, and never past the ceiling — a drawing that never lands is a
 * plate, not a reason to poll for the rest of the day.
 */
export function shouldPollStoryArt(
  episode: StoryEpisode | null | undefined,
  polls: number,
): boolean {
  return storyArtRendering(episode) && polls < STORY_ART_POLL_LIMIT;
}

/**
 * WP-90: whether the controller should look the episode up for this step.
 * The scene reads it; the resolution draws the ending as the page's last
 * panel. Every other step leaves the cache as it is.
 */
export function stepReadsStoryEpisode(kind: string | null | undefined): boolean {
  return kind === 'scene' || kind === 'resolution';
}

/** The saved server position, clamped to the panels the episode actually has. */
export function storyStartIndex(episode: StoryEpisode | null | undefined, stageCount: number): number {
  if (!episode || stageCount <= 0) return 0;
  const saved = Number(episode.panel_index);
  if (!Number.isFinite(saved) || saved < 0) return 0;
  return Math.min(Math.floor(saved), stageCount - 1);
}

/** The reader's eyebrow: chapter title when the engine has one. */
export function storyEpisodeLabel(episode: StoryEpisode | null | undefined): string {
  if (!episode) return '';
  const chapter = episode.chapter?.title_fr ? String(episode.chapter.title_fr).trim() : '';
  return chapter || 'Le feuilleton';
}

// ---------------------------------------------------------------------------
// WP-44 — which of the two reader artboards a panel is drawn as
// ---------------------------------------------------------------------------

/**
 * `bubble` = variant A, the reply in a speech bubble over the art;
 * `line`   = variant B, the art alone with the reply in a card underneath.
 */
export type PanelVariant = 'bubble' | 'line';

/**
 * The one switch.
 *
 * The owner's choice between the two artboards is still open, so it is a single
 * constant rather than a rule spread over the component:
 *
 *   * `'auto'` (shipped) — a bubble when the panel is one line from one named
 *     speaker over real art, which is the only shape a bubble can hold without
 *     covering the picture it sits on; every other panel is a card.
 *   * `'bubble'` — variant A wherever a bubble is physically possible.
 *   * `'line'`  — variant B everywhere; flip here to get the whole reader on
 *     the second artboard with no other edit.
 */
// Owner's decision, 2026-09-17: variant B — the art alone, the line in a card
// under it (`LectureLignes.dc.html`).
export const READER_VARIANT: 'auto' | 'bubble' | 'line' = 'line';

/**
 * How one stage is drawn.
 *
 * Narration-only panels and panels carrying two or more lines are always cards:
 * a bubble that has to hold a stack of replies is a card with a tail, and a
 * bubble with no speaker has nobody to point at. Art is required either way —
 * a bubble over a missing illustration is a card in a worse place.
 */
export function panelReaderVariant(
  stage: ReaderStage | null | undefined,
  variant: 'auto' | 'bubble' | 'line' = READER_VARIANT,
): PanelVariant {
  if (variant === 'line') return 'line';
  if (!stage || stage.kind !== 'panel') return 'line';
  const hasArt = stage.artStatus === 'ready' && Boolean(stage.imageUrl);
  if (!hasArt) return 'line';
  const spoken = (stage.lines || []).filter((line) => String(line.fr || '').trim());
  if (!spoken.length) return 'line';
  if (variant === 'bubble') return 'bubble';
  if (spoken.length !== 1) return 'line';
  return String(spoken[0].who || '').trim() ? 'bubble' : 'line';
}

// ---------------------------------------------------------------------------
// WP-32 — «Écouter d'abord»: the four-stage listening cycle
// ---------------------------------------------------------------------------
//
// The effect this package claims comes from the *cycle*, not from the audio:
// metacognitive listening instruction — predict → listen → verify → debrief —
// has a consistent moderate effect and the largest one for the weakest
// listeners (Vandergrift & Tafaghodtari 2010; Vandergrift & Goh 2012). Playing
// a scene aloud without the other three stages is the part that does least.
//
// Everything below is pure and deterministic. In particular the two guesses are
// derived from the episode the server already sent — **no model call**, no
// second generation, nothing to pay for and nothing new to validate. The price
// of that is honesty about reach: an episode whose lines settle nothing is
// reported as `unresolved` rather than scored either way.

/** The learner's two options at the *prédire* stage. */
export type EpisodeGuessId = 'accord' | 'resistance';

export type EpisodeGuess = { id: EpisodeGuessId; fr: string };

export type RadioStage = 'predire' | 'ecouter' | 'verifier' | 'retenir';

export const RADIO_STAGES: readonly RadioStage[] = ['predire', 'ecouter', 'verifier', 'retenir'];

/**
 * The words a scene uses when the counterpart goes along with the learner, and
 * the words it uses when they do not.
 *
 * A closed, auditable list rather than a classifier: at A1–B1 the endings this
 * engine writes are short and formulaic, and a wrong verdict at the *vérifier*
 * stage is worse than no verdict — it teaches the learner to distrust the one
 * moment in the cycle that is supposed to settle things. Anything these lists
 * do not recognise comes back `unresolved`.
 *
 * Matched on folded text (accents removed, lower-cased) so `désolé`, `desole`
 * and `Désolée` are one marker.
 */
const ACCORD_MARKERS: readonly string[] = [
  "d'accord",
  'entendu',
  'bien sur',
  'volontiers',
  'avec plaisir',
  'ca marche',
  'parfait',
  "c'est note",
  'je veux bien',
  'pas de probleme',
  'oui,',
  'oui !',
  'oui.',
];

const RESISTANCE_MARKERS: readonly string[] = [
  'desole',
  'malheureusement',
  'je ne peux pas',
  "ce n'est pas possible",
  'impossible',
  'je regrette',
  'une autre fois',
  'plutot',
  'non,',
  'non !',
  'non.',
  'je ne crois pas',
  'pas aujourd',
];

/** Lower-case and strip accents so one marker matches all of its spellings. */
export function foldFrench(text: string): string {
  return String(text || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[\u2018\u2019\u201b\u02bc]/g, "'")
    .replace(/\s+/g, ' ')
    .trim();
}

/**
 * One spoken line of the episode, in playback order.
 *
 * The key is `${panelId}:n` for narration and `${panelId}:l${rawIndex}` for a
 * dialogue line — computed from the *raw* dialogue array, exactly as
 * `app/services/episode_audio.py` computes it, so a manifest and this list line
 * up without an index negotiation between the two sides.
 */
export type EpisodeListenLine = {
  key: string;
  /** `narrator`, or the dialogue line's character id. */
  characterId: string;
  /** The display name to show while the words are hidden. Empty for narration. */
  who: string;
  fr: string;
};

export const NARRATOR_ID = 'narrator';

export function episodeListenLines(
  episode: StoryEpisode | null | undefined,
): EpisodeListenLine[] {
  if (!episode) return [];
  const panels = [...(episode.panels || [])].sort((a, b) => a.index - b.index);
  const lines: EpisodeListenLine[] = [];
  for (const panel of panels) {
    const narration = stripPanelPrefix(panel.narration_fr);
    if (narration.length >= 2) {
      lines.push({ key: `${panel.id}:n`, characterId: NARRATOR_ID, who: '', fr: narration });
    }
    const dialogue = (panel.dialogue || []) as StoryDialogueLine[];
    dialogue.forEach((line, index) => {
      const fr = String(line?.text_fr || '').trim();
      if (fr.length < 2) return;
      const characterId = String(line?.character_id || '').trim();
      lines.push({
        key: `${panel.id}:l${index}`,
        characterId,
        who: storyCharacterName(characterId, line?.character_name),
        fr,
      });
    });
  }
  return lines;
}

/**
 * The two guesses, in French, about how the exchange ends.
 *
 * Deterministic from the episode's own cast: the counterpart is the first
 * non-learner speaker, which is the character the scene's objective is aimed
 * at. With no named counterpart the guesses fall back to an impersonal form
 * rather than inventing a name — this module never synthesises a character.
 *
 * They are content, not chrome, and therefore French in every control
 * language: the learner is about to listen to French, and a guess phrased in
 * German would be a different task.
 */
export function buildEpisodeGuesses(
  episode: StoryEpisode | null | undefined,
): EpisodeGuess[] {
  const who = episodeCounterpart(episode);
  const subject = who || 'La personne en face';
  return [
    { id: 'accord', fr: `${subject} dit oui.` },
    { id: 'resistance', fr: `${subject} refuse ou propose autre chose.` },
  ];
}

/** The first speaker who is not the learner: the person being asked. */
export function episodeCounterpart(episode: StoryEpisode | null | undefined): string {
  const learners = new Set(['toi', 'learner', 'you', 'vous']);
  for (const line of episodeListenLines(episode)) {
    if (line.characterId === NARRATOR_ID) continue;
    if (learners.has(line.characterId.toLowerCase())) continue;
    if (line.who) return line.who;
  }
  return '';
}

export type EpisodeVerification = {
  /** What the episode's own words support, or null when they settle nothing. */
  supported: EpisodeGuessId | null;
  /** `confirmed` the guess held; `other` it did not; `unresolved` nobody can say. */
  verdict: 'confirmed' | 'other' | 'unresolved';
  /** The exact line that decided it, so the stage shows evidence, not a verdict. */
  quoteFr: string;
};

/**
 * Check a guess against the scene's stored outcome.
 *
 * The evidence is, in order: the server's own resolution text when it has
 * published one (a completed scene), otherwise the episode's dialogue read from
 * the end backwards — the ending is where an exchange settles. Narration is
 * skipped: "Romy hésite" describes a beat, it does not answer the question.
 */
export function verifyEpisodeGuess(
  episode: StoryEpisode | null | undefined,
  guess: EpisodeGuessId | null,
): EpisodeVerification {
  const evidence: Array<{ fr: string }> = [];
  const resolution = String(episode?.resolution?.text_fr || '').trim();
  if (resolution) evidence.push({ fr: resolution });
  const spoken = episodeListenLines(episode).filter((line) => line.characterId !== NARRATOR_ID);
  for (let i = spoken.length - 1; i >= 0; i -= 1) evidence.push({ fr: spoken[i].fr });

  for (const item of evidence) {
    const folded = foldFrench(item.fr);
    const accord = ACCORD_MARKERS.some((marker) => folded.includes(marker));
    const resistance = RESISTANCE_MARKERS.some((marker) => folded.includes(marker));
    // A line carrying both ("oui, mais malheureusement…") settles nothing on
    // its own; keep looking rather than picking the first list that matched.
    if (accord === resistance) continue;
    const supported: EpisodeGuessId = accord ? 'accord' : 'resistance';
    return {
      supported,
      verdict: guess === null ? 'unresolved' : guess === supported ? 'confirmed' : 'other',
      quoteFr: item.fr,
    };
  }
  return { supported: null, verdict: 'unresolved', quoteFr: '' };
}

/**
 * The one French line for *retenir*: what to listen for tomorrow.
 *
 * Taken from the episode itself — the phrase that actually decided the ending,
 * or failing that the shortest full character line, which is the one a learner
 * has a chance of catching next time. Never invented, never a rule.
 */
export function episodeRetainPhrase(episode: StoryEpisode | null | undefined): string {
  const verification = verifyEpisodeGuess(episode, null);
  if (verification.quoteFr) return verification.quoteFr;
  const spoken = episodeListenLines(episode).filter(
    (line) => line.characterId !== NARRATOR_ID && line.fr.split(/\s+/).length >= 3,
  );
  if (!spoken.length) return '';
  return spoken.reduce((shortest, line) => (line.fr.length < shortest.fr.length ? line : shortest))
    .fr;
}

// ---------------------------------------------------------------------------
// The stage machine
// ---------------------------------------------------------------------------

export type RadioState = {
  stage: RadioStage;
  guess: EpisodeGuessId | null;
  /** How many lines the learner has turned over at *vérifier*. */
  revealed: number;
  /** True once the episode has been played through at least once. */
  heard: boolean;
};

export type RadioEvent =
  | { type: 'guess'; id: EpisodeGuessId }
  | { type: 'listen' }
  | { type: 'heard' }
  | { type: 'verify' }
  | { type: 'reveal' }
  | { type: 'revealAll'; count: number }
  | { type: 'retain' }
  | { type: 'restart' };

export const RADIO_INITIAL: RadioState = {
  stage: 'predire',
  guess: null,
  revealed: 0,
  heard: false,
};

/**
 * The cycle as one pure transition.
 *
 * Two rules carry the pedagogy and are the reason this is a machine rather
 * than four booleans:
 *
 *  * **No listening before a prediction.** A learner who skips straight to the
 *    audio gets the audio-only condition, which is the one the evidence says
 *    does least. `listen` from `predire` without a guess is a no-op.
 *  * **No verifying before listening.** `verify` needs `heard`; otherwise the
 *    *vérifier* stage is just reading, and the guess was never tested.
 *
 * Failure does not trap anyone: `heard` is also set when the audio could not be
 * played at all, so a provider outage degrades to reading the lines rather than
 * to a dead end. That decision lives in the component, which knows whether the
 * synthesis failed; the machine only refuses to *invent* progress.
 */
export function radioReduce(state: RadioState, event: RadioEvent): RadioState {
  switch (event.type) {
    case 'guess':
      return state.stage === 'predire' ? { ...state, guess: event.id } : state;
    case 'listen':
      return state.stage === 'predire' && state.guess
        ? { ...state, stage: 'ecouter' }
        : state;
    case 'heard':
      return state.stage === 'ecouter' ? { ...state, heard: true } : state;
    case 'verify':
      return state.stage === 'ecouter' && state.heard
        ? { ...state, stage: 'verifier' }
        : state;
    case 'reveal':
      return state.stage === 'verifier' ? { ...state, revealed: state.revealed + 1 } : state;
    case 'revealAll':
      return state.stage === 'verifier'
        ? { ...state, revealed: Math.max(state.revealed, Math.max(0, event.count)) }
        : state;
    case 'retain':
      return state.stage === 'verifier' ? { ...state, stage: 'retenir' } : state;
    case 'restart':
      return RADIO_INITIAL;
    default:
      return state;
  }
}

/** 1-based position of a stage, for the progress rule. */
export function radioStageOrdinal(stage: RadioStage): number {
  const index = RADIO_STAGES.indexOf(stage);
  return index < 0 ? 1 : index + 1;
}

// ---------------------------------------------------------------------------
// WP-103 T2 — the text is hidden by default, and never a wall
// ---------------------------------------------------------------------------

/**
 * The owner's test: the words are hidden while you listen — by design — with
 * no way to show them. Hidden stays the default (that is the exercise), but at
 * every stage the learner can show the text of the whole page, and, where the
 * lines are listed, of one line. Pure: the stage machine above is untouched.
 */
export type RadioText = {
  /** The whole page's text, shown. */
  all: boolean;
  /** Line keys shown one by one (while `all` is off). */
  lines: string[];
};

export const RADIO_TEXT_INITIAL: RadioText = { all: false, lines: [] };

export type RadioTextEvent = { type: 'all' } | { type: 'line'; key: string };

/** A toggle either way. Switching the page off hides every line again. */
export function radioTextReduce(state: RadioText, event: RadioTextEvent): RadioText {
  if (event.type === 'all') return state.all ? RADIO_TEXT_INITIAL : { all: true, lines: state.lines };
  const key = String(event.key || '');
  if (!key) return state;
  return state.lines.includes(key)
    ? { ...state, lines: state.lines.filter((item) => item !== key) }
    : { ...state, lines: [...state.lines, key] };
}

export function radioLineShown(state: RadioText, key: string): boolean {
  return state.all || state.lines.includes(key);
}

/**
 * Which text controls a stage draws. The page-wide toggle is at every stage;
 * the per-line ones sit on the stages that list the lines.
 */
export function radioTextControls(stage: RadioStage): { page: true; lines: boolean } {
  return { page: true, lines: stage === 'ecouter' || stage === 'verifier' };
}

/**
 * The listening question, before and after the audio: how does it end, and what
 * the learner guessed (French, as the guesses are). The question itself is
 * chrome, so its words come from the copy table.
 */
export function radioTask(
  episode: StoryEpisode | null | undefined,
  guess: EpisodeGuessId | null,
): { guessFr: string | null } {
  if (!guess) return { guessFr: null };
  return { guessFr: buildEpisodeGuesses(episode).find((item) => item.id === guess)?.fr ?? null };
}

// ---------------------------------------------------------------------------
// The remembered preference
// ---------------------------------------------------------------------------

/** One key, one learner, one device. Nothing here is sent to the server. */
export const LISTEN_FIRST_KEY = 'atelier.journey.listen-first';

function storage(): Storage | null {
  try {
    if (typeof window === 'undefined' || !window.localStorage) return null;
    return window.localStorage;
  } catch {
    // Private mode, or a WebView with site data blocked. Not an error: the
    // learner simply gets the default — reading — every time.
    return null;
  }
}

/**
 * Whether the learner has chosen to listen first.
 *
 * The default is **off**. Listening-first is a harder way to meet a scene and
 * the evidence for it assumes a learner who opted into the cycle; making it the
 * default would hand the hardest condition to the people who never chose it.
 */
export function readListenFirst(fallback = false): boolean {
  const stored = storage()?.getItem(LISTEN_FIRST_KEY);
  if (stored === '1') return true;
  if (stored === '0') return false;
  return fallback;
}

export function writeListenFirst(enabled: boolean): void {
  try {
    storage()?.setItem(LISTEN_FIRST_KEY, enabled ? '1' : '0');
  } catch {
    /* nothing the learner needs to know about */
  }
}

/**
 * Where «Écouter d'abord» belongs on this scene (QA finding F-27).
 *
 * The offer used to sit on the reader's foot, which a learner reaches by
 * reading the whole scene — and the cycle it opens then asks them to *predict
 * how it ends*. An offer you can only accept after the answer is not an offer.
 *
 * Three answers, and only three:
 *
 * * `'cycle'` — go straight into predict → listen → verify → retain, because
 *   the learner asked for it or the planner dealt «jour d'écoute»;
 * * `'before_first_panel'` — the quiet link, above the panels, where it can
 *   still be taken;
 * * `'none'` — this deployment cannot speak the scene. No offer is made at all,
 *   ever: a link that answers "audio is off" is worse than no link.
 */
export type ListenFirstPlacement = 'cycle' | 'before_first_panel' | 'none';

export function listenFirstPlacement({
  audioAvailable,
  preferred = false,
  dealt = false,
}: {
  /** The server's own answer about this deployment (`prompt.audio_available`). */
  audioAvailable: boolean;
  /** The learner's remembered choice. */
  preferred?: boolean;
  /** WP-66 dealt a listening day for this scene (`prompt.listen_first`). */
  dealt?: boolean;
}): ListenFirstPlacement {
  if (!audioAvailable) return 'none';
  return preferred || dealt ? 'cycle' : 'before_first_panel';
}

/**
 * An authored scene's page as an episode the reader can show. Local only: it has no
 * server episode, so nothing is saved against its id.
 */
export function authoredPageEpisode(
  journeyId: string,
  stepId: string,
  panels: StoryPanel[] | null | undefined,
): StoryEpisode | null {
  if (!panels || !panels.length) return null;
  return {
    id: `authored:${stepId}`,
    scene_id: `authored:${stepId}`,
    serial_thread_id: '',
    serial_episode_id: null,
    journey_id: journeyId,
    title_fr: '',
    status: 'available',
    chapter: null,
    panel_index: 0,
    panels,
    resolution: null,
    grammar_focus: null,
  };
}

// ---------------------------------------------------------------------------
// WP-90 — the ending is the last panel («case finale»)
// ---------------------------------------------------------------------------

/**
 * The resolution step's ending as the reader draws it. Read structurally: the
 * step's prompt is the server's `ResolutionPrompt`, plus what a newer server
 * may add (`mood`, `alt_native`).
 */
export type StoryFinaleSource = {
  character_line_fr?: string | null;
  summary_native?: string | null;
  image_url?: string | null;
  story_pending?: boolean | null;
  mood?: unknown;
  alt_native?: string | null;
};

/**
 * The resolution step as the reader's last stage: the red-triangle «case
 * finale». The speaker is the day's counterpart (`journeySpeaker`); without
 * one the line prints without a face, never with somebody else's.
 */
export function storyFinaleStage(
  stepId: string,
  prompt: StoryFinaleSource | null | undefined,
  speaker: { id: string | null; name: string } | null | undefined,
  ordinal = 1,
): ReaderResolutionStage {
  const lineFr = String(prompt?.character_line_fr || '').trim();
  const summary = String(prompt?.summary_native || '').trim();
  const name = String(speaker?.name || '').trim();
  const line: ReaderLine | null = lineFr
    ? {
        key: `finale-${stepId}-l0`,
        who: name,
        fr: lineFr,
        en: '',
        character: readerCharacterKey(speaker?.id) || readerCharacterKey(name) || '',
        faceId: castIdFor(speaker?.id, name),
        faceMood: expressionForMood(prompt?.mood),
        audioKey: `finale:${stepId}`,
        speakerId: speaker?.id ?? null,
      }
    : null;
  const alt = typeof prompt?.alt_native === 'string' ? prompt.alt_native.trim() : '';
  return {
    kind: 'resolution',
    key: `finale:${stepId}`,
    ordinal,
    character: line?.character || 'toi',
    hookQuestion: '',
    hookBeat: '',
    tasks: [],
    finale: {
      imageUrl: String(prompt?.image_url || '').trim(),
      imageAlt: alt || summary,
      line,
      summary,
      waiting: prompt?.story_pending === true,
    },
  };
}

/**
 * The page's panels followed by the finale. The episode's own resolution
 * stage (the replay's «À suivre») gives way to it: one ending, not two.
 */
export function storyStagesWithFinale(
  episode: StoryEpisode | null | undefined,
  finale: ReaderResolutionStage,
): ReaderStage[] {
  const panels = buildStoryStages(episode).filter((stage) => stage.kind === 'panel');
  return [...panels, { ...finale, ordinal: panels.length + 1 }];
}

type JourneyLike = {
  id?: string | null;
  steps?: Array<{ id: string; kind: string; prompt?: unknown }> | null;
} | null | undefined;

/**
 * The page the finale closes: the engine's episode when it published one for
 * this journey, else the authored scene's own page, else nothing (the finale
 * then stands alone).
 */
export function journeyStoryPage(
  journey: JourneyLike,
  episode: StoryEpisode | null | undefined,
): StoryEpisode | null {
  if (episode && episode.panels?.length) return episode;
  if (!journey?.id) return null;
  const scenes = (journey.steps || []).filter((step) => step && step.kind === 'scene');
  for (let i = scenes.length - 1; i >= 0; i -= 1) {
    const panels = (scenes[i].prompt as { panels?: StoryPanel[] | null } | undefined)?.panels;
    const page = authoredPageEpisode(journey.id, scenes[i].id, panels);
    if (page) return page;
  }
  return null;
}

/** The frame a finale stands in when there is no page before it: no panels, nothing saved. */
export function finaleOnlyEpisode(journeyId: string, stepId: string): StoryEpisode {
  return {
    id: `finale:${stepId}`,
    scene_id: `finale:${stepId}`,
    serial_thread_id: '',
    serial_episode_id: null,
    journey_id: journeyId,
    title_fr: '',
    status: 'available',
    chapter: null,
    panel_index: 0,
    panels: [],
    resolution: null,
    grammar_focus: null,
  };
}
