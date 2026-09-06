/* Atelier — "LE RELEVÉ" · the Cahier's third tab (the learner's own record).
 *
 * This replaces the parked /progress + /achievements pair inside the notebook.
 * Those pages were pre-journal English surfaces: an "Anki Sync" dashboard with a
 * raw WORD/STAGE/EASE/INTERVAL table that dumped the GLOBAL vocabulary_words
 * table (the owner's imported deck) to every account, and an "XP Earned"
 * achievements grid. Nothing here reads a global table: every number below is
 * scoped to the signed-in learner and maps to a named API field.
 *
 *   Le Cours       GET /progress/cefr            (the same payload La Une's LuCours reads)
 *   Le Registre    GET /analytics/summary        (UserVocabularyProgress rows for THIS user)
 *                  GET /grammar/summary          (UserGrammarProgress rows for THIS user)
 *   La Collection  GET /achievements/my          (unlocked only)
 *                  GET /atelier/almanac          (minted collectibles for THIS user)
 *
 * Primitives, tokens and phone-shell scoping come from components/cahiers/Cahiers.tsx;
 * the styles below only add the `--rv-*`-free derived rules the ledger needs, all
 * built on `--app-*` / `--nc-*` custom properties (no hex, both themes).
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import {
  NcColophon,
  NcCoverageTrack,
  NcEmpty,
  NcLedgerHead,
  NcNotice,
  NcSkeleton,
} from '@/components/cahiers/Cahiers';
import api, {
  type AtelierAlmanac,
  type CEFRProgress,
  type GrammarProgressSummary,
  type LearnerAnalyticsSummary,
  type UserAchievementProgress,
} from '@/services/api';

/* ---------- vocabulary ----------
   The catalogue keys are machine keys (German SRS states, snake_case collectible
   kinds, English achievement keys). None of them may reach the page: the Cahier
   speaks French. Anything unmapped falls back to a neutral French line rather
   than leaking the key. */

const GRAMMAR_STATES: Array<{ key: string; label: [string, string]; tone: string }> = [
  { key: 'neu', label: ['nouvelle', 'nouvelles'], tone: 'new' },
  { key: 'ausbaufähig', label: ['fragile', 'fragiles'], tone: 'fragile' },
  { key: 'in_arbeit', label: ['en cours', 'en cours'], tone: 'building' },
  { key: 'gefestigt', label: ['solide', 'solides'], tone: 'solid' },
  { key: 'gemeistert', label: ['maîtrisée', 'maîtrisées'], tone: 'mastered' },
];

const COLLECTIBLE_LABELS: Record<string, [string, string]> = {
  logo_token: ['vignette', 'vignettes'],
  gilt_seal: ['sceau doré', 'sceaux dorés'],
  story_seal: ['sceau de feuilleton', 'sceaux de feuilleton'],
  plate_semaine: ['planche de la semaine', 'planches de la semaine'],
  plate_chapter: ['planche de chapitre', 'planches de chapitre'],
  colophon: ['colophon', 'colophons'],
};

const COLLECTIBLE_ORDER = [
  'logo_token',
  'gilt_seal',
  'story_seal',
  'plate_semaine',
  'plate_chapter',
  'colophon',
];

const ACHIEVEMENT_COPY: Record<string, { title: string; note: string }> = {
  first_session: { title: 'Première séance', note: 'La première séance est bouclée.' },
  session_streak_3: { title: 'Trois jours de suite', note: 'Trois jours d’affilée à l’Atelier.' },
  session_streak_7: { title: 'Une semaine de suite', note: 'Sept jours d’affilée à l’Atelier.' },
  session_streak_30: { title: 'Trente jours de suite', note: 'Trente jours d’affilée à l’Atelier.' },
  vocabulary_learner: { title: 'Cinquante mots acquis', note: 'Cinquante mots passés en acquis.' },
  vocabulary_expert: { title: 'Deux cents mots acquis', note: 'Deux cents mots passés en acquis.' },
  vocabulary_master: { title: 'Cinq cents mots acquis', note: 'Cinq cents mots passés en acquis.' },
  xp_bronze: { title: 'Palier bronze', note: 'Cinq cents points cumulés.' },
  xp_silver: { title: 'Palier argent', note: 'Deux mille points cumulés.' },
  xp_gold: { title: 'Palier or', note: 'Cinq mille points cumulés.' },
  accuracy_perfectionist: { title: 'Le perfectionniste', note: 'Cent séances tenues au-dessus de 95 %.' },
  review_champion: { title: 'Mille reprises', note: 'Mille reprises de vocabulaire classées.' },
};

const TIER_CLASS: Record<string, string> = { gold: 'or', silver: 'argent', bronze: 'bronze' };

/* ---------- helpers ---------- */

