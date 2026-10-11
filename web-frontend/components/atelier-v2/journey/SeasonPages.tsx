/**
 * WP-98 «La saison suivante» and WP-99 «Le facteur et les dépêches» — the
 * pages the day can open on, and the Home cards that announce them.
 *
 *   · `EntreTemps` — «Pendant votre absence»: the character's greeting with
 *     their face, up to five dated lines of what happened meanwhile (French,
 *     every word tappable as in the reader), the letters that lapsed as
 *     «courrier en souffrance», and one «Reprendre l’histoire».
 *   · `SeasonPremiere` — the season's front page: «Saison N» in Garamond, the
 *     title, the logline, a poster cut from the day's first panel, one primary.
 *   · `SeasonPremiereCard` — the same front page as Home's card (the card's
 *     one primary sits under it, as for any day).
 *   · `InterludeCard` — between two seasons, said honestly: «l’histoire reprend
 *     le …», the reason, and the practice that exists. No fake scene, no press.
 *
 * Presentation only: every rule (who sees what, once, when) is in
 * `season-return-model.ts`; every word of chrome in `season-return-copy.ts`.
 * Story arrives as `*_fr` and is marked `lang="fr"`.
 */

import React, { useCallback, useState } from 'react';
import Link from 'next/link';

import { Action, ArrowRightIcon, Artwork, AtelierMark, ShapeToken, Surface } from '@/components/atelier-v2/ui';
import { CastPortrait } from '@/components/atelier-v2/ui/CastPortrait';
import { archiveDate } from '@/components/feuilleton/archive/archive-copy';
import { FeuilletonReaderStyles } from '@/components/feuilleton/reader/reader-styles';
import { FrenchLine } from '@/components/feuilleton/reader/TappableFrench';
import { WordHelpSheet, type WordHelpRequest } from '@/components/feuilleton/reader/WordHelpSheet';
import { readerCopy } from '@/components/feuilleton/reader/reader-copy';
import { frenchQuote, frenchSpacing } from '@/lib/french-typography';
import type { ControlLanguage } from '@/types/daily-journey';

import { seasonReturnCopy, srFill } from './season-return-copy';
import {
  interludeHeadline,
  interludePractice,
  type AbsenceView,
  type InterludeView,
  type SeasonPremiereView,
} from './season-return-model';

// ---------------------------------------------------------------------------
// «Pendant votre absence» — WP-99
// ---------------------------------------------------------------------------

