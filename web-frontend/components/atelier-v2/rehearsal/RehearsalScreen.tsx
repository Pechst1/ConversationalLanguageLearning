/**
 * WP-31 «Répétition» — the screen.
 *
 * One state machine (`rehearsal-state.ts`) over one envelope, on the av2 design
 * system: `.av2` tokens, pill sentence-case actions, French chrome, dark-capable
 * by inheritance, one primary action per state.
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
 */

import React from 'react';

import {
  Action,
  ArrowRightIcon,
  Notice,
  Skeleton,
  StepProgress,
  Surface,
  textAnswerField,
} from '@/components/atelier-v2/ui';
import type { RehearsalEnvelope, RehearsalView } from '@/services/api';

import {
  DEBRIEF_CHOICES,
  capSentence,
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

function Transcript({ rehearsal }: { rehearsal: RehearsalView }) {
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
            <span className="av2-label">Vous</span>
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

function SituationCard({ rehearsal }: { rehearsal: RehearsalView }) {
  const when = eventDateSentence(rehearsal) ?? rehearsal.brief.date_text;
  return (
    <Surface tone="outline">
      <p className="rp-lead" lang="fr">
        {rehearsal.brief.goal_fr || rehearsal.declaration}
      </p>
      <p className="rp-fine">
        Avec {rehearsal.brief.counterpart || 'votre interlocuteur'}
        {rehearsal.brief.register ? ` · on dit « ${rehearsal.brief.register} »` : ''}
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
      <>
        <Skeleton />
        <Skeleton />
      </>
    );
  }

  if (phase.kind === 'load_failed') {
    return (
      <>
        <span className="av2-label">L’Atelier · Répétition</span>
        <h1 className="av2-headline av2-headline--screen">Page indisponible</h1>
        <p className="rp-lead">{phase.message}</p>
        <div className="rp-spacer" aria-hidden="true" />
        <Action tone="primary" onClick={props.onLeave}>
          Revenir à l’Atelier
        </Action>
      </>
    );
  }

  if (phase.kind === 'disabled') {
    return (
      <>
        <span className="av2-label">L’Atelier · Répétition</span>
        <h1 className="av2-headline av2-headline--screen">Répétitions désactivées</h1>
        <p className="rp-lead">
          Les répétitions ne sont pas ouvertes en ce moment. Rien n’est perdu : vos séances
          continuent normalement.
        </p>
        <div className="rp-spacer" aria-hidden="true" />
        <Action tone="primary" onClick={props.onLeave}>
          Revenir à l’Atelier
        </Action>
      </>
    );
  }

  /* ---- declare, or wait for a free slot -------------------------------- */
  if (phase.kind === 'declare' || phase.kind === 'capped') {
    const capped = phase.kind === 'capped';
    return (
      <>
        <span className="av2-label">L’Atelier · Répétition</span>
        <h1 className="av2-headline av2-headline--screen">Répétez une vraie situation</h1>
        <p className="rp-lead">
          Dites ce qui vous attend, dans vos mots — en français ou dans votre langue. Nous en
          faisons une scène à répéter une fois, puis nous vous demanderons comment ça s’est
          passé pour de vrai.
        </p>
        {!capped &&
          textAnswerField({
            label: 'Ce qui vous attend',
            value: declaration,
            rows: 4,
            disabled: pending,
            placeholder: 'Appeler le propriétaire pour le chauffage, mardi…',
            onChange: setDeclaration,
          })}
        <Surface tone="outline">
          <p className="rp-fine">
            {capSentence(envelope!.cap)}
            {capped && phase.nextSlotAt ? ` ${nextSlotSentence(phase.nextSlotAt) ?? ''}` : ''}
          </p>
        </Surface>
        {phase.previous?.status === 'debriefed' && (
          <Surface tone="outline">
            <p className="rp-fine">
              Dernière répétition : {phase.previous.brief.goal_fr || phase.previous.declaration}.
            </p>
          </Surface>
        )}
        {alert}
        <div className="rp-spacer" aria-hidden="true" />
        {capped ? (
          <Action tone="primary" onClick={props.onLeave}>
            Revenir à l’Atelier
          </Action>
        ) : (
          <Action
            tone="primary"
            pending={pending}
            pendingLabel="Préparation…"
            disabled={!declaration.trim()}
            onClick={() => props.onDeclare(declaration.trim())}
            iconAfter={<ArrowRightIcon size={14} />}
          >
            Préparer la répétition
          </Action>
        )}
        <button type="button" className="av2-btn av2-btn--quiet" onClick={props.onLeave}>
          Plus tard
        </button>
      </>
    );
  }

  /* ---- the provider did not answer ------------------------------------- */
  if (phase.kind === 'not_prepared') {
    const rehearsal = phase.rehearsal;
    return (
      <>
        <span className="av2-label">L’Atelier · Répétition</span>
        <h1 className="av2-headline av2-headline--screen">Répétition non préparée</h1>
        <p className="rp-lead">
          La préparation n’a pas répondu, donc il n’y a pas de scène. Nous préférons vous le dire
          plutôt que d’inventer une conversation autour de votre situation.
        </p>
        <Surface tone="outline">
          <p className="rp-fine">Ce que vous avez écrit est conservé :</p>
          <p className="rp-lead">{rehearsal.declaration}</p>
        </Surface>
        {alert}
        <div className="rp-spacer" aria-hidden="true" />
        <Action
          tone="primary"
          pending={pending}
          pendingLabel="Nouvelle tentative…"
          onClick={() => props.onPrepare(rehearsal.id)}
        >
          Réessayer
        </Action>
        <button
          type="button"
          className="av2-btn av2-btn--quiet"
          onClick={() => props.onAbandon(rehearsal.id)}
        >
          Abandonner cette répétition
        </button>
      </>
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
      <>
        <span className="av2-label">Répétition · {scene?.place_fr || 'votre situation'}</span>
        <StepProgress
          steps={steps}
          label="Progression de la répétition"
          caption={`Encore ${turnsRemaining(rehearsal)} tour${turnsRemaining(rehearsal) > 1 ? 's' : ''}`}
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
        <Transcript rehearsal={rehearsal} />
        {textAnswerField({
          label: 'Votre réponse, en français',
          value: answer,
          rows: 4,
          disabled: pending,
          placeholder: 'Écrivez ici…',
          onChange: setAnswer,
        })}
        {scene?.phrases_revealed ? (
          <Surface tone="outline">
            <p className="rp-fine">Phrases utiles</p>
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
            Voir des phrases utiles (c’est noté comme une aide)
          </button>
        )}
        {alert}
        <div className="rp-spacer" aria-hidden="true" />
        <Action
          tone="primary"
          pending={pending}
          pendingLabel="Envoi…"
          disabled={!answer.trim()}
          onClick={() => {
            props.onSendTurn(rehearsal.id, answer.trim(), rehearsal.turns.length);
            setAnswer('');
          }}
          iconAfter={<ArrowRightIcon size={14} />}
        >
          Répondre
        </Action>
        <button
          type="button"
          className="av2-btn av2-btn--quiet"
          onClick={() => props.onAbandon(rehearsal.id)}
        >
          Arrêter la répétition
        </button>
      </>
    );
  }

  /* ---- rehearsed, the real thing has not happened yet ------------------- */
  if (phase.kind === 'waiting') {
    const rehearsal = phase.rehearsal;
    return (
      <>
        <span className="av2-label">Répétition · terminée</span>
        <h1 className="av2-headline av2-headline--screen">À vous, pour de vrai</h1>
        <p className="rp-lead">{resultSentence(rehearsal)}</p>
        <SituationCard rehearsal={rehearsal} />
        {rehearsal.result?.ending_summary_fr && (
          <Surface tone="outline">
            <p className="rp-fine" lang="fr">
              {rehearsal.result.ending_summary_fr}
            </p>
          </Surface>
        )}
        <Surface tone="outline">
          <p className="rp-fine">
            Nous vous demanderons comment ça s’est passé
            {rehearsal.event_date ? ' le jour venu' : ' quand ce sera fait'}. C’est cette
            réponse-là qui compte, pas la note de la répétition.
          </p>
        </Surface>
        {alert}
        <div className="rp-spacer" aria-hidden="true" />
        <Action tone="primary" onClick={props.onLeave}>
          Revenir à l’Atelier
        </Action>
      </>
    );
  }

  /* ---- the debrief ------------------------------------------------------ */
  if (phase.kind === 'debrief') {
    const rehearsal = phase.rehearsal;
    return (
      <>
        <span className="av2-label">Répétition · bilan</span>
        <h1 className="av2-headline av2-headline--screen">Comment ça s’est passé ?</h1>
        <SituationCard rehearsal={rehearsal} />
        <div className="rp-choices" role="radiogroup" aria-label="Comment ça s’est passé">
          {DEBRIEF_CHOICES.map((choice) => (
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
          label: 'Une phrase en français sur ce qui s’est passé',
          value: freeLine,
          rows: 3,
          disabled: pending,
          placeholder: 'J’ai appelé et il vient jeudi…',
          onChange: setFreeLine,
        })}
        <p className="rp-fine">Cette phrase-là sera corrigée. Le reste ne l’est pas.</p>
        {alert}
        <div className="rp-spacer" aria-hidden="true" />
        <Action
          tone="primary"
          pending={pending}
          pendingLabel="Enregistrement…"
          disabled={!outcome}
          onClick={() => outcome && props.onDebrief(rehearsal.id, outcome, freeLine.trim())}
          iconAfter={<ArrowRightIcon size={14} />}
        >
          Enregistrer le bilan
        </Action>
        <button type="button" className="av2-btn av2-btn--quiet" onClick={props.onLeave}>
          Pas maintenant
        </button>
      </>
    );
  }

  /* ---- debriefed -------------------------------------------------------- */
  const rehearsal = phase.rehearsal;
  const debrief = rehearsal.debrief;
  const done = rehearsal.outcome === 'done';
  return (
    <>
      <span className="av2-label">Répétition · bilan enregistré</span>
      <h1 className="av2-headline av2-headline--screen">
        {done ? 'Vous l’avez fait' : 'C’est noté'}
      </h1>
      <SituationCard rehearsal={rehearsal} />
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
            <p className="rp-fine">
              Cette phrase n’a pas pu être corrigée. Elle n’est pas jugée correcte pour autant.
            </p>
          )}
        </Surface>
      )}
      {alert}
      <div className="rp-spacer" aria-hidden="true" />
      <Action tone="primary" onClick={props.onLeave}>
        Revenir à l’Atelier
      </Action>
    </>
  );
}

export default RehearsalScreen;
