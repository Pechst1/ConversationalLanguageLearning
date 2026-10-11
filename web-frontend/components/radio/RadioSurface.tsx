/**
 * WP-122 A · La Radio — the bulletin on screen (presentational: every state is a prop,
 * so node tests render each one; `RadioBulletin` owns the player and the requests).
 *
 * Top to bottom: the back arrow and the kicker · the plate as a band with Romy drawn
 * small (and the guest from their line on, in front while they speak) · the title,
 * the progress hairline and the one play control · **listen first**: nothing of the
 * text until the bulletin ends or «Lire» · then the transcript with tap-glosses (the
 * dictée's sentence masked until it is graded) · the dictée in the journey's own
 * `Dictation` · «C'est entendu».
 *
 * One red press at a time: the play control while the text is hidden, then the
 * dictée's «Vérifier», then «C'est entendu».
 */

import React from 'react';

import { Dictation } from '@/components/atelier-v2/journey/Dictation';
import { dictationReady } from '@/components/atelier-v2/journey/dictation-model';
import type { JourneyCopy } from '@/components/atelier-v2/journey/journey-copy';
import { Action, IconAction } from '@/components/atelier-v2/ui';
import { ArrowLeftIcon } from '@/components/atelier-v2/ui/Shapes';
import { RvGlossText, RvStage, type RvWordEvent } from '@/components/revue';
import type { RadioBulletin, RadioDicteeResult, RadioLanguage } from '@/lib/radio-types';

import { fill, type RadioCopy } from './radio-copy';
import {
  dicteeVerdict,
  lineMasked,
  playLabel,
  progressLabel,
  stageMembers,
  textVisible,
  type PlayerPhase,
} from './radio-model';

export type RadioSurfaceProps = {
  bulletin: RadioBulletin;
  copy: RadioCopy;
  journeyCopy: JourneyCopy;
  language: RadioLanguage;
  phase: PlayerPhase;
  /** The line playing (or last played). */
  index: number;
  /** 0..1, for the hairline. */
  progress: number;
  readRequested: boolean;
  onToggle: () => void;
  onRead: () => void;
  dicteeValue: string;
  onDicteeChange: (value: string) => void;
  onCheck: () => void;
  checking?: boolean;
  dicteeResult: RadioDicteeResult | null;
  onDone: () => void;
  donePending?: boolean;
  onWord?: (event: RvWordEvent) => void;
  onExit: () => void;
};

const firstName = (name: string) => name.split(' ')[0] || name;

