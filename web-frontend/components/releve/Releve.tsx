/* Atelier — «Fortschritt» (internal mode `releve`) · the Cahier's one progress place.
 *
 * Owner, 2026-10-12: progress lived in four places with numbers that did not
 * agree (the Relevé, the Carnet tab, the Dossier, La Une's goal line). It is
 * one tab now, top to bottom: the level and the goal from the band's coverage
 * (the numbers La Une and the Dossier print), the Carnet (#carnet), the seals
 * (#sceaux), what is in progress and due, the Papiers and the collection. The
 * Dossier stays the page that explains and corrects those numbers.
 *
 * This replaces the parked /progress + /achievements pair inside the notebook.
 * Those pages were pre-journal English surfaces: an "Anki Sync" dashboard with a
 * raw WORD/STAGE/EASE/INTERVAL table that dumped the GLOBAL vocabulary_words
 * table (the owner's imported deck) to every account, and an "XP Earned"
 * achievements grid. Nothing here reads a global table: every number below is
 * scoped to the signed-in learner and maps to a named API field.
 *
 *   Vos sceaux     GET /analytics/streak     (WP-D5: the streak's own days, as seals)
 *   Le Cours       GET /progress/cefr            (coverage: the same numbers as La Une and the Dossier)
 *   Le Carnet      GET /can-dos                  (CarnetTab, WP-95)
 *   Le Registre    GET /analytics/summary        (UserVocabularyProgress rows for THIS user)
 *                  GET /grammar/summary          (UserGrammarProgress rows for THIS user)
 *   Le Papier      GET /revue/releve             (WP-119: the learner's filed Papiers, RvReleveSection)
 *   La Collection  GET /achievements/my          (unlocked only)
 *                  GET /atelier/almanac          (minted collectibles for THIS user)
 *
 * Presentation is the Atelier V2 design system: the design has no artboard for
 * this ledger, so it is extended from the Cahier's primitives — section heads,
 * rounded card surfaces, the blue progress rule, the four shape tokens — and
 * every rule lives in components/cahiers/CahierV2.tsx as `.av2 .nb-*`. Tokens
 * only, both themes.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';

import {
  Action,
  ArrowRightIcon,
  Notice,
  ProgressRule,
  ShapeToken,
  Skeleton,
  StateBlock,
  Surface,
} from '@/components/atelier-v2/ui';
import CarnetTab from '@/components/cahiers/CarnetTab';
import { NbSectionHead } from '@/components/cahiers/CahierV2';
import SealCollection from '@/components/releve/SealCollection';
import { RvReleveSection } from '@/components/revue/RvReleveSection';
import { fill, plural, releveCopy, type ReleveCopy } from '@/components/releve/releve-copy';
import { targetLines, targetView } from '@/lib/continue-learning';
import { stageWord, type VisibleStage } from '@/lib/grammar-stages';
import { useChromeLanguage } from '@/lib/learner-language';
import api, {
  type AtelierAlmanac,
  type CEFRProgress,
  type GrammarProgressSummary,
  type LearnerAnalyticsSummary,
  type UserAchievementProgress,
} from '@/services/api';

/* ---------- vocabulary ----------
   The catalogue keys are machine keys (German SRS states, snake_case collectible
   kinds, English achievement keys). None of them may reach the page: every
   label is read from `releve-copy.ts` in the chrome language (WP-82). Anything
   unmapped falls back to a neutral line rather than leaking the key. */

/* WP-130 A: the register counts rules by the stage the level counts
   (`stage_counts`: introduced · practising · held), in the notebook's words —
   never by the scheduler's score states, which read as «held» («maîtrisées»)
   for rules the level does not count. */
const GRAMMAR_STAGE_TONES: Array<{ key: VisibleStage; tone: string }> = [
  { key: 'introduced', tone: 'new' },
  { key: 'practising', tone: 'building' },
  { key: 'held', tone: 'mastered' },
];

type CollectibleStem =
  | 'kind_logo_token'
  | 'kind_gilt_seal'
  | 'kind_story_seal'
  | 'kind_plate_semaine'
  | 'kind_plate_chapter'
  | 'kind_colophon';

const COLLECTIBLE_LABELS: Record<string, CollectibleStem> = {
  logo_token: 'kind_logo_token',
  gilt_seal: 'kind_gilt_seal',
  story_seal: 'kind_story_seal',
  plate_semaine: 'kind_plate_semaine',
  plate_chapter: 'kind_plate_chapter',
  colophon: 'kind_colophon',
};

