/**
 * The Today entry point for the daily journey — WP-07 **visual** milestone.
 *
 * One recommendation, one clear start/resume action, and — when the server says
 * one exists — a **separately labelled** resume for the old Atelier session.
 * The two are never merged: a V2 journey must not silently convert, replace or
 * complete a legacy session (CONTRACT-FREEZE, "Frontend recommendation
 * precedence").
 *
 * ---------------------------------------------------------------------------
 * Design mapping — `Atelier App.dc.html`, home direction 1a "La Une, allégée"
 * ---------------------------------------------------------------------------
 * This is the design's episode card: a 22px-radius surface, 16:9 artwork above
 * a blue story label, a Garamond-italic headline, a character byline, and one
 * red 3D-press action. The design's card is followed by three tiles (Séance,
 * Lexique, Errata) and a masthead — those belong to the home composition the
 * frontend lead owns, not to this card.
 *
 * Deliberately NOT taken: the design's masthead carries "12 jours" and
 * "Édition Nº 12". Neither is in the contract, and CONTRACTS forbids inventing
 * a streak, so this card carries neither. Recorded in
 * FRONTEND-ENGINE-HANDOFF §4.
 *
 * Presentation only. Every callback comes from the caller.
 */

import React from 'react';

import {
  Action,
  AtelierV2Root,
  Byline,
  ShapeToken,
  Surface,
} from '@/components/atelier-v2/ui';
import { CastPortrait } from '@/components/atelier-v2/ui/CastPortrait';
import type { StageMember } from '@/components/cast/PanelStage';
import { useArtSet } from '@/lib/art-set';
import { readerCopy } from '@/components/feuilleton/reader/reader-copy';
import {
  headlineKicker,
  headlineTeaser,
  headlineTitle,
  type EpisodeHeadline,
} from '@/lib/episode-headline';
import { atelierCopy, type AtelierCopy } from '@/lib/atelier-v2-copy';
import { canDoCopy } from '@/lib/can-do-copy';
import { epreuveOf, specialListLine } from '@/lib/can-dos';
import { frenchQuote, frenchSpacing } from '@/lib/french-typography';
import { gentleReturnLabel } from '@/lib/gentle-return';
import { preparingLine } from '@/lib/journey-reply-reveal';

import { journeyChromeLanguage } from '@/lib/language-rule';
import { resolveMediaUrl } from '@/lib/media-url';

import { EpisodeVignette, vignettePlace, type VignettePlace } from './EpisodeVignette';
import { journeyCopy } from './journey-copy';
import { tomorrowChoice } from './journey-recap-model';
import { InterludeCard, SeasonPremiereCard } from './SeasonPages';
import { seasonReturnCopy } from './season-return-copy';
import { TomorrowLine } from './TomorrowLine';
import {
  interludeHeadline,
  journeyAtFirstStep,
  premierePoster,
  teaserHint,
  tomorrowLine,
  todayInterlude,
  todayPremiere,
  type InterludeView,
  type SeasonPremiereView,
} from './season-return-model';
import { joinMeta, type JourneyPhase } from './journey-state';
import { coreEstimateLabel, extensionLabel } from './time-estimate';
import { TomorrowChoice } from './TomorrowChoice';
import type { DailyJourneyController } from './useDailyJourney';

export type JourneyTodayCardProps = {
  controller: DailyJourneyController;
  /** Open the connected session shell. */
  onOpen: () => void;
  /**
   * Kept for callers; unused since WP-81 removed the legacy-session card from
   * Home.
   */
  onOpenLegacy?: (href: string) => void;
  /**
   * Walk #123: the story is done but La Forge or the words are still open, so
   * the finished card says the episode is done, not the day.
   */
  restOfDayOpen?: boolean;
};

