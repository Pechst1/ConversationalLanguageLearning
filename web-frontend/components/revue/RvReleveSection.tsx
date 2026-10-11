/**
 * WP-119 phase 3 · «Le Papier» in Le Relevé — the section after «Le Registre»
 * (design §2 and §3.6 `#releve`; owner decision §12.1: the chrome label is
 * «Le Papier»).
 *
 * It fetches its own data (`GET /revue/releve`, `lib/revue-releve.ts`) and
 * renders NOTHING while loading, when the Revue is switched off, when the read
 * fails, or when no Papier was ever filed: Le Relevé is exactly what it was.
 * Otherwise: `NbSectionHead` «Le Papier · N coupures», then one
 * `RvReleveEntry` per Papier, newest first. Only the newest is open; older ones
 * collapse to their title and «Ton titre · 4 mots · 2 faits». An entry named by
 * the URL hash (`#revue-2026-W40`) opens and is scrolled to once the data is in.
 *
 * Under the head, three doors, each drawn only when it has something behind it:
 * La Carte's badge (WP-120 D), «N mots t'attendent sur la carte» → `/carte` when the
 * map has due words (WP-121 A.4), and «Le Correcteur · un brouillon t'attend» when
 * the week has a draft to correct (WP-122 §4). The badge and the due line share ONE
 * `GET /revue/carte`.
 */

import React, { useEffect, useState } from 'react';
import Link from 'next/link';

import { NbSectionHead } from '@/components/cahiers/CahierV2';
import { CarteBadge, CARTE_HREF } from '@/components/carte/CarteBadge';
import { correcteurCopy } from '@/components/correcteur/correcteur-copy';
import { carteClient as defaultCarteClient, type CarteClient } from '@/lib/carte-api';
import { correcteurClient as defaultCorrecteurClient, type CorrecteurClient } from '@/lib/correcteur-api';
import { correcteurHref, correcteurWaiting } from '@/lib/correcteur-une';
import { releveAnchor, revueReleveClient, type ReleveClient, type RvReleveEntryData } from '@/lib/revue-releve';

import { count, releveCopy } from './releve-copy';
import { revueCopy } from './revue-copy';
import { RvReleveEntry } from './RvReleveEntry';

export const RELEVE_SECTION_ID = 'revue';

export type RvReleveSectionProps = {
  /** Given: drawn as is (tests, previews). Absent: fetched from the API. */
  entries?: RvReleveEntryData[];
  client?: ReleveClient;
  /** The chrome language of the labels (the French stays French). */
  language?: unknown;
  now?: Date;
  /** La Carte's pin count and due words; given: drawn as is, absent: one `GET /revue/carte`. */
  carte?: CarteSummary;
  carteClient?: CarteClient;
  /** The Correcteur's waiting draft; given (or null): drawn as is, absent: `GET /revue/correcteur/week`. */
  draft?: { id: string; titleFr: string } | null;
  correcteurClient?: CorrecteurClient;
};

/** What the Relevé needs of La Carte: the badge's pin count and the due words. */
export type CarteSummary = { pins: number; due: number };

/** The one carte read, as the section's doors use it (a disabled Revue is all zero). */
export function carteSummary(result: { enabled: boolean; view?: { counts: { france: number }; dueTotal: number } } | null | undefined): CarteSummary {
  if (!result || !result.enabled || !result.view) return { pins: 0, due: 0 };
  return { pins: result.view.counts.france, due: Math.max(0, result.view.dueTotal) };
}

