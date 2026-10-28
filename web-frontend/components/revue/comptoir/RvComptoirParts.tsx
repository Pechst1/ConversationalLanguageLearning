/**
 * «Au comptoir» · the pieces every screen shares: the head (× and the step dots),
 * a regular's bubble (face, name in their colour, stance tag, French with every
 * word tappable, «Traduire», ▶ in their voice), the learner's own line, the
 * framed picture, Romy's line, and the props each step component receives.
 */

import React from 'react';

import { ArrowLeftIcon, CastPortrait, CrossIcon, IconAction } from '@/components/atelier-v2/ui';
import type { LineVoice } from '@/components/atelier-v2/journey/useLineVoice';
import { resolveMediaUrl } from '@/lib/media-url';
import type { RvComptoirBody, RvComptoirStep, RvComptoirView, RvGloss, RvLanguage, RvSessionView, RvStance } from '@/lib/revue-types';
import type { FaceMood } from '@/lib/onboarding-portraits';

import { fill, type RevueCopy } from '../revue-copy';
import { PICTURE_CREDIT_FR } from '../RvPicture';
import { RvGlossText, RvTranslate, type RvWordEvent } from '../RvThread';
import { COMPTOIR_LINES, lineIn, type ComptoirCopy, type ComptoirLine } from './comptoir-copy';
import { STANCE_TAGS_FR, STEP_LABELS_FR, stepDots } from './comptoir-model';

const ROMY = 'romy_tremblay';

/** What each step component is given by `RvComptoir`. */
export type ComptoirStepProps = {
  session: RvSessionView;
  view: RvComptoirView;
  copy: RevueCopy;
  ccopy: ComptoirCopy;
  glossLanguage: RvLanguage;
  glosses: RvGloss[];
  voice: LineVoice;
  /** The act in flight («vote», «react-<id>», …), or null. */
  pending: string | null;
  readOnly: boolean;
  /** Sends one act; resolves true when it was recorded (no `error_fr`, no failure). */
  onAct: (body: RvComptoirBody, key: string) => Promise<boolean>;
  /** The screen's main button: the next screen. */
  onContinue: () => void;
  /** A word handler for a line said by `speakerId` (null: the publication's own text). */
  wordFor: (speakerId: string | null, speakerName?: string) => (event: RvWordEvent) => void;
  /** Romy's refusal (`error_fr`) or the quiet failure notice, said at the end of the screen. */
  notice: React.ReactNode;
  footRef: React.Ref<HTMLDivElement>;
};

// ---------------------------------------------------------------------------
// The head
// ---------------------------------------------------------------------------

