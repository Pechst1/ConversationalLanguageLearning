/**
 * WP-35 — «Votre dossier», the inspectable learner model.
 *
 * A thin transport shell around `DossierScreen`: it owns the envelope, the
 * pending flag and one French sentence per failure, and nothing else. Every
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
import { AtelierV2Root } from '@/components/atelier-v2/ui';
import api, { type DossierEnvelope } from '@/services/api';

const HOME = '/atelier';

/** The server sends a French sentence with every refusal; this is the fallback. */
const GENERIC_FAILURE = 'Cette action n’a pas abouti. Réessayez dans un instant.';

function messageFor(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (detail && typeof detail === 'object' && 'message_fr' in detail) {
    return String((detail as { message_fr?: unknown }).message_fr || GENERIC_FAILURE);
  }
  if (typeof detail === 'string' && detail.trim()) return detail;
  return GENERIC_FAILURE;
}

export default function DossierPage() {
  const router = useRouter();
  const [envelope, setEnvelope] = React.useState<DossierEnvelope | null>(null);
  const [claim, setClaim] = React.useState<DossierEnvelope | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [pending, setPending] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [failure, setFailure] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      setEnvelope(await api.getDossier());
      setError(null);
    } catch {
      setError('Le dossier n’a pas pu être ouvert. Réessayez dans un instant.');
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
      setFailure(messageFor(caught));
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
        <title>Votre dossier · L’Atelier</title>
      </Head>
      <AtelierV2Root as="main" className="ds-screen" aria-label="Votre dossier">
        <div className="ds-screen__column">
          <DossierScreen
            dossier={envelope?.dossier ?? null}
            check={claim?.check ?? null}
            verdict={claim?.verdict ?? null}
            loading={loading}
            error={error}
            pending={pending}
            failure={failure}
            onClaim={(kind, targetId) => void run(() => api.openDossierClaim(kind, targetId))}
            onVerify={(kind, targetId, answers) =>
              void run(() => api.verifyDossierClaim(kind, targetId, answers))
            }
            onCloseClaim={() => {
              setClaim(null);
              setFailure(null);
            }}
            onLeave={leave}
          />
        </div>
        <DossierStyles />
      </AtelierV2Root>
    </>
  );
}

function DossierStyles() {
  return (
    <style jsx global>{`
      .av2.ds-screen {
        display: flex;
        min-height: 100dvh;
        justify-content: center;
        padding: calc(20px + env(safe-area-inset-top, 0px)) 18px
          calc(20px + env(safe-area-inset-bottom, 0px));
        background: var(--av2-paper);
      }
      .av2 .ds-screen__column {
        display: flex;
        flex: 1 1 auto;
        flex-direction: column;
        gap: 14px;
        max-width: 460px;
        min-width: 0;
      }
      .av2 .ds-lead {
        margin: 0;
        font-size: var(--av2-t-body);
        line-height: 1.5;
        color: var(--av2-ink);
      }
      .av2 .ds-fine {
        margin: 0;
        font-size: var(--av2-t-label);
        line-height: 1.45;
        color: var(--av2-muted);
      }
      /* Keeps the actions at the foot of the flow rather than pinning them, so a
         software keyboard can never cover the only way forward. */
      .av2 .ds-spacer {
        flex: 1 1 auto;
        min-height: 12px;
      }
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