export function EntreTemps({
  absence,
  language,
  journeyId = null,
  onContinue,
}: {
  absence: AbsenceView;
  /** The chrome language the shell resolved. */
  language: ControlLanguage;
  journeyId?: string | null;
  /** «Reprendre l’histoire» and «Passer» both go on to the day. */
  onContinue: () => void;
}) {
  const t = seasonReturnCopy(language);
  const reader = readerCopy(language);
  const [help, setHelp] = useState<WordHelpRequest | null>(null);
  const openHelp = useCallback(
    (sentence: string, character?: string | null) => (word: { surface: string; term: string }) =>
      setHelp({ surface: word.surface, term: word.term, sentence, journeyId, character: character || undefined }),
    [journeyId],
  );
  const days =
    absence.days > 1
      ? srFill(t.absence_days_many, { n: absence.days })
      : absence.days === 1
        ? t.absence_days_one
        : '';
  return (
    <section className="sr-page" aria-labelledby="sr-absence-title" data-prelude="entre_temps">
      <FeuilletonReaderStyles />
      <div className="sr-head">
        <p className="av2-label av2-label--story">
          <span lang="fr">{t.entre_temps_mark}</span>
          {days ? ` · ${days}` : ''}
        </p>
        <Action tone="quiet" inline onClick={onContinue}>
          {t.absence_skip}
        </Action>
      </div>
      <h2 id="sr-absence-title" className="av2-headline av2-headline--screen">
        {t.absence_title}
      </h2>

      {absence.greetingFr && (
        <figure className="sr-greeting" data-greeting="">
          {absence.characterId && (
            <CastPortrait
              characterId={absence.characterId}
              name={absence.characterName || undefined}
              mood="happy"
              size="md"
              ring
            />
          )}
          <div className="sr-greeting__text">
            <blockquote className="sr-greeting__quote av2-fr">
              <FrenchLine
                text={frenchQuote(absence.greetingFr)}
                idPrefix="sr-greeting"
                onWord={openHelp(absence.greetingFr, absence.characterId)}
                wordLabel={reader.word_help}
                className="fr-line sr-greeting__line"
              />
            </blockquote>
            {absence.characterName && (
              <figcaption className="av2-label" lang="fr">
                — {absence.characterName}
              </figcaption>
            )}
          </div>
        </figure>
      )}

      {absence.lines.length > 0 && (
        <ol className="sr-lines" aria-label={t.absence_lines_aria} data-entre-temps="">
          {absence.lines.map((line, index) => {
            const date = archiveDate(line.date, language);
            return (
              <li className="sr-line" key={`${line.date || 'd'}-${index}`}>
                {date && (
                  <time className="sr-line__date av2-label" dateTime={line.date || undefined}>
                    {date}
                  </time>
                )}
                <FrenchLine
                  text={line.textFr}
                  idPrefix={`sr-line-${index}`}
                  onWord={openHelp(line.textFr, line.characterId)}
                  wordLabel={reader.word_help}
                />
              </li>
            );
          })}
        </ol>
      )}

      {absence.letters.length > 0 && (
        <section className="sr-letters" aria-labelledby="sr-letters-title" data-lapsed-letters="">
          <p className="av2-label" id="sr-letters-title">
            {t.lapsed_title}
          </p>
          {absence.letters.map((letter) => (
            <Link
              key={letter.missionId}
              className="av2-row"
              href={letter.href}
              aria-label={
                letter.correspondentName
                  ? srFill(t.lapsed_open, { name: letter.correspondentName })
                  : t.lapsed_open_anon
              }
              data-lapsed-letter={letter.missionId}
            >
              <span className="av2-row__main">
                <span className="av2-label">
                  <ShapeToken kind="story" size="sm" />{' '}
                  {letter.correspondentName
                    ? srFill(t.lapsed_line, { name: letter.correspondentName })
                    : t.lapsed_line_anon}
                </span>
                <span className="av2-label sr-row-hint" lang="fr">
                  {t.courrier_name}
                </span>
              </span>
              <ArrowRightIcon size={18} />
            </Link>
          ))}
        </section>
      )}

      <Action tone="primary" onClick={onContinue} iconAfter={<ArrowRightIcon size={18} />}>
        {t.absence_resume}
      </Action>
      <WordHelpSheet request={help} onClose={() => setHelp(null)} language={language} />
      <SeasonPagesStyles />
    </section>
  );
}

// ---------------------------------------------------------------------------
// «Nouvelle saison» — WP-98
// ---------------------------------------------------------------------------

function PremiereMasthead({
  premiere,
  language,
  headingId,
  as: Heading = 'h2',
}: {
  premiere: SeasonPremiereView;
  language: ControlLanguage;
  headingId: string;
  as?: 'h1' | 'h2';
}) {
  const t = seasonReturnCopy(language);
  return (
    <div className="sr-premiere__mast">
      <p className="av2-label av2-label--story sr-premiere__kicker">
        <AtelierMark size={22} /> <span>{t.premiere_kicker}</span>
      </p>
      <Heading
        id={headingId}
        className="av2-headline av2-headline--display sr-premiere__season"
        lang="fr"
        aria-label={srFill(t.premiere_aria, { n: premiere.number, title: premiere.titleFr })}
      >
        {srFill(t.season_n, { n: premiere.number })}
      </Heading>
      <p className="av2-headline av2-headline--title sr-premiere__title" lang="fr">
        {frenchSpacing(premiere.titleFr)}
      </p>
    </div>
  );
}

