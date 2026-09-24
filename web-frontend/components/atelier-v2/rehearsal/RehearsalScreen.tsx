/**
 * WP-31 «Répétition» — the screen.
 *
 * One state machine (`rehearsal-state.ts`) over one envelope, on the av2 design
 * system: `.av2` tokens, pill sentence-case actions, dark-capable by
 * inheritance, one primary action per state. WP-82: the chrome is read from
 * `rehearsal-copy.ts` in the chrome language (`useChromeLanguage`) — the
 * learner's up to A2, French from B1; the scene and the learner's sentences
 * stay French.
 *
 * The honesty rules the design brief and the backend share, which this file
 * must not break:
 *
 *  1. **«Non préparée» is said in as many words.** When the provider did not
 *     answer there is no scene, and the screen shows the declaration the learner
 *     wrote plus a retry — never an invented scene with their real situation
 *     in it.
 *  2. **Help is a request.** The useful phrases are behind a quiet action, and
 *     the screen says, before the learner asks, that asking is recorded. The
 *     server books it as assistance; the learner is not surprised by that.
 *  3. **The debrief is the point.** The rehearsal result is one modest line; the
 *     screen that matters is «Comment ça s'est passé ?», and its three answers
 *     are equally sized because "pas encore" is information, not a failure.
 *
 * WP-45 redraws it on `docs/design-reference/nouvelles-pages-2026-09-15/`
 * `Repetition.dc.html`: every state is a body plus a screen foot, so the one
 * primary action is the last thing in the flow and sits above the phone tab bar
 * rather than under it (WP-39's CTA finding). The DOM order is pinned by
 * `rehearsal.test.js`.
 */

import React from 'react';

import { Action, ArrowRightIcon, Notice, ScreenFoot, Skeleton, StepProgress, Surface, textAnswerField } from '@/components/atelier-v2/ui';
import { useChromeLanguage } from '@/lib/learner-language';
import type { RehearsalEnvelope, RehearsalView } from '@/services/api';
import type { ControlLanguage } from '@/types/daily-journey';

import { fill, rehearsalCopy, type RehearsalCopy } from './rehearsal-copy';
import {
  capSentence,
  debriefChoices,
  eventDateSentence,
  nextSlotSentence,
  phaseFor,
  resultSentence,
  turnsRemaining,
  type DebriefOutcome,
  type RehearsalPhase,
} from './rehearsal-state';

export type RehearsalScreenProps = {
  envelope: RehearsalEnvelope | null;
  loading?: boolean;
  error?: string | null;
  pending?: boolean;
  failure?: string | null;
  onDeclare: (declaration: string) => void;
  onPrepare: (rehearsalId: string) => void;
  onRevealPhrases: (rehearsalId: string) => void;
  onSendTurn: (rehearsalId: string, text: string, turnIndex: number) => void;
  onDebrief: (rehearsalId: string, outcome: DebriefOutcome, freeLine: string) => void;
  onAbandon: (rehearsalId: string) => void;
  onLeave: () => void;
};

/** The screen's scaffold, on Repetition.dc.html and the canvas note
 *  «note-pied»: a body that carries the reading and a foot that carries the
 *  actions. The foot is the *last thing in the flow*, a sibling after the body
 *  — not a bar floating over the tab bar — so at 390x844 the primary action
 *  sits above the four tabs instead of under them (WP-39's CTA finding).
 *
 *  The foot is the shared `ScreenFoot` (WP-43); the
 *  class it wraps, `.av2-screen__foot`, is already the one that component
 *  carries. */
function Frame({ children, foot }: { children: React.ReactNode; foot?: React.ReactNode }) {
  return (
    <>
      <div className="av2-screen__body rp-body">{children}</div>
      {foot ? <ScreenFoot className="rp-foot">{foot}</ScreenFoot> : null}
    </>
  );
}

type Chrome = { language: ControlLanguage; copy: RehearsalCopy };