export function JourneyTodayCard({
  controller,
  onOpen,
  restOfDayOpen = false,
}: JourneyTodayCardProps) {
  // WP-82: the card is one chrome language — the learner's up to A2, French
  // from B1. French on it is the scene's own title and names.
  const chromeLanguage = journeyChromeLanguage(controller);
  const copy: AtelierCopy = {
    ...atelierCopy(chromeLanguage),
    ...journeyCopy(chromeLanguage),
  };
  const statusCopy = copy;
  const { phase, busy, actions } = controller;

  if (phase.kind === 'disabled' || phase.kind === 'loading') return null;

  // WP-94: a «Numéro spécial» — the band's épreuve is today. The card says so
  // and lists what it asks, in the chrome language. Calm, editorial.
  const epreuve = epreuveOf(controller.journey) ?? epreuveOf(controller.envelope);
  const special: SpecialEdition | null = epreuve
    ? {
        kicker: canDoCopy(chromeLanguage).special_kicker,
        line: specialListLine(epreuve.canDos, chromeLanguage),
      }
    : null;

  // WP-98: a new season opens on its front page; between two seasons, Home
  // says so with the return date instead of pretending there is a scene.
  const premiere = todayPremiere(controller.envelope, controller.journey);
  const interlude = todayInterlude(controller.envelope, controller.journey);
  const forgeHref = controller.envelope?.forge?.href ?? null;
  // WP-109: Home headlines today's episode (number, title or teaser, cast).
  const headline = controller.envelope?.headline ?? null;

  return (
    <AtelierV2Root language={chromeLanguage} className="journey-today">
      <div className="av2-stack">
        <JourneyTodayBody
          premiere={premiere}
          interlude={interlude}
          forgeHref={forgeHref}
          restOfDayOpen={restOfDayOpen}
          phase={phase}
          copy={copy}
          statusCopy={statusCopy}
          busy={busy}
          onOpen={onOpen}
          onStart={() => {
            void actions.start().then(onOpen);
          }}
          onResume={() => {
            void actions.resume().then(onOpen);
          }}
          onRefresh={() => void actions.refresh()}
          onRetryGeneration={() => void actions.retryGeneration()}
          onPickTomorrow={(premiseId) => {
            void actions.pickTomorrow(premiseId);
          }}
          controlLanguage={chromeLanguage}
          special={special}
          headline={headline}
        />

        {/* WP-43 — the nouvelles-pages artboard: the card carries the scene
            (art, label, title, byline, the learner-language line) and the one
            red action sits *under* it, at the same width as the rows below,
            never inside the card. Exactly one primary per composition. */}
        <JourneyPrimary
          premiere={premiere}
          phase={phase}
          copy={copy}
          busy={busy}
          controlLanguage={chromeLanguage}
          onOpen={onOpen}
          onStart={() => {
            void actions.start().then(onOpen);
          }}
          onResume={() => {
            void actions.resume().then(onOpen);
          }}
        />

        {/* WP-81: no «unfinished older practice» card on Home. The legacy
            session is still resumable from the drill loop («Plus de pratique»
            in Cahier and the recap); Home does one thing — the day. */}
      </div>
    </AtelierV2Root>
  );
}

/** WP-94: the special edition's kicker and its can-do line. */
type SpecialEdition = { kicker: string; line: string | null };

function JourneyPrimary({
  premiere = null,
  phase,
  copy,
  busy,
  controlLanguage,
  onOpen,
  onStart,
  onResume,
}: {
  premiere?: SeasonPremiereView | null;
  phase: JourneyPhase;
  copy: AtelierCopy;
  busy: boolean;
  controlLanguage: DailyJourneyController['controlLanguage'];
  onOpen: () => void;
  onStart: () => void;
  onResume: () => void;
}) {
  switch (phase.kind) {
    case 'offer':
      if (!phase.scenario) return null;
      // WP-76: a cold scene takes ~20 s. The button says what is happening in
      // the story («Le Mistral s’anime…»), not «Envoi…».
      return (
        <Action
          tone="primary"
          pending={busy}
          pendingLabel={preparingLine(
            phase.scenario.location_name,
            phase.scenario.character_name,
            controlLanguage,
          )}
          onClick={onStart}
        >
          {premiere ? seasonReturnCopy(controlLanguage).premiere_open : copy.start}
        </Action>
      );
    case 'session':
    case 'paused':
      return (
        <Action
          tone="primary"
          disabled={busy}
          onClick={phase.kind === 'paused' ? onResume : onOpen}
        >
          {copy.resume}
        </Action>
      );
    case 'awaiting_finish':
      return (
        <Action tone="primary" disabled={busy} onClick={onOpen}>
          {copy.awaiting_finish_action}
        </Action>
      );
    default:
      return null;
  }
}