function plural(n: number, [one, many]: [string, string]) {
  return n > 1 ? many : one;
}

/** Normalise the state-count keys: `ausbaufähig` can arrive decomposed. */
function normalizedCounts(counts: Record<string, number> | null | undefined) {
  const out: Record<string, number> = {};
  for (const [key, value] of Object.entries(counts || {})) {
    out[String(key).normalize('NFC')] = Number(value || 0);
  }
  return out;
}

function frenchDate(value: string | null | undefined) {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  try {
    return new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' }).format(parsed);
  } catch {
    return null;
  }
}

function Line({ label, value }: { label: string; value: string }) {
  return (
    <div className="rv-line">
      <span className="l">{label}</span>
      <span className="lead" aria-hidden="true" />
      <span className={'n' + (value === '0' ? ' zero' : '')}>{value}</span>
    </div>
  );
}

/* ---------- the surface ---------- */

export default function Releve() {
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

  /* ---- Le Cours (GET /progress/cefr) ---- */
  const declared = cefr?.estimate_source === 'declared';
  const forecastAvailable = cefr?.forecast?.status === 'available';
  const forecastDays = useMemo(() => {
    const range = cefr?.forecast?.range_days;
    if (!Array.isArray(range) || range.length < 2) return null;
    const days = Math.round((Number(range[0]) + Number(range[1])) / 2);
    return Number.isFinite(days) && days > 0 ? days : null;
  }, [cefr]);
  const nextLevel = cefr?.target || cefr?.next_level || null;
  const coursWords: [number, number] = [
    Number(cefr?.breakdown?.vocabulary?.current || 0),
    Number(cefr?.breakdown?.vocabulary?.target || 0),
  ];
  const coursRules: [number, number] = [
    Number(cefr?.breakdown?.grammar?.current || 0),
    Number(cefr?.breakdown?.grammar?.target || 0),
  ];

  /* ---- Le Registre (GET /analytics/summary + GET /grammar/summary) ---- */
  const grammarCounts = useMemo(() => normalizedCounts(grammar?.state_counts), [grammar]);
  const grammarStarted = Number(grammar?.started || 0);
  const grammarTotal = Number(grammar?.total_concepts || 0);
  const grammarBar = useMemo(
    () =>
      GRAMMAR_STATES.map((state) => {
        const n = Number(grammarCounts[state.key.normalize('NFC')] || 0);
        return { key: state.key, tone: state.tone, n, label: plural(n, state.label) };
      }).filter((state) => state.n > 0),
    [grammarCounts]
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
      .map((row) => ({ ...row, label: plural(row.n, COLLECTIBLE_LABELS[row.kind]) }));
  }, [almanac]);
  const collectionPieces = unlocked.length + collectibleLines.reduce((sum, row) => sum + row.n, 0);

  const everythingFailed = failed.cefr && failed.stats && failed.grammar && failed.collection;
  const stamp = frenchDate(cefr?.generated_at);

  if (loading) {
    return (
      <div className="rv">
        <div className="rv-skel" role="status" aria-label="Le relevé sort de presse">
          <NcSkeleton rows={4} />
        </div>
      </div>
    );
  }

  if (everythingFailed) {
    return (
      <div className="rv">
        <NcNotice
          label="Avis du bureau des archives"
          message="Le relevé n’a pas pu être tiré. Vos chiffres restent au bureau, rien n’est perdu."
          onRetry={() => void load()}
        />
      </div>
    );
  }

  return (
    <div className="rv">
      {/* ---- Le Cours ---- */}
      <section className="rv-sec" aria-label="Le cours">
        {/* The level is the headline below; repeating it in the head would be
            the same number printed twice. */}
        <NcLedgerHead t="Le cours" n={null} />
        {failed.cefr || !cefr ? (
          <NcNotice
            label="Avis du bureau des archives"
            message="Le niveau n’a pas pu être relevé."
            onRetry={() => void load()}
          />
        ) : (
          <div className="rv-cours">
            <p className="rv-level">
              {declared || !forecastAvailable || !nextLevel
                ? cefr.estimate
                : `${cefr.estimate} → ${nextLevel}`}
            </p>
            <p className="rv-status">
              {declared
                ? 'Niveau que vous avez indiqué. L’Atelier le vérifie au fil des séances.'
                : forecastAvailable && forecastDays
                ? `Environ ${forecastDays} jours à ce rythme.`
                : 'Prévisions après sept jours actifs.'}
            </p>
            {/* Gauges count what the Atelier has verified. Against a level it has
                not tested they would read as "vous savez 0 mot", so they wait. */}
            {!declared && (coursWords[1] > 0 || coursRules[1] > 0) && (
              <div className="rv-tracks">
                {coursWords[1] > 0 && <NcCoverageTrack lab="Mots" val={coursWords[0]} max={coursWords[1]} />}
                {coursRules[1] > 0 && (
                  <NcCoverageTrack lab="Règles" val={coursRules[0]} max={coursRules[1]} tone="ink" />
                )}
              </div>
            )}
          </div>
        )}
      </section>

      {/* ---- Le Registre ---- */}
      <section className="rv-sec" aria-label="Le registre">
        <NcLedgerHead t="Le registre" n={null} />
        {failed.stats && failed.grammar ? (
          <NcNotice
            label="Avis du bureau des archives"
            message="Le registre n’a pas pu être ouvert."
            onRetry={() => void load()}
          />
        ) : (
          <>
            <div className="rv-lines">
              {stats ? (
                <>
                  <Line label="Mots acquis" value={String(stats.words_mastered)} />
                  <Line label="Mots en cours" value={String(stats.words_learning)} />
                  <Line label="Mots à revoir aujourd’hui" value={String(stats.reviews_due_today)} />
                </>
              ) : (
                <p className="rv-gap">Le compte des mots n’a pas suivi cette fois-ci.</p>
              )}
              {grammar ? (
                <>
                  <Line
                    label="Règles engagées"
                    value={grammarTotal ? `${grammarStarted} / ${grammarTotal}` : String(grammarStarted)}
                  />
                  <Line label="Règles à revoir aujourd’hui" value={String(grammar.due_today)} />
                </>
              ) : (
                <p className="rv-gap">Le compte des règles n’a pas suivi cette fois-ci.</p>
              )}
            </div>
            {grammarBar.length > 0 && (
              <>
                <div
                  className="rv-bar"
                  role="img"
                  aria-label={
                    'Règles : ' + grammarBar.map((state) => `${state.n} ${state.label}`).join(', ')
                  }
                >
                  {grammarBar.map((state) => (
                    <i
                      key={state.key}
                      className={state.tone}
                      style={{ width: (100 * state.n) / Math.max(1, grammarStarted) + '%' }}
                    />
                  ))}
                </div>
                <div className="rv-legend">
                  {grammarBar.map((state) => (
                    <span key={state.key}>
                      <i className={state.tone} aria-hidden="true" />
                      {state.n} {state.label}
                    </span>
                  ))}
                </div>
              </>
            )}
          </>
        )}
      </section>

      {/* ---- La Collection ---- */}
      <section className="rv-sec" aria-label="La collection">
        <NcLedgerHead
          t="La collection"
          n={collectionPieces > 0 ? `${collectionPieces} pièce${collectionPieces > 1 ? 's' : ''}` : null}
        />
        {failed.collection ? (
          <NcNotice
            label="Avis du bureau des archives"
            message="La collection n’a pas pu être sortie de sa boîte."
            onRetry={() => void load()}
          />
        ) : collectionPieces === 0 ? (
          <NcEmpty
            title="Rien d’accroché encore"
            body="La collection commence avec la première édition bouclée."
          />
        ) : (
          <>
            {unlocked.length > 0 && (
              <div className="rv-pieces">
                {unlocked.map((item) => {
                  const copy = ACHIEVEMENT_COPY[item.achievement_key];
                  const date = frenchDate(item.unlocked_at);
                  return (
                    <div className="rv-piece" key={item.achievement_id}>
                      <span
                        className={'rv-seal ' + (TIER_CLASS[item.tier] || '')}
                        aria-hidden="true"
                      />
                      <span>
                        <b>{copy?.title || 'Distinction de l’Atelier'}</b>
                        <em>{copy?.note || 'Décernée au fil des séances.'}</em>
                      </span>
                      {date && <span className="d">{date}</span>}
                    </div>
                  );
                })}
              </div>
            )}
            {collectibleLines.length > 0 && (
              <div className="rv-lines">
                {collectibleLines.map((row) => (
                  <Line
                    key={row.kind}
                    label={row.label.charAt(0).toUpperCase() + row.label.slice(1)}
                    value={String(row.n)}
                  />
                ))}
              </div>
            )}
          </>
        )}
      </section>

      <NcColophon text={stamp ? `Le Relevé · arrêté au ${stamp}` : 'Le Relevé · vos chiffres, rien d’autre'} />
      <ReleveStyles />
    </div>
  );
}

