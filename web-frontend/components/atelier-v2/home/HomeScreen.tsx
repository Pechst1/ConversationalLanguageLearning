/**
 * Home — the design's HOME artboard, direction 1a "La Une, allégée".
 *
 * `Atelier App.dc.html`, verbatim in structure: the mark and the edition
 * kicker over the one Garamond-italic headline (the date); the streak or the
 * settings gear on the right; one episode card (16:9 art, blue story label,
 * italic headline, character byline); one red 3D-press "Continuer"; three
 * tiles (Séance · Lexique · Errata) each with a shape mark and three progress
 * bars; one italic colophon line — "Demain — l’imparfait, épisode 4."
 *
 * Presentation only. Every string and number is passed in from
 * `pages/atelier.tsx`, which maps them from the real `/atelier/today` payload,
 * so nothing here can print a value the server did not send. The streak is
 * drawn only when it is a real count; otherwise the slot holds the gear.
 */

import React from 'react';
import Link from 'next/link';

import {
  Action,
  ArrowRightIcon,
  AtelierMark,
  AtelierV2Root,
  Byline,
  CheckIcon,
  GearIcon,
  Notice,
  ShapeToken,
  Skeleton,
  Surface,
} from '@/components/atelier-v2/ui';

export type HomeTileMark = 'story' | 'reward' | 'done' | 'action';
export type HomeTileBar = HomeTileMark | null;

export type HomeTile = {
  id: string;
  title: string;
  meta: string;
  mark: HomeTileMark;
  /** One entry per bar; `null` leaves it on the track colour. */
  bars: HomeTileBar[];
  href?: string;
  onSelect?: () => void;
  disabled?: boolean;
  done?: boolean;
  ariaLabel?: string;
  /**
   * WP-16 / decision D-0: one quiet secondary line under the tile —
   * «Plus de pratique» on the Séance tile when the daily journey owns the day.
   * It is a sibling of the tile, never nested inside it, so neither control
   * swallows the other's click or focus. Omitted, the tile is exactly what it
   * was before this package.
   */
  secondary?: {
    label: string;
    href?: string;
    onSelect?: () => void;
    ariaLabel?: string;
  } | null;
};

/**
 * WP-24 — the because-line. When today's scene carries a learning target that
 * exists because of a mistake the learner actually made, the day says so
 * instead of looking arbitrary.
 *
 * Structured, not a sentence: the server sends `kind`, the erratum's label and
 * an optional «faux → juste» example (`app/services/journey_errata.py`,
 * `ErrataTarget.as_because`), and the French is written here, beside the rest
 * of the learner-facing copy. Sentence case, no English, the publication's own
 * register — same rules as every other line on this screen.
 */
export type HomeBecause = {
  /** Only `erratum` today; an unknown kind prints nothing rather than guessing. */
  kind: string;
  /** Machine-readable reason, e.g. `erratum:2f9c…`. Telemetry, never printed. */
  reason?: string | null;
  /** The mistake's own label, e.g. « l’accord du participe passé ». */
  label: string;
  /** « une homme → un homme », when both halves were recorded. */
  example?: string | null;
};

/**
 * WP-37 — one quiet way in to a surface that is not today's work.
 *
 * The design's first principle is one primary action per screen
 * (`docs/design-overhaul-2026-08-31.md`): the red press bar opens the day, and
 * everything else on La Une is a text line. So these are rows, never buttons —
 * a label, one explaining clause, and a link. They sit **below** the tiles,
 * after the day itself, because none of them is the day's work: a rehearsal
 * debrief is about something that already happened, and the dossier is a thing
 * to inspect, not a thing to do.
 *
 * Presentation only, like the rest of this file: `pages/atelier.tsx` decides
 * which entries exist, and an entry that has nothing to say is not passed at
 * all rather than rendered greyed out.
 */
export type HomeEntry = {
  id: string;
  /** « Votre répétition » — the surface, sentence case, French. */
  label: string;
  /** One clause saying what is there. Omitted, the row is the label alone. */
  hint?: string;
  href: string;
  ariaLabel?: string;
};

export type HomeEpisode = {
  kicker: string;
  headline: string;
  artUrl: string | null;
  artState: 'art' | 'press' | 'late' | 'none';
  byline: string;
  bylineMeta?: string;
  /** The episode has been read / answered already. */
  read?: boolean;
  onOpen?: (() => void) | null;
  ariaLabel?: string;
};