export function SeasonPremiere({
  premiere,
  posterUrl,
  language,
  onContinue,
}: {
  premiere: SeasonPremiereView;
  posterUrl: string | null;
  language: ControlLanguage;
  onContinue: () => void;
}) {
  const t = seasonReturnCopy(language);
  return (
    <section className="sr-page sr-premiere" aria-labelledby="sr-premiere-title" data-prelude="premiere">
      <PremiereMasthead premiere={premiere} language={language} headingId="sr-premiere-title" />
      <hr className="sr-rule" aria-hidden="true" />
      {posterUrl && (
        <figure className="sr-poster" data-poster="">
          <Artwork
            url={posterUrl}
            alt={srFill(t.premiere_poster_alt, { n: premiere.number })}
            fallbackLabel={srFill(t.premiere_poster_alt, { n: premiere.number })}
            collapseWhenAbsent
            eager
          />
        </figure>
      )}
      {premiere.loglineFr && (
        <p className="av2-body av2-body--lg av2-fr sr-premiere__logline" lang="fr">
          {frenchSpacing(premiere.loglineFr)}
        </p>
      )}
      <Action tone="primary" onClick={onContinue} iconAfter={<ArrowRightIcon size={18} />}>
        {t.premiere_open}
      </Action>
      <SeasonPagesStyles />
    </section>
  );
}

/** Home's card on a premiere day. The card's one primary sits under it. */
export function SeasonPremiereCard({
  premiere,
  posterUrl,
  language,
}: {
  premiere: SeasonPremiereView;
  posterUrl: string | null;
  language: ControlLanguage;
}) {
  const t = seasonReturnCopy(language);
  return (
    <Surface
      as="section"
      shape="episode"
      className="journey-today-card sr-premiere sr-premiere--card"
      aria-labelledby="sr-premiere-card-title"
      data-premiere={premiere.number}
    >
      {posterUrl && (
        <Artwork
          url={posterUrl}
          alt={srFill(t.premiere_poster_alt, { n: premiere.number })}
          fallbackLabel={srFill(t.premiere_poster_alt, { n: premiere.number })}
          collapseWhenAbsent
          eager
        />
      )}
      <div className="journey-today-card__body av2-stack">
        <PremiereMasthead premiere={premiere} language={language} headingId="sr-premiere-card-title" />
        {premiere.loglineFr && (
          <p className="av2-body av2-fr sr-premiere__logline" lang="fr">
            {frenchSpacing(premiere.loglineFr)}
          </p>
        )}
      </div>
      <SeasonPagesStyles />
    </Surface>
  );
}

// ---------------------------------------------------------------------------
// Between two seasons — WP-98
// ---------------------------------------------------------------------------

export function InterludeCard({
  interlude,
  language,
  forgeHref = null,
}: {
  interlude: InterludeView;
  language: ControlLanguage;
  /** Today's Forge block, when the server offers one. */
  forgeHref?: string | null;
}) {
  const t = seasonReturnCopy(language);
  const practice = interludePractice(forgeHref);
  const rows: Record<(typeof practice)[number]['id'], { label: string; hint: string; lang?: string }> = {
    forge: { label: t.forge_name, hint: t.interlude_forge_hint, lang: 'fr' },
    courrier: { label: t.courrier_name, hint: t.interlude_courrier_hint, lang: 'fr' },
    relecture: { label: t.interlude_relecture, hint: t.interlude_relecture_hint },
  };
  return (
    <Surface
      as="section"
      shape="episode"
      className="journey-today-card sr-interlude"
      aria-labelledby="sr-interlude-title"
      data-interlude={interlude.returnsOn || ''}
    >
      <div className="journey-today-card__body av2-stack">
        <p className="av2-label av2-label--story">{t.interlude_kicker}</p>
        <h2 id="sr-interlude-title" className="av2-headline av2-headline--title">
          {interludeHeadline(interlude, t, language)}
        </h2>
        {interlude.reasonFr && (
          <p className="av2-body av2-fr sr-interlude__reason" lang="fr">
            {frenchSpacing(interlude.reasonFr)}
          </p>
        )}
        <p className="av2-label">{t.interlude_meanwhile}</p>
        <div className="sr-interlude__rows">
          {practice.map((item) => (
            <Link key={item.id} className="av2-row" href={item.href} data-interlude-practice={item.id}>
              <span className="av2-row__main">
                <span className="av2-label" lang={rows[item.id].lang}>
                  {rows[item.id].label}
                </span>
                <span className="av2-label sr-row-hint">{rows[item.id].hint}</span>
              </span>
              <ArrowRightIcon size={18} />
            </Link>
          ))}
        </div>
      </div>
      <SeasonPagesStyles />
    </Surface>
  );
}

