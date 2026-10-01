/**
 * WP-96 «Les Cahiers du feuilleton» — the Feuilleton tab's ONE surface.
 *
 * It replaces three: the season view of `pages/graphic-novel.tsx`, `/serial`
 * («La saison») and `/serial/cast` («Les personnages»). Two places, one
 * surface:
 *
 *   · «Archives du journal» — the season as a bound volume. Chapters fold
 *     open, headed by their title and, once closed, their digest line
 *     «question → résolution». Each day is a planche row (Nº, date, title,
 *     thumbnail) that opens the page in the reader in reread mode, followed by
 *     «la réplique de l'abonné·e» — the learner's own lines, Garamond italic —
 *     and the ending. A closed chapter ends on «Fin du chapitre» under the
 *     Bauhaus mark; a finished season is «Tome N», a pressed seal.
 *   · «Le trombinoscope» — the cast (`Trombinoscope.tsx`).
 *
 * It starts nothing and writes nothing: every read is a GET, and the only way
 * into a scene is the séance. The authored first day and fallback days are
 * planches like any other (W14). Chrome follows the language rule
 * (`archive-copy.ts`); the story is French and marked `lang="fr"`.
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import Router, { useRouter } from 'next/router';

import PhoneProductNav from '@/components/layout/PhoneProductNav';
import { StoryEpisodeReader } from '@/components/atelier-v2/journey/StoryEpisodeReader';
import { ArrowLeftIcon, ArrowRightIcon, AtelierV2Root, Skeleton } from '@/components/atelier-v2/ui';
import { FeuilletonReaderStyles } from '@/components/feuilleton/reader';
import { canDoCopy } from '@/lib/can-do-copy';
import { frenchQuote, frenchSpacing } from '@/lib/french-typography';
import { useChromeLanguage } from '@/lib/learner-language';
import { resolveMediaUrl } from '@/lib/media-url';
import type { SerialCastMember } from '@/services/api';
import type { ControlLanguage, StoryEpisode } from '@/types/daily-journey';

import { getArchiveEpisode, getStoryArchive, getTrombinoscope } from './archive-api';
import { archiveCopy, archiveDate, faFill, faPlural } from './archive-copy';
import { TodayEpisode, useTodayHeadline } from './TodayEpisode';
import {
  archiveDayEpisode,
  archiveDayHref,
  archiveIsEmpty,
  chapterIsCurrent,
  chapterKey,
  defaultOpenChapters,
  findArchiveDay,
  isNewVolume,
  mergeArchiveSeason,
  seasonPageCount,
  type ArchiveChapter,
  type ArchiveDay,
  type ArchivePayload,
  type ArchiveSeason,
} from './archive-model';
import { ChapterColophon, DigestLine, MarginNotes, TomeSeal } from './ArchiveMarks';
import { ArchiveStyles } from './ArchiveStyles';
import { Trombinoscope } from './Trombinoscope';
import { ShellCorner } from '@/components/layout/ShellCorner';

export type ArchiveView = 'archive' | 'cast' | 'day';
export type ArchiveDayQuery = { date: string | null; journeyId: string | null; sceneId: string | null };

const ARCHIVE_HREF = '/graphic-novel';
const CAST_HREF = '/graphic-novel?view=cast';

/* ====================================================================== */
/*  The page: loads, then draws one of the three views.                   */
/* ====================================================================== */