function Transcript({ rehearsal, copy }: { rehearsal: RehearsalView; copy: RehearsalCopy }) {
  const opening = rehearsal.scene?.opening_line_fr ?? '';
  return (
    <ol className="rp-transcript">
      {opening && (
        <li className="rp-transcript__row rp-transcript__row--them">
          <span className="av2-label">{rehearsal.brief.counterpart}</span>
          <p lang="fr">{opening}</p>
        </li>
      )}
      {rehearsal.turns.map((turn) => (
        <React.Fragment key={turn.index}>
          <li className="rp-transcript__row rp-transcript__row--you">
            <span className="av2-label">{copy.you}</span>
            <p lang="fr">{turn.learner_text}</p>
          </li>
          {turn.reply_fr && (
            <li className="rp-transcript__row rp-transcript__row--them">
              <span className="av2-label">{rehearsal.brief.counterpart}</span>
              <p lang="fr">{turn.reply_fr}</p>
            </li>
          )}
          {turn.correction && (
            <li className="rp-transcript__row rp-transcript__row--fix">
              <p lang="fr">
                <s>{turn.correction.span_fr}</s> → <strong>{turn.correction.corrected_fr}</strong>
              </p>
              <p className="rp-fine">{turn.correction.note_native}</p>
            </li>
          )}
        </React.Fragment>
      ))}
    </ol>
  );
}

function SituationCard({ rehearsal, language, copy }: Chrome & { rehearsal: RehearsalView }) {
  const when = eventDateSentence(rehearsal, language) ?? rehearsal.brief.date_text;
  return (
    <Surface tone="outline">
      <p className="rp-lead" lang="fr">
        {rehearsal.brief.goal_fr || rehearsal.declaration}
      </p>
      <p className="rp-fine">
        {fill(copy.with, { who: rehearsal.brief.counterpart || copy.counterpart_fallback })}
        {rehearsal.brief.register ? ` · ${fill(copy.register_line, { register: rehearsal.brief.register })}` : ''}
        {when ? ` · ${when}` : ''}
      </p>
      {rehearsal.brief.facts.length > 0 && (
        <ul className="rp-facts">
          {rehearsal.brief.facts.map((fact) => (
            <li key={fact} lang="fr">
              {fact}
            </li>
          ))}
        </ul>
      )}
    </Surface>
  );
}

