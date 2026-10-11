/**
 * WP-75 / WP-77 — day one meets the cast before the scene.
 *
 * One calm screen: three faces, each with a name, a role line in the learner's
 * language, and one French line that translates on tap. One «Continuer». The
 * server sends `journey.cast_intro` only on the learner's first journey; once
 * dismissed it is remembered for that journey, so a resume goes straight to
 * the scene.
 */

import React from 'react';

import { Action, ArrowRightIcon, useControlLanguage } from '@/components/atelier-v2/ui';
import { CastPortrait } from '@/components/atelier-v2/ui/CastPortrait';
import { frenchQuote } from '@/lib/french-typography';

import { journeyCopy } from './journey-copy';
import type { CastIntroEntry, JourneySnapshot } from '@/types/daily-journey';

export type { CastIntroEntry };

/** The cast intro a snapshot carries, or `[]`. Tolerates a server without the field. */
export function castIntroOf(journey: JourneySnapshot | null | undefined): CastIntroEntry[] {
  const raw = journey?.cast_intro;
  if (!Array.isArray(raw)) return [];
  return raw.filter(
    (entry) =>
      !!entry &&
      typeof entry.character_id === 'string' &&
      typeof entry.name === 'string' &&
      typeof entry.line_fr === 'string',
  );
}

const SEEN_PREFIX = 'atelier.castIntroSeen.';

export function castIntroSeen(journeyId: string): boolean {
  try {
    return window.localStorage.getItem(SEEN_PREFIX + journeyId) === '1';
  } catch {
    return false;
  }
}

export function rememberCastIntroSeen(journeyId: string): void {
  try {
    window.localStorage.setItem(SEEN_PREFIX + journeyId, '1');
  } catch {
    // Not remembered: the intro may show once more on a resume. Harmless.
  }
}

function CastMember({ entry, language }: { entry: CastIntroEntry; language: string }) {
  const [open, setOpen] = React.useState(false);
  const translatable = !!entry.line_native && entry.line_native !== entry.line_fr;
  return (
    <li className="cast-intro__member">
      <CastPortrait characterId={entry.character_id} name={entry.name} mood="neutral" size="md" />
      <div className="cast-intro__text">
        <p className="av2-headline av2-headline--rule cast-intro__name">{entry.name}</p>
        {entry.role_native && (
          <p className="av2-label cast-intro__role" lang={language}>
            {entry.role_native}
          </p>
        )}
        <button
          type="button"
          className="cast-intro__line av2-fr"
          lang="fr"
          aria-expanded={translatable ? open : undefined}
          onClick={() => translatable && setOpen((value) => !value)}
        >
          {frenchQuote(entry.line_fr)}
        </button>
        {translatable && open && (
          <p className="av2-label cast-intro__native" lang={language} aria-live="polite">
            {entry.line_native}
          </p>
        )}
      </div>
    </li>
  );
}

export function CastIntro({
  cast,
  language,
  onContinue,
}: {
  cast: CastIntroEntry[];
  /** The learner's control language, for the role and translation lines. */
  language: string;
  onContinue: () => void;
}) {
  // WP-82: the heading and the button are the screen's chrome, in the
  // chrome language the shell resolved (the root's), never fixed French.
  const copy = journeyCopy(useControlLanguage());
  return (
    <section className="cast-intro" aria-labelledby="cast-intro-title">
      <h2 id="cast-intro-title" className="av2-headline av2-headline--title">
        {copy.cast_title}
      </h2>
      <ul className="cast-intro__list">
        {cast.map((entry) => (
          <CastMember key={entry.character_id} entry={entry} language={language} />
        ))}
      </ul>
      <Action tone="primary" onClick={onContinue} iconAfter={<ArrowRightIcon size={18} />}>
        {copy.continue}
      </Action>
      <style jsx>{`
        .cast-intro {
          display: flex;
          flex-direction: column;
          gap: 18px;
          min-width: 0;
        }
        .cast-intro__list {
          display: flex;
          flex-direction: column;
          gap: 18px;
          margin: 0;
          padding: 0;
          list-style: none;
        }
        .cast-intro :global(.cast-intro__member) {
          display: flex;
          align-items: flex-start;
          gap: 14px;
          min-width: 0;
        }
        .cast-intro :global(.cast-intro__text) {
          display: flex;
          flex-direction: column;
          gap: 4px;
          min-width: 0;
        }
        .cast-intro :global(.cast-intro__name),
        .cast-intro :global(.cast-intro__role),
        .cast-intro :global(.cast-intro__native) {
          margin: 0;
        }
        .cast-intro :global(.cast-intro__role),
        .cast-intro :global(.cast-intro__native) {
          font-weight: 400;
          color: var(--av2-muted);
        }
        .cast-intro :global(.cast-intro__line) {
          padding: 0;
          border: 0;
          background: none;
          text-align: left;
          font-size: var(--av2-t-body-lg);
          line-height: 1.35;
          color: var(--av2-ink);
          cursor: pointer;
          text-decoration: underline dotted var(--av2-line);
          text-underline-offset: 4px;
        }
      `}</style>
    </section>
  );
}

export default CastIntro;
