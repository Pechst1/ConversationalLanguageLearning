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
 * WP-81 — «Home does one thing». With the daily journey on (`day` set) the
 * page is only: the masthead (the mark as the day's progress, the date, the
 * streak), the day's card in the hero slot, the plan row, and at most one
 * quiet row of two chips (one after the day is done). ≤ 5 elements and
 * ≤ 25 words (`home.test.js` counts them). Everything else in this file is
 * the flag-off Home, unchanged. WP-82: Home's own words follow `language`.
 *
 * Presentation only. Every string and number is passed in from
 * `pages/atelier.tsx`, which maps them from the real `/atelier/today` payload,
 * so nothing here can print a value the server did not send. The streak is
 * drawn only when it is a real count; otherwise the slot holds the gear.
 */

import React from 'react';
import Link from 'next/link';

import { PlacementOfferChip } from '@/components/onboarding/PlacementOfferChip';

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
import { useControlLanguage } from '@/components/atelier-v2/ui/AtelierV2Root';
import {
  DAY_MARK_GROUPS,
  STEP_SHAPE,
  dayMarkWords,
  type DayMarkState,
} from '@/components/atelier-v2/journey/day-mark';
import { atelierChrome, atelierCopy, type AtelierCopy } from '@/lib/atelier-v2-copy';
import { NNBSP, frenchQuote } from '@/lib/french-typography';
import type { ControlLanguage } from '@/types/daily-journey';

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
  /** When set, the row is a button that runs this instead of following `href`. */
  onSelect?: () => void;
  ariaLabel?: string;
};

/**
 * WP-81 — one quiet way to what is waiting besides the day: a letter, words
 * due. Never a press bar. At most two sit in one row under the plan, and one
 * once the day is done. The label is the whole chip, in one language.
 */
export type HomeChip = {
  id: string;
  label: string;
  href: string;
  /** The shape beside the word — reward (words), story (a letter). */
  shape?: 'reward' | 'story' | 'action';
  onSelect?: () => void;
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
  /**
   * WP-L7: the sub-band in force and how much of it is covered («A1.1 · 60 %»),
   * from the server's `coverage`. Drawn as one quiet label line in the masthead
   * while the journey owns the day; omitted, nothing is drawn.
   */
  level?: { band: string; percent: number } | null;
  /**
   * WP-79: today's practice is done (the server's `streak.today_done`). The
   * streak carries the ink «done» square, and the Séance tile — extra practice
   * once the journey owns the day — stops reading like unfinished work.
   */
  dayDone?: boolean;
  settingsHref?: string;
  /** WP-D5: where the streak leads — «Vos sceaux» in Cahier → Relevé. */
  streakHref?: string;
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
  /** Where the learner's rhythm (how long the day is) is adjusted. */
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
  /**
   * WP-D1: today's journey as the mark's plan. When set, the mark grows to
   * 44px and carries the day's progress, and one row of four shape + word
   * labels (Scène · Mots · Réponse · Bouclé) replaces the tile grid. Omitted
   * (journey off), Home is exactly what it was.
   */
  day?: DayMarkState | null;
  colophon: { lead: string; focus: string; focusHref: string; tail?: string } | null;
  /**
   * WP-81: the day's scene card (the journey's entry), directly under the masthead —
   * logo, date and streak first, then the one thing the day asks for.
   */
  hero?: React.ReactNode;
  /**
   * WP-81: while the journey owns the day (`day` set), Home does one thing.
   * It draws the masthead, the hero, the plan row and at most one row of
   * these chips — nothing else. The episode, the action, the phrase, the
   * library, the rows and the colophon are ignored in that mode.
   */
  chips?: HomeChip[] | null;
  /**
   * WP-82: the chrome language of Home's own words (the streak, the plan
   * row, the chips' labels are passed in already written). Defaults to
   * French, which is what the flag-off Home has always printed.
   */
  language?: ControlLanguage;
  /** The tab bar, rendered last so it sits under the page in the same scroll. */
  children?: React.ReactNode;
};

