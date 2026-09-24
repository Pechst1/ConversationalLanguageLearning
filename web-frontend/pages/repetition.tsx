/**
 * WP-31 — «Répétition», rehearsing a real upcoming situation.
 *
 * A thin transport shell around `RehearsalScreen`: it owns the envelope, the
 * pending flag and one sentence per failure, and nothing else. Its words are
 * chrome (WP-82): `rehearsal-copy.ts` in the chrome language. Every
 * decision about *what* to show is in `rehearsal-state.ts`, so this file cannot
 * invent a state the server did not send.
 *
 * Reached from Réglages («Répéter une vraie situation»). The Home entry and the
 * day-before push are written out as hooks in
 * `docs/implementation/atelier-v2/WP-31-REHEARSAL.md`; their files are leased
 * elsewhere, so this page is deliberately reachable without them.
 *
 * WP-45 puts it on `docs/design-reference/nouvelles-pages-2026-09-15/`
 * `Repetition.dc.html`: the shell is the av2 screen scaffold, and the actions
 * live in a foot below the body rather than in a bar over the tab bar.
 */

import React from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';

import { RehearsalScreen } from '@/components/atelier-v2/rehearsal';
import type { DebriefOutcome } from '@/components/atelier-v2/rehearsal';
import { rehearsalCopy } from '@/components/atelier-v2/rehearsal/rehearsal-copy';
import { AtelierV2Root } from '@/components/atelier-v2/ui';
import { useChromeLanguage } from '@/lib/learner-language';
import api, { type RehearsalEnvelope } from '@/services/api';

const HOME = '/atelier';

/** The server sends a French sentence with most refusals; `null` means the
 *  page's own fallback (`generic_failure`) in the chrome language. */
function messageFor(error: unknown): string | null {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (detail && typeof detail === 'object' && 'message_fr' in detail) {
    const message = (detail as { message_fr?: unknown }).message_fr;
    return message ? String(message) : null;
  }
  if (typeof detail === 'string' && detail.trim()) return detail;
  return null;
}

export default function RepetitionPage() {
  const router = useRouter();
  const language = useChromeLanguage();
  const copy = rehearsalCopy(language);
  const [envelope, setEnvelope] = React.useState<RehearsalEnvelope | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [pending, setPending] = React.useState(false);
  const [loadFailed, setLoadFailed] = React.useState(false);
  // `{ message: null }` is a failure the server did not word: the page says it.
  const [failure, setFailure] = React.useState<{ message: string | null } | null>(null);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      setEnvelope(await api.getRehearsalState());
      setLoadFailed(false);
    } catch {
      setLoadFailed(true);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    if (!router.isReady) return;
    void load();
  }, [load, router.isReady]);

  const run = React.useCallback(async (call: () => Promise<RehearsalEnvelope>) => {
    setPending(true);
    setFailure(null);
    try {
      setEnvelope(await call());
    } catch (caught) {
      setFailure({ message: messageFor(caught) });
    } finally {
      setPending(false);
    }
  }, []);

  const leave = React.useCallback(() => {
    void router.push(HOME);
  }, [router]);

  return (
    <>
      <Head>
        <title>Répétition · L’Atelier</title>
      </Head>
      <AtelierV2Root as="main" language={language} className="av2-screen rp-screen" aria-label="Répétition">
        <RehearsalScreen
          envelope={envelope}
          loading={loading}
          error={loadFailed ? copy.load_failed : null}
          pending={pending}
          failure={failure ? failure.message ?? copy.generic_failure : null}
          onDeclare={(declaration) => void run(() => api.declareRehearsal(declaration))}
          onPrepare={(id) => void run(() => api.prepareRehearsal(id))}
          onRevealPhrases={(id) => void run(() => api.revealRehearsalPhrases(id))}
          onSendTurn={(id, text, index) => void run(() => api.sendRehearsalTurn(id, text, index))}
          onDebrief={(id, outcome: DebriefOutcome, line) =>
            void run(() => api.debriefRehearsal(id, outcome, line))
          }
          onAbandon={(id) => void run(() => api.abandonRehearsal(id))}
          onLeave={leave}
        />
        <RehearsalStyles />
      </AtelierV2Root>
    </>
  );
}