function JourneyTodayBody({
  phase,
  copy,
  statusCopy,
  busy,
  controlLanguage,
  onOpen,
  onStart,
  onResume,
  onRefresh,
  onRetryGeneration,
  special = null,
  premiere = null,
  interlude = null,
  forgeHref = null,
  headline = null,
  restOfDayOpen = false,
  onPickTomorrow,
}: {
  restOfDayOpen?: boolean;
  /** «Demain»: pick the thread tomorrow follows, on the finished day's card. */
  onPickTomorrow?: (premiseId: string) => void;
  headline?: Headline | null;
  special?: SpecialEdition | null;
  premiere?: SeasonPremiereView | null;
  interlude?: InterludeView | null;
  forgeHref?: string | null;
  phase: JourneyPhase;
  copy: AtelierCopy;
  statusCopy: AtelierCopy;
  busy: boolean;
  controlLanguage: DailyJourneyController['controlLanguage'];
  onOpen: () => void;
  onStart: () => void;
  onResume: () => void;
  onRefresh: () => void;
  onRetryGeneration: () => void;
}) {
  switch (phase.kind) {
    case 'offer': {
      const scenario = phase.scenario;
      // WP-98: no scene between two seasons — said, with the return date.
      if (!scenario && interlude) {
        return <InterludeCard interlude={interlude} language={controlLanguage} forgeHref={forgeHref} />;
      }
      if (scenario && premiere) {
        return (
          <SeasonPremiereCard premiere={premiere} posterUrl={scenario.image_url} language={controlLanguage} />
        );
      }
      if (!scenario) {
        return (
          <Card copy={copy} eyebrow={copy.today_eyebrow} title={copy.nothing_offered}>
            <Action tone="secondary" inline onClick={onRefresh}>
              {copy.retry}
            </Action>
          </Card>
        );
      }
      // WP-82: the estimate is status («5 min»), in the card's chrome language.
      // WP-80: after an absence the day is short, so the standard estimate is
      // not printed beside «Reprise en douceur».
      // WP-98: days between two seasons are not an absence — no «Reprise».
      const gentle = interlude
        ? null
        : gentleReturnLabel({
            missedDays: phase.envelope.missed_days,
            dayShape: null,
            estimatedSeconds: null,
            language: controlLanguage,
          });
      // WP-128: one estimate — the core the rhythm budgets (or the longer day
      // the story alone makes) — and the words' own minutes beside it, never
      // folded into it: the drill is optional.
      const timeEstimate = phase.envelope.time_estimate ?? null;
      const estimate = gentle
        ? null
        : joinMeta(
            coreEstimateLabel(timeEstimate, scenario.estimated_seconds, controlLanguage),
            extensionLabel(timeEstimate, 'words', controlLanguage),
          ) || null;
      return (
        <Card
          copy={copy}
          // WP-81: Home's date says «today»; the card's label is the place.
          // WP-98: a quiet authored interlude scene says it is one.
          eyebrow={
            joinMeta(
              headlineKicker(headline),
              interlude ? seasonReturnCopy(controlLanguage).interlude_kicker : gentle,
              scenario.location_name,
            ) || copy.today_eyebrow
          }
          title={cardTitle(headline, scenario.title_fr)}
          lang="fr"
          headline={headline}
          controlLanguage={controlLanguage}
          // Owner test 2026-09-30: the episode's picture heads the card (the
          // engine's generic offer has none of its own).
          imageUrl={scenario.image_url || headline?.image_url || null}
          imageAlt={scenario.objective_native}
          scene={sceneOf(scenario, headline)}
          preparing={busy}
          special={special}
          byline={
            scenario.character_name ? (
              <Byline
                name={scenario.character_name}
                meta={estimate ? estimate : undefined}
              />
            ) : null
          }
        >
          {/* WP-81/82: the hero is art, title and one press; the objective is
              printed once, on the reply step that asks for it. */}
          {/* An estimate is not a countdown. It is the plan's own number, and
              it is absent rather than guessed when the plan has none. */}
          {estimate && !scenario.character_name && (
            <p className="av2-label">{estimate}</p>
          )}
          <InterludeReturn interlude={interlude} language={controlLanguage} />
        </Card>
      );
    }

    case 'session':
    case 'paused': {
      const scenario = phase.journey.scenario;
      // WP-98: the premiere's front page until the day has moved.
      if (premiere && (phase.kind === 'paused' || journeyAtFirstStep(phase.journey))) {
        return (
          <SeasonPremiereCard
            premiere={premiere}
            posterUrl={premierePoster(phase.journey)}
            language={controlLanguage}
          />
        );
      }
      const gentle = interlude ? null : gentleReturnLabel({
        missedDays: phase.journey.missed_days,
        dayShape: phase.journey.day_shape ?? 'standard',
        estimatedSeconds: phase.journey.estimated_active_seconds,
        language: controlLanguage,
      });
      // WP-128: a day the story alone makes longer than the rhythm says so here,
      // before the learner goes on — the plan's own number.
      const longer = phase.journey.time_estimate?.longer_day
        ? coreEstimateLabel(phase.journey.time_estimate, null, controlLanguage)
        : null;
      return (
        <Card
          copy={copy}
          eyebrow={
            joinMeta(headlineKicker(headline), gentle, longer, scenario.location_name) ||
            copy.today_eyebrow
          }
          title={cardTitle(headline, scenario.title_fr)}
          lang="fr"
          headline={headline}
          controlLanguage={controlLanguage}
          // Owner test 2026-09-30: the episode's picture heads the card (the
          // engine's generic offer has none of its own).
          imageUrl={scenario.image_url || headline?.image_url || null}
          imageAlt={scenario.objective_native}
          scene={sceneOf(scenario, headline)}
          special={special}
          byline={
            scenario.character_name ? <Byline name={scenario.character_name} /> : null
          }
        />
      );
    }

    /**
     * Every step is done and the day is not recorded as finished. Offering
     * "Continue today" here would promise a scene that has nothing left to
     * answer, so the entry says what is actually left: finishing it. The card
     * opens the session, where the finishing action lives.
     */
    case 'awaiting_finish': {
      const scenario = phase.journey.scenario;
      return (
        <Card
          copy={copy}
          eyebrow={joinMeta(copy.today_eyebrow, scenario.location_name)}
          title={scenario.title_fr}
          lang="fr"
          imageUrl={scenario.image_url}
          imageAlt={scenario.objective_native}
          scene={sceneOf(scenario, headline)}
          special={special}
          byline={scenario.character_name ? <Byline name={scenario.character_name} /> : null}
        >
          <p className="av2-body av2-body--lg">{copy.awaiting_finish_body}</p>
        </Card>
      );
    }

    // WP-69: status cards are one language (the learner's), and the preparing
    // button asks the server to take over a dead generation, not just re-read.
    case 'preparing':
      return (
        <Card copy={statusCopy} eyebrow={statusCopy.today_eyebrow} title={statusCopy.preparing_title}>
          <p className="av2-body av2-body--lg">{statusCopy.preparing_body}</p>
          <Action
            tone="secondary"
            inline
            disabled={busy}
            onClick={phase.retryAllowed ? onRetryGeneration : onRefresh}
          >
            {statusCopy.preparing_retry}
          </Action>
        </Card>
      );

    case 'unavailable':
      return (
        <Card copy={statusCopy} eyebrow={statusCopy.today_eyebrow} title={statusCopy.unavailable_title}>
          <p className="av2-body av2-body--lg">{statusCopy.unavailable_body}</p>
          {phase.retryAllowed && (
            <Action tone="secondary" inline disabled={busy} onClick={onRetryGeneration}>
              {statusCopy.unavailable_retry}
            </Action>
          )}
        </Card>
      );

    case 'finished': {
      // Re-entry is a READ. It must not restart the day or touch a streak.
      // WP-81: the completed state — the ink «done» square and «Done for
      // today» over the scene's own French title, and one quiet «Revoir».
      const titleFr = phase.journey?.scenario?.title_fr?.trim();
      // WP-99: «La suite demain» — the engine's own teaser first. Owner,
      // 2026-10-18: on Home it is a few words, where the story goes tomorrow;
      // the whole line stays on the recap.
      const tomorrow = tomorrowLine(phase.recap);
      return (
        <Card
          copy={copy}
          eyebrow={restOfDayOpen ? copy.story_done : copy.done_today}
          title={titleFr || (restOfDayOpen ? copy.story_done : copy.done_today)}
          lang={titleFr ? 'fr' : undefined}
          done
          // Owner test 2026-09-30: the day's episode, pictured above «Look again».
          imageUrl={phase.journey?.scenario?.image_url || null}
          imageAlt={titleFr || ''}
          scene={phase.journey?.scenario ? sceneOf(phase.journey.scenario, headline) : null}
        >
          <TomorrowLine line={tomorrow} language={controlLanguage} />
          {/* «Demain»: the threads tomorrow may follow, picked here or on the recap.
              #382: a question for the open day, not a card that sits on Home
              after the day is done: then only the line it settled on remains. */}
          {tomorrow && restOfDayOpen && (
            <TomorrowChoice
              choice={tomorrowChoice(phase.recap)}
              language={controlLanguage}
              busy={busy}
              onPick={onPickTomorrow}
            />
          )}
          <InterludeReturn interlude={interlude} language={controlLanguage} />
          <Action tone="secondary" inline onClick={onOpen}>
            {copy.done_review}
          </Action>
        </Card>
      );
    }

    case 'load_failed':
      return (
        <Card copy={statusCopy} eyebrow={statusCopy.today_eyebrow} title={statusCopy.transport_error}>
          <Action tone="secondary" inline onClick={onRefresh}>
            {statusCopy.retry}
          </Action>
        </Card>
      );

    default:
      return null;
  }
}

