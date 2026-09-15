/**
 * WP-25 — «Trouvons votre niveau», the five-minute placement.
 *
 * Offered once, right after the first sign-in, and re-runnable from Réglages
 * (`/placement?rerun=1`). Four to six French prompts, each drawn from the band
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
 * French chrome, one primary action per state, dark-capable by inheritance.
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
  Skeleton,
  StepProgress,
  Surface,
  textAnswerField,
} from '@/components/atelier-v2/ui';
import api, { type PlacementEnvelope } from '@/services/api';

const HOME = '/atelier';

/** Turned into a sentence rather than a percentage: a learner reads words. */
function confidenceLabel(confidence: number): string {
  if (confidence >= 0.75) return 'estimation solide';
  if (confidence >= 0.55) return 'estimation raisonnable';
  return 'estimation provisoire';
}

/** The screen scaffold, on `Bilan.dc.html`: a body that holds the reading and
 *  a foot that holds the actions. The foot is a sibling *after* the body in the
 *  flow — not a fixed bar — so on a 390×844 phone the primary action sits above
 *  the four-tab bar instead of under it.
 *
 *  TODO(WP-43): swap the wrapper for the shared `ScreenFoot` once it lands; the
 *  class it wraps, `.av2-screen__foot`, is already the one that component
 *  carries. */
function PlacementFrame({
  children,
  foot,
}: {
  children: React.ReactNode;
  foot?: React.ReactNode;
}) {
  return (
    <AtelierV2Root as="main" className="av2-screen pl-screen" aria-label="Bilan de niveau">
      <div className="av2-screen__body pl-body">{children}</div>
      {foot ? <div className="av2-screen__foot pl-foot">{foot}</div> : null}
      <PlacementStyles />
    </AtelierV2Root>
  );
}