function RehearsalStyles() {
  return (
    <style jsx global>{`
      /* The screen scaffold, on Repetition.dc.html. A column that fills the
         shell, a body that carries the reading, and a foot that is the last
         thing in the flow rather than a bar floating over the tab bar. */
      .av2.rp-screen {
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
        .av2 .rp-foot {
          --av2-safe-bottom: 0px;
        }
      }
      .av2 .rp-body {
        flex: 1 1 auto;
        gap: 16px; /* design 16px between kicker, headline, body, field, note */
        width: 100%;
        max-width: 460px;
        margin: 0 auto;
        padding-top: calc(24px + env(safe-area-inset-top, 0px));
        padding-bottom: 20px;
      }
      .av2 .rp-foot {
        display: flex;
        flex-direction: column;
        align-items: stretch;
        gap: 4px; /* design 4px between the primary and the quiet action */
      }
      .av2 .rp-foot > * {
        width: 100%;
        max-width: 460px;
        margin-left: auto;
        margin-right: auto;
      }
      /* «Ce qui vous attend» — the one field the artboard draws taller than the
         system default. Everything else about it (16px, card ground, radius 16,
         the 12px label above) is the shared av2 field. */
      .av2 .rp-declare .av2-field__control {
        min-height: 120px;
      }
      .av2 .rp-lead {
        margin: 0;
        font-size: var(--av2-t-body); /* design 15px */
        line-height: 1.45;
        color: var(--av2-ink-2);
      }
      .av2 .rp-fine {
        margin: 0;
        font-size: var(--av2-t-label);
        line-height: 1.45;
        color: var(--av2-muted);
      }
      .av2 .rp-objective {
        margin: 0;
        font-size: var(--av2-t-body);
        line-height: 1.45;
      }
      .av2 .rp-facts,
      .av2 .rp-phrases,
      .av2 .rp-transcript {
        display: flex;
        flex-direction: column;
        gap: 8px;
        margin: 8px 0 0;
        padding: 0;
        list-style: none;
        font-size: var(--av2-t-label);
      }
      .av2 .rp-phrases > li {
        display: flex;
        flex-direction: column;
        gap: 2px;
      }
      .av2 .rp-transcript {
        gap: 10px;
        margin: 0;
      }
      .av2 .rp-transcript p {
        margin: 2px 0 0;
        font-size: var(--av2-t-body);
        line-height: 1.45;
      }
      .av2 .rp-transcript__row--you {
        padding-left: 12px;
        border-left: 2px solid var(--av2-line);
      }
      .av2 .rp-transcript__row--fix p {
        font-size: var(--av2-t-label);
      }
      .av2 .rp-choices {
        display: flex;
        flex-direction: column;
        gap: 8px;
      }
      .av2 .rp-choice {
        display: flex;
        flex-direction: column;
        gap: 2px;
        min-height: var(--av2-tap);
        padding: 10px 14px;
        border: 1px solid var(--av2-line);
        border-radius: 16px;
        background: transparent;
        color: var(--av2-ink);
        text-align: left;
        cursor: pointer;
      }
      /* Status is never colour alone: the chosen answer also carries a mark in
         its label weight and a border the theme cannot flatten. */
      .av2 .rp-choice--on {
        border-color: var(--av2-ink);
        box-shadow: inset 0 0 0 1px var(--av2-ink);
      }
      .av2 .rp-choice__label {
        font-weight: 600;
      }
      .av2 .rp-choice--on .rp-choice__label::after {
        content: ' ·';
      }
    `}</style>
  );
}