/* ============================================================
   Styles — `.rv` lives inside the Cahier's `.nc` shell, so it
   inherits both the global --app-* tokens and the derived
   --nc-hair / --nc-fragile values. No hex, no local palette.
   ============================================================ */
export function ReleveStyles() {
  return (
    <style jsx global>{`
      .nc .rv { min-width: 0; }
      .nc .rv-skel { min-height: 240px; }
      .nc .rv-sec { margin-top: 2px; }

      /* ---- Le Cours ---- */
      .nc .rv-cours { margin-top: 12px; border: 1.5px solid var(--app-ink); background: var(--app-sheet); padding: 13px 14px 14px; }
      .nc .rv-level { margin: 0; font-family: var(--app-serif); font-style: italic; font-weight: 600; font-size: var(--t-display); line-height: .95; color: var(--app-ink); overflow-wrap: anywhere; }
      .nc .rv-status { margin: 7px 0 0; font-size: var(--t-small); line-height: 1.4; color: var(--app-ink-2); }
      .nc .rv-tracks { margin-top: 11px; padding-top: 5px; border-top: 1px solid var(--nc-hair); }
      /* Density: the section heads are the only kicker-level labels on this
         surface (three, one per viewport band). The gauge labels drop to plain
         sentence case so they stop competing with them. */
      .nc .rv-tracks .nc-track .lab { text-transform: none; letter-spacing: .01em; font-weight: 600; font-size: var(--t-small); color: var(--app-ink-2); }

      /* ---- ledger lines (dotted leaders, tabular figures) ---- */
      .nc .rv-lines { margin-top: 10px; }
      .nc .rv-line { display: grid; grid-template-columns: auto minmax(10px, 1fr) auto; gap: 9px; align-items: baseline; padding: 9px 0; border-bottom: 1px solid var(--nc-hair); }
      .nc .rv-line:last-child { border-bottom: 0; }
      .nc .rv-line .l { font-size: var(--t-small); line-height: 1.3; color: var(--app-ink-2); }
      .nc .rv-line .lead { height: 1px; align-self: center; background-image: radial-gradient(circle, var(--app-ink-3) 34%, transparent 40%); background-size: 5px 2px; background-repeat: repeat-x; background-position: 0 50%; }
      .nc .rv-line .n { font-family: var(--app-serif); font-style: italic; font-weight: 700; font-size: var(--t-lead); line-height: 1; color: var(--app-ink); font-variant-numeric: tabular-nums; white-space: nowrap; }
      .nc .rv-line .n.zero { color: var(--app-ink-3); }
      .nc .rv-gap { margin: 9px 0 0; font-family: var(--app-serif); font-style: italic; font-size: var(--t-small); line-height: 1.4; color: var(--app-ink-3); }

      /* ---- one token-coloured bar for the rule states ---- */
      .nc .rv-bar { margin-top: 13px; display: flex; height: 9px; border: 1px solid var(--app-ink); background: var(--app-paper-2); overflow: hidden; }
      .nc .rv-bar i { display: block; height: 100%; min-width: 2px; }
      .nc .rv-bar i.new, .nc .rv-legend i.new { background: var(--app-paper-3); }
      .nc .rv-bar i.fragile, .nc .rv-legend i.fragile { background: var(--nc-fragile); }
      .nc .rv-bar i.building, .nc .rv-legend i.building { background: var(--app-yellow); }
      .nc .rv-bar i.solid, .nc .rv-legend i.solid { background: var(--app-blue); }
      .nc .rv-bar i.mastered, .nc .rv-legend i.mastered { background: var(--app-ink); }
      .nc .rv-legend { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 5px 13px; font-size: var(--t-small); color: var(--app-ink-3); }
      .nc .rv-legend span { display: inline-flex; align-items: center; gap: 6px; font-variant-numeric: tabular-nums; }
      .nc .rv-legend i { width: 9px; height: 9px; border: 1px solid var(--app-ink); background: var(--app-paper-2); flex: 0 0 auto; }

      /* ---- La Collection ---- */
      .nc .rv-pieces { margin-top: 10px; }
      .nc .rv-piece { display: grid; grid-template-columns: 12px minmax(0, 1fr) auto; gap: 11px; align-items: baseline; padding: 10px 0; border-bottom: 1px solid var(--nc-hair); }
      .nc .rv-piece:last-child { border-bottom: 0; }
      .nc .rv-seal { width: 11px; height: 11px; align-self: center; border: 1px solid var(--app-ink); background: var(--app-paper-2); }
      .nc .rv-seal.or { background: var(--app-yellow); }
      .nc .rv-seal.argent { background: var(--app-paper-3); }
      .nc .rv-seal.bronze { background: var(--app-red); }
      .nc .rv-piece b { display: block; font-family: var(--app-serif); font-style: italic; font-weight: 600; font-size: var(--t-body); line-height: 1.15; color: var(--app-ink); overflow-wrap: anywhere; }
      .nc .rv-piece em { display: block; margin-top: 3px; font-style: normal; font-size: var(--t-small); line-height: 1.35; color: var(--app-ink-3); }
      .nc .rv-piece .d { font-size: var(--t-small); color: var(--app-ink-3); white-space: nowrap; font-variant-numeric: tabular-nums; }
    `}</style>
  );
}
