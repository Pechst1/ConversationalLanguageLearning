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

function PlacementFrame({ children }: { children: React.ReactNode }) {
  return (
    <AtelierV2Root as="main" className="pl-screen" aria-label="Bilan de niveau">
      <div className="pl-screen__column">{children}</div>
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
        <PlacementFrame>
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
          <div className="pl-spacer" aria-hidden="true" />
          <Action tone="primary" pending={pending} pendingLabel="Ouverture…" onClick={begin}>
            Commencer le bilan
          </Action>
          <button type="button" className="av2-btn av2-btn--quiet" onClick={decline}>
            Passer pour l’instant
          </button>
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
        <PlacementFrame>
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
          <div className="pl-spacer" aria-hidden="true" />
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
        <PlacementFrame>
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
          <div className="pl-spacer" aria-hidden="true" />
          <Action tone="primary" pending={pending} pendingLabel="Ouverture…" onClick={() => void api.startPlacement(true).then(setEnvelope)}>
            Refaire le bilan
          </Action>
          <button type="button" className="av2-btn av2-btn--quiet" onClick={leave}>
            Continuer sans bilan
          </button>
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
      <PlacementFrame>
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

        <div className="pl-spacer" aria-hidden="true" />
        <Action tone="primary" onClick={leave} iconAfter={<ArrowRightIcon size={14} />}>
          Ouvrir ma première séance
        </Action>
      </PlacementFrame>
    </>
  );
}

function PlacementStyles() {
  return (
    <style jsx global>{`
      .av2.pl-screen {
        display: flex;
        min-height: 100dvh;
        justify-content: center;
        padding: calc(20px + env(safe-area-inset-top, 0px)) 18px
          calc(20px + env(safe-area-inset-bottom, 0px));
        background: var(--av2-paper);
      }
      .av2 .pl-screen__column {
        display: flex;
        flex: 1 1 auto;
        flex-direction: column;
        gap: 14px;
        max-width: 460px;
        min-width: 0;
      }
      .av2 .pl-lead {
        margin: 0;
        font-size: var(--av2-t-body);
        line-height: 1.5;
        color: var(--av2-ink);
      }
      .av2 .pl-fine {
        margin: 0;
        font-size: var(--av2-t-small);
        line-height: 1.45;
        color: var(--av2-ink-quiet);
      }
      /* Holds the actions at the foot of the flow rather than pinning them, so
         a software keyboard can never cover the only way forward (AuthShell
         solves the same problem the same way). */
      .av2 .pl-spacer {
        flex: 1 1 auto;
        min-height: 12px;
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
        font-size: var(--av2-t-small);
      }
      .av2 .pl-dims__score {
        font-variant-numeric: tabular-nums;
        color: var(--av2-ink-quiet);
      }
      .av2 .pl-evidence {
        font-size: var(--av2-t-small);
      }
      .av2 .pl-evidence > summary {
        min-height: var(--av2-tap);
        display: flex;
        align-items: center;
        cursor: pointer;
        color: var(--av2-ink-quiet);
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
