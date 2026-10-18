/**
 * Les apparitions · the layer the cast walks in on (see lib/cameo.ts).
 *
 * Mounted once in `_app`. It listens for three things:
 *
 *   * `emitCameo(...)` from a screen (a verdict band, a deck's grade, a recap);
 *   * a tap on any drawn face in the app (`svg.cast-rig[data-cast]`, or an acting `.cast-actor`) that is not
 *     itself a button or a link: the face wobbles and answers back;
 *   * a long stillness on an exercise screen (`.ep-top`), once in a while.
 *
 * Every cameo says why it came in a small tag over its bubble («5 de suite», «Nouvel objet :
 * la clé à la cigale»), in the learner's language, so it reads as an answer to something the
 * learner did. A `chapter` cameo holds out the season's new object (components/cast/items).
 *
 * Whoever has a jointed figure (components/cast/vivant) walks in acting: a bravo
 * for a streak, an «oups» to comfort, their signature move to photobomb.
 *
 * Nothing here blocks the learner: the troupe and the bubbles never take a tap,
 * a peeking figure says what it meant when tapped (and leaves on a second tap),
 * and everything leaves on its own.
 * Reduced motion keeps the cameos but swaps every slide and hop for a fade.
 * Réglages › «Apparitions» switches it all off.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import type { CSSProperties } from 'react';

import {
  CAMEO_EVENT,
  INITIAL_CAMEO_STATE,
  cameoGloss,
  cameosEnabled,
  decideCameo,
  readCameoItems,
  readMetCast,
  readSceneCast,
  writeCameoItems,
  writeMetCast,
  writeSceneCast,
} from '@/lib/cameo';
import { seasonItem } from '@/lib/season-items';
import type { Cameo, CameoEvent, CameoFigure, CameoGag, CameoLang, CameoMood, CameoState } from '@/lib/cameo';
import { readLearnerLanguage } from '@/lib/learner-language';

import { CastRig } from './CastRig';
import { PlotItem } from './items/PlotItem';
import type { ExpressionId, GestureId } from './vivant/kit';
import { figureFor } from './vivant/registry';
import { VivantFigure } from './vivant/VivantFigure';

/** Stillness on an exercise before somebody checks on the learner. */
export const IDLE_AFTER_MS = 35_000;

type Poke = { cameo: Cameo; x: number; y: number };

/** The mood a cameo asks for, as one of the jointed figures' faces. */
const FACE: Record<CameoMood, ExpressionId> = { neutre: 'neutre', ravie: 'joie', surprise: 'surprise', fachee: 'fache', emue: 'emu' };

/** What a jointed figure does as it walks in; each of them does it their own way. */
function gestureFor(cameo: Cameo, figure: CameoFigure): GestureId | null {
  switch (cameo.trigger) {
    case 'streak':
    case 'troupe':
    case 'rebound':
      return 'bravo';
    case 'chapter':
      return 'montre';
    case 'photobomb':
      return 'signature';
    case 'comfort':
      return 'oups';
    case 'idle':
      return 'salut';
    case 'finale':
      return figure.mood === 'emue' ? 'signature' : 'salut';
    default:
      return null;
  }
}

/** The jointed figure when the cast member has one (La troupe vivante), else the rig. */
function CameoFace({ cameo, figure, size, crop = 'bust' }: { cameo: Cameo; figure: CameoFigure; size: number; crop?: 'bust' | 'full' }) {
  if (!figureFor(figure.id)) return <CastRig id={figure.id} mood={figure.mood} crop={crop} size={size} label="" />;
  return <VivantFigure id={figure.id} expression={FACE[figure.mood]} gesture={gestureFor(cameo, figure)} crop={crop} size={size} label="" />;
}

