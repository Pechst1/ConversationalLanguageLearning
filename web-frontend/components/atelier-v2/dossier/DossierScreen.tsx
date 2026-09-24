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
 *
 * WP-82: every word the screen writes itself is read from `dossier-copy.ts` in
 * the chrome language (`useChromeLanguage`) — the learner's up to A2, French
 * from B1. What the server sends as content stays French.
 */

import React from 'react';

import { Action, Notice, ScreenFoot, Skeleton, Surface, textAnswerField } from '@/components/atelier-v2/ui';
import { useChromeLanguage } from '@/lib/learner-language';
import type {
  DossierCapability,
  DossierClaimCheck,
  DossierClaimVerdict,
  DossierErratum,
  DossierPayload,
  DossierWord,
} from '@/services/api';
import type { ControlLanguage } from '@/types/daily-journey';

import { dossierCopy, fill, longDate, shortDate, type DossierCopy } from './dossier-copy';
import {
  ERRATUM_STATE_ORDER,
  becauseSentence,
  capabilityEvidenceRef,
  capabilityEvidenceSentence,
  capabilityStateLabel,
  capabilityTitle,
  coverageRows,
  coverageRuleSentence,
  errataCounters,
  errataStateLabel,
  errataTotalSentence,
  evidenceSentence,
  forecastSentence,
  levelHeadline,
  levelLadderSentence,
  levelSentence,
  levelSourceLine,
  noJourneySentence,
  phaseFor,
  rulesSpeedSentence,
  verdictTone,
  vocabularyCount,
  vocabularyRuleSentence,
  vocabularyUnitSentence,
  type CapabilityWithFrenchTitle,
  type DossierPhase,
  type ErrataWithTotals,
  type LevelWithAttempts,
  type LevelWithRulesSpeed,
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

type Chrome = { language: ControlLanguage; copy: DossierCopy };

function LevelSection({
  dossier,
  onOpenPlacement,
  language,
  copy,
}: Chrome & {
  dossier: DossierPayload;
  onOpenPlacement?: () => void;
}) {
  const level = dossier.level as LevelWithAttempts;
  const unavailable = !level || level.available === false || !level.estimate;
  const rows = coverageRows(level, language);
  const forecast = forecastSentence(level, language);
  const rulesSpeed = rulesSpeedSentence(level as LevelWithRulesSpeed, language);
  return (
    <Surface as="section" className="ds-card" aria-labelledby="ds-level">
      <p className="av2-label" id="ds-level">
        {copy.level_title}
      </p>
      {unavailable ? (
        <p className="av2-body av2-body--lg">{levelSentence(level, language)}</p>
      ) : (
        <div className="ds-level">
          {/* WP-L7: the band and how much of it is covered, «A1.1 · 60 %». */}
          <span className="ds-level__value">{levelHeadline(level)}</span>
          <span className="ds-level__source">{levelSourceLine(level, language)}</span>
        </div>
      )}
      {!unavailable && rows.length > 0 && (
        <>
          <ul className="ds-rows" aria-label={copy.level_rows}>
            {rows.map((row) => (
              <li key={row.key} className="ds-row">
                <span className="ds-row__label">{row.label}</span>
                <span className="ds-row__value">{row.value}</span>
              </li>
            ))}
          </ul>
          <p className="ds-fine">{coverageRuleSentence(level, language)}</p>
        </>
      )}
      {!unavailable && forecast && <p className="av2-body">{forecast}</p>}
      {/* WP-S8: the learner's own measured speed, from three held rules. */}
      {rulesSpeed && <p className="av2-body">{rulesSpeed}</p>}
      <p className="av2-body">{levelLadderSentence(level, language)}</p>
      <EvidenceLine>{evidenceSentence(level?.evidence, language)}</EvidenceLine>
      {onOpenPlacement && (
        <Action tone="quiet" inline onClick={onOpenPlacement}>
          {copy.open_placement}
        </Action>
      )}
    </Surface>
  );
}

function CapabilitySection({ capabilities, language, copy }: Chrome & { capabilities: DossierCapability[] }) {
  return (
    <Surface as="section" className="ds-card" aria-labelledby="ds-capabilities">
      <p className="av2-label" id="ds-capabilities">
        {copy.caps_title}
      </p>
      {/* The section heading the page has always carried, kept as the
          accessible description: «Ce que vous savez faire» is what the four
          states are, and the label above is what the card is called. */}
      <p className="av2-body">{copy.caps_intro}</p>
      <ul className="ds-caps">
        {capabilities.map((capability) => {
          const latest = capability.evidence[0];
          return (
            <li key={capability.key} className="ds-cap">
              <span className="ds-cap__name" lang="fr">
                {capabilityTitle(capability as CapabilityWithFrenchTitle)}
              </span>
              <span className="ds-cap__right">
                <span className="ds-cap__state">{capabilityStateLabel(capability.state, language)}</span>
                <EvidenceRef>{capabilityEvidenceRef(capability, language)}</EvidenceRef>
              </span>
              <span className="av2-sr">{capabilityEvidenceSentence(latest, language) ?? ''}</span>
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
  language,
  copy,
}: Chrome & {
  errata: ErrataWithTotals;
  pending?: boolean;
  onClaim: (kind: string, targetId: string) => void;
}) {
  const [open, setOpen] = React.useState(false);

  if (errata?.available === false) {
    return (
      <Surface as="section" className="ds-card">
        <p className="av2-label">{copy.errata_title}</p>
        <p className="av2-body">{copy.errata_unreadable}</p>
      </Surface>
    );
  }

  const byState = errata?.by_state ?? {};
  const counters = errataCounters(errata, language);
  const anyShown = ERRATUM_STATE_ORDER.some((state) => (byState[state] ?? []).length > 0);

  return (
    <Surface as="section" className="ds-card" aria-labelledby="ds-errata">
      <p className="av2-label" id="ds-errata">
        {copy.errata_title}
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
        {errataTotalSentence(errata, language)}{' '}
        {fill(copy.errata_rule, { n: errata?.mastery_target ?? 3 })}
      </p>
      {anyShown && (
        <>
          <Action
            tone="quiet"
            inline
            aria-expanded={open}
            onClick={() => setOpen((value) => !value)}
          >
            {open ? copy.hide_detail : copy.show_detail}
          </Action>
          {open &&
            ERRATUM_STATE_ORDER.map((state) => {
              const items: DossierErratum[] = byState[state] ?? [];
              if (items.length === 0) return null;
              return (
                <div key={state} className="ds-group">
                  <span className="av2-label">
                    {errataStateLabel(state, language)} · {items.length}
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
                            ? fill(copy.next_repair, { date: longDate(item.next_review_date, language) })
                            : copy.not_scheduled}
                          {' · '}
                          {evidenceSentence(item.evidence, language)}
                        </EvidenceLine>
                        {item.claimable && (
                          <Action
                            tone="quiet"
                            inline
                            disabled={pending}
                            onClick={() => onClaim('erratum', item.id)}
                          >
                            {copy.claim}
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
  language,
  copy,
}: Chrome & {
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
        {copy.vocab_title}
      </p>
      {count === null ? (
        <p className="av2-body av2-body--lg">{vocabularyUnitSentence(vocabulary, language)}</p>
      ) : (
        <div className="ds-stock">
          <span className="ds-stock__value">{count}</span>
          <span className="ds-stock__unit">{vocabularyUnitSentence(vocabulary, language)}</span>
        </div>
      )}
      <p className="av2-body">{vocabularyRuleSentence(vocabulary, language)}</p>
      {claimable.length > 0 && (
        <>
          <button
            type="button"
            className="av2-chip ds-chip"
            aria-expanded={open}
            onClick={() => setOpen((value) => !value)}
          >
            {copy.claim_word}
          </button>
          {open && (
            <ul className="ds-rows">
              {claimable.map((word) => (
                <li key={word.word_id} className="ds-row ds-row--stacked">
                  <span className="ds-row__label" lang="fr">
                    {word.word}
                  </span>
                  {word.translation && <span className="ds-row__value">{word.translation}</span>}
                  <EvidenceLine>{evidenceSentence(word.evidence, language)}</EvidenceLine>
                  <Action
                    tone="quiet"
                    inline
                    disabled={pending}
                    onClick={() => onClaim('word', String(word.word_id))}
                  >
                    {copy.claim}
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

function TodaySection({ today, language, copy }: Chrome & { today: DossierPayload['today'] }) {
  const because = becauseSentence(today, language);
  return (
    <Surface as="section" className="ds-card" aria-labelledby="ds-today">
      <p className="av2-label av2-label--story" id="ds-today">
        {copy.today_title}
      </p>
      {!today?.has_journey ? (
        <p className="av2-body av2-body--lg">{noJourneySentence(language)}</p>
      ) : (
        <>
          <p className="av2-body av2-body--lg">
            {because ?? copy.today_no_because}
          </p>
          <EvidenceRef>
            {today.evidence?.on
              ? fill(copy.evref_one, { date: shortDate(today.evidence.on, language) })
              : copy.today_ref}
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
  language,
  copy,
}: Chrome & {
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
            {copy.back_to_dossier}
          </Action>
        }
      >
        <p className="av2-label">{copy.eyebrow}</p>
        <h1 className="av2-headline av2-headline--screen">{copy.claim_title}</h1>
        <Notice tone={verdictTone(verdict.verdict)} live="status">
          {verdict.message_fr}
        </Notice>
        {verdict.next_review_date && (
          <p className="ds-fine">
            {fill(copy.next_repair_sentence, { date: longDate(verdict.next_review_date, language) })}
          </p>
        )}
      </Frame>
    );
  }

  if (!check.verifiable) {
    return (
      <Frame
        foot={
          <Action tone="primary" onClick={onCloseClaim}>
            {copy.back_to_dossier}
          </Action>
        }
      >
        <p className="av2-label">{copy.eyebrow}</p>
        <h1 className="av2-headline av2-headline--screen">{copy.claim_title}</h1>
        <Notice tone="quiet" live="status">
          {check.message_fr ?? copy.claim_unverifiable}
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
            pendingLabel={copy.verifying}
            disabled={!complete}
            onClick={() => onVerify(check.kind, check.target_id, answers)}
          >
            {copy.verify}
          </Action>
          <Action tone="quiet" onClick={onCloseClaim}>
            {copy.cancel}
          </Action>
        </>
      }
    >
      <p className="av2-label">{copy.eyebrow}</p>
      <h1 className="av2-headline av2-headline--screen">{copy.claim_heading}</h1>
      <p className="av2-body av2-body--lg" lang="fr">
        {check.label}
      </p>
      <Surface tone="outline">
        <p className="ds-fine">{copy.claim_terms}</p>
      </Surface>
      {check.items.map((item) => (
        <div key={item.index} className="ds-item">
          <p className="ds-fine">{item.instruction_fr}</p>
          <p className="av2-body av2-body--lg" lang="fr">
            {item.prompt_fr}
          </p>
          {textAnswerField({
            label: fill(copy.question, { n: item.index + 1 }),
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
  const language = useChromeLanguage();
  const copy = dossierCopy(language);
  const chrome: Chrome = { language, copy };

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
        <p className="av2-label">{copy.eyebrow}</p>
        <h1 className="av2-headline av2-headline--screen">{copy.unavailable}</h1>
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
        {...chrome}
      />
    );
  }

  const model = phase.dossier;
  return (
    <Frame>
      <p className="av2-label">{copy.eyebrow}</p>
      <h1 className="av2-headline">{copy.headline}</h1>
      {alert}
      <LevelSection dossier={model} onOpenPlacement={props.onOpenPlacement} {...chrome} />
      <CapabilitySection capabilities={model.capabilities} {...chrome} />
      <ErrataSection
        errata={model.errata as ErrataWithTotals}
        pending={pending}
        onClaim={props.onClaim}
        {...chrome}
      />
      <VocabularySection
        vocabulary={model.vocabulary}
        pending={pending}
        onClaim={props.onClaim}
        {...chrome}
      />
      <TodaySection today={model.today} {...chrome} />
    </Frame>
  );
}