const COLLECTIBLE_ORDER = [
  'logo_token',
  'gilt_seal',
  'story_seal',
  'plate_semaine',
  'plate_chapter',
  'colophon',
];

/* WP-79: the one catalogue (`app/services/achievement.py::CATALOGUE`). Every
   entry is earned from a row the app really writes; a retired key is never
   sent, and an unknown one falls back to a neutral line below.
   The title is the keepsake's name and stays French (WP-82: keepsake titles
   are content); the note under it is chrome and comes from the copy table. */
const ACHIEVEMENT_COPY: Record<string, { title: string; note: keyof ReleveCopy }> = {
  first_scene: { title: 'Première scène', note: 'note_first_scene' },
  scenes_10: { title: 'Dix scènes', note: 'note_scenes_10' },
  session_streak_3: { title: 'Trois jours de suite', note: 'note_session_streak_3' },
  session_streak_7: { title: 'Une semaine de suite', note: 'note_session_streak_7' },
  session_streak_30: { title: 'Trente jours de suite', note: 'note_session_streak_30' },
  first_letter: { title: 'Première lettre', note: 'note_first_letter' },
  helps_10: { title: 'Un coup de main', note: 'note_helps_10' },
  helps_50: { title: 'L’entraide', note: 'note_helps_50' },
  helps_100: { title: 'Le cœur sur la main', note: 'note_helps_100' },
  words_kept_50: { title: 'Cinquante mots gardés', note: 'note_words_kept_50' },
  first_chapter: { title: 'Premier chapitre bouclé', note: 'note_first_chapter' },
};
const ACHIEVEMENT_TITLE_FALLBACK = 'Distinction de l’Atelier';

/* The tier is printed as a word beside the reward token — never colour alone. */
const TIER_LABEL: Record<string, keyof ReleveCopy> = { gold: 'tier_gold', silver: 'tier_silver', bronze: 'tier_bronze' };

/* ---------- helpers ---------- */

/** Normalise the state-count keys: `ausbaufähig` can arrive decomposed. */
function normalizedCounts(counts: Record<string, number> | null | undefined) {
  const out: Record<string, number> = {};
  for (const [key, value] of Object.entries(counts || {})) {
    out[String(key).normalize('NFC')] = Number(value || 0);
  }
  return out;
}

function shortDate(value: string | null | undefined, locale: string) {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  try {
    return new Intl.DateTimeFormat(locale, { day: 'numeric', month: 'short', year: 'numeric' }).format(parsed);
  } catch {
    return null;
  }
}

function Line({ label, value }: { label: string; value: string }) {
  return (
    <div className="nb-line">
      <span className="nb-line__l">{label}</span>
      <span className="nb-line__n" data-zero={value === '0' ? 'true' : undefined}>{value}</span>
    </div>
  );
}

function ArchiveNotice({ copy, message, onRetry }: { copy: ReleveCopy; message: string; onRetry: () => void }) {
  return (
    <Notice tone="alert" live="alert" shape="action">
      <p><strong>{copy.archive_notice}</strong> — {message}</p>
      <Action tone="secondary" inline onClick={onRetry}>{copy.retry}</Action>
    </Notice>
  );
}

/* ---------- the surface ---------- */