export function FeuilletonArchive({ view, dayQuery }: { view: ArchiveView; dayQuery?: ArchiveDayQuery | null }) {
  const language = useChromeLanguage();
  const t = archiveCopy(language);
  const router = useRouter();
  const [archive, setArchive] = useState<ArchivePayload | null>(null);
  const [archiveState, setArchiveState] = useState<'loading' | 'ready' | 'failed'>('loading');
  const [cast, setCast] = useState<SerialCastMember[] | null>(null);
  const [castState, setCastState] = useState<'idle' | 'loading' | 'ready' | 'failed'>('idle');
  const [open, setOpen] = useState<string[] | null>(null);
  const [openTomes, setOpenTomes] = useState<number[]>([]);
  const [loadingSeason, setLoadingSeason] = useState<number | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (view === 'cast') return undefined;
    let alive = true;
    setArchiveState('loading');
    void getStoryArchive().then((payload) => {
      if (!alive) return;
      setArchive(payload);
      setArchiveState(payload ? 'ready' : 'failed');
    });
    return () => {
      alive = false;
    };
  }, [attempt, view]);

  useEffect(() => {
    if (view !== 'cast' || castState !== 'idle') return undefined;
    let alive = true;
    setCastState('loading');
    void getTrombinoscope().then((members) => {
      if (!alive) return;
      setCast(members);
      setCastState(members ? 'ready' : 'failed');
    });
    return () => {
      alive = false;
    };
  }, [castState, view]);

  const openKeys = open ?? defaultOpenChapters(archive);
  const toggleChapter = useCallback(
    (key: string) => {
      setOpen((current) => {
        const base = current ?? defaultOpenChapters(archive);
        return base.includes(key) ? base.filter((entry) => entry !== key) : [...base, key];
      });
    },
    [archive],
  );
  const toggleTome = useCallback(
    (number: number) => {
      setOpenTomes((current) => (current.includes(number) ? current.filter((n) => n !== number) : [...current, number]));
      const season = archive?.seasons.find((entry) => entry.number === number);
      if (!season || season.loaded || loadingSeason !== null) return;
      setLoadingSeason(number);
      void getStoryArchive(number).then((fetched) => {
        setLoadingSeason(null);
        if (fetched) setArchive((current) => (current ? mergeArchiveSeason(current, fetched, number) : current));
      });
    },
    [archive, loadingSeason],
  );

  const day = useMemo(
    () => (view === 'day' && dayQuery ? findArchiveDay(archive, dayQuery) : null),
    [archive, dayQuery, view],
  );
  const current = archive?.seasons.find((season) => !season.finished) ?? archive?.seasons[0] ?? null;
  // WP-109: the Feuilleton opens on today's episode, then the archive and the cast.
  const todayHeadline = useTodayHeadline();

  return (
    <>
      <Head>
        <title>{view === 'cast' ? 'Le trombinoscope · Le Feuilleton' : 'Archives du journal · Le Feuilleton'}</title>
      </Head>
      <FeuilletonReaderStyles />
      <ArchiveStyles />
      <AtelierV2Root as="main" language={language} className="fr-page fa-page" aria-label={t.nav_aria}>
        {/* Settings, in the same corner on every tab (2026-10-01). */}
        {view !== 'day' && <ShellCorner />}
        {view !== 'day' && (
          <header className="fr-page-head">
            <div className="k">
              {view === 'cast'
                ? t.nav_aria
                : current
                  ? faPlural(t, 'season_pages', seasonPageCount(current), { season: current.number })
                  : t.nav_aria}
            </div>
            {/* the one Garamond italic headline on this screen */}
            <h1>{view === 'cast' ? t.cast_title : t.archive_title}</h1>
            <ArchiveNav view={view} language={language} />
          </header>
        )}
        {view === 'archive' && <TodayEpisode headline={todayHeadline} language={language} />}

        {view === 'cast' ? (
          castState === 'failed' ? (
            <FailedBlock title={t.cast_failed} body={t.archive_failed_body} retry={t.retry} onRetry={() => setCastState('idle')} />
          ) : cast ? (
            <Trombinoscope cast={cast} language={language} />
          ) : (
            <LoadingBlock label={t.archive_loading} />
          )
        ) : archiveState === 'loading' ? (
          <LoadingBlock label={t.archive_loading} />
        ) : archiveState === 'failed' || !archive ? (
          <FailedBlock
            title={t.archive_failed_title}
            body={t.archive_failed_body}
            retry={t.retry}
            onRetry={() => setAttempt((n) => n + 1)}
          />
        ) : view === 'day' ? (
          day ? (
            <ArchiveDayPage
              key={`${day.journey_id}:${day.scene_id}:${day.date}`}
              day={day}
              archive={archive}
              language={language}
              onExit={() => {
                void router.push(ARCHIVE_HREF);
              }}
            />
          ) : (
            <div className="fa-day">
              <BackLink language={language} />
              <div className="fr-empty" role="status">
                <h1 className="av2-headline av2-headline--title">{t.day_missing}</h1>
              </div>
            </div>
          )
        ) : archiveIsEmpty(archive) ? (
          <div className="fr-empty" data-archive-empty="">
            <h2>{t.archive_empty_title}</h2>
            <p>{t.archive_empty_body}</p>
            <Link className="av2-btn av2-btn--primary" href="/atelier">
              {t.open_seance} <ArrowRightIcon size={18} />
            </Link>
          </div>
        ) : (
          <ArchiveVolume
            archive={archive}
            language={language}
            openKeys={openKeys}
            onToggleChapter={toggleChapter}
            openTomes={openTomes}
            onToggleTome={toggleTome}
            loadingSeason={loadingSeason}
          />
        )}
      </AtelierV2Root>
      <PhoneProductNav active="feuilleton" />
      <style jsx global>{`
        body { background: var(--app-paper); }
        .av2.fa-page { min-height: 100vh; padding-bottom: calc(var(--phone-bottom-nav-space, 88px)); }
      `}</style>
    </>
  );
}

