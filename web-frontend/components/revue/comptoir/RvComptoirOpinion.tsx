/**
 * «Au comptoir» · step 4, «Ton avis» (§3 step 4), then on the same screen its
 * «suite»: Romy «Et toi ? Il me manque une voix pour mon micro-trottoir.», the
 * side (preselected from the gut vote), and the learner's sentence at their band —
 * A1 builds it from tiles («Je suis pour, parce que …»), A2 completes the day's
 * frame (the phrase of the day above it, the word bank as chips that add the
 * word), B1 answers a regular by name. Text or voice from A2 (the mic beside
 * «Donner mon avis»).
 *
 * Then Romy's red pen (the words she changed lit, one short reason each, «Dans
 * le journal · corrigé par Romy»), the regular's answer in their bubble, «Ta
 * réponse» — chips at A1–A2, one free line from B1 (the foot's field) — and their
 * last word. «Voir la page» closes the Papier.
 */

import React, { useEffect, useState } from 'react';

import { Action, IconAction, MicIcon, StopIcon } from '@/components/atelier-v2/ui';
import { textAnswerField } from '@/components/atelier-v2/ui/Choice';
import { useVoiceAnswer } from '@/components/atelier-v2/journey/useVoiceAnswer';
import type { RvStance } from '@/lib/revue-types';

import { fill } from '../revue-copy';
import { RvComposer } from '../RvComposer';
import { RvTranslate } from '../RvThread';
import { COMPTOIR_FR, COMPTOIR_LINES } from './comptoir-copy';
import { SIDE_LABELS_FR, a1Sentence, castName, edited, insertWord, wordDiff } from './comptoir-model';
import { ComptoirBubble, MineLine, RomyLine, type ComptoirStepProps } from './RvComptoirParts';

const SIDES: RvStance[] = ['pour', 'contre', 'nuance'];