export type HomeScreenProps = {
  /** The one headline on this screen: the edition's date. */
  dateLabel: string;
  /** "Édition Nº 12 · A2" */
  editionLabel: string;
  /** Real consecutive-day count. 0 hides the slot entirely. */
  streak: number;
  settingsHref?: string;
  notice?: { label: string; message: string; onRetry?: () => void } | null;
  episode: HomeEpisode | null;
  /** The one 3D-press action. `null` on a filed edition. */
  action: { label: string; onSelect: () => void; disabled?: boolean; pending?: boolean } | null;
  /** The filed-edition line shown instead of the action. */
  filedLabel?: string | null;
  /** One quiet explaining clause under the action (first edition only). */
  note?: string | null;
  /** Why today's scene is this scene. Omitted, no line is printed. */
  because?: HomeBecause | null;
  /** The learner's stated budget, passed ONLY when the honest estimate overruns it. */
  overrunMinutes?: number | null;
  /** Where the edition's time budget is adjusted. */
  adjustHref?: string | null;
  /** Yesterday's promised phrase — printed only when the previous edition filed one. */
  phrase?: { text: string; byline: string } | null;
  /** The feature-flagged book episode. Kept independent of the serial story. */
  library?: { title: string; chapter: number; href: string } | false | null;
  /**
   * WP-37. Quiet secondary ways in — the rehearsal debrief, the dossier. Never
   * a second press bar; an empty list renders nothing at all.
   */
  entries?: HomeEntry[] | null;
  tiles: HomeTile[];
  colophon: { lead: string; focus: string; focusHref: string; tail?: string } | null;
  /** The tab bar, rendered last so it sits under the page in the same scroll. */
  children?: React.ReactNode;
};

export function HomeScreen({
  dateLabel,
  editionLabel,
  streak,
  settingsHref = '/settings',
  notice,
  episode,
  action,
  filedLabel,
  note,
  because,
  overrunMinutes,
  adjustHref,
  phrase,
  library,
  entries,
  tiles,
  colophon,
  children,
}: HomeScreenProps) {
  return (
    <AtelierV2Root as="main" className="av2-home" aria-label="Atelier · La Une">
      <header className="av2-home__mast">
        <div className="av2-home__mast-main">
          <AtelierMark size={26} />
          <p className="av2-home__kicker">{editionLabel}</p>
          <h1 className="av2-headline av2-headline--screen av2-home__date">{dateLabel}</h1>
        </div>
        {streak > 0 ? (
          <Link
            className="av2-home__streak"
            href={settingsHref}
            aria-label={`${streak} ${streak === 1 ? 'jour' : 'jours de suite'} · réglages`}
          >
            <span className="av2-home__streak-n">{streak}</span>
            <span className="av2-home__streak-l">{streak === 1 ? '1ᵉʳ jour' : 'jours de suite'}</span>
          </Link>
        ) : (
          <Link className="av2-icon-btn" href={settingsHref} aria-label="Réglages">
            <GearIcon size={18} />
          </Link>
        )}
      </header>

      {notice && (
        <div className="av2-home__section av2-home__section--first">
          <Notice tone="alert" live="alert" shape="action">
            <p>
              <strong>{notice.label}</strong>
              {notice.message ? ` — ${notice.message}` : ''}
            </p>
            {notice.onRetry && (
              <Action tone="secondary" inline onClick={notice.onRetry}>
                Réessayer
              </Action>
            )}
          </Notice>
        </div>
      )}

      {episode && (
        <div className={`av2-home__section${notice ? '' : ' av2-home__section--first'}`}>
          <EpisodeCard episode={episode} />
        </div>
      )}

      {action ? (
        <div className="av2-home__section">
          <Action
            tone="primary"
            disabled={action.disabled}
            pending={action.pending}
            pendingLabel="Un instant…"
            onClick={action.onSelect}
            iconAfter={<ArrowRightIcon size={18} />}
          >
            {action.label}
          </Action>
          {note && <p className="av2-label av2-home__note">{note}</p>}
          <BecauseLine because={because} />
          {overrunMinutes != null && (
            <p className="av2-body av2-home__note">
              Plus long que les {overrunMinutes} minutes demandées — vous pouvez vous arrêter quand
              vous voulez.
            </p>
          )}
          {adjustHref && (
            <Link className="av2-btn av2-btn--quiet av2-btn--inline" href={adjustHref}>
              Ajuster le temps de l’édition
            </Link>
          )}
        </div>
      ) : filedLabel ? (
        <div className="av2-home__section">
          <p className="av2-label">
            <ShapeToken kind="done" size="sm" /> {filedLabel}
          </p>
        </div>
      ) : null}

      {tiles.length > 0 && (
        <div className="av2-home__tiles">
          {tiles.map((tile) => (
            <DayTile key={tile.id} tile={tile} />
          ))}
        </div>
      )}

      {entries && entries.length > 0 && (
        <div className="av2-home__section" style={{ display: 'grid', gap: 8 }}>
          {entries.map((entry) => (
            <Link
              key={entry.id}
              className="av2-row"
              href={entry.href}
              aria-label={entry.ariaLabel || entry.label}
            >
              <span className="av2-row__main">
                <span className="av2-label">{entry.label}</span>
                {entry.hint && (
                  <span className="av2-label" style={{ display: 'block', fontWeight: 400 }}>
                    {entry.hint}
                  </span>
                )}
              </span>
              <ArrowRightIcon size={18} />
            </Link>
          ))}
        </div>
      )}

      {phrase && (
        <div className="av2-home__section">
          <Surface as="section" aria-label="La phrase d’hier">
            <p className="av2-label">La phrase d’hier</p>
            <blockquote className="av2-fr av2-headline av2-headline--rule av2-home__quote" lang="fr">
              « {phrase.text} »
            </blockquote>
            <p className="av2-label">par {phrase.byline}</p>
          </Surface>
        </div>
      )}

      {library && (
        <div className="av2-home__section">
          <Link
            className="av2-row"
            href={library.href}
            aria-label={`Lire ${library.title}, chapitre ${library.chapter}`}
          >
            <span className="av2-row__main">
              <span className="av2-label">La Bibliothèque</span>
              <span className="av2-headline av2-headline--rule" style={{ display: 'block' }}>
                {library.title}
              </span>
              <span className="av2-label" style={{ fontWeight: 400 }}>
                Chapitre {library.chapter} · lecture du soir, sans exercice.
              </span>
            </span>
            <ArrowRightIcon size={18} />
          </Link>
        </div>
      )}

      {colophon && (
        <p className="av2-home__foot">
          {colophon.lead}
          <Link href={colophon.focusHref}>{colophon.focus}</Link>
          {colophon.tail ?? '.'}
        </p>
      )}

      {children}
    </AtelierV2Root>
  );
}