/** WP-98: «L’histoire reprend le 12 octobre.» — one line, when an interlude is on. */
function InterludeReturn({
  interlude,
  language,
}: {
  interlude: InterludeView | null;
  language: DailyJourneyController['controlLanguage'];
}) {
  if (!interlude) return null;
  const t = seasonReturnCopy(language);
  return (
    <p className="av2-label" data-interlude-return={interlude.returnsOn || ''}>
      {interludeHeadline(interlude, t, language)}
    </p>
  );
}

function Card({
  copy,
  eyebrow,
  title,
  lang,
  imageUrl,
  imageAlt,
  scene = null,
  byline,
  done,
  preparing = false,
  special = null,
  headline = null,
  controlLanguage = null,
  children,
}: {
  headline?: Headline | null;
  controlLanguage?: DailyJourneyController['controlLanguage'] | null;
  special?: SpecialEdition | null;
  copy: AtelierCopy;
  eyebrow: string;
  title: string;
  lang?: string;
  imageUrl?: string | null;
  imageAlt?: string;
  /**
   * Owner, 2026-10-18: where the scene is and who is in it. A day with no
   * picture gets its place drawn, with its people in front.
   */
  scene?: CardScene | null;
  byline?: React.ReactNode;
  done?: boolean;
  /** WP-76: the scene is being prepared — the place breathes, no spinner. */
  preparing?: boolean;
  children?: React.ReactNode;
}) {
  return (
    <Surface
      as="section"
      shape="episode"
      className={preparing ? 'journey-today-card journey-today-card--preparing' : 'journey-today-card'}
      aria-busy={preparing || undefined}
      data-special={special ? 'epreuve' : undefined}
    >
      <CardArt url={imageUrl ?? null} alt={imageAlt ?? ''} scene={scene} />
      <div className="journey-today-card__body av2-stack">
        <p className="av2-label av2-label--story">
          {done && <ShapeToken kind="done" size="sm" />}{' '}
          {special && (
            <>
              <span className="av2-special__kicker" lang="fr" data-special-kicker="">
                {special.kicker}
              </span>
              {eyebrow ? ' · ' : ''}
            </>
          )}
          {eyebrow}
        </p>
        <h2 className="av2-headline av2-headline--title" lang={lang}>
          {lang === 'fr' ? frenchSpacing(title) : title}
        </h2>
        {byline}
        {headline && (
          <HeadlineCast headline={headline} language={controlLanguage} title={title} faces={Boolean(imageUrl) || !scene} />
        )}
        {special?.line && (
          <p className="av2-body av2-special__list" data-special-list="">
            {special.line}
          </p>
        )}
        {children}
      </div>
    </Surface>
  );
}

