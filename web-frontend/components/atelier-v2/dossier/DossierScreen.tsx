/**
 * WP-35 «Votre dossier» — the screen. Redrawn for WP-45 on
 * `docs/design-reference/nouvelles-pages-2026-09-15/Dossier.dc.html`.
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
 *
 * WP-45 adds two of its own, both from the canvas note «chaque chiffre a une
 * unité et une preuve» and from WP-39's D-5 and D-3:
 *
 *  4. **No bare ratio.** «0 / 300» is gone. Every figure on this screen is a
 *     count of something named — mots, fautes, réponses — with the denominator
 *     said in words beside it.
 *  5. **One chrome language.** The capability titles are French, from the
 *     payload's `title_fr`; the control-language title is the fallback, never
 *     the default, so a German title never lands under a French label.
 */

import React from 'react';

import { Action, Notice, ScreenFoot, Skeleton, Surface, textAnswerField } from '@/components/atelier-v2/ui';
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
  capabilityEvidenceRef,
  capabilityEvidenceSentence,
  capabilityStateLabel,
  capabilityTitle,
  errataCounters,
  errataStateLabel,
  errataTotalSentence,
  evidenceSentence,
  frenchDate,
  frenchShortDate,
  levelLadderSentence,
  levelSentence,
  levelSourceLine,
  phaseFor,
  verdictTone,
  vocabularyCount,
  vocabularyRuleSentence,
  vocabularyUnitSentence,
  type CapabilityWithFrenchTitle,
  type DossierPhase,
  type ErrataWithTotals,
  type LevelWithAttempts,
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
  /** Where «Faire le bilan de niveau» goes. The page owns the route. */
  onOpenPlacement?: () => void;
};

/** The screen's scaffold: a scrolling body, and a foot only when there is an
 *  action. The dossier proper has none — it is a page one reads — so on it the
 *  tab bar is the only thing below the last card.
 *
 *  TODO(WP-43): swap the wrapper for the shared `ScreenFoot` once it lands;
 *  the class and the padding are already its own. */
function Frame({ children, foot }: { children: React.ReactNode; foot?: React.ReactNode }) {
  return (
    <>
      <div className="av2-screen__body ds-body">{children}</div>
      {foot ? <ScreenFoot className="ds-foot">{foot}</ScreenFoot> : null}
    </>
  );
}

function EvidenceLine({ children }: { children: React.ReactNode }) {
  if (!children) return null;
  return <p className="ds-fine">{children}</p>;
}

/** A dated reference to the work that produced a belief.
 *
 *  Drawn underlined, as the artboard draws it, and deliberately *not* an
 *  anchor: no route in this app opens a past séance, and a link that goes
 *  nowhere is a worse promise than a reference that never claimed to be one. */
function EvidenceRef({ children }: { children: React.ReactNode }) {
  return <span className="ds-ref">{children}</span>;
}

function LevelSection({
  dossier,
  onOpenPlacement,
}: {
  dossier: DossierPayload;
  onOpenPlacement?: () => void;
}) {
  const level = dossier.level as LevelWithAttempts;
  const unavailable = !level || level.available === false || !level.estimate;
  return (
    <Surface as="section" className="ds-card" aria-labelledby="ds-level">
      <p className="av2-label" id="ds-level">
        Votre niveau
      </p>
      {unavailable ? (
        <p className="av2-body av2-body--lg">{levelSentence(level)}</p>
      ) : (
        <div className="ds-level">
          <span className="ds-level__value">{level.estimate}</span>
          <span className="ds-level__source">{levelSourceLine(level)}</span>
        </div>
      )}
      <p className="av2-body">{levelLadderSentence(level)}</p>
      <EvidenceLine>{evidenceSentence(level?.evidence)}</EvidenceLine>
      {onOpenPlacement && (
        <Action tone="quiet" inline onClick={onOpenPlacement}>
          Faire le bilan de niveau
        </Action>
      )}
    </Surface>
  );
}