/**
 * « Cette scène reprend une faute notée : l’accord du participe passé (une
 * homme → un homme). »
 *
 * One sentence, French, sentence case. It names the mistake and — when both
 * halves were recorded — shows it, because "you got something wrong" without
 * saying what is the kind of line that makes a learner anxious rather than
 * informed. An unknown `kind` prints nothing: an unexplained scene is better
 * than an invented explanation.
 */
function BecauseLine({ because }: { because?: HomeBecause | null }) {
  if (!because || because.kind !== 'erratum') return null;
  const label = (because.label || '').trim();
  if (!label) return null;
  const example = (because.example || '').trim();
  return (
    <p className="av2-body av2-home__note" data-reason={because.reason || undefined}>
      Cette scène reprend une faute notée&nbsp;: {label}
      {example ? ` (${example})` : ''}.
    </p>
  );
}

function EpisodeCard({ episode }: { episode: HomeEpisode }) {
  const body = (
    <>
      <EpisodeArt episode={episode} />
      <div className="av2-home__episode-body">
        <p className="av2-label av2-label--story">
          {episode.kicker}
          {episode.read ? (
            <>
              {' '}
              · <ShapeToken kind="done" size="sm" /> lu
            </>
          ) : null}
        </p>
        <h2 className="av2-headline av2-headline--title" lang="fr">
          {episode.headline}
        </h2>
        <Byline name={episode.byline} meta={episode.bylineMeta} />
      </div>
    </>
  );

  if (episode.onOpen) {
    return (
      <button
        type="button"
        className="av2-home__episode"
        onClick={episode.onOpen}
        aria-label={episode.ariaLabel || episode.headline}
      >
        {body}
      </button>
    );
  }
  return <article className="av2-home__episode">{body}</article>;
}

/**
 * The episode's art. The design draws a 16:9 plate on every card; when the
 * server has no image the plate says why — printing, delayed — rather than
 * showing a broken frame, and a text-first beat (a letter) shows no plate.
 */
