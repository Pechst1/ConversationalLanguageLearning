/**
 * WP-144 «La page verticale» — one story panel, full-bleed.
 *
 * The panel is the screen between the reader's bar and its nav. The plate
 * covers it, cropped for the beat; the drawn cast stands at its foot; the camera
 * pushes in slowly. Speech is balloons anchored to the speaker, narration is a
 * caption box at the top, the learner's own line is the balloon at the bottom
 * edge. Lines arrive one by one with the voice (`reveal-model.ts`), every word
 * is still a word to tap for help, and nothing ever covers a face: what does not
 * fit goes to a sheet at the panel's foot, or under it (`balloon-layout.ts`).
 *
 * The reader around it (bar, dots, ← / Weiter, «Übersetzen», word help) is the
 * unchanged FeuilletonReader; this replaces only its PanelBody, behind the
 * `readerLayout` switch (`lib/reader-layout.ts`).
 */

import React, { useCallback, useEffect, useLayoutEffect, useMemo, useReducer, useRef, useState } from 'react';

import { FrenchLine } from '@/components/feuilleton/reader/TappableFrench';
import { fillReaderCopy, type ReaderCopy } from '@/components/feuilleton/reader/reader-copy';
import type { ReaderLine, ReaderPanelStage } from '@/components/feuilleton/reader/panel-model';
import { PanelStage, stageMembers } from '@/components/cast/PanelStage';
import { useMouth } from '@/components/cast/useMouth';
import type { LineVoice } from '@/components/atelier-v2/journey/useLineVoice';
import { useArtSet } from '@/lib/art-set';
import { frenchSpacing } from '@/lib/french-typography';
import { resolveMediaUrl } from '@/lib/media-url';
import { voicesAloud } from '@/lib/voice-preference';

import { layoutPanel, type LayoutItem, type LayoutKind, type PanelLayout } from './balloon-layout';
import {
  castBox,
  headIndexFor,
  plateFocus,
  pushInBounds,
  pushInOrigin,
  stageHeadBoxes,
  type HeadBox,
  type Size,
} from './page-geometry';
import {
  revealDone,
  revealedChars,
  revealInitial,
  revealModeName,
  revealPlan,
  revealReduce,
  timedDelayMs,
  type RevealPlan,
} from './reveal-model';

/**
 * TODO(WP-143 merge): PanelStage gains `framing: 'band' | 'fill'` and a focus
 * point. Until it lands the vertical page frames the cast itself (a cast box at
 * the panel's foot, `castBox`), and passes nothing new. Flip this once the prop
 * exists and PanelStage reports the head boxes it framed, so the balloons keep
 * anchoring to the faces it actually draws.
 */
const PANEL_STAGE_FILL = false;

const useIsoLayoutEffect = typeof window === 'undefined' ? useEffect : useLayoutEffect;

type WordContext = {
  sentence: string;
  sentenceEn?: string;
  character?: string;
  speaker?: string;
  speakerId?: string | null;
  panelId?: string;
  lineKey?: string;
};

export type VerticalWordHandler = (word: { surface: string; term: string }, context: WordContext) => void;

/** What the reader adds to a marked line while «Rayons X» is on (see FeuilletonReader). */
export type LineMarks = (line: ReaderLine) => Record<string, unknown>;

type Entry =
  | { key: string; kind: 'caption'; role: 'head' | 'narration' | 'silent' }
  | { key: string; kind: 'speech' | 'you'; line: ReaderLine; order: number };

function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined' && typeof window.matchMedia === 'function'
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/** The panel's entries in reading order: the captions, then the lines as they are said. */
export function panelEntries(stage: ReaderPanelStage, head: { eyebrow?: string; title: string } | null): Entry[] {
  const entries: Entry[] = [];
  if (head && head.title) entries.push({ key: 'vp-head', kind: 'caption', role: 'head' });
  if (stage.caption) entries.push({ key: 'vp-cap', kind: 'caption', role: 'narration' });
  if (stage.silent) entries.push({ key: 'vp-silent', kind: 'caption', role: 'silent' });
  stage.lines.forEach((line, order) => {
    entries.push({ key: line.key, kind: line.you ? 'you' : 'speech', line, order });
  });
  return entries;
}

