/**
 * Le Quartier · the screen: the quarter full-bleed, and over it the Feuilleton's own cards.
 *
 * A caption box at the top, a speaker's card at the bottom, the sheet you answer on, a thumb
 * stick when there is somewhere to walk. The engine draws the street; the director (`Stage`)
 * says what the cards show; this component only lays them out and passes your taps back.
 * Around the place you are in sit the things that outlast it: the quarter's memory, your carnet,
 * and the map of the Paris the game has built so far. From the map you can ride to a place the
 * forge has built (`world/sites`): the engine is rebuilt there, a `Visit` directs it instead of the
 * episode's `Stage`, and «Rentrer au quai» brings you home with what you did there remembered.
 * In the app the episode is today's (`day`): the page hands over the journey's story, or a card in
 * its stead, and the end card's lower half (the engine's recap, «Demain»). Without one (the
 * standalone page) the quarter plays its own copy of T1 day a.
 * Nothing here is server-rendered: the page imports it with `ssr: false`.
 */
import React from 'react';

import { WHILE_AWAY } from '@/lib/quartier/agency';
import { Sound } from '@/lib/quartier/audio';
import { figureArt, itemArt } from '@/lib/quartier/cast-art';
import type { ArtSource } from '@/lib/quartier/cast';
import { Course } from '@/lib/quartier/course';
import { Crowd } from '@/lib/quartier/crowd';
import { Quartier } from '@/lib/quartier/engine';
import type { Stats } from '@/lib/quartier/engine';
import { Memory, eligible } from '@/lib/quartier/memory';
import type { Words } from '@/lib/quartier/memory';
import { AMBIANCES } from '@/lib/quartier/palette';
import type { AmbianceId } from '@/lib/quartier/palette';
import type { SiteSpec } from '@/lib/quartier/site';
import { Stage } from '@/lib/quartier/stage';
import type { AnswerUi, Cue, Director, Level, Native, PhoneUi, SpeechUi, StageUi, TalkUi } from '@/lib/quartier/stage';
import { pageOfCopy } from '@/lib/quartier/story';
import type { HelpStep, Story, StoryPage } from '@/lib/quartier/story';
import { Visit } from '@/lib/quartier/visit';
import { placeOf, worldState } from '@/lib/quartier/world';
import { SITE_FILES } from '@/lib/quartier/world/sites';
import type { SeasonItemId } from '@/lib/season-items';

import { Carnet } from './Carnet';
import { QuartierMap } from './QuartierMap';
import { QUARTIER_CSS } from './quartier-styles';

/** A card in place of the episode's title card: the day is on its way, played, or the Feuilleton's. */
export interface DayNote {
  kicker?: string;
  title: string;
  text?: string | null;
  /** under the text: the engine's recap and «Demain», on a day already played */
  body?: React.ReactNode;
  action?: { label: string; run: () => void } | null;
}

/** Today, in the app. */
export interface QuartierDay {
  /** the day's story, once it is known: «Commencer» plays it */
  story: Story | null;
  /** a card instead of the episode's */
  note?: DayNote | null;
  /** the end card's lower half: the engine's recap, «Demain», what comes next */
  end?: React.ReactNode;
  /** the scene has played to its hook, and the engine has the day */
  onPlayed?: () => void;
}

export interface QuartierScreenProps {
  /** today's episode, in the app; left out, the quarter plays its own copy of T1 day a */
  day?: QuartierDay;
  /** the language the translations are in (defaults to the phone's: German, else English) */
  native?: Native;
  level?: Level;
  ambiance?: AmbianceId;
  /** the × in the corner; without it, the corner offers to start over */
  onExit?: () => void;
  /** a frame counter in the corner */
  showStats?: boolean;
  /** start at a place the forge built instead of the quai (`marche_aligre`) */
  startPlace?: string;
  /** the cast in the round (the default), or on `paper` as the cut-out cards */
  cast?: 'round' | 'paper';
  /** the quarter is built and its director ready (for tools that drive it: a play-through, a test) */
  onReady?: (engine: Quartier, director: Director, memory: Memory) => void;
  /** something covers the whole quarter (the rest of the day): the frame and the sound rest */
  hidden?: boolean;
}

const ART: ArtSource = {
  figure: (key, expression, gesture) => figureArt(key, { expression: expression as never, gesture: gesture as never, size: 600 }),
  item: (id) => itemArt(id as SeasonItemId, 512),
};

/** Away this long, and the title card says what happened while you were gone. */
const AWAY_MS = 10 * 60 * 1000;

/** The hand-drawn quarter: the quai de Valmy and Le Mistral. */
const HOME = 'quai_de_valmy';

function phoneNative(): Native {
  if (typeof navigator === 'undefined') return 'en';
  return /^de\b/i.test(navigator.language || '') ? 'de' : 'en';
}