export function RvComptoirHead({
  steps,
  shown,
  closed,
  back,
  onExit,
  copy,
  ccopy,
}: {
  steps: RvComptoirStep[];
  shown: RvComptoirStep;
  closed: boolean;
  back: boolean;
  onExit: () => void;
  copy: RevueCopy;
  ccopy: ComptoirCopy;
}) {
  const dots = stepDots(steps, shown, closed);
  const at = Math.max(0, steps.indexOf(shown));
  return (
    <div className="rv-head ct-head">
      <IconAction label={back ? copy.back_label : copy.exit_label} onClick={onExit}>
        {back ? <ArrowLeftIcon size={18} /> : <CrossIcon size={16} />}
      </IconAction>
      <ol
        className="rv-head__beats ct-head__dots"
        role="progressbar"
        aria-label={ccopy.steps_label}
        aria-valuemin={1}
        aria-valuemax={steps.length}
        aria-valuenow={at + 1}
        aria-valuetext={fill(ccopy.step_value, { n: String(at + 1), total: String(steps.length), name: STEP_LABELS_FR[shown] })}
        data-steps={steps.length}
      >
        {dots.map((dot) => (
          <li key={dot.step} className="av2-progress__segment" data-step={dot.step} data-state={dot.state} />
        ))}
      </ol>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Bubbles
// ---------------------------------------------------------------------------

export function StanceTag({ stance }: { stance: RvStance }) {
  return (
    <span className="ct-st" data-stance={stance} lang="fr">
      {STANCE_TAGS_FR[stance]}
    </span>
  );
}

/** ▶ in the speaker's voice (the device's French voice, one per character), when the device can speak. */
export function ListenChip({ voice, voiceKey, textFr, castId, copy, ccopy }: { voice: LineVoice; voiceKey: string; textFr: string; castId: string; copy: RevueCopy; ccopy: ComptoirCopy }) {
  if (!voice.supported) return null;
  const speaking = voice.speakingKey === voiceKey;
  return (
    <button
      type="button"
      className="rv-chip ct-listen"
      aria-pressed={speaking}
      onClick={() => (speaking ? voice.stop() : voice.speak({ key: voiceKey, text_fr: textFr, character_id: castId }))}
    >
      <span className="rv-lead__play" aria-hidden="true" />
      {speaking ? copy.listen_stop : ccopy.listen}
    </button>
  );
}

export type ComptoirBubbleProps = {
  castId: string;
  name: string;
  textFr: string;
  translation?: string | null;
  stance?: RvStance | null;
  mood?: FaceMood;
  /** Older lines on the same screen: smaller, no tools. */
  past?: boolean;
  glosses: RvGloss[];
  glossLanguage: RvLanguage;
  voice: LineVoice;
  voiceKey: string;
  copy: RevueCopy;
  ccopy: ComptoirCopy;
  onWord?: (event: RvWordEvent) => void;
  children?: React.ReactNode;
  anchor?: 'start' | 'nearest';
};

/** A regular talking: their face, their name in their colour, the side they take, their French. */
export function ComptoirBubble({
  castId,
  name,
  textFr,
  translation = null,
  stance = null,
  mood = 'neutral',
  past = false,
  glosses,
  glossLanguage,
  voice,
  voiceKey,
  copy,
  ccopy,
  onWord,
  children,
  anchor,
}: ComptoirBubbleProps) {
  return (
    <div className="ct-say" data-char={castId} data-past={past ? '' : undefined} data-ct-anchor={anchor}>
      <span className="ct-say__face" aria-hidden="true">
        <CastPortrait characterId={castId} name={name} mood={mood} size={past ? 'xs' : 'sm'} ring />
      </span>
      <div className="ct-bub">
        <p className="ct-bub__nm">
          <span className="ct-bub__name">
            {name}
            <span className="av2-sr"> : </span>
          </span>
          {stance && <StanceTag stance={stance} />}
        </p>
        <p className="ct-bub__fr" lang="fr">
          <RvGlossText text={textFr} glosses={glosses} mode="tap" glossLanguage={glossLanguage} onWord={onWord} speaker={name} />
        </p>
        {!past && (
          <RvTranslate
            textFr={textFr}
            translation={translation}
            glossLanguage={glossLanguage}
            copy={copy}
            before={<ListenChip voice={voice} voiceKey={voiceKey} textFr={textFr} castId={castId} copy={copy} ccopy={ccopy} />}
          />
        )}
        {children}
      </div>
    </div>
  );
}

/** One of Romy's authored client lines, in her bubble (no stance: she asks the questions). */
export function RomyLine({
  line,
  vars,
  extra = null,
  past = false,
  props,
  anchor,
}: {
  line: ComptoirLine | { fr: string; tr: string | null };
  vars?: Record<string, string>;
  /** A server line said after hers in the same bubble (the intox's question). */
  extra?: { fr: string; tr: string | null } | null;
  past?: boolean;
  props: Pick<ComptoirStepProps, 'copy' | 'ccopy' | 'glossLanguage' | 'glosses' | 'voice' | 'wordFor'>;
  anchor?: 'start' | 'nearest';
}) {
  const own = 'en' in line ? lineIn(line, props.glossLanguage, vars) : line;
  const fr = extra ? `${own.fr} ${extra.fr}` : own.fr;
  const tr = extra ? (own.tr && extra.tr ? `${own.tr} ${extra.tr}` : null) : own.tr;
  return (
    <ComptoirBubble
      castId={ROMY}
      name={props.copy.romy}
      textFr={fr}
      translation={tr}
      past={past}
      glosses={props.glosses}
      glossLanguage={props.glossLanguage}
      voice={props.voice}
      voiceKey={`ct-romy-${fr}`}
      copy={props.copy}
      ccopy={props.ccopy}
      onWord={props.wordFor(ROMY, props.copy.romy)}
      anchor={anchor}
    />
  );
}

/** Romy's refusal of an act (the server's `error_fr`), French, said on the same screen. */
export function RomyRefusal({ textFr, props }: { textFr: string; props: Pick<ComptoirStepProps, 'copy' | 'ccopy' | 'glossLanguage' | 'glosses' | 'voice' | 'wordFor'> }) {
  return <RomyLine line={{ fr: textFr, tr: null }} props={props} anchor="nearest" />;
}

/** The learner's own French, on the right with a hairline rule (as in the Papier's thread). */
export function MineLine({ textFr, copy, anchor }: { textFr: string; copy: RevueCopy; anchor?: 'start' | 'nearest' }) {
  return (
    <p className="rv-thread__mine ct-mine" lang="fr" data-ct-anchor={anchor}>
      <span className="av2-sr">{copy.you} : </span>
      {textFr}
    </p>
  );
}

/** The story's picture (or the place's plate), framed, credited when it is the story's own. */
export function ComptoirPicture({ url, credit, band = false }: { url: string | null; credit: boolean; band?: boolean }) {
  const [failed, setFailed] = React.useState(false);
  const src = url ? resolveMediaUrl(url) ?? url : null;
  return (
    <figure className="ct-pic" data-band={band ? '' : undefined} aria-hidden="true">
      {src && !failed && (
        // eslint-disable-next-line @next/next/no-img-element -- a painted print, already sized
        <img className="ct-pic__img" src={src} alt="" decoding="async" onError={() => setFailed(true)} />
      )}
      {credit && (
        <figcaption className="ct-pic__credit" lang="fr">
          {PICTURE_CREDIT_FR}
        </figcaption>
      )}
    </figure>
  );
}

export { COMPTOIR_LINES };