export default FeuilletonArchive;

/* ====================================================================== */
/*  Pieces (pure renders — the gallery and the node suite draw them).     */
/* ====================================================================== */

export function ArchiveNav({ view, language = null }: { view: ArchiveView; language?: ControlLanguage | null }) {
  const t = archiveCopy(language);
  return (
    <nav className="fa-seg" aria-label={t.nav_aria}>
      <Link href={ARCHIVE_HREF} aria-current={view === 'archive' ? 'page' : undefined} lang="fr">
        {t.archive_title}
      </Link>
      <Link href={CAST_HREF} aria-current={view === 'cast' ? 'page' : undefined} lang="fr">
        {t.cast_title}
      </Link>
    </nav>
  );
}

function LoadingBlock({ label }: { label: string }) {
  return (
    <div className="gn-skeleton fa-volume" aria-live="polite" aria-busy="true">
      <span className="fr-sr">{label}</span>
      <Skeleton height={64} radius={16} />
      <Skeleton height={80} radius={16} />
      <Skeleton height={80} radius={16} />
    </div>
  );
}

function FailedBlock({ title, body, retry, onRetry }: { title: string; body: string; retry: string; onRetry: () => void }) {
  return (
    <div className="fr-empty" role="status">
      <h2>{title}</h2>
      <p>{body}</p>
      <button type="button" className="av2-btn av2-btn--secondary" onClick={onRetry}>
        {retry}
      </button>
    </div>
  );
}

function BackLink({ language }: { language: ControlLanguage | null }) {
  const t = archiveCopy(language);
  return (
    <Link className="fa-back" href={ARCHIVE_HREF}>
      <ArrowLeftIcon size={16} /> {t.back_archive}
    </Link>
  );
}

/** «Nº 4 · 12 sept.» (+ «Numéro spécial») — a planche's kicker. */
export function plancheKicker(day: ArchiveDay, language: ControlLanguage | null): string {
  const t = archiveCopy(language);
  return [
    day.edition_no !== null ? faFill(t.edition_n, { n: day.edition_no }) : '',
    archiveDate(day.date, language),
    day.special === 'epreuve' ? canDoCopy(language).special_kicker : '',
  ]
    .filter(Boolean)
    .join(' · ');
}