const COPY = {
  en: {
    start: 'Commencer',
    howto: 'Drag to look around. Tap the ground to walk there, or use the stick. Tap a card to go on. You can walk out of a scene, refuse, or talk to anyone when the scene gives you a moment.',
    go: 'Y aller',
    direct: 'Directement',
    send: 'Envoyer',
    placeholder: 'Réponds en français…',
    sayPlaceholder: 'Dis quelque chose…',
    end: 'À suivre…',
    replay: 'Rejouer',
    roam: 'Se promener',
    roamHint: 'Touche le sol pour marcher · touche quelqu’un pour parler',
    silent: 'Touche pour continuer',
    asks: 'te demande',
    choice: 'À toi',
    goOn: 'Continuer',
    leaveScene: 'Partir',
    carnet: 'Ton carnet',
    map: 'La carte',
    away: 'Pendant ton absence',
    tonight: 'Ce soir',
    tomorrow: 'Demain',
    now: 'maintenant',
    close: 'Fermer',
    failed: 'This phone could not open the 3D quarter.',
    leave: 'Back',
    retry: 'Try again',
    home: 'Rentrer',
    goHome: 'Rentrer au quai',
    stay: 'Rester',
    seeYou: 'À bientôt',
    today: 'Aujourd’hui',
    nextTime: 'La prochaine fois',
    back: 'De retour au quai',
    backText: 'The evening goes on at Le Mistral. Walk about and talk to anyone, or play the episode again.',
    visitHowto: 'Tap a stallholder to talk, in French: say bonjour, ask a price, buy by the kilo or by the piece. Tap the ground to walk. «Rentrer» takes you back to the quai.',
    help: { hint: 'Un indice', words: 'Des mots', example: 'Un exemple' } as Record<HelpStep, string>,
    aide: 'Aide',
    again: 'Encore une fois',
    notSent: 'That did not get through. Send it again.',
    yourDay: 'Ta journée',
    dayLoading: 'Your day is on its way…',
  },
  de: {
    start: 'Commencer',
    howto: 'Wischen zum Umsehen. Tippe auf den Boden, um dorthin zu gehen, oder nutze den Stick. Tippe auf eine Karte, um weiterzumachen. Du kannst eine Szene verlassen, ablehnen, oder mit allen reden, wenn die Szene dir einen Moment lässt.',
    go: 'Y aller',
    direct: 'Directement',
    send: 'Envoyer',
    placeholder: 'Réponds en français…',
    sayPlaceholder: 'Dis quelque chose…',
    end: 'À suivre…',
    replay: 'Rejouer',
    roam: 'Se promener',
    roamHint: 'Touche le sol pour marcher · touche quelqu’un pour parler',
    silent: 'Touche pour continuer',
    asks: 'te demande',
    choice: 'À toi',
    goOn: 'Continuer',
    leaveScene: 'Partir',
    carnet: 'Ton carnet',
    map: 'La carte',
    away: 'Pendant ton absence',
    tonight: 'Ce soir',
    tomorrow: 'Demain',
    now: 'maintenant',
    close: 'Fermer',
    failed: 'Dieses Telefon konnte das 3D-Viertel nicht öffnen.',
    leave: 'Zurück',
    retry: 'Erneut versuchen',
    home: 'Rentrer',
    goHome: 'Rentrer au quai',
    stay: 'Rester',
    seeYou: 'À bientôt',
    today: 'Aujourd’hui',
    nextTime: 'La prochaine fois',
    back: 'De retour au quai',
    backText: 'Im Mistral geht der Abend weiter. Geh herum und sprich mit allen, oder spiel die Folge noch einmal.',
    visitHowto: 'Tippe auf jemanden am Stand, um zu reden, auf Französisch: sag bonjour, frag nach dem Preis, kauf nach Kilo oder Stück. Tippe auf den Boden, um zu gehen. «Rentrer» bringt dich zurück an den Quai.',
    help: { hint: 'Un indice', words: 'Des mots', example: 'Un exemple' } as Record<HelpStep, string>,
    aide: 'Aide',
    again: 'Encore une fois',
    notSent: 'Das kam nicht an. Schick es noch einmal.',
    yourDay: 'Ta journée',
    dayLoading: 'Dein Tag kommt gleich…',
  },
};

type Copy = (typeof COPY)['en'];

/** «Épisode 12», or the quarter's name when the page has no number. */
function episodeOf(page: StoryPage | null) {
  return page?.number ? `Épisode ${page.number}` : 'Le Quartier';
}