function reducedMotion(): boolean {
  return typeof window !== 'undefined' && typeof window.matchMedia === 'function'
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

function lang(): CameoLang {
  const value = readLearnerLanguage();
  return value === 'de' || value === 'fr' ? value : 'en';
}

function GagMark({ gag }: { gag: CameoGag }) {
  // Small props in the cast's own colours; the flash is drawn by the layer.
  if (gag === 'coffee') {
    return (
      <svg className="cameo-gag cameo-gag--coffee" viewBox="0 0 32 32" width="30" height="30" aria-hidden="true" focusable="false">
        <path d="M11 6c-1 2 1 3 0 5M16 5c-1 2 1 3 0 5M21 6c-1 2 1 3 0 5" fill="none" stroke="#a59e8f" strokeWidth="1.6" strokeLinecap="round" />
        <path d="M7 14h18v6a7 7 0 0 1-7 7h-4a7 7 0 0 1-7-7z" fill="#f8f3e8" stroke="#2a231c" strokeWidth="1.8" />
        <path d="M25 16h2a3 3 0 0 1 0 6h-2" fill="none" stroke="#2a231c" strokeWidth="1.8" />
      </svg>
    );
  }
  if (gag === 'note') {
    return (
      <svg className="cameo-gag cameo-gag--note" viewBox="0 0 32 32" width="30" height="30" aria-hidden="true" focusable="false">
        <rect x="6" y="5" width="17" height="22" rx="2" fill="#f8f3e8" stroke="#14285f" strokeWidth="1.8" />
        <path d="M10 11h9M10 15h9M10 19h5" stroke="#14285f" strokeWidth="1.4" strokeLinecap="round" />
        <path d="M27 6l-9 15-2 4 4-2 9-15z" fill="#d8321a" stroke="#14110d" strokeWidth="1.2" strokeLinejoin="round" />
      </svg>
    );
  }
  if (gag === 'phone') {
    return (
      <svg className="cameo-gag cameo-gag--phone" viewBox="0 0 32 32" width="30" height="30" aria-hidden="true" focusable="false">
        <rect x="10" y="4" width="12" height="24" rx="3" fill="#14110d" />
        <rect x="12" y="7" width="8" height="16" rx="1" fill="#f3c318" />
        <path d="M5 10q-2 6 0 12M27 10q2 6 0 12" fill="none" stroke="#f3c318" strokeWidth="1.8" strokeLinecap="round" />
      </svg>
    );
  }
  if (gag === 'sparkle') {
    return (
      <svg className="cameo-gag cameo-gag--sparkle" viewBox="0 0 32 32" width="30" height="30" aria-hidden="true" focusable="false">
        <path d="M16 2l3 10 10 3-10 3-3 10-3-10-10-3 10-3z" fill="#f3c318" stroke="#14110d" strokeWidth="1.2" strokeLinejoin="round" />
      </svg>
    );
  }
  if (gag === 'tears') {
    return (
      <svg className="cameo-gag cameo-gag--tears" viewBox="0 0 32 32" width="30" height="30" aria-hidden="true" focusable="false">
        <path d="M10 6q-5 8 0 11q5-3 0-11zM22 12q-5 8 0 11q5-3 0-11z" fill="#8fc3e8" stroke="#14285f" strokeWidth="1.2" />
      </svg>
    );
  }
  return null;
}

/** Why they came, in the learner's own language: a small tag over the bubble. */
function Reason({ cameo, language }: { cameo: Cameo; language: CameoLang }) {
  if (!cameo.reason) return null;
  return (
    <span className="cameo-reason" lang={language} data-reason={cameo.trigger}>
      {cameo.reason[language] || cameo.reason.en}
    </span>
  );
}

/** The season's new object, held out beside the figure, with its French name. */
function HeldItem({ cameo, language, glossed }: { cameo: Cameo; language: CameoLang; glossed: boolean }) {
  const item = seasonItem(cameo.item);
  if (!item) return null;
  const gloss = glossed ? cameoGloss(item.name, language) : null;
  return (
    <span className="cameo-item">
      <PlotItem id={item.id} size={76} />
      <span className="cameo-item__name" lang="fr">
        {item.name.fr}
        {gloss && <span className="cameo-item__gloss" lang={language}>{gloss}</span>}
      </span>
    </span>
  );
}

/** The line in French, as the app's own speech bubbles say it; the gloss only once asked for. */
function Bubble({ cameo, language, figureIndex = 0, glossed = false }: { cameo: Cameo; language: CameoLang; figureIndex?: number; glossed?: boolean }) {
  const figure = cameo.figures[figureIndex];
  const gloss = glossed ? cameoGloss(figure.line, language) : null;
  return (
    <span className="cameo-bubble" lang="fr">
      <span className="cameo-bubble__fr">{figure.line.fr}</span>
      {gloss && <span className="cameo-bubble__gloss" lang={language}>{gloss}</span>}
    </span>
  );
}

export function CameoLayer() {
  const director = useRef<CameoState>(INITIAL_CAMEO_STATE);
  // What this device remembers (who was met, today's page, the objects handed over), read once.
  const remembered = useRef(false);
  const [shown, setShown] = useState<Cameo | null>(null);
  const [leaving, setLeaving] = useState(false);
  const [flash, setFlash] = useState(0);
  const [poke, setPoke] = useState<Poke | null>(null);
  const [language, setLanguage] = useState<CameoLang>('en');
  // A tap on the peeking figure asks what they said: the gloss shows and they stay a little longer.
  const [glossed, setGlossed] = useState(false);
  const lastActivity = useRef(Date.now());
  const timers = useRef<number[]>([]);
  const leaveTimer = useRef<number | null>(null);
  const soloRef = useRef<Cameo | null>(null);
  soloRef.current = shown && shown.kind !== 'troupe' && !leaving ? shown : null;

  const later = useCallback((fn: () => void, ms: number) => {
    timers.current.push(window.setTimeout(fn, ms));
  }, []);

  const dismiss = useCallback(() => {
    setLeaving(true);
    later(() => {
      setShown(null);
      setLeaving(false);
    }, 420);
  }, [later]);

  const play = useCallback((event: CameoEvent, anchor?: Element | null) => {
    if (!remembered.current) {
      remembered.current = true;
      director.current = { ...director.current, met: readMetCast(), scene: readSceneCast(), items: readCameoItems() };
    }
    if (event.type === 'met' || event.type === 'scene') {
      const before = director.current.met.length;
      const { state } = decideCameo(director.current, event, Date.now());
      director.current = state;
      if (state.met.length !== before) writeMetCast(state.met);
      if (event.type === 'scene') writeSceneCast(state.scene);
      return;
    }
    if (!cameosEnabled()) return;
    const { state, cameo } = decideCameo(director.current, event, Date.now());
    if (state.items.length !== director.current.items.length) writeCameoItems(state.items);
    director.current = state;
    if (!cameo) return;
    setLanguage(lang());
    if (cameo.kind === 'poke') {
      const rect = anchor?.getBoundingClientRect();
      const x = rect ? rect.left + rect.width / 2 : window.innerWidth / 2;
      const y = rect ? rect.top : window.innerHeight / 2;
      setPoke({ cameo, x, y });
      if (anchor && !reducedMotion() && typeof (anchor as HTMLElement).animate === 'function') {
        const angry = cameo.figures[0].mood === 'fachee';
        (anchor as HTMLElement).animate(
          angry
            ? [{ transform: 'translateX(0)' }, { transform: 'translateX(-4px)' }, { transform: 'translateX(4px)' }, { transform: 'translateX(-3px)' }, { transform: 'translateX(0)' }]
            : [{ transform: 'scale(1) rotate(0)' }, { transform: 'scale(1.18, 0.86) rotate(-6deg)' }, { transform: 'scale(0.92, 1.1) rotate(5deg)' }, { transform: 'scale(1) rotate(0)' }],
          { duration: angry ? 360 : 560, easing: 'cubic-bezier(.3,1.6,.5,1)' },
        );
      }
      later(() => setPoke((current) => (current && current.cameo.key === cameo.key ? null : current)), cameo.ttl);
      return;
    }
    setLeaving(false);
    setGlossed(false);
    setShown(cameo);
    if (cameo.gag === 'flash') {
      later(() => setFlash((n) => n + 1), reducedMotion() ? 0 : 520);
    }
    leaveAfter(cameo, cameo.ttl);
  }, [later]); // eslint-disable-line react-hooks/exhaustive-deps

  function leaveAfter(cameo: Cameo, ms: number) {
    if (leaveTimer.current !== null) window.clearTimeout(leaveTimer.current);
    leaveTimer.current = window.setTimeout(() => {
      leaveTimer.current = null;
      setLeaving(true);
      later(() => {
        setShown((current) => (current && current.key === cameo.key ? null : current));
        setLeaving(false);
      }, 420);
    }, ms);
  }

  /** First tap: what did they say? Second tap: off you go. */
  const tapFigure = (cameo: Cameo) => {
    if (glossed) {
      if (leaveTimer.current !== null) window.clearTimeout(leaveTimer.current);
      leaveTimer.current = null;
      dismiss();
      return;
    }
    setGlossed(true);
    leaveAfter(cameo, 3200);
  };

  // Screens announce what happened.
  useEffect(() => {
    const onCameo = (event: Event) => {
      const detail = (event as CustomEvent<CameoEvent>).detail;
      if (detail) play(detail);
    };
    window.addEventListener(CAMEO_EVENT, onCameo);
    return () => window.removeEventListener(CAMEO_EVENT, onCameo);
  }, [play]);

  // Any drawn face can be poked.
  useEffect(() => {
    const onClick = (event: MouseEvent) => {
      lastActivity.current = Date.now();
      const target = event.target as Element | null;
      const face = target?.closest?.('svg.cast-rig[data-cast], .cast-actor[data-cast]');
      if (!face || face.closest('.cameo-layer')) return;
      // A face inside a control belongs to the control's tap.
      if (face.closest('button, a, [role="button"], label')) return;
      const id = face.getAttribute('data-cast');
      if (id) play({ type: 'poke', id }, face);
    };
    const onActivity = () => {
      lastActivity.current = Date.now();
    };
    // The learner reaching for the page comes first: a figure in the way steps off at once.
    const onReach = (event: PointerEvent) => {
      onActivity();
      const target = event.target as Element | null;
      if (!soloRef.current || target?.closest?.('.cameo-layer')) return;
      if (leaveTimer.current !== null) window.clearTimeout(leaveTimer.current);
      leaveTimer.current = null;
      soloRef.current = null;
      dismiss();
    };
    document.addEventListener('click', onClick);
    document.addEventListener('keydown', onActivity);
    document.addEventListener('pointerdown', onReach, true);
    document.addEventListener('scroll', onActivity, { passive: true, capture: true });
    return () => {
      document.removeEventListener('click', onClick);
      document.removeEventListener('keydown', onActivity);
      document.removeEventListener('pointerdown', onReach, true);
      document.removeEventListener('scroll', onActivity, { capture: true } as EventListenerOptions);
    };
  }, [play, dismiss]);

  // Stillness on an exercise.
  useEffect(() => {
    const tick = window.setInterval(() => {
      if (document.visibilityState !== 'visible') return;
      if (Date.now() - lastActivity.current < IDLE_AFTER_MS) return;
      if (!document.querySelector('.ep-top')) return;
      lastActivity.current = Date.now();
      play({ type: 'idle' });
    }, 5000);
    return () => window.clearInterval(tick);
  }, [play]);

  useEffect(() => () => {
    timers.current.forEach((id) => window.clearTimeout(id));
    if (leaveTimer.current !== null) window.clearTimeout(leaveTimer.current);
  }, []);

  return (
    <div className="cameo-layer">
      {flash > 0 && <span key={flash} className="cameo-flash" aria-hidden="true" />}

      {shown && shown.kind === 'solo' && (
        <div
          key={shown.key}
          className="cameo-solo"
          data-edge={shown.edge}
          data-trigger={shown.trigger}
          data-item={shown.item}
          data-leaving={leaving ? 'true' : undefined}
          role="status"
          aria-live="polite"
        >
          {/* The whole figure swings in from behind the screen's edge, which cuts it, never mid-air. */}
          <button
            type="button"
            className="cameo-solo__figure"
            onClick={() => tapFigure(shown)}
            aria-label={shown.figures[0].name}
            aria-expanded={glossed}
          >
            <CameoFace cameo={shown} figure={shown.figures[0]} size={170} crop="full" />
          </button>
          <span className="cameo-solo__talk">
            <Reason cameo={shown} language={language} />
            <Bubble cameo={shown} language={language} glossed={glossed} />
            {shown.item && <HeldItem cameo={shown} language={language} glossed={glossed} />}
            {shown.gag && shown.gag !== 'flash' && <GagMark gag={shown.gag} />}
          </span>
        </div>
      )}

      {shown && shown.kind === 'troupe' && (
        <div
          key={shown.key}
          className="cameo-troupe"
          data-trigger={shown.trigger}
          data-crowd={shown.figures.length > 4 ? 'true' : undefined}
          data-leaving={leaving ? 'true' : undefined}
          role="status"
          aria-live="polite"
        >
          <Reason cameo={shown} language={language} />
          {shown.figures.map((figure, i) => (
            <span key={figure.id} className="cameo-troupe__member" style={{ '--i': i } as CSSProperties}>
              <Bubble cameo={shown} language={language} figureIndex={i} />
              <CameoFace cameo={shown} figure={figure} size={shown.figures.length > 4 ? 70 : 96} />
            </span>
          ))}
        </div>
      )}

      {poke && (
        <span
          key={poke.cameo.key}
          className="cameo-poke"
          style={{ left: Math.max(90, Math.min(window.innerWidth - 90, poke.x)), top: Math.max(56, poke.y) } as CSSProperties}
          role="status"
          aria-live="polite"
        >
          <span className="cameo-poke__face">
            <CastRig id={poke.cameo.figures[0].id} mood={poke.cameo.figures[0].mood} crop="head" size={30} label="" still />
          </span>
          {/* A poke is already a question: the answer comes with its gloss. */}
          <Bubble cameo={poke.cameo} language={language} glossed />
        </span>
      )}
    </div>
  );
}

export default CameoLayer;