function EpisodeArt({ episode }: { episode: HomeEpisode }) {
  const [failed, setFailed] = React.useState(false);
  if (episode.artState === 'none') return null;
  if (episode.artState === 'art' && episode.artUrl && !failed) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        className="av2-art"
        src={episode.artUrl}
        alt=""
        loading="lazy"
        decoding="async"
        onError={() => setFailed(true)}
      />
    );
  }
  const label =
    episode.artState === 'press'
      ? 'Illustration sous presse'
      : episode.artState === 'late'
        ? 'Illustration retardée — le texte, lui, n’attend pas'
        : 'Illustration à paraître';
  return (
    <div className="av2-art__fallback" role="img" aria-label={label}>
      <span className="av2-label" style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
        <ShapeToken kind="story" size="sm" /> {label}
      </span>
    </div>
  );
}

function DayTile({ tile }: { tile: HomeTile }) {
  const body = <DayTileControl tile={tile} />;
  if (!tile.secondary) return body;
  // The secondary needs a grid cell of its own to sit in, under the tile.
  return (
    <div className="av2-day-tile-cell">
      {body}
      {tile.secondary.href && !tile.secondary.onSelect ? (
        <Link
          className="av2-day-tile__more"
          href={tile.secondary.href}
          aria-label={tile.secondary.ariaLabel}
        >
          {tile.secondary.label}
        </Link>
      ) : (
        <button
          type="button"
          className="av2-day-tile__more"
          onClick={tile.secondary.onSelect}
          aria-label={tile.secondary.ariaLabel}
        >
          {tile.secondary.label}
        </button>
      )}
    </div>
  );
}

function DayTileControl({ tile }: { tile: HomeTile }) {
  const inner = (
    <>
      <span
        className={[
          'av2-day-tile__mark',
          tile.mark === 'story' ? 'av2-day-tile__mark--story' : null,
          tile.mark === 'done' ? 'av2-day-tile__mark--done' : null,
          tile.mark === 'action' ? 'av2-day-tile__mark--action' : null,
        ]
          .filter(Boolean)
          .join(' ')}
        aria-hidden="true"
      >
        {tile.mark === 'done' ? <CheckIcon size={14} /> : null}
      </span>
      <span>
        <span className="av2-day-tile__title">{tile.title}</span>
        <span className="av2-day-tile__meta" style={{ display: 'block' }}>
          {tile.meta}
        </span>
      </span>
      <span className="av2-day-tile__bars" aria-hidden="true">
        {tile.bars.map((bar, index) => (
          <i key={index} data-on={bar ?? undefined} />
        ))}
      </span>
    </>
  );
  const state = tile.done ? 'done' : undefined;
  if (tile.href && !tile.onSelect) {
    return (
      <Link className="av2-day-tile" href={tile.href} data-state={state} aria-label={tile.ariaLabel}>
        {inner}
      </Link>
    );
  }
  return (
    <button
      type="button"
      className="av2-day-tile"
      data-state={state}
      onClick={tile.onSelect}
      disabled={tile.disabled}
      aria-label={tile.ariaLabel}
    >
      {inner}
    </button>
  );
}

/** The page coming off the press: the same shapes, empty. */
export function HomeSkeleton({ children }: { children?: React.ReactNode }) {
  return (
    <AtelierV2Root as="main" className="av2-home" aria-busy="true" aria-label="Atelier · chargement">
      <header className="av2-home__mast">
        <div className="av2-home__mast-main">
          <AtelierMark size={26} />
          <div style={{ marginTop: 14 }}>
            <Skeleton height={14} radius={7} />
          </div>
          <div style={{ marginTop: 8, width: '60%' }}>
            <Skeleton height={32} radius={8} />
          </div>
        </div>
      </header>
      <div className="av2-home__section av2-home__section--first">
        <Skeleton height={260} radius={22} />
      </div>
      <div className="av2-home__section">
        <Skeleton height={56} radius={16} />
      </div>
      <div className="av2-home__tiles">
        <Skeleton height={104} radius={18} />
        <Skeleton height={104} radius={18} />
        <Skeleton height={104} radius={18} />
      </div>
      <span className="av2-sr" role="status">
        Chargement de l’édition
      </span>
      {children}
    </AtelierV2Root>
  );
}

export default HomeScreen;