export function QuartierScreen({ day, native: nativeProp, level = 'a2', ambiance: firstAmbiance = 'nuit', onExit, showStats = false, startPlace, cast, onReady, hidden = false }: QuartierScreenProps) {
  const canvasRef = React.useRef<HTMLCanvasElement>(null);
  const engine = React.useRef<Quartier | null>(null);
  const stage = React.useRef<Director | null>(null);
  const sound = React.useRef<Sound | null>(null);
  const [native] = React.useState<Native>(() => nativeProp ?? phoneNative());
  const [memory] = React.useState(() => new Memory());
  const [loading, setLoading] = React.useState<{ share: number; label: string } | null>({ share: 0, label: 'Les encres' });
  const [failed, setFailed] = React.useState<string | null>(null);
  const [ui, setUi] = React.useState<StageUi | null>(null);
  const [translate, setTranslate] = React.useState(false);
  const [soundOn, setSoundOn] = React.useState(true);
  const [ambiance, setAmbiance] = React.useState<AmbianceId>(firstAmbiance);
  const [stats, setStats] = React.useState<Stats | null>(null);
  const [panel, setPanel] = React.useState<'carnet' | 'map' | null>(null);
  const [awayNotes, setAwayNotes] = React.useState<Words[]>([]);
  // where you are: the quai, or a place the forge built (its site, once loaded)
  const [place, setPlace] = React.useState(() => (startPlace && SITE_FILES[startPlace] ? startPlace : HOME));
  const [site, setSite] = React.useState<SiteSpec | null>(null);
  // the ride you took, on the loading card; back on the quai from somewhere else
  const [ride, setRide] = React.useState<Words | null>(null);
  const [back, setBack] = React.useState(false);
  const copy = COPY[native];
  const here = placeOf(place);
  // the episode: today's in the app, the quarter's own copy on the standalone page
  const [offline] = React.useState(() => pageOfCopy(undefined, { level, native }));
  const page: StoryPage | null = day ? (day.story?.page ?? null) : offline;
  const played = React.useRef(false);
  const onPlayed = React.useRef(day?.onPlayed);
  onPlayed.current = day?.onPlayed;

  // you arrive: how long were you gone, and what happened meanwhile?
  React.useEffect(() => {
    const away = memory.arrive();
    if (Number.isFinite(away) && away > AWAY_MS) {
      setAwayNotes(
        eligible(WHILE_AWAY, { ...memory.state(), ...worldState() })
          .slice(0, 3)
          .map((b) => b.say),
      );
    }
    const touch = window.setInterval(() => memory.touch(), 30000);
    const onHide = () => memory.touch();
    window.addEventListener('pagehide', onHide);
    document.addEventListener('visibilitychange', onHide);
    return () => {
      window.clearInterval(touch);
      window.removeEventListener('pagehide', onHide);
      document.removeEventListener('visibilitychange', onHide);
      memory.touch();
    };
  }, [memory]);

  React.useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;
    let cancelled = false;
    let q: Quartier | null = null;
    let st: Director | null = null;
    let snd: Sound | null = null;
    let unsubscribe: (() => void) | null = null;
    let unbind: (() => void) | null = null;
    let stopTick: (() => void) | null = null;
    let crowd: Crowd | null = null;
    const onResize = () => q?.resize();
    window.addEventListener('resize', onResize);
    (async () => {
      try {
        // a forged place is data, loaded only when you go there
        let spec: SiteSpec | null = null;
        if (place !== HOME) {
          const file = SITE_FILES[place];
          if (!file) throw new Error(`Nothing is built at ${place} yet`);
          spec = await file();
          if (cancelled) return;
        }
        setSite(spec);
        const eq = new Quartier({ canvas, art: ART, ambiance: spec ? spec.ambiance : ambiance, site: spec ?? undefined, cast, onProgress: (share, label) => !cancelled && setLoading({ share, label }) });
        q = eq;
        engine.current = eq;
        const sn = new Sound();
        snd = sn;
        sound.current = sn;
        await eq.load();
        if (cancelled) return;
        const opts = { level, native, onCue: (c: Cue) => sn.cue(c), onSay: (fr: string, heat: number) => sn.announce(fr, heat), memory };
        // a place where the news happens plays the event; a street, its people and their trade
        const director: Director = spec ? (spec.venue ? new Course(eq, opts) : new Visit(eq, opts)) : new Stage(eq, undefined, opts);
        st = director;
        stage.current = director;
        unsubscribe = director.subscribe(setUi);
        await director.prepare();
        if (cancelled) return;
        unbind = eq.bindInput();
        const last = eq.feet.clone();
        let statAt = 0;
        stopTick = eq.onTick((_dt, now) => {
          const moved = eq.feet.distanceTo(last) > 0.004;
          last.copy(eq.feet);
          const a = AMBIANCES[eq.ambiance];
          const neon = eq.parts ? eq.camera.position.distanceTo(eq.parts.neon.center) : 999;
          sn.update({ indoors: eq.indoors, walking: moved, rain: a.rain, night: a.night > 0.5, neon, din: director.din?.() });
          if (showStats && now - statAt > 0.5) {
            statAt = now;
            setStats({ ...eq.stats });
          }
        });
        eq.start();
        setLoading(null);
        onReady?.(eq, director, memory);
        // the street fills while you read the title card; a market more than the quai at night
        crowd = new Crowd(eq, { count: spec ? 24 : 10, spots: spec?.spots, onNear: (key) => director.passerby(key, false) });
        director.setStreet(crowd);
        await crowd.load();
      } catch (e) {
        if (!cancelled) setFailed(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
      window.removeEventListener('resize', onResize);
      unsubscribe?.();
      unbind?.();
      stopTick?.();
      crowd?.dispose();
      st?.dispose();
      snd?.dispose();
      q?.dispose();
      engine.current = null;
      stage.current = null;
    };
    // the quarter is built once a place; level and language changes go through the setters below
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [place]);

  // under a cover the quarter draws nothing and is silent
  React.useEffect(() => {
    const q = engine.current;
    if (!q || loading) return;
    if (hidden) {
      q.pause();
      sound.current?.setEnabled(false);
    } else {
      q.start();
      sound.current?.setEnabled(soundOn);
    }
    // the sound switch is the learner's; this only rests it
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hidden, loading]);

  const startSound = () => {
    const snd = sound.current;
    snd?.start();
    snd?.setEnabled(soundOn);
  };

  const begin = () => {
    const st = stage.current;
    if (day?.story && st instanceof Stage) st.setStory(day.story);
    startSound();
    setAwayNotes([]);
    setBack(false);
    st?.begin();
  };

  /** Back on the quai: the evening goes on, without playing the episode again. */
  const stroll = () => {
    startSound();
    setAwayNotes([]);
    setBack(false);
    stage.current?.roam();
  };

  /** Ride somewhere on the map: the quarter is taken down and the place built in its stead. */
  const travel = (id: string) => {
    if (id === place) return;
    const to = placeOf(id);
    setPanel(null);
    setUi(null);
    setFailed(null);
    setStats(null);
    setSite(null);
    setRide(id === HOME ? null : to?.ride ?? null);
    setBack(id === HOME);
    setLoading({ share: 0, label: 'Les encres' });
    setPlace(id);
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
  const ready = !loading && !failed;

  // once a play reaches its end card, the page hears that the engine has the day
  React.useEffect(() => {
    if (phase === 'scene') played.current = false;
    if (phase !== 'end' || site || played.current) return;
    played.current = true;
    onPlayed.current?.();
  }, [phase, site]);

  const walkable = (phase === 'roam' || Boolean(ui?.goal) || Boolean(ui?.moment)) && !ui?.talk && !ui?.answer && !ui?.aside;
  // a line outside the script (why you leave, welcome back) takes the speaker's card
  const line: SpeechUi | null = ui?.aside ?? (ui?.speech && !ui.silent ? ui.speech : null);
  const st = stage.current;
  // The map takes you anywhere open, even mid-scene: leaving is a choice like any other.
  const canTravel = ready && !ui?.talk;
  const name = here?.name.fr ?? 'Le quai de Valmy';
  // a day the engine has kept is not played twice
  const replayable = st instanceof Stage ? st.replayable : true;

  return (
    <div className={`qz${ui?.silent ? ' qz-letterbox' : ''}`} data-phase={phase} data-beat={ui?.beat ?? undefined} data-place={place}>
      <style dangerouslySetInnerHTML={{ __html: QUARTIER_CSS }} />
      <canvas key={place} ref={canvasRef} className="qz-canvas" aria-label={site ? `${name}, ${site.title.fr.toLowerCase()}` : 'Le quai de Valmy, la nuit, sous la pluie'} />

      {ready ? (
        <>
          <div className="qz-top">
            <button type="button" className="qz-round" aria-label={onExit ? 'Quitter' : 'Recommencer'} onClick={() => (onExit ? onExit() : st?.replay())}>
              {onExit ? <IconClose /> : <IconReplay />}
            </button>
            {ui?.canLeave ? (
              <button type="button" className="qz-leave" onClick={() => st?.leave()}>
                <IconDoor />
                {site ? copy.home : copy.leaveScene}
              </button>
            ) : site ? (
              <div className="qz-title">
                <em>{name}</em>
              </div>
            ) : page ? (
              <div className="qz-title">
                {episodeOf(page)} · <em>{page.title_fr}</em>
              </div>
            ) : (
              <div className="qz-title">
                <em>{name}</em>
              </div>
            )}
            <button type="button" className="qz-round" aria-label={copy.carnet} onClick={() => setPanel('carnet')}>
              <IconCarnet />
            </button>
            {site ? null : (
              <button type="button" className="qz-round" aria-label={ambiance === 'nuit' ? 'Le matin' : 'La nuit'} onClick={toggleAmbiance}>
                {ambiance === 'nuit' ? <IconMoon /> : <IconSun />}
              </button>
            )}
            <button type="button" className="qz-round" aria-label="Le son" aria-pressed={soundOn} onClick={toggleSound}>
              <IconSound on={soundOn} />
            </button>
            <button type="button" className="qz-round" aria-label="Traduction" aria-pressed={translate} onClick={() => setTranslate(!translate)}>
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

      {ui?.moment && !ui.talk && !ui.aside ? (
        <div className="qz-moment" aria-live="polite">
          <p lang="fr">{ui.moment.text}</p>
          {translate ? <small>{ui.moment.native}</small> : null}
          <button type="button" className="qz-primary" onClick={() => st?.goOn()}>
            {copy.goOn}
          </button>
        </div>
      ) : null}

      {ui?.caption ? (
        <button type="button" className="qz-caption" onClick={() => st?.tap()} aria-live="polite">
          {ui.caption.text}
          {translate && ui.caption.native ? <small>{ui.caption.native}</small> : null}
        </button>
      ) : null}

      {ui?.bark && !ui.talk ? (
        <div key={ui.bark.at} className="qz-bark" data-char={ui.bark.char} aria-live="polite">
          <b>{ui.bark.name}</b>
          <span lang="fr">{ui.bark.text}</span>
          {translate && ui.bark.native ? <small>{ui.bark.native}</small> : null}
        </div>
      ) : null}

      {line && !ui?.talk ? (
        <button type="button" className="qz-speech" data-char={line.char} data-aside={ui?.aside ? true : undefined} onClick={() => st?.tap()} aria-live="polite">
          <p className="qz-speaker">
            <i aria-hidden />
            {line.name}
            {line.direction ? <span className="qz-direction">{line.direction}</span> : null}
          </p>
          <p className="qz-line" lang="fr">
            {line.text}
          </p>
          {translate && line.native ? <p className="qz-native">{line.native}</p> : null}
          {ui?.waitingTap || ui?.aside ? <span className="qz-more" aria-hidden /> : null}
        </button>
      ) : null}

      {ui?.silent && ui.waitingTap ? <div className="qz-hint">{copy.silent}</div> : null}

      {ui?.you ? (
        <button type="button" className="qz-you" data-char="toi" data-mend={ui.mend ? true : undefined} onClick={() => st?.tap()}>
          <b>Toi</b>
          <span lang="fr">{ui.you}</span>
          {ui.mend ? (
            <span className="qz-mend">
              <s lang="fr">{ui.mend.span}</s> <span lang="fr">{ui.mend.corrected}</span>
              {ui.mend.note ? <small>{ui.mend.note}</small> : null}
            </span>
          ) : null}
          {ui.mend && ui.waitingTap ? <span className="qz-more" aria-hidden /> : null}
        </button>
      ) : null}

      {ui?.goal && !ui.talk && !ui.aside ? (
        <div className="qz-goal">
          <div className="qz-goal-label">
            {ui.goal.label}
            {translate ? <small>{ui.goal.native}</small> : null}
          </div>
          <div className="qz-goal-actions">
            <button type="button" className="qz-primary" onClick={() => st?.go()}>
              {copy.go}
            </button>
            <button type="button" className="qz-quiet" onClick={() => st?.skipWalk()}>
              {copy.direct}
            </button>
          </div>
        </div>
      ) : null}

      {walkable && ready ? <Stick onMove={(x, y) => engine.current?.setStick(x, y)} /> : null}

      {ui?.answer ? <AnswerSheet key={ui.answer.id} a={ui.answer} copy={copy} onSend={(t) => st?.answer(t)} onHelp={() => st?.askHelp?.()} /> : null}

      {ui?.talk ? <TalkSheet key={ui.talk.who} t={ui.talk} translate={translate} copy={copy} onSay={(t) => st?.talkSay(t)} onClose={() => st?.endTalk()} /> : null}

      {phase === 'roam' && !ui?.talk && !ui?.goal ? <div className="qz-hint">{copy.roamHint}</div> : null}
      {phase === 'roam' && ui?.met ? (
        <div key={ui.met.at} className="qz-met" data-char={ui.met.char}>
          {ui.met.name}
        </div>
      ) : null}

      {ui?.phone ? <PhoneCard key={ui.phone.from} p={ui.phone} translate={translate} copy={copy} onReply={(t) => st?.phoneReply(t)} onClose={() => st?.closePhone()} /> : null}

      {loading || failed ? (
        <div className="qz-cover qz-cover--paper">
          <div style={{ width: '100%', maxWidth: 320 }}>
            <p className="qz-kicker">Le Quartier</p>
            <h1 className="qz-h">{name}</h1>
            {ride && !failed ? (
              <p className="qz-ride" lang="fr">
                {ride.fr}
                {translate ? <small>{ride[native]}</small> : null}
              </p>
            ) : null}
            {failed ? (
              <>
                <p className="qz-cando">
                  {copy.failed} <small style={{ display: 'block', marginTop: 8, color: 'var(--qz-muted)' }}>{failed}</small>
                </p>
                {place !== HOME ? (
                  <button type="button" className="qz-primary" onClick={() => travel(HOME)}>
                    {copy.goHome}
                  </button>
                ) : (
                  <button type="button" className="qz-primary" onClick={() => (onExit ? onExit() : window.location.reload())}>
                    {onExit ? copy.leave : copy.retry}
                  </button>
                )}
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

      {ready && phase === 'title' && site ? (
        <div className="qz-cover qz-cover--day">
          <div className="qz-card">
            <p className="qz-kicker">{name}</p>
            <h1 className="qz-h">{site.title.fr}</h1>
            {here ? <p className="qz-date">{here.why.fr}</p> : null}
            <p className="qz-cando" lang="fr">
              {site.can_do.fr}
              {translate ? <small style={{ display: 'block', marginTop: 6, color: 'var(--qz-muted)' }}>{site.can_do[native]}</small> : null}
            </p>
            <button type="button" className="qz-primary" onClick={begin}>
              {copy.start}
            </button>
            <p className="qz-howto">{copy.visitHowto}</p>
          </div>
        </div>
      ) : null}

      {ready && phase === 'title' && !site && back ? (
        <div className="qz-cover qz-cover--night">
          <div className="qz-card">
            <p className="qz-kicker">{name}</p>
            <h1 className="qz-h">{copy.back}</h1>
            <p className="qz-cando">{copy.backText}</p>
            <button type="button" className="qz-primary" onClick={stroll}>
              {copy.roam}
            </button>
            <div className="qz-card-row">
              {page && (!day || (day.story && !day.note)) ? (
                <button type="button" className="qz-quiet" onClick={begin}>
                  {episodeOf(page)}
                </button>
              ) : null}
              <button type="button" className="qz-quiet" onClick={() => setPanel('map')}>
                {copy.map}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {ready && phase === 'title' && !site && !back && day?.note ? (
        <div className="qz-cover qz-cover--night">
          <div className="qz-card">
            <p className="qz-kicker">{day.note.kicker ?? copy.yourDay}</p>
            <h1 className="qz-h">{day.note.title}</h1>
            {day.note.text ? <p className="qz-cando">{day.note.text}</p> : null}
            {day.note.body}
            {day.note.action ? (
              <button type="button" className="qz-primary" onClick={day.note.action.run}>
                {day.note.action.label}
              </button>
            ) : null}
            <div className="qz-card-row">
              <button type="button" className={day.note.action ? 'qz-quiet' : 'qz-primary'} onClick={stroll}>
                {copy.roam}
              </button>
              <button type="button" className="qz-quiet" onClick={() => setPanel('map')}>
                {copy.map}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {ready && phase === 'title' && !site && !back && !day?.note ? (
        <div className="qz-cover qz-cover--night">
          <div className="qz-card">
            <p className="qz-kicker">{page ? episodeOf(page) : copy.yourDay}</p>
            <h1 className="qz-h">{page ? page.title_fr : name}</h1>
            {page?.story_date_fr ? <p className="qz-date">{page.story_date_fr}</p> : null}
            {awayNotes.length ? (
              <Recap title={copy.away} lines={awayNotes.map((w) => ({ text: w.fr, native: w[native] }))} translate={translate} />
            ) : page?.can_do_native ? (
              <p className="qz-cando">{page.can_do_native}</p>
            ) : null}
            {page ? (
              <button type="button" className="qz-primary" onClick={begin}>
                {copy.start}
              </button>
            ) : (
              <p className="qz-loading-label">{copy.dayLoading}</p>
            )}
            <button type="button" className="qz-quiet" onClick={() => setPanel('map')}>
              {copy.map}
            </button>
            <p className="qz-howto">{copy.howto}</p>
          </div>
        </div>
      ) : null}

      {phase === 'end' && site ? (
        <div className="qz-cover qz-cover--day">
          <div className="qz-card qz-card--end">
            <p className="qz-kicker">{name}</p>
            <h1 className="qz-h">{copy.seeYou}</h1>
            <p className="qz-date">{site.title.fr}</p>
            {ui?.recap?.did.length ? <Recap title={copy.today} lines={ui.recap.did} translate={translate} /> : null}
            {ui?.recap?.tomorrow.length ? <Recap title={copy.nextTime} lines={ui.recap.tomorrow} translate={translate} /> : null}
            <button type="button" className="qz-primary" onClick={() => travel(HOME)}>
              {copy.goHome}
            </button>
            <div className="qz-card-row">
              <button type="button" className="qz-quiet" onClick={() => st?.roam()}>
                {copy.stay}
              </button>
              <button type="button" className="qz-quiet" onClick={() => setPanel('carnet')}>
                {copy.carnet}
              </button>
              <button type="button" className="qz-quiet" onClick={() => setPanel('map')}>
                {copy.map}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {phase === 'end' && !site ? (
        <div className="qz-cover qz-cover--night">
          <div className="qz-card qz-card--end">
            <p className="qz-kicker">{episodeOf(page)}</p>
            <h1 className="qz-h">{copy.end}</h1>
            {page ? <p className="qz-date">{page.title_fr}</p> : null}
            {ui?.recap?.did.length ? <Recap title={copy.tonight} lines={ui.recap.did} translate={translate} /> : null}
            {day?.end ?? (ui?.recap?.tomorrow.length ? <Recap title={copy.tomorrow} lines={ui.recap.tomorrow} translate={translate} /> : null)}
            {day?.end ? null : (
              <button type="button" className="qz-primary" onClick={() => st?.roam()}>
                {copy.roam}
              </button>
            )}
            <div className="qz-card-row">
              {day?.end ? (
                <button type="button" className="qz-quiet" onClick={() => st?.roam()}>
                  {copy.roam}
                </button>
              ) : null}
              <button type="button" className="qz-quiet" onClick={() => setPanel('carnet')}>
                {copy.carnet}
              </button>
              <button type="button" className="qz-quiet" onClick={() => setPanel('map')}>
                {copy.map}
              </button>
              {replayable ? (
                <button type="button" className="qz-quiet" onClick={() => st?.replay()}>
                  {copy.replay}
                </button>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}

      {panel === 'carnet' ? <Carnet memory={memory} native={native} translate={translate} onClose={() => setPanel(null)} onMap={() => setPanel('map')} /> : null}
      {panel === 'map' ? <QuartierMap native={native} translate={translate} here={place} been={memory.places()} onGo={canTravel ? travel : undefined} onClose={() => setPanel(null)} /> : null}

      {showStats && stats ? (
        <div className="qz-stats">
          {`${stats.fps.toFixed(0)} fps  ${stats.frameMs.toFixed(1)} ms\n${stats.calls} calls  ${(stats.triangles / 1000).toFixed(0)}k tris\nscale ${stats.scale.toFixed(2)}`}
        </div>
      ) : null}
    </div>
  );
}

/** A short list on a card: tonight's choices, tomorrow's consequences, what happened while you were away. */
function Recap({ title, lines, translate }: { title: string; lines: Array<{ text: string; native: string | null }>; translate: boolean }) {
  return (
    <section className="qz-recap">
      <h2>{title}</h2>
      <ul>
        {lines.map((l, i) => (
          <li key={i} lang="fr">
            {l.text}
            {translate && l.native ? <small>{l.native}</small> : null}
          </li>
        ))}
      </ul>
    </section>
  );
}

/**
 * What you type, with chips that fill it in. Chips that are help (`onAsk`) wait behind «Aide»;
 * `keep` leaves what you sent in the field, for an answer that may have to be sent again.
 */
function Write({
  placeholder,
  copy,
  onSend,
  chips = [],
  onAsk = false,
  busy = false,
  keep = false,
  text: held,
  onText,
}: {
  placeholder: string;
  copy: Copy;
  onSend: (text: string) => void;
  chips?: string[];
  onAsk?: boolean;
  busy?: boolean;
  keep?: boolean;
  text?: string;
  onText?: (text: string) => void;
}) {
  const [own, setOwn] = React.useState('');
  const [asked, setAsked] = React.useState(false);
  const text = held ?? own;
  const setText = onText ?? setOwn;
  const submit = (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!text.trim() || busy) return;
    onSend(text);
    if (!keep) setText('');
  };
  return (
    <form onSubmit={submit}>
      {chips.length && (!onAsk || asked) ? (
        <div className="qz-chips">
          {chips.map((c) => (
            <button key={c} type="button" className="qz-chip" lang="fr" onClick={() => setText(c)}>
              {c}
            </button>
          ))}
        </div>
      ) : null}
      <div className="qz-write">
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder={placeholder} lang="fr" autoCapitalize="sentences" autoCorrect="off" spellCheck={false} enterKeyHint="send" aria-label={placeholder} />
        {chips.length && onAsk && !asked ? (
          <button type="button" className="qz-quiet qz-aide" onClick={() => setAsked(true)}>
            {copy.aide}
          </button>
        ) : null}
        <button type="submit" className="qz-primary qz-send" disabled={!text.trim() || busy} aria-busy={busy || undefined} aria-label={copy.send}>
          {busy ? (
            <span className="qz-dots" aria-hidden>
              <i />
              <i />
              <i />
            </span>
          ) : (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <path d="M5 12h13M13 6l6 6-6 6" />
            </svg>
          )}
        </button>
      </div>
    </form>
  );
}

/**
 * The answer sheet: the question, an empty field, and help only when asked for, a step at a time
 * (a hint, words to build with, an example), each recorded by the engine before it shows.
 */
function AnswerSheet({ a, copy, onSend, onHelp }: { a: AnswerUi; copy: Copy; onSend: (text: string) => void; onHelp: () => void }) {
  const [text, setText] = React.useState('');
  const hint = a.help.find((h) => h.step === 'hint');
  const words = a.help.find((h) => h.step === 'words');
  const example = a.help.find((h) => h.step === 'example');
  const add = (w: string) => setText((t) => (t.trim() ? `${t.trimEnd()} ${w}` : w));
  return (
    <div className="qz-sheet" data-char={a.char} data-busy={a.busy || undefined}>
      <p className="qz-ask">{a.kind === 'choice' ? copy.choice : `${a.to} ${copy.asks}`}</p>
      {a.task ? <p className="qz-task">{a.task}</p> : null}
      {a.again ? <p className="qz-again">{copy.again}</p> : null}
      {hint?.native || hint?.text ? (
        <p className="qz-help-hint" lang={hint.text ? 'fr' : undefined}>
          {hint.text ?? hint.native}
        </p>
      ) : null}
      {words?.words.length || example?.text ? (
        <div className="qz-chips">
          {words?.words.map((w) => (
            <button key={`w:${w}`} type="button" className="qz-chip qz-chip--word" lang="fr" onClick={() => (a.kind === 'choice' ? setText(w) : add(w))}>
              {w}
            </button>
          ))}
          {example?.text ? (
            <button type="button" className="qz-chip" lang="fr" onClick={() => setText(example.text ?? '')}>
              {example.text}
            </button>
          ) : null}
        </div>
      ) : null}
      {a.failed ? <p className="qz-failed">{copy.notSent}</p> : null}
      <Write placeholder={copy.placeholder} copy={copy} onSend={onSend} busy={a.busy} keep text={text} onText={setText} />
      {a.more ? (
        <button type="button" className="qz-quiet qz-help" disabled={a.busy} onClick={onHelp}>
          {copy.help[a.more]}
        </button>
      ) : null}
    </div>
  );
}

/** Talking to someone: what they said last, what you said, and your next line. */
function TalkSheet({ t, translate, copy, onSay, onClose }: { t: TalkUi; translate: boolean; copy: Copy; onSay: (text: string) => void; onClose: () => void }) {
  return (
    <div className="qz-sheet qz-talk" data-char={t.char}>
      <div className="qz-talk-head">
        <p className="qz-ask">
          <i aria-hidden />
          {t.name}
        </p>
        <button type="button" className="qz-x" aria-label={copy.close} onClick={onClose}>
          <IconClose />
        </button>
      </div>
      {t.you ? (
        <p className="qz-talk-you" lang="fr">
          <b>Toi</b>
          {t.you}
        </p>
      ) : null}
      <div className="qz-talk-lines" aria-live="polite">
        {t.busy ? (
          <div className="qz-talk-line">
            <span className="qz-dots qz-dots--ink" aria-hidden>
              <i />
              <i />
              <i />
            </span>
          </div>
        ) : (
          t.lines.map((l, i) => (
            <div key={`${i}-${l.text}`} className="qz-talk-line">
              {l.direction ? <p className="qz-direction">{l.direction}</p> : null}
              <p className="qz-line" lang="fr">
                {l.text}
              </p>
              {translate && l.native ? <p className="qz-native">{l.native}</p> : null}
            </div>
          ))
        )}
      </div>
      {t.failed ? <p className="qz-failed">{copy.notSent}</p> : null}
      {/* the chips are help until you have said something yourself */}
      <Write placeholder={copy.sayPlaceholder} copy={copy} onSend={onSay} chips={t.chips} onAsk={t.chipsOnAsk && !t.you} busy={t.busy} />
    </div>
  );
}

/** A text on your phone, while you are out of the scene. */
function PhoneCard({ p, translate, copy, onReply, onClose }: { p: PhoneUi; translate: boolean; copy: Copy; onReply: (text: string) => void; onClose: () => void }) {
  return (
    <div className="qz-phone" data-char={p.char} role="dialog" aria-label={p.from}>
      <div className="qz-phone-head">
        <IconPhone />
        <b>{p.from}</b>
        <span>{copy.now}</span>
        <button type="button" className="qz-x" aria-label={copy.close} onClick={onClose}>
          <IconClose />
        </button>
      </div>
      <p className="qz-bubble" lang="fr">
        {p.text}
        {translate && p.native ? <small>{p.native}</small> : null}
      </p>
      {p.sent ? (
        <p className="qz-bubble qz-bubble--me" lang="fr">
          {p.sent}
        </p>
      ) : null}
      {p.reply ? (
        <p className="qz-bubble" lang="fr">
          {p.reply.text}
          {translate && p.reply.native ? <small>{p.reply.native}</small> : null}
        </p>
      ) : null}
      {!p.sent ? <Write placeholder={copy.placeholder} copy={copy} onSend={onReply} chips={p.chips} onAsk={p.chipsOnAsk} /> : null}
    </div>
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

function IconCarnet() {
  return (
    <svg {...svg}>
      <path d="M6 3.5h11a1 1 0 0 1 1 1v15a1 1 0 0 1-1 1H6z" />
      <path d="M6 3.5v17M9.5 8h5M9.5 11.5h5" />
    </svg>
  );
}

function IconDoor() {
  return (
    <svg {...svg}>
      <path d="M13 4H6v16h7" />
      <path d="M11 12h9M17 9l3 3-3 3" />
    </svg>
  );
}

function IconPhone() {
  return (
    <svg {...svg}>
      <rect x="7" y="3" width="10" height="18" rx="2" />
      <path d="M11 18h2" />
    </svg>
  );
}

export default QuartierScreen;