export function VerticalPanel({
  stage,
  showTranslation,
  onWord,
  voice = null,
  marksFor,
  head = null,
  topInset = 0,
  t,
}: {
  stage: ReaderPanelStage;
  showTranslation: boolean;
  onWord: VerticalWordHandler;
  voice?: LineVoice | null;
  marksFor?: LineMarks;
  /** The first panel carries the page's kicker and headline as its establishing caption. */
  head?: { eyebrow?: string; title: string } | null;
  /** Room kept at the top for the reader's state chip («Déjà lu», «À vous»). */
  topInset?: number;
  t: ReaderCopy;
}) {
  const drawn = useArtSet() === 'drawn' && Boolean(stage.plateUrl);
  const src = drawn ? resolveMediaUrl(stage.plateUrl) : stage.artStatus === 'ready' ? resolveMediaUrl(stage.imageUrl) : '';
  const unknownFaces = !drawn && Boolean(src);
  const alt = stage.imageAlt || (stage.title ? fillReaderCopy(t.plate_alt, { title: stage.title }) : '');
  const focus = plateFocus(stage);
  const members = useMemo(() => stage.cast ?? [], [stage.cast]);
  const castCount = drawn ? stageMembers(members).length : 0;

  const headTitle = head?.title ?? '';
  const headEyebrow = head?.eyebrow ?? '';
  const entries = useMemo(
    () => panelEntries(stage, headTitle ? { eyebrow: headEyebrow, title: headTitle } : null),
    [stage, headTitle, headEyebrow],
  );
  const lines = useMemo(() => entries.filter((entry): entry is Extract<Entry, { line: ReaderLine }> => entry.kind !== 'caption'), [entries]);

  // ---- the reveal ---------------------------------------------------------
  const [motion] = useState(() => !prefersReducedMotion());
  const plan: RevealPlan = useMemo(
    () => revealPlan({
      reducedMotion: !motion,
      voicesAloud: Boolean(voice) && voicesAloud(),
      voiceSupported: Boolean(voice?.supported),
      lineCount: lines.length,
    }),
    // The plan is fixed for the panel: a voice object that re-renders does not restart it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [motion, lines.length, Boolean(voice), Boolean(voice?.supported)],
  );
  const total = lines.length;
  const [reveal, dispatch] = useReducer(
    (state: ReturnType<typeof revealInitial>, event: Parameters<typeof revealReduce>[1]) => revealReduce(state, event, total),
    undefined,
    () => revealInitial(plan, total),
  );
  const [chars, setChars] = useState<{ index: number; count: number } | null>(null);
  const autoStopped = useRef(false);

  // ---- measuring and laying out --------------------------------------------
  const panelRef = useRef<HTMLDivElement | null>(null);
  const measureRef = useRef<HTMLDivElement | null>(null);
  const [panel, setPanel] = useState<Size | null>(null);
  const [layout, setLayout] = useState<PanelLayout | null>(null);
  const [tick, setTick] = useState(0);
  const signature = useRef('');

  const box = panel ? castBox(panel, castCount) : null;
  // The push-in moves toward the lead speaker's face (the faces as drawn, not padded).
  const origin = panel ? pushInOrigin(panel, box ? stageHeadBoxes(members, box, 0) : []) : null;

  useEffect(() => {
    const node = panelRef.current;
    if (!node || typeof ResizeObserver === 'undefined') return undefined;
    const observer = new ResizeObserver(() => setTick((value) => value + 1));
    observer.observe(node);
    if (measureRef.current) observer.observe(measureRef.current);
    // A web font landing changes every balloon's size.
    void (document as Document & { fonts?: { ready: Promise<unknown> } }).fonts?.ready.then(() => setTick((value) => value + 1));
    return () => observer.disconnect();
  }, []);

  useIsoLayoutEffect(() => {
    const node = panelRef.current;
    const measure = measureRef.current;
    if (!node || !measure) return;
    const size = { w: node.clientWidth, h: node.clientHeight };
    if (!size.w || !size.h) return;
    const items: LayoutItem[] = [];
    const nextHeads = (() => {
      const cbox = castBox(size, castCount);
      const raw = cbox ? stageHeadBoxes(members, cbox) : [];
      if (!motion) return raw;
      const o = pushInOrigin(size, raw);
      return raw.map((entry) => ({ ...pushInBounds(entry, o), rigId: entry.rigId }));
    })();
    for (const entry of entries) {
      const el = measure.querySelector<HTMLElement>(`[data-measure="${CSS.escape(entry.key)}"]`);
      if (!el) continue;
      items.push({
        key: entry.key,
        kind: entry.kind as LayoutKind,
        size: { w: Math.ceil(el.offsetWidth), h: Math.ceil(el.offsetHeight) },
        anchor: entry.kind === 'speech' ? headIndexFor(nextHeads, entry.line) : -1,
      });
    }
    const key = JSON.stringify([size, items.map((item) => [item.key, item.size.w, item.size.h, item.anchor]), topInset, unknownFaces, motion]);
    if (key === signature.current) return;
    signature.current = key;
    setPanel(size);
    setLayout(layoutPanel(size, nextHeads, items, { topInset, unknownFaces }));
  }, [tick, entries, showTranslation, topInset, unknownFaces, castCount, members, motion]);

  // ---- the sequence --------------------------------------------------------
  // `driving` is the line being brought in: said (voice), or given its reading time.
  const ready = Boolean(layout);
  const [driving, setDriving] = useState(0);
  const voiceRef = useRef(voice);
  voiceRef.current = voice;
  const expected = useRef<{ key: string; index: number; started: boolean } | null>(null);

  useEffect(() => {
    if (!ready || driving >= total) return undefined;
    if (plan.text === 'all' && !plan.speak) return undefined;
    const entry = lines[driving];
    if (!entry) return undefined;
    const index = driving;
    dispatch({ type: 'line-started', index });
    const v = voiceRef.current;
    if (plan.speak && v && !autoStopped.current && entry.kind !== 'you') {
      const key = entry.line.audioKey || entry.line.key;
      expected.current = { key, index, started: false };
      v.speak({ key, text_fr: entry.line.fr, character_id: entry.line.speakerId ?? entry.line.faceId ?? null });
      // A voice that never starts (autoplay refused, no clip, no device voice)
      // must not hold the page: the rest of the panel arrives silently.
      const giveUp = window.setTimeout(() => {
        if (expected.current?.index === index && !expected.current.started) {
          expected.current = null;
          autoStopped.current = true;
          setChars(null);
          dispatch({ type: 'line-ended', index });
          setDriving(index + 1);
        }
      }, 2500);
      return () => window.clearTimeout(giveUp);
    }
    // Silent: the next balloon opens once this one has been read. (The learner's own line has no clip.)
    if (plan.text !== 'sequence') {
      setDriving(index + 1);
      return undefined;
    }
    const timer = window.setTimeout(() => {
      dispatch({ type: 'line-ended', index });
      setDriving(index + 1);
    }, timedDelayMs(entry.line.fr));
    return () => window.clearTimeout(timer);
  }, [ready, driving, total, plan, lines]);

  // The voice says when a line has begun and when it is over.
  const speakingKey = voice?.speakingKey ?? null;
  useEffect(() => {
    const wanted = expected.current;
    if (!wanted) return undefined;
    if (speakingKey === wanted.key) {
      wanted.started = true;
      return undefined;
    }
    if (!wanted.started) return undefined;
    expected.current = null;
    setChars(null);
    dispatch({ type: 'line-ended', index: wanted.index });
    const timer = window.setTimeout(() => setDriving(wanted.index + 1), 250);
    return () => window.clearTimeout(timer);
  }, [speakingKey]);

  // The words follow the voice's clock, on animation frames.
  useEffect(() => {
    if (!plan.words || !voice?.progress || reveal.speaking < 0) return undefined;
    const entry = lines[reveal.speaking];
    if (!entry || entry.kind === 'you') return undefined;
    const progress = voice.progress;
    const index = reveal.speaking;
    let frame = 0;
    let last = -1;
    const step = () => {
      const count = revealedChars(entry.line.fr, progress());
      if (count !== last) {
        last = count;
        setChars({ index, count });
      }
      frame = window.requestAnimationFrame(step);
    };
    frame = window.requestAnimationFrame(step);
    return () => window.cancelAnimationFrame(frame);
  }, [plan.words, voice?.progress, reveal.speaking, lines]);

  // Leaving the panel silences it.
  const linesRef = useRef(lines);
  linesRef.current = lines;
  useEffect(
    () => () => {
      const v = voiceRef.current;
      if (!v?.speakingKey) return;
      if (linesRef.current.some((entry) => (entry.line.audioKey || entry.line.key) === v.speakingKey)) v.stop();
    },
    [],
  );

  const showAll = useCallback((event: React.MouseEvent) => {
    const target = event.target as HTMLElement | null;
    if (target?.closest('button, a, input, textarea, select, [data-roving-line]')) return;
    autoStopped.current = true;
    dispatch({ type: 'all' });
    setDriving(Number.MAX_SAFE_INTEGER);
  }, []);

  // ---- the speaker's mouth follows the voice ----------------------------------
  const heard = voice ? stage.lines.find((line) => !line.you && (line.audioKey || line.key) === voice.speakingKey) ?? null : null;
  const heardMouth = useMouth(voice, heard ? heard.audioKey || heard.key : null, heard?.fr ?? null);

  // ---- drawing ---------------------------------------------------------------
  const shownCount = plan.text === 'all' ? total : reveal.shown;
  const placed = new Map((layout?.placed ?? []).map((entry) => [entry.key, entry]));
  const overflow = new Set(layout?.overflow ?? []);
  const sheetMode = layout?.sheet.mode ?? 'none';

  const lineVisible = (entry: Entry) => entry.kind === 'caption' || entry.order < shownCount;
  const lineChars = (entry: Entry) =>
    entry.kind !== 'caption' && plan.words && chars && chars.index === entry.order && reveal.speaking === entry.order ? chars.count : null;

  const captionBody = (entry: Extract<Entry, { kind: 'caption' }>) => {
    if (entry.role === 'head' && head) {
      return (
        <>
          {head.eyebrow && <p className="vp-caption__eyebrow">{head.eyebrow}</p>}
          <h1 className="vp-caption__title">{frenchSpacing(head.title)}</h1>
        </>
      );
    }
    if (entry.role === 'silent') return <p className="vp-caption__line vp-caption__line--silent">{t.silent_beat}</p>;
    return (
      <FrenchLine
        className="fr-line vp-caption__line"
        text={stage.caption}
        idPrefix={`${stage.key}-cap`}
        wordLabel={t.word_help}
        onWord={(word) => onWord(word, { sentence: stage.caption, character: stage.character })}
      />
    );
  };

  const lineBody = (entry: Extract<Entry, { line: ReaderLine }>, revealChars: number | null) => {
    const line = entry.line;
    const canPlay = Boolean(voice) && !line.you && Boolean(line.who);
    return (
      <>
        {line.who && (
          canPlay ? (
            <button
              type="button"
              className="vp-who"
              aria-label={fillReaderCopy(t.listen_to, { name: line.who })}
              aria-pressed={voice?.speakingKey === (line.audioKey || line.key)}
              onClick={() => voice?.speak({ key: line.audioKey || line.key, text_fr: line.fr, character_id: line.speakerId ?? line.faceId ?? null })}
            >
              {line.who}
            </button>
          ) : (
            <p className="vp-who">{line.who}</p>
          )
        )}
        <FrenchLine
          className="fr-line vp-line"
          text={line.fr}
          idPrefix={line.key}
          wordLabel={t.word_help}
          revealChars={revealChars}
          {...(marksFor ? marksFor(line) : {})}
          onWord={(word) =>
            onWord(word, {
              sentence: line.fr,
              sentenceEn: line.en,
              character: line.character || stage.character,
              speaker: line.who,
              speakerId: line.you ? null : line.speakerId ?? null,
              panelId: stage.panelId,
              lineKey: line.audioKey,
            })
          }
        />
        {showTranslation && line.en && <p className="fr-line-en vp-en">{line.en}</p>}
      </>
    );
  };

  const balloonClass = (kind: Entry['kind']) =>
    kind === 'caption' ? 'vp-caption' : kind === 'you' ? 'vp-balloon vp-balloon--you' : 'vp-balloon';

  const sheetEntries = entries.filter((entry) => overflow.has(entry.key));
  const sheet = sheetEntries.length ? (
    <section
      className="vp-sheet"
      data-sheet={sheetMode}
      aria-label={t.sheet_label}
      style={sheetMode === 'dock' ? { maxHeight: layout?.sheet.maxHeight } : undefined}
    >
      {sheetEntries.map((entry) => (
        <div
          key={entry.key}
          className="vp-sheet__row"
          data-kind={entry.kind}
          data-char={entry.kind !== 'caption' ? entry.line.character || stage.character || undefined : undefined}
          data-shown={lineVisible(entry) ? 'true' : 'false'}
        >
          {entry.kind === 'caption' ? captionBody(entry) : lineBody(entry, lineChars(entry))}
        </div>
      ))}
    </section>
  ) : null;

  const tails = (layout?.placed ?? []).filter((entry) => {
    if (!entry.tail) return false;
    const source = entries.find((candidate) => candidate.key === entry.key);
    return Boolean(source && lineVisible(source));
  });

  const fillFraming = PANEL_STAGE_FILL
    ? ({ framing: 'fill', focus } as Record<string, unknown>)
    : {};

  return (
    <>
      <div
        className="vp-panel"
        ref={panelRef}
        data-vertical-panel={stage.panelId}
        data-reveal={revealModeName(plan)}
        data-laid-out={layout ? 'true' : undefined}
        data-silent={stage.silent ? 'true' : undefined}
        data-art={src ? (drawn ? 'drawn' : 'painted') : 'none'}
        onClick={showAll}
      >
        <div
          className="vp-camera"
          data-push={motion ? 'in' : undefined}
          style={origin ? { transformOrigin: `${origin.x}px ${origin.y}px` } : undefined}
        >
          {src ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              className="vp-plate"
              src={src}
              alt={alt}
              data-pending={!drawn && stage.artPending ? 'true' : undefined}
              data-pan={stage.silent && motion ? 'slow' : undefined}
              style={{ objectPosition: `${focus.x}% ${focus.y}%` }}
            />
          ) : (
            <div className="vp-plate vp-plate--none" aria-hidden="true" />
          )}
          {drawn && castCount > 0 && (
            <div
              className="vp-cast"
              data-cast-count={castCount}
              style={box ? { left: box.x, top: box.y, width: box.w, height: box.h } : undefined}
            >
              <PanelStage
                members={members}
                you={false}
                talking={heard ? { id: heard.speakerId || heard.who, mouth: heardMouth } : null}
                {...fillFraming}
              />
            </div>
          )}
        </div>

        {tails.length > 0 && panel && (
          <svg className="vp-tails" width={panel.w} height={panel.h} viewBox={`0 0 ${panel.w} ${panel.h}`} aria-hidden="true">
            {tails.map((entry) => {
              const tail = entry.tail!;
              const half = 7;
              const points = tail.side === 'down'
                ? `${tail.baseX - half},${tail.baseY - 2} ${tail.baseX + half},${tail.baseY - 2} ${tail.tipX},${tail.tipY}`
                : `${tail.baseX},${tail.baseY - half} ${tail.baseX},${tail.baseY + half} ${tail.tipX},${tail.tipY}`;
              return <polygon key={entry.key} className="vp-tail" data-tail={entry.key} points={points} />;
            })}
          </svg>
        )}

        {entries.map((entry) => {
          const spot = placed.get(entry.key);
          if (!spot) return null;
          return (
            <div
              key={entry.key}
              className={balloonClass(entry.kind)}
              data-entry={entry.key}
              data-kind={entry.kind}
              data-char={entry.kind !== 'caption' ? entry.line.character || stage.character || undefined : undefined}
              data-shown={lineVisible(entry) ? 'true' : 'false'}
              data-speaking={entry.kind !== 'caption' && reveal.speaking === entry.order ? 'true' : undefined}
              style={{ left: spot.x, top: spot.y, width: spot.w }}
            >
              {entry.kind === 'caption' ? captionBody(entry) : lineBody(entry, lineChars(entry))}
            </div>
          );
        })}

        {sheetMode === 'dock' && sheet}

        {/* Every entry at its natural size, invisible, for the layout to measure. */}
        <div className="vp-measure" ref={measureRef} aria-hidden="true">
          {entries.map((entry) => (
            <div
              key={entry.key}
              className={balloonClass(entry.kind)}
              data-measure={entry.key}
              data-kind={entry.kind}
            >
              {entry.kind === 'caption' ? captionBody(entry) : lineBody(entry, null)}
            </div>
          ))}
        </div>
      </div>
      {sheetMode === 'below' && sheet}
      {/* Before the first measure (and on the server) nothing is placed: the lines are a plain list. */}
      {!layout && (
        <div className="vp-fallback">
          {entries.map((entry) => (
            <div key={entry.key} className="vp-sheet__row" data-kind={entry.kind}>
              {entry.kind === 'caption' ? captionBody(entry) : lineBody(entry, null)}
            </div>
          ))}
        </div>
      )}
    </>
  );
}

export default VerticalPanel;
