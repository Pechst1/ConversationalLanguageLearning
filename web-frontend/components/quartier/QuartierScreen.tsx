/**
 * Le Quartier · the screen: the quarter full-bleed, and over it the Feuilleton's own cards.
 *
 * A caption box at the top, a speaker's card at the bottom, the sheet you answer on, a thumb
 * stick when there is somewhere to walk. The engine draws the street; the director (`Stage`)
 * says what the cards show; this component only lays them out and passes your taps back.
 * Nothing here is server-rendered: the page imports it with `ssr: false`.
 */
import React from 'react';

import { Sound } from '@/lib/quartier/audio';
import { figureArt, itemArt } from '@/lib/quartier/cast-art';
import type { ArtSource } from '@/lib/quartier/cast';
import { Quartier } from '@/lib/quartier/engine';
import type { Stats } from '@/lib/quartier/engine';
import { AMBIANCES } from '@/lib/quartier/palette';
import type { AmbianceId } from '@/lib/quartier/palette';
import { Stage, T1A } from '@/lib/quartier/stage';
import type { AnswerUi, Level, Native, StageUi } from '@/lib/quartier/stage';
import type { SeasonItemId } from '@/lib/season-items';

import { QUARTIER_CSS } from './quartier-styles';

export interface QuartierScreenProps {
  /** the language the translations are in (defaults to the phone's: German, else English) */
  native?: Native;
  level?: Level;
  ambiance?: AmbianceId;
  /** the × in the corner; without it, the corner offers to start over */
  onExit?: () => void;
  /** a frame counter in the corner */
  showStats?: boolean;
}

const ART: ArtSource = {
  figure: (key, expression, gesture) => figureArt(key, { expression: expression as never, gesture: gesture as never, size: 600 }),
  item: (id) => itemArt(id as SeasonItemId, 512),
};

function phoneNative(): Native {
  if (typeof navigator === 'undefined') return 'en';
  return /^de\b/i.test(navigator.language || '') ? 'de' : 'en';
}

const COPY = {
  en: {
    start: 'Commencer',
    howto: 'Drag to look around. Tap the ground to walk there, or use the stick. Tap a card to go on.',
    go: 'Y aller',
    direct: 'Directement',
    send: 'Envoyer',
    placeholder: 'Réponds en français…',
    end: 'À suivre…',
    replay: 'Rejouer',
    roam: 'Se promener',
    roamHint: 'Touche le sol pour marcher · glisse pour regarder',
    silent: 'Touche pour continuer',
    asks: 'te demande',
    failed: 'This phone could not open the 3D quarter.',
    leave: 'Back',
    retry: 'Try again',
  },
  de: {
    start: 'Commencer',
    howto: 'Wischen zum Umsehen. Tippe auf den Boden, um dorthin zu gehen, oder nutze den Stick. Tippe auf eine Karte, um weiterzumachen.',
    go: 'Y aller',
    direct: 'Directement',
    send: 'Envoyer',
    placeholder: 'Réponds en français…',
    end: 'À suivre…',
    replay: 'Rejouer',
    roam: 'Se promener',
    roamHint: 'Touche le sol pour marcher · glisse pour regarder',
    silent: 'Touche pour continuer',
    asks: 'te demande',
    failed: 'Dieses Telefon konnte das 3D-Viertel nicht öffnen.',
    leave: 'Zurück',
    retry: 'Erneut versuchen',
  },
};

