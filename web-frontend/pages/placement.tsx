/**
 * WP-25 — «Trouvons votre niveau», the five-minute placement.
 *
 * WP-75: never the first task. Sign-up lands in the day-1 scene; a learner who
 * did not start as «Nouveau» is offered this from Home after three completed
 * days (`/placement?from=offer`, when `GET /placement/offer` says so), and
 * anyone can re-run it from Réglages (`/placement?rerun=1`). Four to six French prompts, each drawn from the band
 * the previous answer earned; the server does the grading and the ladder, so
 * this screen is a thin renderer over one envelope — which is why it has one
 * state machine rather than four screens.
 *
 * Two honesty rules the design brief and the backend share, and this file must
 * not break:
 *
 *  1. **Skippable, and skipping costs nothing.** The declared level stands
 *     exactly as it does today. The quiet action is never disguised, never
 *     delayed, and never nagged about afterwards.
 *  2. **A placement that could not be measured says so.** When the grader never
 *     answered, this screen says «Niveau non évalué» in as many words and offers
 *     to try again. It never shows a level nobody measured.
 *
 * On the av2 system throughout: `.av2` tokens, pill sentence-case actions,
 * one primary action per state, dark-capable by inheritance.
 *
 * 2026-09-24 — the chrome follows the learner's declared native language
 * (`lib/placement-copy.ts`); the prompts and the answers stay French.
 *
 * WP-45 redraws it on `docs/design-reference/nouvelles-pages-2026-09-15/`
 * `Bilan.dc.html` and its canvas note «note-pied»: every state carries its
 * actions in a screen foot that is the *last thing in the flow*, above the
 * phone tab bar, never a bar floating under it (WP-39's CTA finding). The DOM
 * order — body, then foot — is pinned by `tests/test_placement_onboarding_surface.py`.
 */

import React from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';

import {
  Action,
  ArrowRightIcon,
  AtelierV2Root,
  Notice,
  ScreenFoot,
  Skeleton,
  StepProgress,
  Surface,
  textAnswerField,
} from '@/components/atelier-v2/ui';
import api, { type PlacementEnvelope } from '@/services/api';
import { useLearnerLanguage } from '@/lib/learner-language';
import { pickByLanguage } from '@/lib/language-rule';
import {
  placementConfidenceLabel as confidenceLabel,
  placementCopy,
  placementFill,
  type PlacementCopy,
} from '@/lib/placement-copy';

const HOME = '/atelier';

/** The screen scaffold, on `Bilan.dc.html`: a body that holds the reading and
 *  a foot that holds the actions. The foot is a sibling *after* the body in the
 *  flow — not a fixed bar — so on a 390×844 phone the primary action sits above
 *  the four-tab bar instead of under it.
 *
 *  The foot is the shared `ScreenFoot` (WP-43). */
function PlacementFrame({
  children,
  foot,
}: {
  children: React.ReactNode;
  foot?: React.ReactNode;
}) {
  const copy = placementCopy(useLearnerLanguage());
  return (
    <AtelierV2Root as="main" className="av2-screen pl-screen" aria-label={copy.screen_aria}>
      <div className="av2-screen__body pl-body">{children}</div>
      {foot ? <ScreenFoot className="pl-foot">{foot}</ScreenFoot> : null}
      <PlacementStyles />
    </AtelierV2Root>
  );
}