/** Which entries start open: the newest, plus the one the URL names. */
export function initialOpen(entries: RvReleveEntryData[], hash: string | null = null): Set<string> {
  const open = new Set<string>();
  if (entries[0]) open.add(entries[0].sessionId);
  const wanted = (hash || '').replace(/^#/, '');
  const named = wanted ? entries.find((entry) => releveAnchor(entry.period) === wanted) : null;
  if (named) open.add(named.sessionId);
  return open;
}

function currentHash(): string | null {
  return typeof window === 'undefined' ? null : window.location.hash || null;
}

export function RvReleveSection({
  entries: given,
  client,
  language = 'fr',
  now,
  carte: givenCarte,
  carteClient,
  draft: givenDraft,
  correcteurClient,
}: RvReleveSectionProps) {
  const [entries, setEntries] = useState<RvReleveEntryData[]>(given ?? []);
  const [open, setOpen] = useState<Set<string>>(() => initialOpen(given ?? []));
  const [carte, setCarte] = useState<CarteSummary | null>(givenCarte ?? null);
  const [draft, setDraft] = useState<{ id: string; titleFr: string } | null>(givenDraft ?? null);

  // One read of La Carte for the badge and the due line.
  useEffect(() => {
    if (givenCarte) {
      setCarte(givenCarte);
      return undefined;
    }
    let alive = true;
    (carteClient ?? defaultCarteClient())
      .carte()
      .then((result) => {
        if (alive) setCarte(carteSummary(result));
      })
      .catch(() => {
        // A failing read is a missing door, never an error on the Relevé.
      });
    return () => {
      alive = false;
    };
  }, [givenCarte, carteClient]);

  useEffect(() => {
    if (givenDraft !== undefined) {
      setDraft(givenDraft);
      return undefined;
    }
    let alive = true;
    (correcteurClient ?? defaultCorrecteurClient())
      .week()
      .then((result) => {
        if (alive) setDraft(correcteurWaiting(result));
      })
      .catch(() => {
        // The Correcteur off or failing: no row.
      });
    return () => {
      alive = false;
    };
  }, [givenDraft, correcteurClient]);

  useEffect(() => {
    if (given) return undefined;
    let alive = true;
    (client ?? revueReleveClient())
      .releve()
      .then((result) => {
        if (!alive || !result.enabled) return;
        setEntries(result.entries);
        setOpen(initialOpen(result.entries, currentHash()));
      })
      .catch(() => {
        // A failing read is a missing section, never an error on the Relevé.
      });
    return () => {
      alive = false;
    };
  }, [given, client]);

  // The anchor: the entry did not exist when the browser read the hash.
  useEffect(() => {
    const hash = currentHash();
    if (!hash || !hash.startsWith('#revue') || entries.length === 0) return;
    const target = typeof document === 'undefined' ? null : document.getElementById(hash.slice(1));
    target?.scrollIntoView?.({ block: 'start' });
  }, [entries]);

  if (entries.length === 0) return null;
  const copy = revueCopy(language);
  const releve = releveCopy(language);
  const toggle = (id: string) =>
    setOpen((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  return (
    <section className="nb-rv__sec" id={RELEVE_SECTION_ID} aria-label={releve.section_title} data-revue-releve="">
      <NbSectionHead t={releve.section_title} n={count(releve, 'clippings', entries.length)} />
      {/* WP-120 phase D: the door onto La Carte, with the pin count (nothing when 0). */}
      {carte && carte.pins > 0 && <CarteBadge count={carte.pins} language={typeof language === 'string' ? language : null} />}
      {/* WP-121 A.4: the words due on the map. */}
      {carte && carte.due > 0 && (
        <Link href={CARTE_HREF} className="nb-rv__door" data-releve-due={carte.due}>
          {count(releve, 'carte_due', carte.due)}
        </Link>
      )}
      {/* WP-122 §4: a draft waiting for the learner's marks. */}
      {draft && (
        <Link href={correcteurHref(draft.id)} className="nb-rv__door" data-releve-correcteur={draft.id}>
          {correcteurCopy(language).releve_row}
        </Link>
      )}
      {entries.map((entry) => (
        <RvReleveEntry
          key={entry.sessionId}
          entry={entry}
          collapsed={!open.has(entry.sessionId)}
          onToggle={() => toggle(entry.sessionId)}
          copy={copy}
          releve={releve}
          now={now}
        />
      ))}
    </section>
  );
}

export default RvReleveSection;