function CapabilitySection({ capabilities }: { capabilities: DossierCapability[] }) {
  return (
    <Surface as="section" className="ds-card" aria-labelledby="ds-capabilities">
      <p className="av2-label" id="ds-capabilities">
        Vos capacités
      </p>
      {/* The section heading the page has always carried, kept as the
          accessible description: «Ce que vous savez faire» is what the four
          states are, and the label above is what the card is called. */}
      <p className="av2-body">
        Ce que vous savez faire, en quatre états — du jamais tenté au refait un autre jour. Ils
        viennent de vos séances, jamais d’une note recalculée ici.
      </p>
      <ul className="ds-caps">
        {capabilities.map((capability) => {
          const latest = capability.evidence[0];
          return (
            <li key={capability.key} className="ds-cap">
              <span className="ds-cap__name" lang="fr">
                {capabilityTitle(capability as CapabilityWithFrenchTitle)}
              </span>
              <span className="ds-cap__right">
                <span className="ds-cap__state">{capabilityStateLabel(capability.state)}</span>
                <EvidenceRef>{capabilityEvidenceRef(capability)}</EvidenceRef>
              </span>
              <span className="av2-sr">{capabilityEvidenceSentence(latest) ?? ''}</span>
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
  errata: ErrataWithTotals;
  pending?: boolean;
  onClaim: (kind: string, targetId: string) => void;
}) {
  const [open, setOpen] = React.useState(false);

  if (errata?.available === false) {
    return (
      <Surface as="section" className="ds-card">
        <p className="av2-label">Vos fautes notées</p>
        <p className="av2-body">Cette partie de votre dossier est illisible pour l’instant.</p>
      </Surface>
    );
  }

  const byState = errata?.by_state ?? {};
  const counters = errataCounters(errata);
  const anyShown = ERRATUM_STATE_ORDER.some((state) => (byState[state] ?? []).length > 0);

  return (
    <Surface as="section" className="ds-card" aria-labelledby="ds-errata">
      <p className="av2-label" id="ds-errata">
        Vos fautes notées
      </p>
      <div className="ds-counters">
        {counters.map((counter) => (
          <span key={counter.state} className="ds-counter">
            <span className="ds-counter__value">{counter.count}</span>
            <span className="ds-counter__label">{counter.label}</span>
          </span>
        ))}
      </div>
      <p className="av2-body">
        {errataTotalSentence(errata)} Une faute quitte le relevé après{' '}
        {errata?.mastery_target ?? 3} reprises justes, à des jours différents.
      </p>
      {anyShown && (
        <>
          <Action
            tone="quiet"
            inline
            aria-expanded={open}
            onClick={() => setOpen((value) => !value)}
          >
            {open ? 'Masquer le détail' : 'Voir le détail'}
          </Action>
          {open &&
            ERRATUM_STATE_ORDER.map((state) => {
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
                          <Action
                            tone="quiet"
                            inline
                            disabled={pending}
                            onClick={() => onClaim('erratum', item.id)}
                          >
                            Je connais déjà
                          </Action>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              );
            })}
        </>
      )}
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
  const [open, setOpen] = React.useState(false);
  const words: DossierWord[] = vocabulary?.words ?? [];
  const claimable = words.filter((word) => word.claimable);
  const count = vocabularyCount(vocabulary);

  return (
    <Surface as="section" className="ds-card" aria-labelledby="ds-vocabulary">
      <p className="av2-label" id="ds-vocabulary">
        Vos mots
      </p>
      {count === null ? (
        <p className="av2-body av2-body--lg">{vocabularyUnitSentence(vocabulary)}</p>
      ) : (
        <div className="ds-stock">
          <span className="ds-stock__value">{count}</span>
          <span className="ds-stock__unit">{vocabularyUnitSentence(vocabulary)}</span>
        </div>
      )}
      <p className="av2-body">{vocabularyRuleSentence(vocabulary)}</p>
      {claimable.length > 0 && (
        <>
          <button
            type="button"
            className="av2-chip ds-chip"
            aria-expanded={open}
            onClick={() => setOpen((value) => !value)}
          >
            Je connais déjà un mot…
          </button>
          {open && (
            <ul className="ds-rows">
              {claimable.map((word) => (
                <li key={word.word_id} className="ds-row ds-row--stacked">
                  <span className="ds-row__label" lang="fr">
                    {word.word}
                  </span>
                  {word.translation && <span className="ds-row__value">{word.translation}</span>}
                  <EvidenceLine>{evidenceSentence(word.evidence)}</EvidenceLine>
                  <Action
                    tone="quiet"
                    inline
                    disabled={pending}
                    onClick={() => onClaim('word', String(word.word_id))}
                  >
                    Je connais déjà
                  </Action>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </Surface>
  );
}

function TodaySection({ today }: { today: DossierPayload['today'] }) {
  const because = becauseSentence(today);
  return (
    <Surface as="section" className="ds-card" aria-labelledby="ds-today">
      <p className="av2-label av2-label--story" id="ds-today">
        La scène du jour
      </p>
      {!today?.has_journey ? (
        <p className="av2-body av2-body--lg">{NO_JOURNEY_FR}</p>
      ) : (
        <>
          <p className="av2-body av2-body--lg">
            {because ?? 'Cette scène ne reprend aucune faute notée en particulier.'}
          </p>
          <EvidenceRef>
            {today.evidence?.on ? `séance du ${frenchShortDate(today.evidence.on)}` : 'séance du jour'}
          </EvidenceRef>
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
      <Frame
        foot={
          <Action tone="primary" onClick={onCloseClaim}>
            Revenir au dossier
          </Action>
        }
      >
        <p className="av2-label">L’Atelier · Votre dossier</p>
        <h1 className="av2-headline av2-headline--screen">Votre déclaration</h1>
        <Notice tone={verdictTone(verdict.verdict)} live="status">
          {verdict.message_fr}
        </Notice>
        {verdict.next_review_date && (
          <p className="ds-fine">Prochaine reprise le {frenchDate(verdict.next_review_date)}.</p>
        )}
      </Frame>
    );
  }

  if (!check.verifiable) {
    return (
      <Frame
        foot={
          <Action tone="primary" onClick={onCloseClaim}>
            Revenir au dossier
          </Action>
        }
      >
        <p className="av2-label">L’Atelier · Votre dossier</p>
        <h1 className="av2-headline av2-headline--screen">Votre déclaration</h1>
        <Notice tone="quiet" live="status">
          {check.message_fr ?? 'Nous ne pouvons pas vérifier cette déclaration.'}
        </Notice>
      </Frame>
    );
  }

  const complete = check.items.every((item) => (answers[item.index] ?? '').trim().length > 0);
  return (
    <Frame
      foot={
        <>
          <Action
            tone="primary"
            pending={pending}
            pendingLabel="Vérification…"
            disabled={!complete}
            onClick={() => onVerify(check.kind, check.target_id, answers)}
          >
            Vérifier
          </Action>
          <Action tone="quiet" onClick={onCloseClaim}>
            Annuler
          </Action>
        </>
      }
    >
      <p className="av2-label">L’Atelier · Votre dossier</p>
      <h1 className="av2-headline av2-headline--screen">Deux questions, puis c’est réglé</h1>
      <p className="av2-body av2-body--lg" lang="fr">
        {check.label}
      </p>
      <Surface tone="outline">
        <p className="ds-fine">
          Si les deux réponses sont justes, nous avançons l’échéance. Si elles ne le sont pas,
          rien n’est retiré et rien n’est ajouté.
        </p>
      </Surface>
      {check.items.map((item) => (
        <div key={item.index} className="ds-item">
          <p className="ds-fine">{item.instruction_fr}</p>
          <p className="av2-body av2-body--lg" lang="fr">
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
    </Frame>
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
            Revenir à l’Atelier
          </Action>
        }
      >
        <p className="av2-label">L’Atelier · Votre dossier</p>
        <h1 className="av2-headline av2-headline--screen">Dossier indisponible</h1>
        <p className="av2-body av2-body--lg">{phase.message}</p>
      </Frame>
    );
  }

  if (check) {
    return (
      <ClaimPanel
        key={`${check.kind}:${check.target_id}`}
        check={check}
        verdict={verdict}
        pending={pending}
        onVerify={props.onVerify}
        onCloseClaim={props.onCloseClaim}
      />
    );
  }

  const model = phase.dossier;
  return (
    <Frame>
      <p className="av2-label">L’Atelier · Votre dossier</p>
      <h1 className="av2-headline">Ce que nous croyons savoir de vous</h1>
      {alert}
      <LevelSection dossier={model} onOpenPlacement={props.onOpenPlacement} />
      <CapabilitySection capabilities={model.capabilities} />
      <ErrataSection
        errata={model.errata as ErrataWithTotals}
        pending={pending}
        onClaim={props.onClaim}
      />
      <VocabularySection
        vocabulary={model.vocabulary}
        pending={pending}
        onClaim={props.onClaim}
      />
      <TodaySection today={model.today} />
    </Frame>
  );
}