export default function PlacementPage() {
  const router = useRouter();
  const rerun = router.query.rerun === '1';
  // The placement measures the level, so it cannot follow it: its chrome is
  // the learner's declared native language at every level.
  const language = useLearnerLanguage();
  const copy = placementCopy(language);
  const [envelope, setEnvelope] = React.useState<PlacementEnvelope | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [pending, setPending] = React.useState(false);
  const [answer, setAnswer] = React.useState('');
  const [failure, setFailure] = React.useState<'failed_open' | 'failed_send' | 'failed_close' | null>(null);
  const fieldRef = React.useRef<HTMLTextAreaElement | null>(null);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      setEnvelope(rerun ? await api.startPlacement(true) : await api.getPlacementState());
    } catch {
      setFailure('failed_open');
    } finally {
      setLoading(false);
    }
  }, [rerun]);

  React.useEffect(() => {
    if (!router.isReady) return;
    void load();
  }, [load, router.isReady]);

  // Each question and the result are one screen: the learner scrolled down to
  // «Envoyer», so the next one must not open with its title under the top edge.
  const promptIndex = envelope?.prompt?.index ?? null;
  const screenKey = `${envelope?.status ?? ''}:${promptIndex ?? ''}`;
  React.useEffect(() => {
    if (typeof window === 'undefined') return;
    window.scrollTo({ top: 0 });
  }, [screenKey]);

  const leave = React.useCallback(() => {
    void router.replace(HOME);
  }, [router]);

  const begin = async () => {
    setPending(true);
    setFailure(null);
    try {
      setEnvelope(await api.startPlacement(false));
    } catch {
      setFailure('failed_open');
    } finally {
      setPending(false);
    }
  };

  const decline = async () => {
    setPending(true);
    try {
      await api.skipPlacement();
    } catch {
      // Declining must never trap the learner on this screen: a failed skip
      // still lets them leave, and the offer simply comes back next time.
    } finally {
      setPending(false);
      leave();
    }
  };

  const send = async () => {
    if (!envelope?.session_id || !envelope.prompt) return;
    const text = answer.trim();
    if (!text) return;
    setPending(true);
    setFailure(null);
    try {
      const next = await api.respondToPlacement(
        envelope.session_id,
        text,
        envelope.prompt.index,
      );
      setEnvelope(next);
      setAnswer('');
      if (next.status === 'in_progress') fieldRef.current?.focus();
    } catch {
      setFailure('failed_send');
    } finally {
      setPending(false);
    }
  };

  const stopEarly = async () => {
    if (!envelope?.session_id) return;
    setPending(true);
    try {
      setEnvelope(await api.finishPlacement(envelope.session_id));
    } catch {
      setFailure('failed_close');
    } finally {
      setPending(false);
    }
  };

  if (loading) {
    return (
      <PlacementFrame>
        <Skeleton />
        <Skeleton />
      </PlacementFrame>
    );
  }

  const status = envelope?.status ?? 'none';

  /* ---- the offer ------------------------------------------------------- */
  if (status === 'none' || status === 'skipped' || status === 'abandoned') {
    // A learner who already declined and came back by hand is offered it again
    // rather than sent away: they are here on purpose.
    return (
      <>
        <Head>
          <title>{`${copy.offer_title_tab} · L’Atelier`}</title>
        </Head>
        <PlacementFrame
          foot={
            <>
              <Action
                tone="primary"
                pending={pending}
                pendingLabel={copy.opening}
                onClick={begin}
                iconAfter={<ArrowRightIcon size={14} />}
              >
                {copy.begin}
              </Action>
              <button type="button" className="av2-btn av2-btn--quiet" onClick={decline}>
                {copy.skip}
              </button>
            </>
          }
        >
          <span className="av2-label">{copy.offer_kicker}</span>
          <h1 className="av2-headline av2-headline--screen">{copy.offer_title}</h1>
          <p className="pl-lead">{copy.offer_lead}</p>
          <Surface tone="outline">
            <p className="pl-fine">{copy.offer_fine}</p>
          </Surface>
          {failure && <Notice tone="alert" live="alert">{copy[failure]}</Notice>}
        </PlacementFrame>
      </>
    );
  }

  /* ---- the conversation ------------------------------------------------ */
  if (status === 'in_progress' && envelope?.prompt) {
    const prompt = envelope.prompt;
    const hintText = pickByLanguage(prompt.hint_by_language, language);
    const steps = Array.from({ length: prompt.max_turns }, (_, index) => ({
      id: `t${index}`,
      state:
        index < prompt.turns_so_far
          ? ('done' as const)
          : index === prompt.turns_so_far
            ? ('active' as const)
            : ('pending' as const),
    }));
    return (
      <>
        <Head>
          <title>{`${copy.kicker} · L’Atelier`}</title>
        </Head>
        <PlacementFrame
          foot={
            <>
              <Action
                tone="primary"
                pending={pending}
                pendingLabel={copy.reading}
                disabled={!answer.trim()}
                onClick={send}
                iconAfter={<ArrowRightIcon size={14} />}
              >
                {copy.send}
              </Action>
              <button type="button" className="av2-btn av2-btn--quiet" onClick={stopEarly}>
                {copy.stop}
              </button>
            </>
          }
        >
          <span className="av2-label">{copy.kicker}</span>
          <StepProgress
            steps={steps}
            label={copy.progress_aria}
            caption={placementFill(copy.question, { n: prompt.turns_so_far + 1 })}
          />
          <h1 className="av2-headline av2-headline--screen" lang="fr">
            {prompt.prompt_fr}
          </h1>
          {/* The hint is chrome: the native-language version when the server
              has one; an unknown hint keeps its French, marked as such. */}
          <p className="pl-fine" lang={hintText ? language : 'fr'}>
            {hintText || prompt.hint_fr}
          </p>
          {textAnswerField({
            label: copy.answer_label,
            value: answer,
            rows: 5,
            disabled: pending,
            placeholder: copy.answer_placeholder,
            onChange: setAnswer,
            inputRef: fieldRef,
          })}
          {failure && <Notice tone="alert" live="alert">{copy[failure]}</Notice>}
        </PlacementFrame>
      </>
    );
  }

  /* ---- no level was measured ------------------------------------------ */
  if (status === 'unassessed') {
    return (
      <>
        <Head>
          <title>{`${copy.unassessed_title} · L’Atelier`}</title>
        </Head>
        <PlacementFrame
          foot={
            <>
              <Action
                tone="primary"
                pending={pending}
                pendingLabel={copy.opening}
                onClick={() => void api.startPlacement(true).then(setEnvelope)}
              >
                {copy.retry}
              </Action>
              <button type="button" className="av2-btn av2-btn--quiet" onClick={leave}>
                {copy.continue_without}
              </button>
            </>
          }
        >
          <span className="av2-label">{copy.kicker}</span>
          <h1 className="av2-headline av2-headline--screen">{copy.unassessed_title}</h1>
          <p className="pl-lead">{copy.unassessed_lead}</p>
          <Surface tone="outline">
            <p className="pl-fine">{copy.unassessed_fine}</p>
          </Surface>
          {failure && <Notice tone="alert" live="alert">{copy[failure]}</Notice>}
        </PlacementFrame>
      </>
    );
  }

  /* ---- the result ------------------------------------------------------ */
  const estimate = envelope?.estimate ?? null;
  const dimensions = Object.entries(estimate?.dimensions ?? {});
  return (
    <>
      <Head>
        <title>{`${copy.result_title_tab} · L’Atelier`}</title>
      </Head>
      <PlacementFrame
        foot={
          <Action tone="primary" onClick={leave} iconAfter={<ArrowRightIcon size={14} />}>
            {copy.open_first}
          </Action>
        }
      >
        <span className="av2-label">{copy.kicker}</span>
        <h1 className="av2-headline av2-headline--screen">
          {placementFill(copy.estimated, { level: envelope?.level ?? '—' })}
        </h1>
        <p className="pl-lead">
          {placementFill(copy.result_lead, {
            confidence: confidenceLabel(envelope?.confidence ?? 0, copy),
            n: estimate?.graded_turns ?? 0,
          })}
        </p>

        {dimensions.length > 0 && (
          <Surface tone="outline">
            <ul className="pl-dims">
              {dimensions.map(([key, value]) => (
                <li key={key} className="pl-dims__row">
                  <span>
                    {copy.dimensions[key as keyof PlacementCopy['dimensions']] ?? estimate?.dimension_labels?.[key] ?? key}
                  </span>
                  <span className="pl-dims__score">{value.toFixed(1)} / 4</span>
                </li>
              ))}
            </ul>
          </Surface>
        )}

        {Array.isArray(estimate?.evidence) && estimate.evidence.length > 0 && (
          <details className="pl-evidence">
            <summary>{copy.evidence_summary}</summary>
            <ul>
              {estimate.evidence.map((item, index) => (
                <li key={index}>
                  <span className="av2-label">{String(item.band ?? '')}</span>
                  <p lang="fr">{String(item.answer ?? '')}</p>
                  {/* The grader writes its evidence in French: content, marked so. */}
                  {item.evidence_fr && <p className="pl-fine" lang="fr">{String(item.evidence_fr)}</p>}
                </li>
              ))}
            </ul>
          </details>
        )}

      </PlacementFrame>
    </>
  );
}