export function ArchiveVolume({
  archive,
  language = null,
  openKeys,
  onToggleChapter,
  openTomes = [],
  onToggleTome,
  loadingSeason = null,
}: {
  archive: ArchivePayload;
  language?: ControlLanguage | null;
  openKeys: string[];
  onToggleChapter: (key: string) => void;
  openTomes?: number[];
  onToggleTome?: (number: number) => void;
  loadingSeason?: number | null;
}) {
  const t = archiveCopy(language);
  const several = archive.seasons.length > 1;
  return (
    <div className="fa-volume" data-archive="">
      {archive.seasons.map((season) => {
        const chapters = (
          <SeasonChapters
            season={season}
            archive={archive}
            language={language}
            openKeys={openKeys}
            onToggleChapter={onToggleChapter}
          />
        );
        if (season.finished) {
          const tomeOpen = openTomes.includes(season.number);
          return (
            <section className="fa-season" key={season.number} data-tome={season.number}>
              <div className="fa-tome">
                {/* the seal says «Saison N»; the title is the heading under it */}
                <TomeSeal number={season.number} language={language} />
                {season.title_fr && (
                  <h2 className="fa-tome__title" lang="fr">
                    {frenchSpacing(season.title_fr)}
                  </h2>
                )}
                <p className="av2-label">{faPlural(t, 'pages', seasonPageCount(season))}</p>
                {onToggleTome && (
                  <button
                    type="button"
                    className="av2-btn av2-btn--quiet av2-btn--inline"
                    aria-expanded={tomeOpen}
                    aria-controls={`fa-tome-${season.number}`}
                    onClick={() => onToggleTome(season.number)}
                  >
                    {t.tome_open}
                  </button>
                )}
              </div>
              {tomeOpen && (
                <div id={`fa-tome-${season.number}`}>
                  {loadingSeason === season.number ? <LoadingBlock label={t.archive_loading} /> : chapters}
                </div>
              )}
            </section>
          );
        }
        if (isNewVolume(archive, season)) {
          // WP-98: the season being written after a finished one opens a new
          // volume — «Saison N» in Garamond, its title and its logline.
          return (
            <section
              className="fa-season fa-volume-new"
              key={season.number}
              aria-labelledby={`fa-volume-${season.number}`}
              data-new-volume={season.number}
            >
              <header className="fa-volume-new__head">
                <p className="av2-label av2-label--story">{t.volume_new}</p>
                <h2 id={`fa-volume-${season.number}`} className="av2-headline av2-headline--screen" lang="fr">
                  {faFill(archiveCopy('fr').season_n, { n: season.number })}
                </h2>
                {season.title_fr && (
                  <p className="av2-headline av2-headline--title fa-volume-new__title" lang="fr">
                    {frenchSpacing(season.title_fr)}
                  </p>
                )}
                {season.logline_fr && (
                  <p className="av2-body av2-fr fa-volume-new__logline" lang="fr">
                    {frenchSpacing(season.logline_fr)}
                  </p>
                )}
              </header>
              {season.chapters.length > 0 ? chapters : <p className="av2-label">{t.volume_first_pages}</p>}
            </section>
          );
        }
        return (
          <section className="fa-season" key={season.number} aria-label={faFill(t.season_n, { n: season.number })}>
            {several && (
              <p className="av2-label av2-label--story">
                {faFill(t.season_n, { n: season.number })}
                {season.title_fr ? (
                  <>
                    {' · '}
                    <span lang="fr">{season.title_fr}</span>
                  </>
                ) : null}
              </p>
            )}
            {chapters}
          </section>
        );
      })}
    </div>
  );
}