export function RvComptoirOpinion(props: ComptoirStepProps) {
  const { view, copy, ccopy, glossLanguage, glosses, voice, pending, readOnly, onAct, onContinue, wordFor, notice, footRef } = props;
  const kit = view.kit;
  const opinion = view.opinion;
  const [side, setSide] = useState<RvStance>(view.vote ?? 'pour');
  const [reason, setReason] = useState<number | null>(null);
  const [text, setText] = useState('');
  const [mode, setMode] = useState<'text' | 'voice'>('text');
  const mic = useVoiceAnswer();
  const micState = mic.state;

  useEffect(() => {
    if (micState.kind === 'transcript') {
      setText(micState.text);
      setMode('voice');
    }
  }, [micState]);

  if (!kit) return null;
  const input = kit.input;
  const reasons = kit.reasons[side] ?? [];
  const frame = kit.frames[side];
  const opponent = kit.opponents[side];
  const opponentName = opponent ? castName(view, opponent) : '';
  const busy = pending !== null;
  const ready = input === 'tiles' ? reason !== null && Boolean(reasons[reason]) : text.trim().length > 0;
  const recording = micState.kind === 'recording';
  const transcribing = micState.kind === 'transcribing';
  const voiceAvailable = typeof navigator === 'undefined' || Boolean(navigator.mediaDevices?.getUserMedia);

  const send = () => {
    if (!ready || busy) return;
    if (input === 'tiles' && reason !== null) void onAct({ act: 'opinion', value: side, reasonIndex: reason }, 'opinion');
    else void onAct({ act: 'opinion', value: side, text: text.trim(), mode }, 'opinion');
  };

  // --- before the opinion ------------------------------------------------------
  let composer: React.ReactNode = null;
  if (!opinion) {
    const sideChips = (
      <div className="ct-side" role="radiogroup" aria-label={ccopy.side_label}>
        {SIDES.map((value) => (
          <button
            key={value}
            type="button"
            role="radio"
            className="ct-side__b"
            lang="fr"
            data-stance={value}
            aria-checked={side === value}
            disabled={readOnly || busy}
            onClick={() => {
              setSide(value);
              setReason(null);
            }}
          >
            {SIDE_LABELS_FR[value]}
          </button>
        ))}
      </div>
    );
    if (input === 'tiles') {
      composer = (
        <>
          {sideChips}
          <p className="ct-label">{ccopy.a1_reason_label}</p>
          <div className="ct-tiles" role="radiogroup" aria-label={ccopy.a1_reason_label}>
            {reasons.map((row, index) => (
              <button
                key={`${side}-${index}`}
                type="button"
                role="radio"
                className="ct-tile"
                aria-checked={reason === index}
                disabled={readOnly || busy}
                onClick={() => setReason(index)}
              >
                <span className="ct-tile__fr" lang="fr">
                  {row.fr}
                </span>
                {row.tr && (
                  <span className="ct-tile__tr" lang={glossLanguage}>
                    {row.tr}
                  </span>
                )}
              </button>
            ))}
          </div>
          <div className="ct-frame" aria-live="polite">
            <p className="ct-frame__k">
              {ccopy.phrase_label} · <span lang="fr">{kit.phrase.fr}</span>
            </p>
            <p className="ct-frame__fr" lang="fr" data-built={reason !== null ? '' : undefined}>
              {a1Sentence(side, reason !== null ? reasons[reason]?.fr ?? null : null)}
            </p>
          </div>
        </>
      );
    } else {
      const field = textAnswerField({
        label: input === 'frame' ? ccopy.reason_label : fill(ccopy.answer_to, { name: opponentName }),
        value: text,
        rows: input === 'frame' ? 2 : 3,
        disabled: readOnly || busy || recording || transcribing,
        placeholder: transcribing ? copy.transcribing : input === 'frame' ? ccopy.reason_placeholder : ccopy.opinion_placeholder,
        onChange: (value) => {
          setText(value);
          if (!value) setMode('text');
        },
      });
      composer = (
        <>
          {sideChips}
          <div className="ct-frame" data-input={input}>
            <p className="ct-frame__k">
              {ccopy.phrase_label} · <span lang="fr">{kit.phrase.fr}</span>
            </p>
            {input === 'frame' && frame && (
              <p className="ct-frame__fr" lang="fr">
                {frame.fr}…
              </p>
            )}
            {field}
          </div>
          {input === 'frame' && kit.bank.length > 0 && (
            <>
              <p className="ct-label">{ccopy.bank_label}</p>
              <div className="ct-bank">
                {kit.bank.map((word) => (
                  <button
                    key={word.fr}
                    type="button"
                    className="ct-bank__b"
                    lang="fr"
                    title={word.tr ?? undefined}
                    disabled={readOnly || busy}
                    onClick={() => setText((current) => insertWord(current, word.fr))}
                  >
                    {word.fr}
                  </button>
                ))}
              </div>
            </>
          )}
        </>
      );
    }
  }

  // --- after the opinion: Romy's pen, the answer, the comeback -------------------
  let suite: React.ReactNode = null;
  if (opinion) {
    const changed = edited(opinion.learnerFr, opinion.editedFr);
    const replier = view.cast.find((member) => member.id === opinion.reply.by) ?? null;
    suite = (
      <>
        <section className="ct-paper" data-ct-anchor="start" aria-label={changed ? COMPTOIR_FR.in_paper_fixed : COMPTOIR_FR.in_paper_read}>
          <p className="ct-paper__k" lang="fr">
            {changed ? COMPTOIR_FR.in_paper_fixed : COMPTOIR_FR.in_paper_read}
          </p>
          <p className="ct-paper__fr" lang="fr">
            {wordDiff(opinion.learnerFr, opinion.editedFr).map((segment, index) =>
              segment.changed ? (
                <mark key={index} className="ct-fix">
                  {segment.text}
                </mark>
              ) : (
                <React.Fragment key={index}>{segment.text}</React.Fragment>
              ),
            )}
          </p>
          {opinion.notes.map((note, index) => (
            <p key={index} className="ct-why">
              <b lang="fr">{note.spanFr}</b> · {note.why}
            </p>
          ))}
          <RvTranslate textFr={opinion.editedFr} glossLanguage={glossLanguage} copy={copy} />
        </section>
        {opinion.reply.line.fr && (
          <ComptoirBubble
            castId={opinion.reply.by}
            name={opinion.reply.nameFr}
            textFr={opinion.reply.line.fr}
            translation={opinion.reply.line.tr}
            stance={replier?.stance ?? null}
            mood="happy"
            glosses={glosses}
            glossLanguage={glossLanguage}
            voice={voice}
            voiceKey={`ct-reply-${opinion.reply.by}`}
            copy={copy}
            ccopy={ccopy}
            onWord={wordFor(opinion.reply.by, opinion.reply.nameFr)}
          />
        )}
        {!opinion.comeback && opinion.comebacks.length > 0 && (
          <>
            <p className="ct-label">{ccopy.your_reply}</p>
            <div className="ct-comebacks" role="group" aria-label={ccopy.your_reply}>
              {opinion.comebacks.map((chip, index) => (
                <button
                  key={index}
                  type="button"
                  className="ct-comeback"
                  disabled={readOnly || busy}
                  onClick={() => void onAct({ act: 'comeback', index }, 'comeback')}
                >
                  <span lang="fr">{chip.fr}</span>
                  {chip.tr && (
                    <span className="ct-comeback__tr" lang={glossLanguage}>
                      {chip.tr}
                    </span>
                  )}
                </button>
              ))}
            </div>
          </>
        )}
        {opinion.comeback && (
          <>
            <MineLine textFr={opinion.comeback.textFr} copy={copy} anchor="nearest" />
            {opinion.comeback.lastWord.fr && (
              <ComptoirBubble
                castId={opinion.reply.by}
                name={opinion.reply.nameFr}
                textFr={opinion.comeback.lastWord.fr}
                translation={opinion.comeback.lastWord.tr}
                mood="happy"
                glosses={glosses}
                glossLanguage={glossLanguage}
                voice={voice}
                voiceKey={`ct-last-${opinion.reply.by}`}
                copy={copy}
                ccopy={ccopy}
                onWord={wordFor(opinion.reply.by, opinion.reply.nameFr)}
                anchor="nearest"
              />
            )}
          </>
        )}
      </>
    );
  }

  // --- the foot ------------------------------------------------------------------
  let foot: React.ReactNode;
  if (!opinion) {
    foot = (
      <>
        {!ready && <p className="ct-foot__hint">{input === 'tiles' ? ccopy.a1_pick_hint : ccopy.write_hint}</p>}
        <div className="ct-foot__row">
          {input !== 'tiles' && voiceAvailable && (
            recording ? (
              <IconAction label={copy.stop} tone="recording" onClick={() => mic.stop()}>
                <StopIcon size={18} />
              </IconAction>
            ) : (
              <IconAction label={copy.speak} tone="action" pending={transcribing} disabled={busy} onClick={() => void mic.start()}>
                <MicIcon size={18} />
              </IconAction>
            )
          )}
          <Action tone="primary" pending={pending === 'opinion'} pendingLabel={ccopy.give_opinion} disabled={!ready || busy} onClick={send}>
            {ccopy.give_opinion}
          </Action>
        </div>
      </>
    );
  } else if (!opinion.comeback && opinion.comebacks.length === 0) {
    // From B1: one free line, no model call.
    foot = (
      <RvComposer
        key="comeback"
        label={ccopy.reply_label}
        placeholder={ccopy.reply_placeholder}
        disabled={busy}
        onSend={(value, how) => void onAct({ act: 'comeback', text: value, mode: how }, 'comeback')}
        copy={copy}
      />
    );
  } else {
    foot = (
      <Action tone="primary" pending={pending === 'close'} pendingLabel={ccopy.see_page} disabled={!opinion.comeback || busy} onClick={onContinue}>
        {ccopy.see_page}
      </Action>
    );
  }

  return (
    <>
      <div className="rv-body ct-body" data-step="opinion" data-input={input}>
        <RomyLine line={COMPTOIR_LINES.opinion_ask} props={props} past={Boolean(opinion)} />
        {opinion && <MineLine textFr={opinion.learnerFr} copy={copy} />}
        {composer}
        {suite}
        {notice}
      </div>
      {!readOnly && (
        <div className="rv-foot ct-foot" ref={footRef}>
          {foot}
        </div>
      )}
    </>
  );
}

export default RvComptoirOpinion;