export function HomeScreen({
  dateLabel,
  editionLabel,
  streak,
  level = null,
  dayDone = false,
  settingsHref = '/settings',
  streakHref = '/notebook?mode=releve#sceaux',
  notice,
  episode,
  action,
  filedLabel,
  note,
  because,
  adjustHref,
  phrase,
  library,
  entries,
  tiles,
  day,
  colophon,
  hero,
  chips,
  language = 'fr',
  children,
}: HomeScreenProps) {
  const copy = atelierCopy(language);
  // WP-81: with the journey on, Home does one thing — the day.
  const oneThing = Boolean(day);
  const shownChips = (chips || []).slice(0, dayDone ? 1 : 2);
  const streakWord = streak === 1 ? copy.home_streak_first : copy.home_streak_days;
  return (
    <AtelierV2Root as="main" language={language} className="av2-home" aria-label={copy.home_label}>
      <header className="av2-home__mast">
        <div className="av2-home__mast-main">
          {day ? (
            // WP-D1: the mark is the day's only gauge — no goal ring.
            <AtelierMark size={44} progress={day.groups} title={day.label} />
          ) : (
            <AtelierMark size={26} />
          )}
          {/* WP-81: with the day on, the mark and the date are the header; the
              edition kicker is cut (≤ 25 words on Home). */}
          {!oneThing && <p className="av2-home__kicker">{editionLabel}</p>}
          {/* WP-L7: the level, back as one quiet label — never a second
              Garamond line (the date is the screen's one headline). */}
          {oneThing && level && (
            <p className="av2-home__kicker av2-home__level">
              <span className="av2-sr">
                {copy.home_level_aria.replace('{band}', level.band).replace('{percent}', String(level.percent))}
              </span>
              <span aria-hidden="true" data-level-figure="">
                {level.band} · {level.percent}
                {NNBSP}%
              </span>
            </p>
          )}
          <h1 className="av2-headline av2-headline--screen av2-home__date">{dateLabel}</h1>
        </div>
        {streak > 0 ? (
          // WP-79: at 0 the slot stays the gear (the July rule — a zero is
          // not a reward, and no placeholder number is ever drawn).
          <Link
            className="av2-home__streak"
            href={streakHref}
            data-state={dayDone ? 'done' : undefined}
            aria-label={`${streak === 1 ? streakWord : `${streak} ${streakWord}`}${dayDone ? ` · ${copy.home_streak_done}` : ''} · ${copy.home_streak_seals}`}
          >
            <span className="av2-home__streak-n">{streak}</span>
            <span className="av2-home__streak-l">
              {dayDone && <ShapeToken kind="done" size="sm" />}
              {streakWord}
            </span>
          </Link>
        ) : (
          <Link className="av2-icon-btn" href={settingsHref} aria-label={copy.settings}>
            <GearIcon size={18} />
          </Link>
        )}
      </header>

      {hero && <div className="av2-home__section av2-home__section--first av2-home__hero">{hero}</div>}

      {notice && (
        <div className={`av2-home__section${hero ? '' : ' av2-home__section--first'}`}>
          <Notice tone="alert" live="alert" shape="action">
            <p>
              <strong>{notice.label}</strong>
              {notice.message ? ` — ${notice.message}` : ''}
            </p>
            {notice.onRetry && (
              <Action tone="secondary" inline onClick={notice.onRetry}>
                {copy.action_retry}
              </Action>
            )}
          </Notice>
        </div>
      )}

      {!oneThing && episode && (
        <div className={`av2-home__section${notice || hero ? '' : ' av2-home__section--first'}`}>
          <EpisodeCard episode={episode} copy={copy} />
        </div>
      )}

      {oneThing ? null : action ? (
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
          {/* 2026-09-24: the «Plus long que les N minutes demandées» clause is
              gone. It compared the edition with the pre-rhythm daily goal (a
              stored 15 that no Réglages control sets any more); the rhythm now
              sizes the day on the server, and WP-81's Home says one thing. */}
          {adjustHref && (
            <Link className="av2-btn av2-btn--quiet av2-btn--inline" href={adjustHref}>
              Ajuster votre rythme
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

      {day && (
        <div className="av2-home__section">
          <DayPlanRow day={day} language={language} />
        </div>
      )}

      {/* WP-81: at most one quiet row — a letter waiting, words due. */}
      {oneThing && shownChips.length > 0 && (
        <div className="av2-home__section av2-home__chips">
          {shownChips.map((chip) => {
            const inner = (
              <>
                <ShapeToken kind={chip.shape ?? 'reward'} size="sm" />
                <span>{chip.label}</span>
              </>
            );
            return chip.onSelect ? (
              <button
                key={chip.id}
                type="button"
                className="av2-chip"
                data-chip={chip.id}
                onClick={chip.onSelect}
                aria-label={chip.ariaLabel || chip.label}
              >
                {inner}
              </button>
            ) : (
              <Link
                key={chip.id}
                className="av2-chip"
                data-chip={chip.id}
                href={chip.href}
                aria-label={chip.ariaLabel || chip.label}
              >
                {inner}
              </Link>
            );
          })}
        </div>
      )}

      {!day && tiles.length > 0 && (
        <div className="av2-home__tiles">
          {tiles.map((tile) => (
            <DayTile key={tile.id} tile={dayDone ? settledTile(tile, copy) : tile} />
          ))}
        </div>
      )}

      {!oneThing && entries && entries.length > 0 && (
        <div className="av2-home__section" style={{ display: 'grid', gap: 8 }}>
          {entries.map((entry) => {
            const inner = (
              <>
                <span className="av2-row__main">
                  <span className="av2-label">{entry.label}</span>
                  {entry.hint && (
                    <span className="av2-label" style={{ display: 'block', fontWeight: 400 }}>
                      {entry.hint}
                    </span>
                  )}
                </span>
                <ArrowRightIcon size={18} />
              </>
            );
            return entry.onSelect ? (
              <button
                key={entry.id}
                type="button"
                className="av2-row"
                onClick={entry.onSelect}
                aria-label={entry.ariaLabel || entry.label}
              >
                {inner}
              </button>
            ) : (
              <Link
                key={entry.id}
                className="av2-row"
                href={entry.href}
                aria-label={entry.ariaLabel || entry.label}
              >
                {inner}
              </Link>
            );
          })}
        </div>
      )}

      {/* WP-75: the placement, offered only after day three and never to a
          «Nouveau» learner. Renders nothing until the server says so. */}
      <PlacementOfferChip className="av2-home__section" />

      {!oneThing && phrase && (
        <div className="av2-home__section">
          <Surface as="section" aria-label={copy.home_phrase}>
            <p className="av2-label">{copy.home_phrase}</p>
            <blockquote className="av2-fr av2-headline av2-headline--rule av2-home__quote" lang="fr">
              {frenchQuote(phrase.text)}
            </blockquote>
            <p className="av2-label">par {phrase.byline}</p>
          </Surface>
        </div>
      )}

      {!oneThing && library && (
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

      {!oneThing && colophon && (
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
 * One sentence, sentence case, in Home's chrome language (the label and the
 * example are the learner's French and stay French). It names the mistake and — when both
 * halves were recorded — shows it, because "you got something wrong" without
 * saying what is the kind of line that makes a learner anxious rather than
 * informed. An unknown `kind` prints nothing: an unexplained scene is better
 * than an invented explanation.
 */
function BecauseLine({ because }: { because?: HomeBecause | null }) {
  // The chrome language of the surrounding AtelierV2Root (the home screen sets it).
  const copy = atelierCopy(useControlLanguage());
  if (!because || because.kind !== 'erratum') return null;
  const label = (because.label || '').trim();
  if (!label) return null;
  const example = (because.example || '').trim();
  return (
    <p className="av2-body av2-home__note" data-reason={because.reason || undefined}>
      {copy.home_because.replace('{label}', label)}
      {example ? ` (${example})` : ''}.
    </p>
  );
}

function EpisodeCard({ episode, copy }: { episode: HomeEpisode; copy: AtelierCopy }) {
  const body = (
    <>
      <EpisodeArt episode={episode} copy={copy} />
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
function EpisodeArt({ episode, copy }: { episode: HomeEpisode; copy: AtelierCopy }) {
  const [failed, setFailed] = React.useState(false);
  if (episode.artState === 'none') return null;
  if (episode.artState === 'art' && episode.artUrl && !failed) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        className="av2-art"
        src={episode.artUrl}
        alt=""
        // WP-83: the episode plate is Home's hero — it loads first.
        loading="eager"
        decoding="async"
        onError={() => setFailed(true)}
      />
    );
  }
  const label =
    episode.artState === 'press'
      ? copy.home_art_press
      : episode.artState === 'late'
        ? copy.home_art_late
        : copy.home_art_soon;
  return (
    <div className="av2-art__fallback" role="img" aria-label={label}>
      <span className="av2-label" style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
        <ShapeToken kind="story" size="sm" /> {label}
      </span>
    </div>
  );
}

/**
 * WP-79 (L13): once the day is done, the Séance tile that only offers extra
 * practice («Plus de pratique» under it) reads as a closed day, not as work
 * left. It still opens the drill loop; only its words and marks change.
 */
function settledTile(tile: HomeTile, copy: AtelierCopy): HomeTile {
  if (tile.id !== 'seance' || !tile.secondary) return tile;
  return {
    ...tile,
    meta: copy.home_day_settled,
    mark: 'done',
    bars: ['done', 'done', 'done'],
    done: true,
    ariaLabel: tile.ariaLabel || copy.home_seance_settled_aria,
  };
}

/**
 * WP-D1: the day's four parts as shape + word, under the primary. A part
 * that is not done is a ghost of its own shape; the done ones carry a check
 * and the one in progress is bold, so colour is never the only signal. A
 * part today's shape does not deal («jour court»: no recall) is left out.
 * WP-82: the words are status, in Home's chrome language.
 */
function DayPlanRow({ day, language }: { day: DayMarkState; language: ControlLanguage }) {
  const copy = atelierCopy(language);
  const words = dayMarkWords(language);
  const stateWord = { done: copy.home_part_done, active: copy.home_part_active, todo: copy.home_part_todo };
  const parts = DAY_MARK_GROUPS.filter((group) => day.groups[group] !== 'absent');
  return (
    <ol className="av2-day-plan" aria-label={copy.home_plan}>
      {parts.map((group) => {
        const state = day.groups[group] as keyof typeof stateWord;
        return (
          <li key={group} className="av2-day-plan__part" data-part={group} data-state={state}>
            <ShapeToken kind={STEP_SHAPE[group]} />
            <span className="av2-day-plan__word">
              {words[group]}
              {state === 'done' && <CheckIcon size={12} />}
            </span>
            <span className="av2-sr"> — {stateWord[state]}</span>
          </li>
        );
      })}
    </ol>
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
/**
 * WP-83 / 2026-09-24 — Home's one loader: the journey Home's shape (the day's
 * card, the plan row, one chip row), labelled in the learner's chrome
 * language. It is what a learner sees until the server has said which Home
 * they have, so it never draws the legacy Home's three tiles.
 */
export function HomeSkeleton({
  children,
  language,
}: {
  children?: React.ReactNode;
  /** WP-82: the loader's label follows the one language rule. */
  language?: ControlLanguage | null;
}) {
  const label = atelierChrome(language ?? 'fr').loading;
  return (
    <AtelierV2Root
      as="main"
      className="av2-home"
      language={language ?? undefined}
      aria-busy="true"
      aria-label={label}
      data-home-skeleton="journey"
    >
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
      <div className="av2-home__section" style={{ width: '70%' }}>
        <Skeleton height={36} radius={18} />
      </div>
      <span className="av2-sr" role="status">
        {label}
      </span>
      {children}
    </AtelierV2Root>
  );
}

export default HomeScreen;
