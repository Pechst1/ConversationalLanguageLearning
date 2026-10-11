/**
 * WP-35 — «Votre dossier», the inspectable learner model.
 *
 * A thin transport shell around `DossierScreen`: it owns the envelope, the
 * pending flag and one sentence per failure, and nothing else. Its words are
 * chrome (WP-82): `dossier-copy.ts` in the chrome language. Every
 * decision about *what* to show lives in `dossier-state.ts`, so this file
 * cannot invent a belief the server did not send.
 *
 * Reached from Réglages («Votre dossier»). A Home entry is written out as a hook
 * in `docs/implementation/atelier-v2/WP-35-DOSSIER.md`; HomeScreen belongs to
 * another lease, so this page is deliberately reachable without it.
 */

import React from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';

import { DossierScreen } from '@/components/atelier-v2/dossier';
import { dossierCopy } from '@/components/atelier-v2/dossier/dossier-copy';
import { AtelierV2Root } from '@/components/atelier-v2/ui';
import { useChromeLanguage } from '@/lib/learner-language';
import api, { type DossierEnvelope } from '@/services/api';

const HOME = '/atelier';
/** WP-45: the level card's quiet way to the bilan. `rerun=1` because a learner
 *  who already declined once is on this screen on purpose. */
const PLACEMENT = '/placement?rerun=1';

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