/**
 * The card's headline. A generated day has no title until it is written, and
 * yesterday's whole «À suivre…» then stood in at headline size (owner,
 * 2026-10-19: far too big). It is cut to its heart, as the teaser line is.
 */
function cardTitle(headline: Headline | null | undefined, fallback: string): string {
  const title = headlineTitle(headline, fallback);
  if (title === fallback || String(headline?.title_fr || '').trim()) return title;
  return teaserHint(title) || title;
}

/** Where today's scene happens and who is on its page, for the drawn card art. */
type CardScene = { place: VignettePlace; cast: StageMember[] };

type SceneSource = {
  character_id?: string | null;
  character_name?: string | null;
  location_id?: string | null;
  location_name?: string | null;
};

/** The scene's place, and its lead first, then the headline's cast. */
function sceneOf(scenario: SceneSource, headline: Headline | null | undefined): CardScene {
  const ids = [scenario.character_id || scenario.character_name, ...(headline?.cast || []).map((member) => member.id)];
  const cast: StageMember[] = [];
  for (const id of ids) {
    const key = String(id || '').trim();
    if (key && !cast.some((member) => member.id === key)) cast.push({ id: key, speaking: cast.length === 0 });
  }
  return { place: vignettePlace(scenario.location_id, scenario.location_name), cast };
}