// ---------------------------------------------------------------------------
// Styles — av2 tokens only; motion only when the learner has not asked for less
// ---------------------------------------------------------------------------

function SeasonPagesStyles() {
  return (
    <style jsx global>{`
      .av2 .sr-page {
        --fr-ink: var(--av2-ink);
        --fr-muted: var(--av2-muted);
        --fr-yellow: var(--av2-yellow);
        --fr-focus: var(--av2-focus);
        display: flex;
        flex-direction: column;
        gap: 18px;
        min-width: 0;
      }
      .av2 .sr-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        min-height: var(--av2-tap);
      }
      .av2 .sr-head .av2-label { margin: 0; }
      .av2 .sr-head .av2-btn { min-height: var(--av2-tap); }
      .av2 .sr-greeting {
        display: flex;
        align-items: flex-start;
        gap: 14px;
        margin: 0;
        min-width: 0;
      }
      .av2 .sr-greeting__text {
        display: flex;
        flex-direction: column;
        gap: 6px;
        min-width: 0;
      }
      .av2 .sr-greeting__quote { margin: 0; }
      .av2 .sr-greeting__line {
        font-family: var(--av2-serif);
        font-style: italic;
        font-size: var(--av2-t-option);
        line-height: 1.35;
      }
      .av2 .sr-greeting figcaption { margin: 0; color: var(--av2-muted); font-weight: 400; }
      .av2 .sr-lines {
        list-style: none;
        margin: 0;
        padding: 0;
        border-top: 1px solid var(--av2-line);
      }
      .av2 .sr-line {
        display: grid;
        grid-template-columns: 4.5rem minmax(0, 1fr);
        gap: 12px;
        padding: 12px 0;
        border-bottom: 1px solid var(--av2-line);
      }
      .av2 .sr-line__date { margin: 0; padding-top: 3px; color: var(--av2-muted); font-weight: 400; }
      .av2 .sr-line .fr-line { grid-column: 2; }
      .av2 .sr-letters { display: grid; gap: 8px; }
      .av2 .sr-letters > .av2-label { margin: 0; }
      .av2 .sr-row-hint { display: block; font-weight: 400; color: var(--av2-muted); }
      .av2 .sr-premiere__mast { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
      .av2 .sr-premiere__kicker { display: flex; align-items: center; gap: 8px; margin: 0; }
      .av2 .sr-premiere__season { margin: 0; }
      .av2 .sr-premiere__title { margin: 0; font-style: italic; }
      .av2 .sr-premiere__logline { margin: 0; color: var(--av2-ink-2); }
      .av2 .sr-rule { width: 100%; margin: 0; border: 0; border-top: 2px solid var(--av2-ink); }
      .av2 .sr-poster { margin: 0; border-radius: var(--av2-r-episode); overflow: hidden; }
      .av2 .sr-interlude h2 { margin: 0; }
      .av2 .sr-interlude__reason { margin: 0; font-style: italic; color: var(--av2-ink-2); }
      .av2 .sr-interlude__rows { display: grid; gap: 8px; }
      @media (prefers-reduced-motion: no-preference) {
        .av2 .sr-page { animation: sr-rise 0.32s ease-out both; }
        @keyframes sr-rise {
          from { opacity: 0; transform: translateY(6px); }
          to { opacity: 1; transform: none; }
        }
      }
    `}</style>
  );
}