function SeasonChapters({
  season,
  archive,
  language,
  openKeys,
  onToggleChapter,
}: {
  season: ArchiveSeason;
  archive: ArchivePayload;
  language: ControlLanguage | null;
  openKeys: string[];
  onToggleChapter: (key: string) => void;
}) {
  return (
    <>
      {season.chapters.map((chapter) => {
        const key = chapterKey(season, chapter);
        return (
          <ChapterFold
            key={key}
            id={key}
            chapter={chapter}
            current={chapterIsCurrent(archive, season, chapter)}
            open={openKeys.includes(key)}
            onToggle={() => onToggleChapter(key)}
            language={language}
          />
        );
      })}
    </>
  );
}

export function ChapterFold({
  id,
  chapter,
  current,
  open,
  onToggle,
  language = null,
}: {
  id: string;
  chapter: ArchiveChapter;
  current: boolean;
  open: boolean;
  onToggle: () => void;
  language?: ControlLanguage | null;
}) {
  const t = archiveCopy(language);
  const kicker = [
    chapter.prologue || chapter.index <= 0 ? '' : faFill(t.chapter_n, { n: chapter.index }),
    faPlural(t, 'pages', chapter.days.length),
    current ? t.chapter_running : '',
  ]
    .filter(Boolean)
    .join(' · ');
  const bodyId = `fa-chapter-${id}`;
  return (
    <section className="fa-chapter" data-chapter={chapter.index} data-closed={chapter.closed ? 'true' : undefined}>
      <button
        type="button"
        className="fa-chapter__head"
        aria-expanded={open}
        aria-controls={bodyId}
        onClick={onToggle}
      >
        <span className="fa-chapter__id">
          <span className="fa-chapter__kicker" data-current={current ? 'true' : undefined}>
            {kicker}
          </span>
          {chapter.title_fr && (
            <span className="fa-chapter__title" lang="fr">
              {frenchSpacing(chapter.title_fr)}
            </span>
          )}
          {chapter.closed && !open && <DigestLine digest={chapter.digest_fr} />}
        </span>
        <span className="fa-chapter__fold" aria-hidden="true" />
      </button>
      {open && (
        <div className="fa-chapter__body" id={bodyId}>
          <div className="fr-rows">
            {chapter.days.map((day) => (
              <PlancheRow key={`${day.journey_id}:${day.scene_id}:${day.date}`} day={day} language={language} />
            ))}
          </div>
          {chapter.closed && <ChapterColophon digest={chapter.digest_fr} />}
        </div>
      )}
    </section>
  );
}

export function PlancheRow({ day, language = null }: { day: ArchiveDay; language?: ControlLanguage | null }) {
  const thumb = resolveMediaUrl(day.image_url);
  return (
    <Link className="fr-row fa-planche" href={archiveDayHref(day)} data-planche={day.date || day.scene_id || ''}>
      <span className="thumb" aria-hidden="true">
        {thumb ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={thumb} alt="" />
        ) : null}
      </span>
      <span className="meta">
        <span className="k">{plancheKicker(day, language)}</span>
        <span className="t" lang="fr">
          {frenchSpacing(day.title_fr) || '—'}
        </span>
      </span>
      <span className="go" aria-hidden="true">
        <ArrowRightIcon size={18} />
      </span>
    </Link>
  );
}

/* ---------------------------------------------------------------------- */
/*  One planche, reread                                                    */
/* ---------------------------------------------------------------------- */