export default function DossierPage() {
  const router = useRouter();
  const language = useChromeLanguage();
  const copy = dossierCopy(language);
  const [envelope, setEnvelope] = React.useState<DossierEnvelope | null>(null);
  const [claim, setClaim] = React.useState<DossierEnvelope | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [pending, setPending] = React.useState(false);
  const [loadFailed, setLoadFailed] = React.useState(false);
  // `{ message: null }` is a failure the server did not word: the page says it.
  const [failure, setFailure] = React.useState<{ message: string | null } | null>(null);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      setEnvelope(await api.getDossier());
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

  const run = React.useCallback(async (call: () => Promise<DossierEnvelope>) => {
    setPending(true);
    setFailure(null);
    try {
      const next = await call();
      setClaim(next);
      // A verification answers with the refreshed model, so the page behind the
      // panel is already up to date when the learner closes it.
      if (next.dossier) setEnvelope({ ...next, check: null, verdict: null });
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
        <title>{copy.page_title}</title>
      </Head>
      <AtelierV2Root as="main" language={language} className="av2-screen ds-screen" aria-label={copy.page_label}>
        <DossierScreen
            dossier={envelope?.dossier ?? null}
            check={claim?.check ?? null}
            verdict={claim?.verdict ?? null}
            loading={loading}
            error={loadFailed ? copy.load_failed : null}
            pending={pending}
            failure={failure ? failure.message ?? copy.generic_failure : null}
            onClaim={(kind, targetId) => void run(() => api.openDossierClaim(kind, targetId))}
            onVerify={(kind, targetId, answers) =>
              void run(() => api.verifyDossierClaim(kind, targetId, answers))
            }
            onCloseClaim={() => {
              setClaim(null);
              setFailure(null);
            }}
            onLeave={leave}
            onOpenPlacement={() => void router.push(PLACEMENT)}
          />
        <DossierStyles />
      </AtelierV2Root>
    </>
  );
}


/* ===========================================================================
   WP-45 — «Votre dossier» on `Dossier.dc.html`.

   Page-scoped `.av2 .ds-*` only, tokens only, no hard-coded colour: dark mode
   is inherited from the tokens rather than re-implemented here. Sizes are rem
   so the app's text-size setting moves them; the design's px are in comments.
   =========================================================================== */
function DossierStyles() {
  return (
    <style jsx global>{`
      /* The screen scaffold. A column that fills the shell, a body that
         scrolls, and — on the states that carry an action — a foot that is the
         last thing in the flow rather than a bar floating over the tab bar.
         The foot is the shared ScreenFoot (WP-43). */
      .av2.ds-screen {
        display: flex;
        flex: 1 1 auto;
        flex-direction: column;
        min-height: 100%;
        min-width: 0;
        background: var(--av2-paper);
      }
      /* Canvas note «note-pied»: the action does not hide under the tab bar.
         Below 760px the route shell reserves the tab bar's height once
         (WP-43), so this screen adds no reservation of its own; the foot gives
         back its safe-area inset because the bar below it already owns it. */
      @media (max-width: 760px) {
        .av2 .ds-foot {
          --av2-safe-bottom: 0px;
        }
      }
      .av2 .ds-body {
        flex: 1 1 auto;
        gap: 12px;
        width: 100%;
        max-width: 460px;
        margin: 0 auto;
        padding-top: 24px;
        padding-bottom: 20px;
      }
      .av2 .ds-foot {
        display: flex;
        flex-direction: column;
        align-items: stretch;
        gap: 4px;
      }
      .av2 .ds-foot > * {
        width: 100%;
        max-width: 460px;
        margin-left: auto;
        margin-right: auto;
      }

      .av2 .ds-card {
        display: flex;
        flex-direction: column;
        gap: 6px;
        min-width: 0;
      }
      .av2 .ds-fine {
        margin: 0;
        font-size: var(--av2-t-label);
        line-height: 1.45;
        color: var(--av2-muted);
      }

      /* The level: one 46px serif figure, and the sentence that says who said
         so. They wrap onto two lines rather than shrinking at large text. */
      .av2 .ds-level {
        display: flex;
        flex-wrap: wrap;
        align-items: baseline;
        gap: 4px 10px;
      }
      .av2 .ds-level__value {
        font-family: var(--av2-serif);
        font-style: italic;
        font-weight: 600;
        font-size: calc(var(--av2-t-display) * 1.35); /* design 46px, on the display token */
        line-height: 0.9;
        color: var(--av2-ink);
      }
      .av2 .ds-level__source {
        font-size: var(--av2-t-label);
        line-height: 1.45;
        color: var(--av2-ink-2);
      }

      /* A dated reference to the work behind a belief. Underlined like the
         artboard, and a span rather than an anchor: nothing in this app opens
         a past séance, and a dead link is a worse promise than a reference. */
      .av2 .ds-ref {
        font-size: var(--av2-t-meta);
        font-weight: 600;
        color: var(--av2-ink-2);
        text-decoration: underline;
        text-underline-offset: 3px;
      }

      /* Capability rows: serif name, state on the right, hairline separators. */
      .av2 .ds-caps {
        display: flex;
        flex-direction: column;
        margin: 6px 0 0;
        padding: 0;
        list-style: none;
      }
      .av2 .ds-cap {
        display: flex;
        flex-wrap: wrap;
        align-items: baseline;
        justify-content: space-between;
        gap: 2px 12px;
        padding: 8px 0;
        border-top: 1px solid var(--av2-line);
      }
      .av2 .ds-cap__name {
        font-family: var(--av2-serif);
        font-style: italic;
        font-size: var(--av2-t-action); /* design 17px */
        line-height: 1.25;
        color: var(--av2-ink);
        overflow-wrap: anywhere;
      }
      .av2 .ds-cap__right {
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        gap: 2px;
        text-align: right;
      }
      .av2 .ds-cap__state {
        font-size: var(--av2-t-meta);
        font-weight: 700;
        color: var(--av2-muted);
      }

      /* Three counters, each a figure over the noun it counts. Never a ratio:
         the denominator is the sentence under them (WP-39 D-5). */
      .av2 .ds-counters {
        display: flex;
        flex-wrap: wrap;
        gap: 8px 18px;
        margin-top: 2px;
      }
      .av2 .ds-counter,
      .av2 .ds-stock {
        display: flex;
        min-width: 0;
      }
      .av2 .ds-counter {
        flex-direction: column;
        gap: 2px;
      }
      .av2 .ds-counter__value,
      .av2 .ds-stock__value {
        font-family: var(--av2-serif);
        font-style: italic;
        font-weight: 600;
        font-size: calc(var(--av2-t-title) * 1.1667); /* design 28px, on the title token */
        line-height: 1;
        color: var(--av2-ink);
        font-variant-numeric: tabular-nums;
      }
      .av2 .ds-counter__label {
        font-size: var(--av2-t-meta);
        font-weight: 700;
        color: var(--av2-muted);
      }
      .av2 .ds-stock {
        flex-wrap: wrap;
        align-items: baseline;
        gap: 4px 8px;
      }
      .av2 .ds-stock__unit {
        font-size: var(--av2-t-label);
        line-height: 1.45;
        color: var(--av2-ink-2);
      }
      .av2 .ds-chip {
        align-self: flex-start;
        margin-top: 4px;
      }

      /* Disclosures: the detail behind a counter, and the words a learner may
         push back on. Both closed by default — the page is a summary first. */
      .av2 .ds-group {
        display: flex;
        flex-direction: column;
        gap: 6px;
        margin-top: 10px;
      }
      .av2 .ds-rows {
        display: flex;
        flex-direction: column;
        gap: 10px;
        margin: 8px 0 0;
        padding: 0;
        list-style: none;
      }
      /* Label and value sit on one line while they fit and wrap onto two when
         the text size grows, so nothing is truncated at large Dynamic Type. */
      .av2 .ds-row {
        display: flex;
        flex-wrap: wrap;
        gap: 2px 10px;
        align-items: baseline;
        justify-content: space-between;
        font-size: var(--av2-t-label);
      }
      .av2 .ds-row--stacked {
        flex-direction: column;
        align-items: flex-start;
      }
      .av2 .ds-row__label {
        font-weight: 600;
        color: var(--av2-ink);
      }
      .av2 .ds-row__value {
        color: var(--av2-ink);
      }
      .av2 .ds-item {
        display: flex;
        flex-direction: column;
        gap: 6px;
        margin-top: 12px;
      }
    `}</style>
  );
}
