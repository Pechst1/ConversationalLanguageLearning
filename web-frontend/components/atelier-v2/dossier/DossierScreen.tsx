/**
 * WP-35 «Votre dossier» — the screen.
 *
 * One page that answers, in French, two questions: what does the app believe
 * about me, and what happens when I disagree. Every belief is printed with the
 * evidence that produced it — a séance and its date, a bilan and its date —
 * because a model nobody can check is a model nobody can correct.
 *
 * The honesty rules the design and the backend share, which this file must not
 * break:
 *
 *  1. **A source is named next to every number.** A declared level says it was
 *     declared; a placement says how sure it is; in-app counters say they are
 *     the app's own arithmetic. No bare badge anywhere.
 *  2. **«Je connais déjà» is a claim, not a switch.** Pressing it opens two
 *     questions. The learner is told, before answering, that passing moves the
 *     schedule and that failing costs nothing.
 *  3. **Nothing is invented where the server said nothing.** No scene today is
 *     «pas encore de scène aujourd'hui», not a forecast; an unreadable section
 *     says so rather than rendering an empty shell as if it were a zero.
 */

import React from 'react';

import { Action, Notice, Skeleton, Surface, textAnswerField } from '@/components/atelier-v2/ui';
import type {
  DossierCapability,
  DossierClaimCheck,
  DossierClaimVerdict,
  DossierErratum,
  DossierPayload,
  DossierWord,
} from '@/services/api';

import {
  ERRATUM_STATE_ORDER,
  NO_JOURNEY_FR,
  becauseSentence,
  capabilityEvidenceSentence,
  capabilityStateLabel,
  confidenceSentence,
  errataStateLabel,
  evidenceSentence,
  frenchDate,
  levelBasisSentence,
  levelSentence,
  phaseFor,
  verdictTone,
  verifiedSentence,
  vocabularyRuleSentence,
  vocabularySentence,
  type DossierPhase,
} from './dossier-state';

export type DossierScreenProps = {
  dossier: DossierPayload | null;
  check: DossierClaimCheck | null;
  verdict: DossierClaimVerdict | null;
  loading?: boolean;
  error?: string | null;
  pending?: boolean;
  failure?: string | null;
  onClaim: (kind: string, targetId: string) => void;
  onVerify: (kind: string, targetId: string, answers: string[]) => void;
  onCloseClaim: () => void;
  onLeave: () => void;
};

function EvidenceLine({ children }: { children: React.ReactNode }) {
  if (!children) return null;
  return <p className="ds-fine">{children}</p>;
}

function LevelSection({ dossier }: { dossier: DossierPayload }) {
  const level = dossier.level;
  const placement = level?.placement;
  const dimensions = Object.entries(placement?.dimensions ?? {});
  const breakdown = level?.breakdown ?? {};
  const rows: [string, any][] = [
    ['Mots acquis', breakdown.vocabulary],
    ['Notions acquises', breakdown.grammar],
    ['Score récent', breakdown.score],
    ['Taux d’erreur', breakdown.error_rate],
  ];
  return (
    <Surface tone="outline" as="section" aria-labelledby="ds-level">
      <h2 className="av2-headline av2-headline--rule" id="ds-level">
        Votre niveau
      </h2>
      <p className="ds-lead">{levelSentence(level)}</p>
      <p className="ds-fine">{levelBasisSentence(level)}</p>
      <p className="ds-fine">{verifiedSentence(level)}</p>
      <EvidenceLine>{evidenceSentence(level?.evidence)}</EvidenceLine>
      {dimensions.length > 0 && (
        <ul className="ds-rows">
          {dimensions.map(([key, value]) => (
            <li key={key} className="ds-row">
              <span className="ds-row__label">
                {placement?.dimension_labels?.[key] ?? key}
              </span>
              <span className="ds-row__value">{Number(value).toFixed(1)} / 4</span>
            </li>
          ))}
        </ul>
      )}
      {placement && (
        <EvidenceLine>
          {confidenceSentence(placement.confidence)}
          {placement.taken_at ? ` Bilan du ${frenchDate(placement.taken_at)}.` : ''}
        </EvidenceLine>
      )}
      {rows.some(([, value]) => value) && (
        <ul className="ds-rows">
          {rows.map(([label, value]) =>
            value ? (
              <li key={label} className="ds-row">
                <span className="ds-row__label">{label}</span>
                <span className="ds-row__value">
                  {value.current} / {value.target}
                </span>
              </li>
            ) : null,
          )}
        </ul>
      )}
    </Surface>
  );
}