export function ArchiveDayPage({
  day,
  archive = null,
  language = null,
  onExit,
  episode: givenEpisode,
}: {
  day: ArchiveDay;
  archive?: ArchivePayload | null;
  language?: ControlLanguage | null;
  onExit?: () => void;
  /** The gallery hands the page in; the app reads it (`scene_id`) or has it (authored panels). */
  episode?: StoryEpisode | null;
}) {
  const authored = useMemo(() => archiveDayEpisode(day), [day]);
  const [fetched, setFetched] = useState<StoryEpisode | null>(null);
  const [state, setState] = useState<'loading' | 'ready' | 'none'>(
    givenEpisode !== undefined || authored || !day.scene_id ? 'ready' : 'loading',
  );
  const replyRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (givenEpisode !== undefined || authored || !day.scene_id) return undefined;
    let alive = true;
    void getArchiveEpisode(day.scene_id).then((episode) => {
      if (!alive) return;
      setFetched(episode);
      setState(episode ? 'ready' : 'none');
    });
    return () => {
      alive = false;
    };
  }, [authored, day.scene_id, givenEpisode]);

  const episode = givenEpisode !== undefined ? givenEpisode : fetched ?? authored;
  // WP-110: a finished day is one page with the learner's lines in it — the page is
  // the record, so the replies are not repeated underneath it.
  const isPage = Boolean(episode?.page?.rows?.length);
  const t = archiveCopy(language);
  // The singleton, not the hook: the day page also renders outside a mounted router.
  const toArchive = useCallback(() => {
    void Router.push(ARCHIVE_HREF);
  }, []);
  const toReply = useCallback(() => {
    const node = replyRef.current;
    if (!node) return;
    const reduce =
      typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    node.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
    node.focus({ preventScroll: true });
  }, []);

  return (
    <div
      className="fa-day"
      data-archive-day={day.date || day.scene_id || ''}
      data-authored={episode && episode === authored ? 'true' : undefined}
    >
      <BackLink language={language} />
      {state === 'loading' ? (
        <LoadingBlock label={t.archive_loading} />
      ) : episode ? (
        <div className="gn-reader">
          <StoryEpisodeReader
            episode={episode}
            mode="reread"
            title={day.title_fr || null}
            eyebrow={plancheKicker(day, language) || null}
            onExit={onExit ?? null}
            onContinue={isPage ? toArchive : toReply}
            continueLabel={isPage ? t.back_archive : t.to_reply}
            language={language}
            savePosition={false}
            marginNotes={day.margin_notes}
          />
        </div>
      ) : (
        <PlancheCard day={day} language={language} />
      )}

      {!isPage && (
      <section
        className="fa-reply"
        ref={replyRef}
        tabIndex={-1}
        aria-label={t.reply_label}
        data-reply=""
      >
        <p className="av2-label">{t.reply_label}</p>
        {day.learner_lines.length ? (
          day.learner_lines.map((line, index) => (
            <p className="fa-reply__line" lang="fr" key={`${index}-${line}`}>
              {frenchQuote(line)}
            </p>
          ))
        ) : (
          <p className="av2-body">{t.reply_none}</p>
        )}
        {day.ending_fr && (
          <>
            <p className="av2-label">{t.ending_label}</p>
            <p className="fa-ending" lang="fr">
              {frenchSpacing(day.ending_fr)}
            </p>
          </>
        )}
        {/* In the reader the notes sit on their panel; without it, here. */}
        {!episode && <MarginNotes notes={day.margin_notes} language={language} archive={archive} />}
      </section>
      )}
    </div>
  );
}

/** A planche with no page to reread (none recorded, or the page cannot be opened here). */
function PlancheCard({ day, language }: { day: ArchiveDay; language: ControlLanguage | null }) {
  const t = archiveCopy(language);
  const art = resolveMediaUrl(day.image_url);
  return (
    <article className="fa-plate" data-planche-card="">
      {art && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={art} alt="" />
      )}
      <div className="fa-plate__body">
        <p className="av2-label">{plancheKicker(day, language)}</p>
        {/* the one Garamond italic headline on this screen */}
        <h1 className="av2-headline av2-headline--title" lang="fr">
          {frenchSpacing(day.title_fr) || '—'}
        </h1>
        {day.scene_id && (
          <>
            <p className="av2-body">{t.page_unavailable}</p>
            <Link
              className="av2-btn av2-btn--quiet av2-btn--inline"
              href={`/graphic-novel?scene=${encodeURIComponent(day.scene_id)}`}
            >
              {t.open_page}
            </Link>
          </>
        )}
      </div>
    </article>
  );
}