export function QuartierScreen({ native: nativeProp, level = 'a2', ambiance: firstAmbiance = 'nuit', onExit, showStats = false }: QuartierScreenProps) {
  const canvasRef = React.useRef<HTMLCanvasElement>(null);
  const engine = React.useRef<Quartier | null>(null);
  const stage = React.useRef<Stage | null>(null);
  const sound = React.useRef<Sound | null>(null);
  const [native] = React.useState<Native>(() => nativeProp ?? phoneNative());
  const [loading, setLoading] = React.useState<{ share: number; label: string } | null>({ share: 0, label: 'Les encres' });
  const [failed, setFailed] = React.useState<string | null>(null);
  const [ui, setUi] = React.useState<StageUi | null>(null);
  const [translate, setTranslate] = React.useState(false);
  const [soundOn, setSoundOn] = React.useState(true);
  const [ambiance, setAmbiance] = React.useState<AmbianceId>(firstAmbiance);
  const [stats, setStats] = React.useState<Stats | null>(null);
  const copy = COPY[native];

  React.useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;
    let cancelled = false;
    let q: Quartier;
    try {
      q = new Quartier({ canvas, art: ART, ambiance: firstAmbiance, onProgress: (share, label) => !cancelled && setLoading({ share, label }) });
    } catch (e) {
      setFailed(e instanceof Error ? e.message : String(e));
      return undefined;
    }
    engine.current = q;
    const snd = new Sound();
    sound.current = snd;
    const st = new Stage(q, T1A, { level, native, onCue: (c) => snd.cue(c) });
    stage.current = st;
    const unsubscribe = st.subscribe(setUi);
    let unbind: (() => void) | null = null;
    let stopTick: (() => void) | null = null;
    const onResize = () => q.resize();
    window.addEventListener('resize', onResize);
    (async () => {
      try {
        await q.load();
        if (cancelled) return;
        await st.prepare();
        if (cancelled) return;
        unbind = q.bindInput();
        const last = q.feet.clone();
        let statAt = 0;
        stopTick = q.onTick((_dt, now) => {
          const moved = q.feet.distanceTo(last) > 0.004;
          last.copy(q.feet);
          const a = AMBIANCES[q.ambiance];
          snd.update({ indoors: q.indoors, walking: moved, rain: a.rain, night: a.night > 0.5, neon: q.camera.position.distanceTo(q.parts.neon.center) });
          if (showStats && now - statAt > 0.5) {
            statAt = now;
            setStats({ ...q.stats });
          }
        });
        q.start();
        setLoading(null);
      } catch (e) {
        if (!cancelled) setFailed(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
      window.removeEventListener('resize', onResize);
      unsubscribe();
      unbind?.();
      stopTick?.();
      st.dispose();
      snd.dispose();
      q.dispose();
      engine.current = null;
      stage.current = null;
    };
    // the quarter is built once; level and language changes go through the setters below
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const begin = () => {
    const snd = sound.current;
    snd?.start();
    snd?.setEnabled(soundOn);
    stage.current?.begin();
  };

  const toggleSound = () => {
    const on = !soundOn;
    setSoundOn(on);
    sound.current?.start();
    sound.current?.setEnabled(on);
  };

  const toggleAmbiance = () => {
    const next: AmbianceId = ambiance === 'nuit' ? 'matin' : 'nuit';
    setAmbiance(next);
    engine.current?.setAmbiance(next);
  };

  const phase = ui?.phase ?? 'title';
  const walkable = phase === 'roam' || Boolean(ui?.goal);

  return (
    <div className={`qz${ui?.silent ? ' qz-letterbox' : ''}`} data-phase={phase} data-beat={ui?.beat ?? undefined}>
      <style dangerouslySetInnerHTML={{ __html: QUARTIER_CSS }} />
      <canvas ref={canvasRef} className="qz-canvas" aria-label="Le quai de Valmy, la nuit, sous la pluie" />

      {!loading && !failed ? (
        <>
          <div className="qz-top">
            <button type="button" className="qz-round" aria-label={onExit ? 'Quitter' : 'Recommencer'} onClick={() => (onExit ? onExit() : stage.current?.replay())}>
              {onExit ? <IconClose /> : <IconReplay />}
            </button>
            <div className="qz-title">
              Épisode {T1A.number} · <em>{T1A.title_fr}</em>
            </div>
            <button type="button" className="qz-round" aria-label={ambiance === 'nuit' ? 'Le matin' : 'La nuit'} onClick={toggleAmbiance}>
              {ambiance === 'nuit' ? <IconMoon /> : <IconSun />}
            </button>
            <button type="button" className="qz-round" aria-label="Le son" aria-pressed={soundOn} onClick={toggleSound}>
              <IconSound on={soundOn} />
            </button>
            <button
              type="button"
              className="qz-round"
              aria-label="Traduction"
              aria-pressed={translate}
              onClick={() => setTranslate(!translate)}
            >
              <span className="qz-lang">{native.toUpperCase()}</span>
            </button>
          </div>
          {phase !== 'title' && phase !== 'roam' ? (
            <div className="qz-progress" aria-hidden>
              <i style={{ width: `${Math.round((ui?.progress ?? 0) * 100)}%` }} />
            </div>
          ) : null}
        </>
      ) : null}

      {ui?.caption ? (
        <button type="button" className="qz-caption" onClick={() => stage.current?.tap()} aria-live="polite">
          {ui.caption.text}
          {translate && ui.caption.native ? <small>{ui.caption.native}</small> : null}
        </button>
      ) : null}

      {ui?.speech && !ui.silent ? (
        <button type="button" className="qz-speech" data-char={ui.speech.char} onClick={() => stage.current?.tap()} aria-live="polite">
          <p className="qz-speaker">
            <i aria-hidden />
            {ui.speech.name}
          </p>
          <p className="qz-line" lang="fr">
            {ui.speech.text}
          </p>
          {translate && ui.speech.native ? <p className="qz-native">{ui.speech.native}</p> : null}
          {ui.waitingTap ? <span className="qz-more" aria-hidden /> : null}
        </button>
      ) : null}

      {ui?.silent && ui.waitingTap ? <div className="qz-hint">{copy.silent}</div> : null}

      {ui?.you ? (
        <div className="qz-you" data-char="toi" lang="fr">
          <b>Toi</b>
          {ui.you}
        </div>
      ) : null}

      {ui?.goal ? (
        <div className="qz-goal">
          <div className="qz-goal-label">
            {ui.goal.label}
            {translate ? <small>{ui.goal.native}</small> : null}
          </div>
          <div className="qz-goal-actions">
            <button type="button" className="qz-primary" onClick={() => stage.current?.go()}>
              {copy.go}
            </button>
            <button type="button" className="qz-quiet" onClick={() => stage.current?.skipWalk()}>
              {copy.direct}
            </button>
          </div>
        </div>
      ) : null}

      {walkable && !loading ? <Stick onMove={(x, y) => engine.current?.setStick(x, y)} /> : null}

      {ui?.answer ? <AnswerSheet key={ui.answer.id} a={ui.answer} translate={translate} copy={copy} onSend={(t) => stage.current?.answer(t)} /> : null}

      {phase === 'roam' ? <div className="qz-hint">{copy.roamHint}</div> : null}
      {phase === 'roam' && ui?.met ? (
        <div key={ui.met.at} className="qz-met" data-char={ui.met.char}>
          {ui.met.name}
        </div>
      ) : null}

      {loading || failed ? (
        <div className="qz-cover qz-cover--paper">
          <div style={{ width: '100%', maxWidth: 320 }}>
            <p className="qz-kicker">Le Quartier</p>
            <h1 className="qz-h">Le quai de Valmy</h1>
            {failed ? (
              <>
                <p className="qz-cando">
                  {copy.failed} <small style={{ display: 'block', marginTop: 8, color: 'var(--qz-muted)' }}>{failed}</small>
                </p>
                <button type="button" className="qz-primary" onClick={() => (onExit ? onExit() : window.location.reload())}>
                  {onExit ? copy.leave : copy.retry}
                </button>
              </>
            ) : (
              <>
                <div className="qz-bar">
                  <i style={{ width: `${Math.round((loading?.share ?? 0) * 100)}%` }} />
                </div>
                <p className="qz-loading-label">{loading?.label}…</p>
                {onExit ? (
                  <button type="button" className="qz-quiet" onClick={onExit}>
                    {copy.leave}
                  </button>
                ) : null}
              </>
            )}
          </div>
        </div>
      ) : null}

      {!loading && !failed && phase === 'title' ? (
        <div className="qz-cover qz-cover--night">
          <div className="qz-card">
            <p className="qz-kicker">Épisode {T1A.number}</p>
            <h1 className="qz-h">{T1A.title_fr}</h1>
            <p className="qz-date">{T1A.story_date_fr}</p>
            <p className="qz-cando">{T1A.can_do.fr}</p>
            <button type="button" className="qz-primary" onClick={begin}>
              {copy.start}
            </button>
            <p className="qz-howto">{copy.howto}</p>
          </div>
        </div>
      ) : null}

      {phase === 'end' ? (
        <div className="qz-cover qz-cover--night">
          <div className="qz-card">
            <p className="qz-kicker">Épisode {T1A.number}</p>
            <h1 className="qz-h">{copy.end}</h1>
            <p className="qz-date">{T1A.title_fr}</p>
            <button type="button" className="qz-primary" onClick={() => stage.current?.replay()}>
              {copy.replay}
            </button>
            <button type="button" className="qz-quiet" onClick={() => stage.current?.roam()}>
              {copy.roam}
            </button>
          </div>
        </div>
      ) : null}

      {showStats && stats ? (
        <div className="qz-stats">
          {`${stats.fps.toFixed(0)} fps  ${stats.frameMs.toFixed(1)} ms\n${stats.calls} calls  ${(stats.triangles / 1000).toFixed(0)}k tris\nscale ${stats.scale.toFixed(2)}`}
        </div>
      ) : null}
    </div>
  );
}

function AnswerSheet({ a, translate, copy, onSend }: { a: AnswerUi; translate: boolean; copy: (typeof COPY)['en']; onSend: (text: string) => void }) {
  const [text, setText] = React.useState('');
  const send = (e?: React.FormEvent) => {
    e?.preventDefault();
    if (text.trim()) onSend(text);
  };
  return (
    <form className="qz-sheet" data-char={a.char} onSubmit={send}>
      <p className="qz-ask">
        {a.to} {copy.asks}
      </p>
      <p className="qz-task" lang="fr">
        {a.task}
      </p>
      {translate ? <p className="qz-task-native">{a.taskNative}</p> : null}
      <div className="qz-chips">
        {a.chips.map((c) => (
          <button key={c} type="button" className="qz-chip" lang="fr" onClick={() => setText(c)}>
            {c}
          </button>
        ))}
      </div>
      <div className="qz-write">
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder={copy.placeholder} lang="fr" autoCapitalize="sentences" autoCorrect="off" spellCheck={false} enterKeyHint="send" aria-label={copy.placeholder} />
        <button type="submit" className="qz-primary qz-send" disabled={!text.trim()} aria-label={copy.send}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
            <path d="M5 12h13M13 6l6 6-6 6" />
          </svg>
        </button>
      </div>
    </form>
  );
}

/** A thumb stick: drag the knob; up walks ahead. */
function Stick({ onMove }: { onMove: (x: number, y: number) => void }) {
  const ref = React.useRef<HTMLDivElement>(null);
  const knob = React.useRef<HTMLElement>(null);
  const active = React.useRef<number | null>(null);
  const move = React.useRef(onMove);
  move.current = onMove;
  const set = (x: number, y: number) => {
    move.current(x, y);
    if (knob.current) knob.current.style.transform = `translate(${x * 34}px, ${y * 34}px)`;
  };
  const at = (e: React.PointerEvent) => {
    const r = ref.current?.getBoundingClientRect();
    if (!r) return;
    let x = (e.clientX - (r.left + r.width / 2)) / (r.width / 2);
    let y = (e.clientY - (r.top + r.height / 2)) / (r.height / 2);
    const l = Math.hypot(x, y);
    if (l > 1) {
      x /= l;
      y /= l;
    }
    set(x, y);
  };
  React.useEffect(() => () => move.current(0, 0), []);
  return (
    <div
      ref={ref}
      className="qz-stick"
      onPointerDown={(e) => {
        active.current = e.pointerId;
        e.currentTarget.setPointerCapture(e.pointerId);
        at(e);
      }}
      onPointerMove={(e) => {
        if (active.current === e.pointerId) at(e);
      }}
      onPointerUp={() => {
        active.current = null;
        set(0, 0);
      }}
      onPointerCancel={() => {
        active.current = null;
        set(0, 0);
      }}
      role="presentation"
    >
      <i ref={knob} />
    </div>
  );
}

const svg = { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, 'aria-hidden': true };

function IconClose() {
  return (
    <svg {...svg}>
      <path d="M6 6l12 12M18 6L6 18" />
    </svg>
  );
}

function IconReplay() {
  return (
    <svg {...svg}>
      <path d="M4 12a8 8 0 1 0 2.4-5.7M4 4v4.5h4.5" />
    </svg>
  );
}

function IconMoon() {
  return (
    <svg {...svg}>
      <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" />
    </svg>
  );
}

function IconSun() {
  return (
    <svg {...svg}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </svg>
  );
}

function IconSound({ on }: { on: boolean }) {
  return (
    <svg {...svg}>
      <path d="M4 9h4l5-4v14l-5-4H4z" />
      {on ? <path d="M16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12" /> : <path d="M17 9l5 6M22 9l-5 6" />}
    </svg>
  );
}

export default QuartierScreen;