function PlacementStyles() {
  return (
    <style jsx global>{`
      /* The screen scaffold, on Bilan.dc.html. A column that fills the shell, a
         body that carries the reading, and a foot that is the last thing in the
         flow rather than a bar floating over the tab bar. */
      .av2.pl-screen {
        display: flex;
        flex: 1 1 auto;
        flex-direction: column;
        /* 100%, not 100dvh: the masthead sits above this element, so a full
           viewport height here pushes the foot below the fold and back under
           the tab bar — which is the bug this screen exists to fix. The flex
           parent .app-route-shell already hands it the space that is left. */
        min-height: 100%;
        min-width: 0;
        background: var(--av2-paper);
      }
      /* Canvas note «note-pied»: the action does not hide under the tab bar.
         Below 760px the shell draws a fixed four-tab bar over this route, and
         the page frame this screen is mounted in already ends 96px above the
         viewport floor to clear it — measured in the pane at 390x844. So the
         screen adds no second reservation of its own (that is what pushed the
         foot back down under the bar), and the foot gives back its safe-area
         inset, because the bar below it already owns that inset. */
      @media (max-width: 760px) {
        .av2 .pl-foot {
          --av2-safe-bottom: 0px;
        }
      }
      .av2 .pl-body {
        flex: 1 1 auto;
        gap: 16px; /* design 16px between kicker, headline, body, note */
        width: 100%;
        max-width: 460px;
        margin: 0 auto;
        padding-top: calc(24px + env(safe-area-inset-top, 0px));
        padding-bottom: 20px;
      }
      .av2 .pl-foot {
        display: flex;
        flex-direction: column;
        align-items: stretch;
        gap: 4px; /* design 4px between the primary and the quiet action */
      }
      .av2 .pl-foot > * {
        width: 100%;
        max-width: 460px;
        margin-left: auto;
        margin-right: auto;
      }
      .av2 .pl-lead {
        margin: 0;
        font-size: var(--av2-t-body); /* design 15px */
        line-height: 1.45;
        color: var(--av2-ink-2);
      }
      .av2 .pl-fine {
        margin: 0;
        font-size: var(--av2-t-label);
        line-height: 1.45;
        color: var(--av2-muted);
      }
      .av2 .pl-dims {
        display: flex;
        flex-direction: column;
        gap: 8px;
        margin: 0;
        padding: 0;
        list-style: none;
      }
      .av2 .pl-dims__row {
        display: flex;
        gap: 12px;
        align-items: baseline;
        justify-content: space-between;
        font-size: var(--av2-t-label);
      }
      .av2 .pl-dims__score {
        font-variant-numeric: tabular-nums;
        color: var(--av2-muted);
      }
      .av2 .pl-evidence {
        font-size: var(--av2-t-label);
      }
      .av2 .pl-evidence > summary {
        min-height: var(--av2-tap);
        display: flex;
        align-items: center;
        cursor: pointer;
        color: var(--av2-muted);
      }
      .av2 .pl-evidence ul {
        display: flex;
        flex-direction: column;
        gap: 12px;
        margin: 0;
        padding: 0;
        list-style: none;
      }
      .av2 .pl-evidence p {
        margin: 2px 0 0;
      }
    `}</style>
  );
}
