/**
 * Le Montage (grammar pilot, owner's choice of 9 November 2026): a rule's first visit, built in five
 * taps on one sentence about people the learner knows. The script is data (`lib/rule-montage.ts`);
 * this draws it and moves it.
 *
 * «Skip» is always on screen and opens the rule card. A tap during any motion finishes it. Under
 * reduced motion the beats are the same with instant changes, and a still underline replaces the
 * shape that runs along the sentence. Transform and opacity only.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { flushSync } from 'react-dom';

import { CastPortrait } from '@/components/atelier-v2/ui/CastPortrait';
import { EASE_OVER, flyWords, motionIsStill, PRINT_KEYFRAMES, useScene } from '@/lib/motion';
import { parseMarked, pick, RULE_CARD_COPY, type RuleCardData } from '@/lib/rule-card';
import {
  MONTAGE_COPY,
  type MontageBeat,
  type MontageCast,
  type MontageLine,
  type MontageToken,
  type RuleMontageScript,
} from '@/lib/rule-montage';
import type { ControlLanguage } from '@/types/daily-journey';

function MarkedText({ value }: { value: string }) {
  return (
    <>
      {parseMarked(value).map((segment, index) =>
        segment.tone === 'plain' ? (
          <React.Fragment key={index}>{segment.text}</React.Fragment>
        ) : (
          <span key={index} className="rm-mk">{segment.text}</span>
        ),
      )}
    </>
  );
}

type Seen = Map<string, { rect: DOMRect; html: string }>;

export function RuleMontage({
  script,
  card,
  language,
  onDone,
  onSkip,
}: {
  script: RuleMontageScript;
  card: RuleCardData;
  language: ControlLanguage;
  /** «Try it»: the first drill. */
  onDone: () => void;
  /** «Skip»: the rule card. */
  onSkip: () => void;
}) {
  const copy = MONTAGE_COPY[language] ?? MONTAGE_COPY.en;
  const tryIt = (RULE_CARD_COPY[language] ?? RULE_CARD_COPY.en).tryIt;
  const say = (line: MontageLine) => line[language] ?? line.en;

  const rootRef = useRef<HTMLDivElement | null>(null);
  const sentenceRef = useRef<HTMLParagraphElement | null>(null);
  const trayRef = useRef<HTMLDivElement | null>(null);
  const portraitRef = useRef<HTMLSpanElement | null>(null);
  const scene = useScene();
  /** Each playthrough's id: a replay or a skip leaves an older one with nothing to do. */
  const runRef = useRef(0);

  const [tokens, setTokens] = useState<MontageToken[]>(script.start);
  const [subject, setSubject] = useState<MontageCast>(script.subject);
  const [beatIndex, setBeatIndex] = useState(0);
  const [line, setLine] = useState(() => say(script.beats[0].ask));
  const [waiting, setWaiting] = useState(true);
  const [underlined, setUnderlined] = useState<string[]>([]);
  const [ended, setEnded] = useState(false);

  useEffect(() => {
    const root = rootRef.current;
    const skip = () => scene.finish();
    root?.addEventListener('pointerdown', skip, true);
    return () => {
      root?.removeEventListener('pointerdown', skip, true);
      runRef.current += 1;
    };
  }, [scene]);

  const tokenNode = useCallback((key: string) => sentenceRef.current?.querySelector<HTMLElement>(`[data-k="${key}"]`) ?? null, []);

  /** Where every word is now, and how to draw it once it has gone. */
  const remember = (): Seen => {
    const seen: Seen = new Map();
    sentenceRef.current?.querySelectorAll<HTMLElement>('[data-k]').forEach((node) => {
      seen.set(node.dataset.k as string, { rect: node.getBoundingClientRect(), html: node.innerHTML });
    });
    return seen;
  };

  /** Kept words glide to their new place, new ones drop in and gone ones fall away. */
  const settle = (seen: Seen, { dropIn = true }: { dropIn?: boolean } = {}) => {
    const root = rootRef.current;
    const sentence = sentenceRef.current;
    if (!root || !sentence) return Promise.resolve();
    const moves: Array<Promise<void>> = [];
    const present = new Set<string>();
    const area = root.getBoundingClientRect();
    sentence.querySelectorAll<HTMLElement>('[data-k]').forEach((node) => {
      const key = node.dataset.k as string;
      present.add(key);
      const was = seen.get(key);
      if (was) {
        const now = node.getBoundingClientRect();
        const dx = was.rect.left - now.left;
        const dy = was.rect.top - now.top;
        if (dx || dy) {
          moves.push(scene.animate(node, [{ transform: `translate(${dx}px,${dy}px)` }, { transform: 'none' }], { duration: 280 }));
        }
      } else if (dropIn) {
        moves.push(scene.animate(node, [{ opacity: 0, transform: 'translateY(-0.5em)' }, { opacity: 1, transform: 'none' }], { duration: 240, easing: EASE_OVER }));
      }
    });
    if (!motionIsStill()) {
      seen.forEach((was, key) => {
        if (present.has(key)) return;
        const gone = document.createElement('span');
        gone.className = 'rm-gone';
        gone.setAttribute('aria-hidden', 'true');
        gone.innerHTML = was.html;
        gone.style.left = `${was.rect.left - area.left}px`;
        gone.style.top = `${was.rect.top - area.top}px`;
        root.append(gone);
        void scene
          .animate(gone, [{ opacity: 1, transform: 'none' }, { opacity: 0, transform: 'translateY(0.7em) rotate(-5deg)' }], { duration: 240, fill: 'forwards' })
          .then(() => gone.remove());
      });
    }
    return Promise.all(moves).then(() => undefined);
  };

  /** The subject's shape runs along the words, then prints or stops. */
  const runThread = async (through: string[], blocked: boolean) => {
    const root = rootRef.current;
    const nodes = through.map(tokenNode).filter(Boolean) as HTMLElement[];
    if (!root || !nodes.length) return;
    if (motionIsStill()) {
      flushSync(() => setUnderlined(through));
      return;
    }
    const area = root.getBoundingClientRect();
    const points = nodes.map((node, index) => {
      const rect = node.getBoundingClientRect();
      const last = index === nodes.length - 1;
      return { x: (last && !blocked ? rect.right - 4 : rect.left + rect.width / 2) - area.left - 7, y: rect.bottom - area.top };
    });
    const at = (point: { x: number; y: number }, scale: string | number = 1) => `translate(${point.x}px,${point.y}px) scale(${scale})`;
    const runner = document.createElement('span');
    runner.className = 'rm-runner';
    runner.setAttribute('aria-hidden', 'true');
    root.append(runner);
    await scene.animate(runner, [{ transform: at(points[0], 0) }, { transform: at(points[0]) }], { duration: 140, easing: EASE_OVER, fill: 'forwards' });
    await scene.animate(runner, points.map((point) => ({ transform: at(point) })), { duration: 240 * (points.length - 1) + 120, easing: 'ease-in-out', fill: 'forwards' });
    const last = points[points.length - 1];
    await scene.animate(
      runner,
      blocked
        ? [{ transform: at(last), opacity: 1 }, { transform: at(last, '1.6,0.3'), opacity: 0 }]
        : [{ transform: at(last) }, { transform: at(last, 0) }],
      { duration: 200, fill: 'forwards' },
    );
    runner.remove();
  };

  const printIn = (node: Element | null, delay = 60) => {
    node?.querySelectorAll('.rm-mk').forEach((mark, index) => {
      void scene.animate(mark, PRINT_KEYFRAMES, { duration: 280, delay: delay + index * 70, easing: EASE_OVER });
    });
  };

  /** Keyboard users keep their place: the next thing to tap takes the focus they had. */
  const passFocus = () => {
    const active = document.activeElement;
    if (active && active !== document.body && !rootRef.current?.contains(active)) return;
    rootRef.current?.querySelector<HTMLElement>('.rm-tap')?.focus({ preventScroll: true });
  };

  const openBeat = (index: number, run: number) => {
    const beat = script.beats[index];
    flushSync(() => {
      setBeatIndex(index);
      setLine(say(beat.ask));
      setWaiting(true);
    });
    const tile = trayRef.current?.firstElementChild;
    void scene.animate(tile, [{ opacity: 0, transform: 'scale(0.8)' }, { opacity: 1, transform: 'none' }], { duration: 200, easing: EASE_OVER });
    if (run === runRef.current) passFocus();
  };

  const finishAll = () => {
    flushSync(() => setEnded(true));
    printIn(rootRef.current?.querySelector('.rm-examples') ?? null);
    rootRef.current?.querySelector<HTMLElement>('.rm-end .av2-btn')?.focus({ preventScroll: true });
  };

  const play = async (beat: MontageBeat, from: HTMLElement) => {
    const run = ++runRef.current;
    scene.resume();
    const seen = remember();
    const stale = () => run !== runRef.current;
    const label = from.closest('.rm-tile') ? from : null;
    // The tile's place on screen, kept while it leaves the tray.
    const origin = label?.cloneNode(true) as HTMLElement | undefined;
    if (origin && label) {
      const rect = label.getBoundingClientRect();
      // Out of its styled place, so it carries its size: the word takes off at the size it was written.
      Object.assign(origin.style, { position: 'fixed', left: `${rect.left}px`, top: `${rect.top}px`, width: `${rect.width}px`, height: `${rect.height}px`, visibility: 'hidden', margin: '0', fontSize: getComputedStyle(label).fontSize });
      document.body.append(origin);
    }
    flushSync(() => {
      setWaiting(false);
      setUnderlined([]);
      setTokens(beat.then);
      if (beat.subject) setSubject(beat.subject);
    });
    if (beat.subject) {
      void scene.animate(portraitRef.current, [{ opacity: 0, transform: 'scale(0.86)' }, { opacity: 1, transform: 'none' }], { duration: 240, easing: EASE_OVER });
    }
    const target = beat.flyInto ? tokenNode(beat.flyInto) : null;
    const moving = [settle(seen, { dropIn: !target })];
    if (target && origin) moving.push(flyWords(scene, origin, [target], { center: true }));
    await Promise.all(moving);
    origin?.remove();
    if (stale()) return;
    if (target) printIn(target, 0);
    if (beat.wobble) {
      void scene.animate(tokenNode(beat.wobble), [0, -5, 4, -3, 2, 0].map((x) => ({ transform: `translateX(${x}px)` })), { duration: 340, easing: 'ease-in-out' });
    }
    if (!target) printIn(sentenceRef.current);
    if (beat.thread) {
      await scene.wait(240);
      if (stale()) return;
      await runThread(beat.thread.through, Boolean(beat.thread.blocked));
      if (stale()) return;
      const prints = beat.thread.prints;
      if (prints) {
        flushSync(() => setTokens((current) => current.map((token) => (token.k === prints.k ? { ...token, text: prints.text } : token))));
        printIn(tokenNode(prints.k), 0);
      }
    }
    if (beat.say) setLine(say(beat.say));
    await scene.wait(beat.hold);
    if (stale()) return;
    const index = script.beats.indexOf(beat);
    if (index + 1 < script.beats.length) {
      scene.resume();
      openBeat(index + 1, run);
    } else finishAll();
  };

  const replay = () => {
    runRef.current += 1;
    scene.resume();
    flushSync(() => {
      setEnded(false);
      setUnderlined([]);
      setTokens(script.start);
      setSubject(script.subject);
    });
    openBeat(0, runRef.current);
  };

  const beat = script.beats[beatIndex];
  const tap = beat.tap;

  return (
    <div className="rm" ref={rootRef} data-ended={ended ? 'true' : undefined}>
      {!ended && (
        <button type="button" className="rm-skip" onClick={() => { runRef.current += 1; onSkip(); }}>{copy.skip}</button>
      )}
      {ended ? (
        <div className="rm-end">
          <ul className="rm-examples" lang="fr">
            {script.examples.map((example) => (
              <li key={example.fr}>
                <CastPortrait characterId={example.cast.id} name={example.cast.name} size="sm" ring />
                <span className="rm-example"><MarkedText value={example.fr} /></span>
              </li>
            ))}
          </ul>
          <p className="rm-rule">{pick(card.rule, language)}</p>
          <button type="button" className="av2-btn av2-btn--primary" onClick={onDone}>{tryIt}</button>
          <button type="button" className="rm-again" onClick={replay}>{copy.replay}</button>
        </div>
      ) : (
        <>
          <div className="rm-stage">
            <span className="rm-portrait" ref={portraitRef} key={subject.id}>
              <CastPortrait characterId={subject.id} name={subject.name} size="lg" />
            </span>
            <p className="rm-sentence" ref={sentenceRef} lang="fr">
              {tokens.map((token, index) => {
                const tappable = waiting && tap.kind === 'token' && tap.k === token.k;
                const className = `rm-w${token.off ? ' rm-off' : ''}${underlined.includes(token.k) ? ' rm-under' : ''}${tappable ? ' rm-tap' : ''}`;
                const inner = token.gap ? <span className="rm-gap" /> : <MarkedText value={token.text} />;
                return (
                  <React.Fragment key={token.k}>
                    {tappable ? (
                      <button type="button" className={className} data-k={token.k} onClick={(event) => void play(beat, event.currentTarget)}>{inner}</button>
                    ) : (
                      <span className={className} data-k={token.k}>{inner}</span>
                    )}
                    {index < tokens.length - 1 && !token.tight ? ' ' : null}
                  </React.Fragment>
                );
              })}
            </p>
            <p className="rm-line" aria-live="polite">{line}</p>
          </div>
          <div className="rm-tray" ref={trayRef}>
            {waiting && tap.kind === 'tile' && (
              <button type="button" className="av2-tile rm-tile rm-tap" lang="fr" onClick={(event) => void play(beat, event.currentTarget)}>{tap.label}</button>
            )}
            {waiting && tap.kind === 'cast' && (
              <button type="button" className="av2-tile rm-tile rm-cast rm-tap" onClick={(event) => void play(beat, event.currentTarget)}>
                <CastPortrait characterId={tap.cast.id} name={tap.cast.name} size="xs" />
                <span>{tap.cast.name}</span>
              </button>
            )}
          </div>
        </>
      )}
    </div>
  );
}

export default RuleMontage;