export default function Releve() {
  const chromeLanguage = useChromeLanguage();
  const copy = releveCopy(chromeLanguage);
  const [loading, setLoading] = useState(true);
  const [cefr, setCefr] = useState<CEFRProgress | null>(null);
  const [stats, setStats] = useState<LearnerAnalyticsSummary | null>(null);
  const [grammar, setGrammar] = useState<GrammarProgressSummary | null>(null);
  const [achievements, setAchievements] = useState<UserAchievementProgress[] | null>(null);
  const [almanac, setAlmanac] = useState<AtelierAlmanac | null>(null);
  const [failed, setFailed] = useState({ cefr: false, stats: false, grammar: false, collection: false });
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    const [cefrResult, statsResult, grammarResult, achievementsResult, almanacResult] = await Promise.allSettled([
      api.getCefrProgress(),
      api.getAnalyticsSummary(),
      api.getGrammarSummary() as Promise<GrammarProgressSummary>,
      api.getUserAchievements(),
      api.getAtelierAlmanac(),
    ]);
    if (!alive.current) return;

    setCefr(cefrResult.status === 'fulfilled' ? cefrResult.value : null);
    setStats(statsResult.status === 'fulfilled' ? statsResult.value : null);
    setGrammar(grammarResult.status === 'fulfilled' ? grammarResult.value : null);
    setAchievements(
      achievementsResult.status === 'fulfilled' && Array.isArray(achievementsResult.value)
        ? achievementsResult.value
        : null
    );
    setAlmanac(almanacResult.status === 'fulfilled' ? almanacResult.value : null);
    setFailed({
      cefr: cefrResult.status === 'rejected',
      stats: statsResult.status === 'rejected',
      grammar: grammarResult.status === 'rejected',
      // Both halves of the collection have to fail before the section is dark.
      collection: achievementsResult.status === 'rejected' && almanacResult.status === 'rejected',
    });
    setLoading(false);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  /* The page draws after its data, so the browser's own jump to #carnet or
     #sceaux (La Une's level line and streak) found nothing; jump once drawn.
     An old `?mode=carnet` link means the Carnet too. */
  useEffect(() => {
    if (loading || typeof window === 'undefined') return;
    const legacyCarnet = new URLSearchParams(window.location.search).get('mode') === 'carnet';
    const wanted = window.location.hash.replace(/^#/, '') || (legacyCarnet ? 'carnet' : '');
    if (wanted !== 'carnet' && wanted !== 'sceaux') return;
    document.getElementById(wanted)?.scrollIntoView?.({ block: 'start' });
  }, [loading]);

  /* ---- Le Cours (GET /progress/cefr) ---- */
  const declared = cefr?.estimate_source === 'declared';
  /* WP-25. A placement is a measured prior, not a verdict: the learner's own
     in-app counters are still zero, so the gauges and the forecast stay away
     exactly as they do for a declared level — but the line must not say the
     learner told us, because they did not. */
  const placement = cefr?.estimate_source === 'placement';
  const unverified = declared || placement;
  const placementDate = useMemo(() => {
    const taken = cefr?.placement?.taken_at;
    if (!taken) return null;
    const at = new Date(String(taken));
    return Number.isNaN(at.getTime())
      ? null
      : at.toLocaleDateString(copy.locale, { day: 'numeric', month: 'long' });
  }, [cefr, copy]);
  const forecastAvailable = cefr?.forecast?.status === 'available';
  // WP-L8: a range, worded as an estimate — never one number read as a promise.
  const forecastRange = useMemo(() => {
    if (cefr?.forecast?.capped) return null;
    const range = cefr?.forecast?.range_days;
    if (!Array.isArray(range) || range.length < 2) return null;
    const low = Math.round(Number(range[0]));
    const high = Math.round(Number(range[1]));
    return Number.isFinite(low) && Number.isFinite(high) && low > 0 ? { low, high } : null;
  }, [cefr]);
  // WP-L8: the forecast is for the next sub-band, so the arrow points there.
  const nextLevel = cefr?.forecast?.target || cefr?.next_level || cefr?.target || null;
  /* Fortschritt (owner, 2026-10-12: one place for progress): the gauges read
     the band's coverage, the same numbers La Une's goal line and the Dossier
     print, so no screen disagrees with another about words and rules. */
  const coursWords: [number, number] = [
    Number(cefr?.coverage?.words?.known || 0),
    Number(cefr?.coverage?.words?.required || 0),
  ];
  const coursRules: [number, number] = [
    Number(cefr?.coverage?.units?.held || 0),
    Number(cefr?.coverage?.units?.required || 0),
  ];
  const goal = useMemo(() => {
    const target = targetView(cefr, chromeLanguage);
    return target ? targetLines(target, chromeLanguage) : null;
  }, [cefr, chromeLanguage]);

  /* ---- Le Registre (GET /analytics/summary + GET /grammar/summary) ---- */
  const grammarCounts = useMemo(
    () => normalizedCounts((grammar as { stage_counts?: Record<string, number> } | null | undefined)?.stage_counts),
    [grammar],
  );
  const grammarBar = useMemo(
    () =>
      GRAMMAR_STAGE_TONES.map((state) => {
        const n = Number(grammarCounts[state.key] || 0);
        return { key: state.key, tone: state.tone, n, label: stageWord(state.key, chromeLanguage, n).replace(/^\d+ /, '') };
      }).filter((state) => state.n > 0),
    [grammarCounts, chromeLanguage]
  );

  /* ---- La Collection (GET /achievements/my + GET /atelier/almanac) ---- */
  const unlocked = useMemo(
    () => (achievements || []).filter((item) => item.completed),
    [achievements]
  );
  const collectibleLines = useMemo(() => {
    // `totals` counts every minted row, including the originals already set into
    // a plate — counting both would inflate the collection. Only loose pieces
    // and the plates that hold the rest are on the shelf.
    const grouped = almanac?.collectibles || {};
    const kinds = Object.keys(grouped);
    kinds.sort((a, b) => {
      const ai = COLLECTIBLE_ORDER.indexOf(a);
      const bi = COLLECTIBLE_ORDER.indexOf(b);
      return (ai < 0 ? COLLECTIBLE_ORDER.length : ai) - (bi < 0 ? COLLECTIBLE_ORDER.length : bi);
    });
    return kinds
      .map((kind) => ({
        kind,
        n: (grouped[kind] || []).filter((piece) => !piece.composed).length,
      }))
      .filter((row) => row.n > 0 && COLLECTIBLE_LABELS[row.kind])
      .map((row) => ({ ...row, label: plural(copy, COLLECTIBLE_LABELS[row.kind], row.n) }));
  }, [almanac, copy]);
  const collectionPieces = unlocked.length + collectibleLines.reduce((sum, row) => sum + row.n, 0);

  const everythingFailed = failed.cefr && failed.stats && failed.grammar && failed.collection;
  const stamp = shortDate(cefr?.generated_at, copy.locale);

  if (loading) {
    return (
      <div className="nb-rv" aria-busy="true">
        <Skeleton height={120} radius={16} />
        <Skeleton height={160} radius={16} />
        <Skeleton height={120} radius={16} />
        <span className="av2-sr" role="status">{copy.loading}</span>
      </div>
    );
  }

  if (everythingFailed) {
    return (
      <div className="nb-rv">
        <StateBlock
          tone="error"
          title={copy.failed_title}
          body={copy.failed_body}
          action={{ label: copy.retry, onSelect: () => void load() }}
        />
      </div>
    );
  }

  return (
    <div className="nb-rv">
      {/* ---- Le Cours: level, goal, words and rules, from one source ---- */}
      <section className="nb-rv__sec" aria-label={copy.cours_title}>
        {/* The level is the headline below; repeating it in the head would be
            the same number printed twice. */}
        <NbSectionHead t={copy.cours_title} n={null} />
        {failed.cefr || !cefr ? (
          <ArchiveNotice copy={copy} message={copy.cours_failed} onRetry={() => void load()} />
        ) : (
          <Surface>
            <p className="av2-headline av2-headline--display">
              {unverified || !forecastAvailable || !nextLevel
                ? cefr.estimate
                : `${cefr.estimate} → ${nextLevel}`}
            </p>
            <p className="av2-body nb-rv__status">
              {placement
                ? placementDate
                  ? fill(copy.status_placement_dated, { date: placementDate })
                  : copy.status_placement
                : declared
                ? copy.status_declared
                : forecastAvailable && forecastRange
                ? fill(copy.status_forecast, { low: forecastRange.low, high: forecastRange.high })
                : forecastAvailable && cefr?.forecast?.capped
                ? copy.status_capped
                : copy.status_no_forecast}
            </p>
            {/* Gauges count what the Atelier has verified. Against a level it has
                not tested they would read as "vous savez 0 mot", so they wait. */}
            {/* The goal is La Une's line, word for word, so it shows whenever La Une shows it. */}
            {goal && (
              <p className="av2-body nb-rv__goal">
                {goal.goal}
                {goal.when ? `, ${goal.when}` : ''}
              </p>
            )}
            {!unverified && (coursWords[1] > 0 || coursRules[1] > 0) && (
              <div className="nb-rv__tracks">
                {coursWords[1] > 0 && (
                  <div className="nb-rv__track">
                    <span>{copy.track_words}</span>
                    <ProgressRule value={coursWords[0]} max={coursWords[1]} label={copy.track_words_label} caption={`${coursWords[0]} / ${coursWords[1]}`} />
                  </div>
                )}
                {coursRules[1] > 0 && (
                  <div className="nb-rv__track">
                    <span>{copy.track_rules}</span>
                    <ProgressRule value={coursRules[0]} max={coursRules[1]} label={copy.track_rules_label} caption={`${coursRules[0]} / ${coursRules[1]}`} />
                  </div>
                )}
              </div>
            )}
            <Link className="av2-row nb-rv__how" href="/dossier">
              <span className="av2-row__main av2-label">{copy.cours_how}</span>
              <ArrowRightIcon size={18} />
            </Link>
          </Surface>
        )}
      </section>

      {/* ---- Le Carnet (WP-95): what the level means in practice ---- */}
      <div id="carnet" className="nb-rv__sec">
        <CarnetTab />
      </div>

      {/* ---- Vos sceaux (WP-D5): the streak, reached from the Home streak ---- */}
      <SealCollection />

      {/* ---- Le Registre ----
          What is in progress and due today. The totals live in Le Cours
          above, so they are not counted a second way here. */}
      <section className="nb-rv__sec" aria-label={copy.registre_title}>
        <NbSectionHead t={copy.registre_title} n={null} />
        {failed.stats && failed.grammar ? (
          <ArchiveNotice copy={copy} message={copy.registre_failed} onRetry={() => void load()} />
        ) : (
          <Surface className="nb-sec">
            <div className="nb-lines">
              {stats ? (
                <>
                  <Line label={copy.words_learning} value={String(stats.words_learning)} />
                  <Line label={copy.words_due} value={String(stats.reviews_due_today)} />
                </>
              ) : (
                <p className="nb-gap">{copy.words_gap}</p>
              )}
              {grammar ? (
                <>
                  <Line label={copy.rules_due} value={String(grammar.due_today)} />
                </>
              ) : (
                <p className="nb-gap">{copy.rules_gap}</p>
              )}
            </div>
            {grammarBar.length > 0 && (
              <>
                <div
                  className="nb-bar"
                  role="img"
                  aria-label={fill(copy.rules_bar, {
                    list: grammarBar.map((state) => `${state.n} ${state.label}`).join(', '),
                  })}
                >
                  {grammarBar.map((state) => (
                    <i
                      key={state.key}
                      data-tone={state.tone}
                      style={{ width: (100 * state.n) / Math.max(1, grammarBar.reduce((sum, row) => sum + row.n, 0)) + '%' }}
                    />
                  ))}
                </div>
                <div className="nb-legend">
                  {grammarBar.map((state) => (
                    <span key={state.key}>
                      <i data-tone={state.tone} aria-hidden="true" />
                      {state.n} {state.label}
                    </span>
                  ))}
                </div>
              </>
            )}
          </Surface>
        )}
      </section>

      {/* ---- Le Papier (WP-119 phase 3): the Revue's clippings, anchored at
          #revue / #revue-<period>; draws nothing when the Revue is off or empty. ---- */}
      <RvReleveSection language={chromeLanguage} />

      {/* ---- La Collection ---- */}
      <section className="nb-rv__sec" aria-label={copy.collection_title}>
        <NbSectionHead
          t={copy.collection_title}
          n={collectionPieces > 0 ? plural(copy, 'pieces', collectionPieces) : null}
        />
        {failed.collection ? (
          <ArchiveNotice copy={copy} message={copy.collection_failed} onRetry={() => void load()} />
        ) : collectionPieces === 0 ? (
          <StateBlock
            tone="empty"
            title={copy.collection_empty_title}
            body={copy.collection_empty_body}
          />
        ) : (
          <Surface className="nb-sec">
            {unlocked.length > 0 && (
              <div className="nb-lines">
                {unlocked.map((item) => {
                  const entry = ACHIEVEMENT_COPY[item.achievement_key];
                  const date = shortDate(item.unlocked_at, copy.locale);
                  const tier = TIER_LABEL[item.tier] ? copy[TIER_LABEL[item.tier]] : null;
                  return (
                    <div className="nb-piece" key={item.achievement_id}>
                      <ShapeToken kind="reward" size="sm" />
                      <span className="nb-piece__main">
                        <span className="nb-piece__t" lang="fr">{entry?.title || ACHIEVEMENT_TITLE_FALLBACK}</span>
                        <span className="nb-piece__m">
                          {entry ? copy[entry.note] : copy.achievement_note_fallback}{tier ? ` · ${tier}` : ''}
                        </span>
                      </span>
                      {date && <span className="nb-piece__d">{date}</span>}
                    </div>
                  );
                })}
              </div>
            )}
            {collectibleLines.length > 0 && (
              <div className="nb-lines">
                {collectibleLines.map((row) => (
                  <Line
                    key={row.kind}
                    label={row.label.charAt(0).toUpperCase() + row.label.slice(1)}
                    value={String(row.n)}
                  />
                ))}
              </div>
            )}
          </Surface>
        )}
      </section>

      <p className="nb-foot">{stamp ? fill(copy.foot_dated, { date: stamp }) : copy.foot}</p>
    </div>
  );
}