/**
 * The card's picture: the episode's art when there is one; otherwise (or when it
 * fails to load) its place drawn, with its people in front (owner, 2026-10-18).
 * A painted-cast device keeps the drawn place and leaves the drawn people out.
 */
function CardArt({ url, alt, scene }: { url: string | null; alt: string; scene: CardScene | null }) {
  const [failed, setFailed] = React.useState(false);
  React.useEffect(() => setFailed(false), [url]);
  const drawn = useArtSet() === 'drawn';
  const resolved = url ? resolveMediaUrl(url) || url : null;
  if (resolved && !failed) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        className="av2-art"
        src={resolved}
        alt={alt}
        onError={() => setFailed(true)}
        loading="eager"
        {...{ fetchpriority: 'high' }}
        decoding="async"
      />
    );
  }
  if (!scene) return null;
  return <EpisodeVignette place={scene.place} cast={drawn ? scene.cast : []} />;
}

// ---------------------------------------------------------------------------
// WP-109 «Une seule maison» — Home headlines today's episode
// ---------------------------------------------------------------------------

type Headline = EpisodeHeadline;

/** The teaser (when it is not already the title) and the faces of who is in it. */
function HeadlineCast({
  headline,
  language,
  title,
  faces = true,
}: {
  headline: Headline;
  language?: DailyJourneyController['controlLanguage'] | null;
  title: string;
  /** false: the card's drawing already shows who is in it. */
  faces?: boolean;
}) {
  // Owner, 2026-10-18: a few words, never a paragraph, on Home.
  const teaser = teaserHint(headlineTeaser(headline, title));
  // A title cut from the teaser is not printed again under itself.
  const showTeaser = Boolean(teaser) && teaser !== title;
  const cast = faces ? headline.cast || [] : [];
  if (!showTeaser && !cast.length) return null;
  return (
    <div className="journey-today-card__headline av2-stack" data-headline="">
      {showTeaser && (
        <p className="av2-body" data-headline-teaser="">
          <span className="av2-label">{readerCopy(language ?? null).to_follow}</span>{' '}
          <span className="av2-fr" lang="fr">
            {frenchSpacing(teaser ?? '')}
          </span>
        </p>
      )}
      {cast.length > 0 && (
        <ul className="journey-today-card__cast" aria-label={cast.map((member) => member.name).join(', ')}>
          {cast.map((member) => (
            <li key={member.id}>
              <CastPortrait characterId={member.id} name={member.name} size="xs" alt={member.name} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default JourneyTodayCard;