export function RehearsalScreen(props: RehearsalScreenProps) {
  const { envelope, loading, error, pending, failure } = props;
  const phase: RehearsalPhase = phaseFor(envelope, { loading, error });
  const language = useChromeLanguage();
  const copy = rehearsalCopy(language);
  const chrome: Chrome = { language, copy };

  const [declaration, setDeclaration] = React.useState('');
  const [answer, setAnswer] = React.useState('');
  const [freeLine, setFreeLine] = React.useState('');
  const [outcome, setOutcome] = React.useState<DebriefOutcome | null>(null);

  const alert = failure ? (
    <Notice tone="alert" live="alert">
      {failure}
    </Notice>
  ) : null;

  if (phase.kind === 'loading') {
    return (
      <Frame>
        <Skeleton />
        <Skeleton />
      </Frame>
    );
  }

  if (phase.kind === 'load_failed') {
    return (
      <Frame
        foot={
          <Action tone="primary" onClick={props.onLeave}>
            {copy.back_to_atelier}
          </Action>
        }
      >
        <span className="av2-label">{copy.eyebrow}</span>
        <h1 className="av2-headline av2-headline--screen">{copy.unavailable_title}</h1>
        <p className="rp-lead">{phase.message}</p>
      </Frame>
    );
  }

  if (phase.kind === 'disabled') {
    return (
      <Frame
        foot={
          <Action tone="primary" onClick={props.onLeave}>
            {copy.back_to_atelier}
          </Action>
        }
      >
        <span className="av2-label">{copy.eyebrow}</span>
        <h1 className="av2-headline av2-headline--screen">{copy.disabled_title}</h1>
        <p className="rp-lead">{copy.disabled_body}</p>
      </Frame>
    );
  }

  /* ---- declare, or wait for a free slot -------------------------------- */
  if (phase.kind === 'declare' || phase.kind === 'capped') {
    const capped = phase.kind === 'capped';
    return (
      <Frame
        foot={
          <>
            {capped ? (
              <Action tone="primary" onClick={props.onLeave}>
                {copy.back_to_atelier}
              </Action>
            ) : (
              <Action
                tone="primary"
                pending={pending}
                pendingLabel={copy.preparing}
                disabled={!declaration.trim()}
                onClick={() => props.onDeclare(declaration.trim())}
                iconAfter={<ArrowRightIcon size={14} />}
              >
                {copy.prepare}
              </Action>
            )}
            <button type="button" className="av2-btn av2-btn--quiet" onClick={props.onLeave}>
              {copy.later}
            </button>
          </>
        }
      >
        <span className="av2-label">{copy.eyebrow}</span>
        <h1 className="av2-headline av2-headline--screen">{copy.declare_title}</h1>
        <p className="rp-lead">{copy.declare_body}</p>
        {!capped && (
          // The artboard draws this one field taller than the system default —
          // 120px — because what the learner writes here is the whole input to
          // the rehearsal. The control itself is the shared `av2-field`; only
          // its height is page-scoped.
          <div className="rp-declare">
            {textAnswerField({
              label: copy.declare_label,
              value: declaration,
              rows: 4,
              disabled: pending,
              placeholder: copy.declare_placeholder,
              onChange: setDeclaration,
            })}
          </div>
        )}
        <Surface tone="outline">
          <p className="rp-fine">
            {capSentence(envelope!.cap, language)}
            {capped && phase.nextSlotAt ? ` ${nextSlotSentence(phase.nextSlotAt, language) ?? ''}` : ''}
          </p>
        </Surface>
        {phase.previous?.status === 'debriefed' && (
          <Surface tone="outline">
            <p className="rp-fine">
              {fill(copy.previous, { goal: phase.previous.brief.goal_fr || phase.previous.declaration })}
            </p>
          </Surface>
        )}
        {alert}
      </Frame>
    );
  }

  /* ---- the provider did not answer ------------------------------------- */
  if (phase.kind === 'not_prepared') {
    const rehearsal = phase.rehearsal;
    return (
      <Frame
        foot={
          <>
            <Action
              tone="primary"
              pending={pending}
              pendingLabel={copy.retrying}
              onClick={() => props.onPrepare(rehearsal.id)}
            >
              {copy.retry}
            </Action>
            <button
              type="button"
              className="av2-btn av2-btn--quiet"
              onClick={() => props.onAbandon(rehearsal.id)}
            >
              {copy.abandon}
            </button>
          </>
        }
      >
        <span className="av2-label">{copy.eyebrow}</span>
        <h1 className="av2-headline av2-headline--screen">{copy.not_prepared_title}</h1>
        <p className="rp-lead">{copy.not_prepared_body}</p>
        <Surface tone="outline">
          <p className="rp-fine">{copy.kept}</p>
          <p className="rp-lead">{rehearsal.declaration}</p>
        </Surface>
        {alert}
      </Frame>
    );
  }

  /* ---- the rehearsal itself -------------------------------------------- */
  if (phase.kind === 'rehearsing') {
    const rehearsal = phase.rehearsal;
    const scene = rehearsal.scene;
    const total = rehearsal.turns_total || 0;
    const steps = Array.from({ length: total }, (_, index) => ({
      id: `t${index}`,
      state:
        index < rehearsal.turns.length
          ? ('done' as const)
          : index === rehearsal.turns.length
            ? ('active' as const)
            : ('pending' as const),
    }));
    return (
      <Frame
        foot={
          <>
            <Action
              tone="primary"
              pending={pending}
              pendingLabel={copy.sending}
              disabled={!answer.trim()}
              onClick={() => {
                props.onSendTurn(rehearsal.id, answer.trim(), rehearsal.turns.length);
                setAnswer('');
              }}
              iconAfter={<ArrowRightIcon size={14} />}
            >
              {copy.reply}
            </Action>
            <button
              type="button"
              className="av2-btn av2-btn--quiet"
              onClick={() => props.onAbandon(rehearsal.id)}
            >
              {copy.stop}
            </button>
          </>
        }
      >
        <span className="av2-label">{fill(copy.live_eyebrow, { place: scene?.place_fr || copy.place_fallback })}</span>
        <StepProgress
          steps={steps}
          label={copy.progress_label}
          caption={fill(turnsRemaining(rehearsal) > 1 ? copy.turns_many : copy.turns_one, {
            n: turnsRemaining(rehearsal),
          })}
        />
        <h1 className="av2-headline av2-headline--screen" lang="fr">
          {scene?.title_fr || rehearsal.brief.goal_fr}
        </h1>
        <p className="rp-lead" lang="fr">
          {scene?.setup_fr}
        </p>
        <Surface tone="blue">
          <p className="rp-objective">{scene?.objective_native || scene?.objective_fr}</p>
        </Surface>
        <Transcript rehearsal={rehearsal} copy={copy} />
        {textAnswerField({
          label: copy.answer_label,
          value: answer,
          rows: 4,
          disabled: pending,
          placeholder: copy.answer_placeholder,
          onChange: setAnswer,
        })}
        {scene?.phrases_revealed ? (
          <Surface tone="outline">
            <p className="rp-fine">{copy.phrases_title}</p>
            <ul className="rp-phrases">
              {scene.phrases.map((phrase) => (
                <li key={phrase.fr}>
                  <span lang="fr">{phrase.fr}</span>
                  <span className="rp-fine">{phrase.native}</span>
                </li>
              ))}
            </ul>
          </Surface>
        ) : (
          <button
            type="button"
            className="av2-btn av2-btn--quiet"
            onClick={() => props.onRevealPhrases(rehearsal.id)}
          >
            {copy.reveal_phrases}
          </button>
        )}
        {alert}
      </Frame>
    );
  }

  /* ---- rehearsed, the real thing has not happened yet ------------------- */
  if (phase.kind === 'waiting') {
    const rehearsal = phase.rehearsal;
    return (
      <Frame
        foot={
          <Action tone="primary" onClick={props.onLeave}>
            {copy.back_to_atelier}
          </Action>
        }
      >
        <span className="av2-label">{copy.waiting_eyebrow}</span>
        <h1 className="av2-headline av2-headline--screen">{copy.waiting_title}</h1>
        <p className="rp-lead">{resultSentence(rehearsal, language)}</p>
        <SituationCard rehearsal={rehearsal} {...chrome} />
        {rehearsal.result?.ending_summary_fr && (
          <Surface tone="outline">
            <p className="rp-fine" lang="fr">
              {rehearsal.result.ending_summary_fr}
            </p>
          </Surface>
        )}
        <Surface tone="outline">
          <p className="rp-fine">{rehearsal.event_date ? copy.waiting_note_dated : copy.waiting_note}</p>
        </Surface>
        {alert}
      </Frame>
    );
  }

  /* ---- the debrief ------------------------------------------------------ */
  if (phase.kind === 'debrief') {
    const rehearsal = phase.rehearsal;
    return (
      <Frame
        foot={
          <>
            <Action
              tone="primary"
              pending={pending}
              pendingLabel={copy.saving}
              disabled={!outcome}
              onClick={() => outcome && props.onDebrief(rehearsal.id, outcome, freeLine.trim())}
              iconAfter={<ArrowRightIcon size={14} />}
            >
              {copy.save_debrief}
            </Action>
            <button type="button" className="av2-btn av2-btn--quiet" onClick={props.onLeave}>
              {copy.not_now}
            </button>
          </>
        }
      >
        <span className="av2-label">{copy.debrief_eyebrow}</span>
        <h1 className="av2-headline av2-headline--screen">{copy.debrief_title}</h1>
        <SituationCard rehearsal={rehearsal} {...chrome} />
        <div className="rp-choices" role="radiogroup" aria-label={copy.debrief_group}>
          {debriefChoices(language).map((choice) => (
            <button
              key={choice.id}
              type="button"
              role="radio"
              aria-checked={outcome === choice.id}
              className={`rp-choice${outcome === choice.id ? ' rp-choice--on' : ''}`}
              onClick={() => setOutcome(choice.id)}
            >
              <span className="rp-choice__label">{choice.label}</span>
              <span className="rp-fine">{choice.hint}</span>
            </button>
          ))}
        </div>
        {textAnswerField({
          label: copy.free_line_label,
          value: freeLine,
          rows: 3,
          disabled: pending,
          placeholder: 'J’ai appelé et il vient jeudi…',
          onChange: setFreeLine,
        })}
        <p className="rp-fine">{copy.free_line_note}</p>
        {alert}
      </Frame>
    );
  }

  /* ---- debriefed -------------------------------------------------------- */
  const rehearsal = phase.rehearsal;
  const debrief = rehearsal.debrief;
  const done = rehearsal.outcome === 'done';
  return (
    <Frame
      foot={
          <Action tone="primary" onClick={props.onLeave}>
            {copy.back_to_atelier}
          </Action>
      }
    >
      <span className="av2-label">{copy.debriefed_eyebrow}</span>
      <h1 className="av2-headline av2-headline--screen">
        {done ? copy.done_title : copy.noted_title}
      </h1>
      <SituationCard rehearsal={rehearsal} {...chrome} />
      {debrief?.free_line && (
        <Surface tone="outline">
          <p className="rp-lead" lang="fr">
            {debrief.free_line}
          </p>
          {debrief.correction_available ? (
            <>
              {debrief.corrected_fr && debrief.corrected_fr !== debrief.free_line && (
                <p className="rp-lead" lang="fr">
                  <strong>{debrief.corrected_fr}</strong>
                </p>
              )}
              {debrief.note_fr && (
                <p className="rp-fine" lang="fr">
                  {debrief.note_fr}
                </p>
              )}
            </>
          ) : (
            <p className="rp-fine">{copy.uncorrected}</p>
          )}
        </Surface>
      )}
      {alert}
    </Frame>
  );
}

export default RehearsalScreen;