export function RadioSurface({
  bulletin,
  copy,
  journeyCopy,
  language,
  phase,
  index,
  progress,
  readRequested,
  onToggle,
  onRead,
  dicteeValue,
  onDicteeChange,
  onCheck,
  checking = false,
  dicteeResult,
  onDone,
  donePending = false,
  onWord,
  onExit,
}: RadioSurfaceProps) {
  const visible = textVisible(phase, readRequested, bulletin.audio);
  const playable = bulletin.audio === 'ready';
  const dicteeLine = bulletin.lines.find((line) => line.index === bulletin.dictee.lineIndex) ?? null;
  const withDictee = playable && dicteeLine !== null;
  const graded = dicteeResult !== null;
  const members = stageMembers(bulletin, index, phase);
  const guestLine = bulletin.lines.find((line) => line.role === 'guest');
  const entering = phase === 'playing' && guestLine && index === guestLine.index ? bulletin.guestId : null;
  const percent = Math.round(progress * 100);
  const week = /W(\d+)$/.exec(bulletin.week)?.[1];

  return (
    <div className="radio" data-phase={phase} data-text={visible ? 'shown' : 'hidden'}>
      <header className="radio__head">
        <IconAction label={copy.back} onClick={onExit}>
          <ArrowLeftIcon size={18} />
        </IconAction>
        <p className="radio__kicker" lang="fr">
          La Radio{week ? ` · semaine ${Number(week)}` : ''}
        </p>
      </header>

      <RvStage plateUrl={bulletin.stage.plateUrl} size="band" cast={members} entering={entering} still={phase !== 'playing'} />

      <section className="radio__deck" aria-label={copy.page_title}>
        <h1 className="radio__title" lang="fr">
          {bulletin.titleFr}
        </h1>
        <div
          className="radio__hairline"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={percent}
          aria-label={progressLabel(progress, copy)}
        >
          <span style={{ width: `${percent}%` }} />
        </div>
        {playable && (
          <div className="radio__controls">
            <Action
              tone={visible ? 'secondary' : 'primary'}
              inline={visible}
              onClick={onToggle}
              data-radio-play=""
              aria-pressed={phase === 'playing' ? true : undefined}
              icon={<span className="radio__glyph" data-state={phase === 'playing' ? 'pause' : 'play'} aria-hidden="true" />}
            >
              {playLabel(phase, copy)}
            </Action>
            {!visible && (
              <button type="button" className="radio__read" onClick={onRead} aria-label={copy.read_aria} lang="fr">
                {copy.read}
              </button>
            )}
          </div>
        )}
        {!visible && <p className="radio__hint">{copy.listen_first}</p>}
        {!playable && (
          <p className="radio__hint" role="status">
            {copy.audio_unavailable}
          </p>
        )}
      </section>

      {visible && (
        <section className="radio__transcript" aria-label={copy.transcript_title}>
          <h2 className="radio__section-title">{copy.transcript_title}</h2>
          <ol className="radio__lines">
            {bulletin.lines.map((line) => {
              const masked = withDictee && lineMasked(line, bulletin.dictee.lineIndex, graded);
              return (
                <li key={line.index} className="radio__line" data-role={line.role} data-speaker={line.speaker} data-now={phase === 'playing' && line.index === index ? '' : undefined}>
                  <span className="radio__speaker">{firstName(line.speakerName)}</span>
                  <p className="radio__text" lang="fr">
                    {masked ? (
                      <span className="radio__mask" data-dictee-mask="">
                        {copy.dictee_masked}
                      </span>
                    ) : (
                      <RvGlossText text={line.textFr} glosses={[]} mode="tap" glossLanguage={language} onWord={onWord} />
                    )}
                  </p>
                </li>
              );
            })}
          </ol>
        </section>
      )}

      {visible && (
        <section className="radio__dictee" aria-label={copy.dictee_title}>
          {withDictee && dicteeLine && (
            <>
              <h2 className="radio__section-title">{copy.dictee_title}</h2>
              <p className="radio__lead">
                {copy.dictee_lead} <span className="radio__count">{fill(copy.dictee_words, { n: bulletin.dictee.words })}</span>
              </p>
              <Dictation
                prompt={{ audio_url: dicteeLine.clipUrl, instruction_native: copy.dictee_lead }}
                copy={journeyCopy}
                value={dicteeValue}
                onChange={onDicteeChange}
                disabled={graded || checking}
                onSubmit={graded ? undefined : onCheck}
                speaker={{ id: dicteeLine.speaker, name: firstName(dicteeLine.speakerName) }}
              />
              {dicteeResult && (
                <div className="radio__verdict" data-outcome={dicteeResult.outcome} role="status">
                  <p>{dicteeVerdict(dicteeResult.outcome, copy)}</p>
                  {dicteeResult.outcome !== 'met' && (
                    <p className="radio__said">
                      {copy.dictee_said} <q lang="fr">{dicteeResult.expectedFr}</q>
                    </p>
                  )}
                </div>
              )}
            </>
          )}
          <div className="radio__foot">
            {withDictee && !graded ? (
              <Action tone="primary" onClick={onCheck} disabled={!dictationReady(dicteeValue)} pending={checking} pendingLabel={copy.checking}>
                {copy.check}
              </Action>
            ) : (
              <Action tone="primary" onClick={onDone} pending={donePending} pendingLabel={copy.done_pending} data-radio-done="">
                <span lang="fr">{copy.done}</span>
              </Action>
            )}
          </div>
        </section>
      )}
    </div>
  );
}

export default RadioSurface;