function CapabilitySection({ capabilities }: { capabilities: DossierCapability[] }) {
  return (
    <Surface tone="outline" as="section" aria-labelledby="ds-capabilities">
      <h2 className="av2-headline av2-headline--rule" id="ds-capabilities">
        Ce que vous savez faire
      </h2>
      <p className="ds-fine">
        Quatre états, du jamais tenté au refait un autre jour. Ils viennent de vos séances,
        jamais d’une note recalculée ici.
      </p>
      <ul className="ds-rows">
        {capabilities.map((capability) => {
          const latest = capability.evidence[0];
          return (
            <li key={capability.key} className="ds-row ds-row--stacked">
              <span className="ds-row__label">{capability.title}</span>
              <span className="ds-row__value">{capabilityStateLabel(capability.state)}</span>
              <EvidenceLine>{capabilityEvidenceSentence(latest)}</EvidenceLine>
            </li>
          );
        })}
      </ul>
    </Surface>
  );
}

function ErrataSection({
  errata,
  pending,
  onClaim,
}: {
  errata: DossierPayload['errata'];
  pending?: boolean;
  onClaim: (kind: string, targetId: string) => void;
}) {
  if (errata?.available === false) {
    return (
      <Surface tone="outline" as="section">
        <h2 className="av2-headline av2-headline--rule">Vos fautes notées</h2>
        <p className="ds-fine">Cette partie de votre dossier est illisible pour l’instant.</p>
      </Surface>
    );
  }
  const byState = errata?.by_state ?? {};
  return (
    <Surface tone="outline" as="section" aria-labelledby="ds-errata">
      <h2 className="av2-headline av2-headline--rule" id="ds-errata">
        Vos fautes notées
      </h2>
      <p className="ds-fine">
        Une faute quitte le relevé après {errata?.mastery_target ?? 3} reprises justes, à des
        jours différents.
      </p>
      {ERRATUM_STATE_ORDER.map((state) => {
        const items: DossierErratum[] = byState[state] ?? [];
        if (items.length === 0) return null;
        return (
          <div key={state} className="ds-group">
            <span className="av2-label">
              {errataStateLabel(state)} · {items.length}
            </span>
            <ul className="ds-rows">
              {items.map((item) => (
                <li key={item.id} className="ds-row ds-row--stacked">
                  <span className="ds-row__label" lang="fr">
                    {item.label}
                  </span>
                  {item.learner_text && item.corrected_target && (
                    <span className="ds-row__value" lang="fr">
                      <s>{item.learner_text}</s> → <strong>{item.corrected_target}</strong>
                    </span>
                  )}
                  <EvidenceLine>
                    {item.next_review_date
                      ? `Prochaine reprise le ${frenchDate(item.next_review_date)}`
                      : 'Pas encore programmée'}
                    {' · '}
                    {evidenceSentence(item.evidence)}
                  </EvidenceLine>
                  {item.claimable && (
                    <button
                      type="button"
                      className="av2-btn av2-btn--quiet av2-btn--inline"
                      disabled={pending}
                      onClick={() => onClaim('erratum', item.id)}
                    >
                      Je connais déjà
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </Surface>
  );
}

function VocabularySection({
  vocabulary,
  pending,
  onClaim,
}: {
  vocabulary: DossierPayload['vocabulary'];
  pending?: boolean;
  onClaim: (kind: string, targetId: string) => void;
}) {
  const words: DossierWord[] = vocabulary?.words ?? [];
  return (
    <Surface tone="outline" as="section" aria-labelledby="ds-vocabulary">
      <h2 className="av2-headline av2-headline--rule" id="ds-vocabulary">
        Vos mots
      </h2>
      <p className="ds-lead">{vocabularySentence(vocabulary)}</p>
      <p className="ds-fine">{vocabularyRuleSentence(vocabulary)}</p>
      {words.length > 0 && (
        <ul className="ds-rows">
          {words.map((word) => (
            <li key={word.word_id} className="ds-row ds-row--stacked">
              <span className="ds-row__label" lang="fr">
                {word.word}
              </span>
              {word.translation && <span className="ds-row__value">{word.translation}</span>}
              <EvidenceLine>{evidenceSentence(word.evidence)}</EvidenceLine>
              {word.claimable && (
                <button
                  type="button"
                  className="av2-btn av2-btn--quiet av2-btn--inline"
                  disabled={pending}
                  onClick={() => onClaim('word', String(word.word_id))}
                >
                  Je connais déjà
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </Surface>
  );
}

function TodaySection({ today }: { today: DossierPayload['today'] }) {
  const because = becauseSentence(today);
  return (
    <Surface tone="outline" as="section" aria-labelledby="ds-today">
      <h2 className="av2-headline av2-headline--rule" id="ds-today">
        La scène du jour
      </h2>
      {!today?.has_journey && <p className="ds-lead">{NO_JOURNEY_FR}</p>}
      {today?.has_journey && (
        <>
          <p className="ds-lead">
            {because ?? 'Cette scène ne reprend aucune faute notée en particulier.'}
          </p>
          <EvidenceLine>{evidenceSentence(today.evidence)}</EvidenceLine>
        </>
      )}
    </Surface>
  );
}

function ClaimPanel({
  check,
  verdict,
  pending,
  onVerify,
  onCloseClaim,
}: {
  check: DossierClaimCheck;
  verdict: DossierClaimVerdict | null;
  pending?: boolean;
  onVerify: (kind: string, targetId: string, answers: string[]) => void;
  onCloseClaim: () => void;
}) {
  // Keyed by the claim in the parent, so a new claim mounts a new panel and the
  // previous answers cannot survive into a different question.
  const [answers, setAnswers] = React.useState<string[]>(() => check.items.map(() => ''));

  if (verdict) {
    return (
      <Surface tone="outline" as="section" aria-labelledby="ds-claim">
        <h2 className="av2-headline av2-headline--rule" id="ds-claim">
          Votre déclaration
        </h2>
        <Notice tone={verdictTone(verdict.verdict)} live="status">
          {verdict.message_fr}
        </Notice>
        {verdict.next_review_date && (
          <p className="ds-fine">
            Prochaine reprise le {frenchDate(verdict.next_review_date)}.
          </p>
        )}
        <Action tone="primary" onClick={onCloseClaim}>
          Revenir au dossier
        </Action>
      </Surface>
    );
  }

  if (!check.verifiable) {
    return (
      <Surface tone="outline" as="section" aria-labelledby="ds-claim">
        <h2 className="av2-headline av2-headline--rule" id="ds-claim">
          Votre déclaration
        </h2>
        <Notice tone="quiet" live="status">
          {check.message_fr ?? 'Nous ne pouvons pas vérifier cette déclaration.'}
        </Notice>
        <Action tone="primary" onClick={onCloseClaim}>
          Revenir au dossier
        </Action>
      </Surface>
    );
  }

  const complete = check.items.every((item) => (answers[item.index] ?? '').trim().length > 0);
  return (
    <Surface tone="outline" as="section" aria-labelledby="ds-claim">
      <h2 className="av2-headline av2-headline--rule" id="ds-claim">
        Deux questions, puis c’est réglé
      </h2>
      <p className="ds-lead" lang="fr">
        {check.label}
      </p>
      <p className="ds-fine">
        Si les deux réponses sont justes, nous avançons l’échéance. Si elles ne le sont pas,
        rien n’est retiré et rien n’est ajouté.
      </p>
      {check.items.map((item) => (
        <div key={item.index} className="ds-item">
          <p className="ds-fine">{item.instruction_fr}</p>
          <p className="ds-lead" lang="fr">
            {item.prompt_fr}
          </p>
          {textAnswerField({
            label: `Question ${item.index + 1}`,
            value: answers[item.index] ?? '',
            rows: 2,
            disabled: pending,
            placeholder: item.placeholder_fr,
            onChange: (value: string) =>
              setAnswers((previous) => {
                const next = [...previous];
                next[item.index] = value;
                return next;
              }),
          })}
        </div>
      ))}
      <Action
        tone="primary"
        pending={pending}
        pendingLabel="Vérification…"
        disabled={!complete}
        onClick={() => onVerify(check.kind, check.target_id, answers)}
      >
        Vérifier
      </Action>
      <button type="button" className="av2-btn av2-btn--quiet" onClick={onCloseClaim}>
        Annuler
      </button>
    </Surface>
  );
}

export function DossierScreen(props: DossierScreenProps) {
  const { dossier, check, verdict, loading, error, pending, failure } = props;
  const phase: DossierPhase = phaseFor(dossier, { loading, error });

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
        <span className="av2-label">L’Atelier · Votre dossier</span>
        <h1 className="av2-headline av2-headline--screen">Dossier indisponible</h1>
        <p className="ds-lead">{phase.message}</p>
        <div className="ds-spacer" aria-hidden="true" />
        <Action tone="primary" onClick={props.onLeave}>
          Revenir à l’Atelier
        </Action>
      </>
    );
  }

  if (check) {
    return (
      <>
        <span className="av2-label">L’Atelier · Votre dossier</span>
        {alert}
        <ClaimPanel
          key={`${check.kind}:${check.target_id}`}
          check={check}
          verdict={verdict}
          pending={pending}
          onVerify={props.onVerify}
          onCloseClaim={props.onCloseClaim}
        />
      </>
    );
  }

  const model = phase.dossier;
  return (
    <>
      <span className="av2-label">L’Atelier · Votre dossier</span>
      <h1 className="av2-headline av2-headline--screen">Ce que nous croyons savoir de vous</h1>
      <p className="ds-lead">
        Chaque chiffre vient d’un travail daté. Si l’un d’eux vous semble faux, dites-le : deux
        questions suffisent à le corriger.
      </p>
      {alert}
      <LevelSection dossier={model} />
      <CapabilitySection capabilities={model.capabilities} />
      <ErrataSection errata={model.errata} pending={pending} onClaim={props.onClaim} />
      <VocabularySection
        vocabulary={model.vocabulary}
        pending={pending}
        onClaim={props.onClaim}
      />
      <TodaySection today={model.today} />
      <div className="ds-spacer" aria-hidden="true" />
      <Action tone="primary" onClick={props.onLeave}>
        Revenir à l’Atelier
      </Action>
    </>
  );
}