export default function PlacementPage() {
  const router = useRouter();
  const rerun = router.query.rerun === '1';
  const [envelope, setEnvelope] = React.useState<PlacementEnvelope | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [pending, setPending] = React.useState(false);
  const [answer, setAnswer] = React.useState('');
  const [failure, setFailure] = React.useState<string | null>(null);
  const fieldRef = React.useRef<HTMLTextAreaElement | null>(null);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      setEnvelope(rerun ? await api.startPlacement(true) : await api.getPlacementState());
    } catch {
      setFailure('Le bilan n’a pas pu être ouvert. Réessayez dans un instant.');
    } finally {
      setLoading(false);
    }
  }, [rerun]);

  React.useEffect(() => {
    if (!router.isReady) return;
    void load();
  }, [load, router.isReady]);

  const leave = React.useCallback(() => {
    void router.replace(HOME);
  }, [router]);

  const begin = async () => {
    setPending(true);
    setFailure(null);
    try {
      setEnvelope(await api.startPlacement(false));
    } catch {
      setFailure('Le bilan n’a pas pu être ouvert. Réessayez dans un instant.');
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
      setFailure('Votre réponse n’est pas partie. Elle est toujours là — réessayez.');
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
      setFailure('Le bilan n’a pas pu être clos. Réessayez dans un instant.');
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
          <title>Trouvons votre niveau · L’Atelier</title>
        </Head>
        <PlacementFrame
          foot={
            <>
              <Action
                tone="primary"
                pending={pending}
                pendingLabel="Ouverture…"
                onClick={begin}
                iconAfter={<ArrowRightIcon size={14} />}
              >
                Commencer le bilan
              </Action>
              <button type="button" className="av2-btn av2-btn--quiet" onClick={decline}>
                Passer pour l’instant
              </button>
            </>
          }
        >
          <span className="av2-label">L’Atelier · Bilan de niveau</span>
          <h1 className="av2-headline av2-headline--screen">Trouvons votre niveau</h1>
          <p className="pl-lead">
            Quatre à six questions, en français, cinq minutes. Vos réponses fixent le niveau
            de vos premières séances — pour que la première semaine soit à votre mesure.
          </p>
          <Surface tone="outline">
            <p className="pl-fine">
              Sans bilan, nous gardons le niveau que vous avez indiqué à l’inscription.
              Vous pouvez faire ce bilan plus tard depuis les Réglages.
            </p>
          </Surface>
          {failure && <Notice tone="alert" live="alert">{failure}</Notice>}
        </PlacementFrame>
      </>
    );
  }

  /* ---- the conversation ------------------------------------------------ */
  if (status === 'in_progress' && envelope?.prompt) {
    const prompt = envelope.prompt;
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
          <title>Bilan de niveau · L’Atelier</title>
        </Head>
        <PlacementFrame
          foot={
            <>
              <Action
                tone="primary"
                pending={pending}
                pendingLabel="Lecture…"
                disabled={!answer.trim()}
                onClick={send}
                iconAfter={<ArrowRightIcon size={14} />}
              >
                Envoyer
              </Action>
              <button type="button" className="av2-btn av2-btn--quiet" onClick={stopEarly}>
                Arrêter le bilan
              </button>
            </>
          }
        >
          <span className="av2-label">Bilan de niveau</span>
          <StepProgress
            steps={steps}
            label="Progression du bilan"
            caption={`Question ${prompt.turns_so_far + 1}`}
          />
          <h1 className="av2-headline av2-headline--screen" lang="fr">
            {prompt.prompt_fr}
          </h1>
          <p className="pl-fine">{prompt.hint_fr}</p>
          {textAnswerField({
            label: 'Votre réponse, en français',
            value: answer,
            rows: 5,
            disabled: pending,
            placeholder: 'Écrivez ici…',
            onChange: setAnswer,
            inputRef: fieldRef,
          })}
          {failure && <Notice tone="alert" live="alert">{failure}</Notice>}
        </PlacementFrame>
      </>
    );
  }

  /* ---- no level was measured ------------------------------------------ */
  if (status === 'unassessed') {
    return (
      <>
        <Head>
          <title>Niveau non évalué · L’Atelier</title>
        </Head>
        <PlacementFrame
          foot={
            <>
              <Action
                tone="primary"
                pending={pending}
                pendingLabel="Ouverture…"
                onClick={() => void api.startPlacement(true).then(setEnvelope)}
              >
                Refaire le bilan
              </Action>
              <button type="button" className="av2-btn av2-btn--quiet" onClick={leave}>
                Continuer sans bilan
              </button>
            </>
          }
        >
          <span className="av2-label">Bilan de niveau</span>
          <h1 className="av2-headline av2-headline--screen">Niveau non évalué</h1>
          <p className="pl-lead">
            La correction n’a pas répondu, donc nous n’avons rien mesuré. Nous préférons vous
            le dire plutôt que d’annoncer un niveau que personne n’a vérifié.
          </p>
          <Surface tone="outline">
            <p className="pl-fine">
              Le niveau que vous avez indiqué à l’inscription reste en place. Vos réponses
              n’ont pas été perdues : elles ne portent simplement aucune note.
            </p>
          </Surface>
          {failure && <Notice tone="alert" live="alert">{failure}</Notice>}
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
        <title>Votre niveau estimé · L’Atelier</title>
      </Head>
      <PlacementFrame
        foot={
          <Action tone="primary" onClick={leave} iconAfter={<ArrowRightIcon size={14} />}>
            Ouvrir ma première séance
          </Action>
        }
      >
        <span className="av2-label">Bilan de niveau</span>
        <h1 className="av2-headline av2-headline--screen">
          Niveau estimé&nbsp;: {envelope?.level ?? '—'}
        </h1>
        <p className="pl-lead">
          {confidenceLabel(envelope?.confidence ?? 0)}, sur {estimate?.graded_turns ?? 0} réponses
          corrigées. Ce niveau guide vos premières séances ; il bougera dès que vos exercices
          en diront davantage.
        </p>

        {dimensions.length > 0 && (
          <Surface tone="outline">
            <ul className="pl-dims">
              {dimensions.map(([key, value]) => (
                <li key={key} className="pl-dims__row">
                  <span>{estimate?.dimension_labels?.[key] ?? key}</span>
                  <span className="pl-dims__score">{value.toFixed(1)} / 4</span>
                </li>
              ))}
            </ul>
          </Surface>
        )}

        {Array.isArray(estimate?.evidence) && estimate.evidence.length > 0 && (
          <details className="pl-evidence">
            <summary>Sur quoi repose cette estimation</summary>
            <ul>
              {estimate.evidence.map((item, index) => (
                <li key={index}>
                  <span className="av2-label">{String(item.band ?? '')}</span>
                  <p lang="fr">{String(item.answer ?? '')}</p>
                  {item.evidence_fr && <p className="pl-fine">{String(item.evidence_fr)}</p>}
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
