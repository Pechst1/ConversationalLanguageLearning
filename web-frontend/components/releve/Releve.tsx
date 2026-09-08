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
 * Presentation is the Atelier V2 design system: the design has no artboard for
 * this ledger, so it is extended from the Cahier's primitives — section heads,
 * rounded card surfaces, the blue progress rule, the four shape tokens — and
 * every rule lives in components/cahiers/CahierV2.tsx as `.av2 .nb-*`. Tokens
 * only, both themes.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import {
  Action,
  Notice,
  ProgressRule,
  ShapeToken,
  Skeleton,
  StateBlock,
  Surface,
} from '@/components/atelier-v2/ui';
import { NbSectionHead } from '@/components/cahiers/CahierV2';
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

/* The tier is printed as a word beside the reward token — never colour alone. */
const TIER_LABEL: Record<string, string> = { gold: 'or', silver: 'argent', bronze: 'bronze' };

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
    <div className="nb-line">
      <span className="nb-line__l">{label}</span>
      <span className="nb-line__n" data-zero={value === '0' ? 'true' : undefined}>{value}</span>
    </div>
  );
}

function ArchiveNotice({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <Notice tone="alert" live="alert" shape="action">
      <p><strong>Avis du bureau des archives</strong> — {message}</p>
      <Action tone="secondary" inline onClick={onRetry}>Réessayer</Action>
    </Notice>
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
      <div className="nb-rv" aria-busy="true">
        <Skeleton height={120} radius={16} />
        <Skeleton height={160} radius={16} />
        <Skeleton height={120} radius={16} />
        <span className="av2-sr" role="status">Le relevé sort de presse</span>
      </div>
    );
  }

  if (everythingFailed) {
    return (
      <div className="nb-rv">
        <StateBlock
          tone="error"
          title="Le relevé n’a pas pu être tiré"
          body="Vos chiffres restent au bureau, rien n’est perdu."
          action={{ label: 'Réessayer', onSelect: () => void load() }}
        />
      </div>
    );
  }

  return (
    <div className="nb-rv">
      {/* ---- Le Cours ---- */}
      <section className="nb-rv__sec" aria-label="Le cours">
        {/* The level is the headline below; repeating it in the head would be
            the same number printed twice. */}
        <NbSectionHead t="Le cours" n={null} />
        {failed.cefr || !cefr ? (
          <ArchiveNotice message="Le niveau n’a pas pu être relevé." onRetry={() => void load()} />
        ) : (
          <Surface>
            <p className="av2-headline av2-headline--display">
              {declared || !forecastAvailable || !nextLevel
                ? cefr.estimate
                : `${cefr.estimate} → ${nextLevel}`}
            </p>
            <p className="av2-body nb-rv__status">
              {declared
                ? 'Niveau que vous avez indiqué. L’Atelier le vérifie au fil des séances.'
                : forecastAvailable && forecastDays
                ? `Environ ${forecastDays} jours à ce rythme.`
                : 'Prévisions après sept jours actifs.'}
            </p>
            {/* Gauges count what the Atelier has verified. Against a level it has
                not tested they would read as "vous savez 0 mot", so they wait. */}
            {!declared && (coursWords[1] > 0 || coursRules[1] > 0) && (
              <div className="nb-rv__tracks">
                {coursWords[1] > 0 && (
                  <div className="nb-rv__track">
                    <span>Mots</span>
                    <ProgressRule value={coursWords[0]} max={coursWords[1]} label="Mots vérifiés" caption={`${coursWords[0]} / ${coursWords[1]}`} />
                  </div>
                )}
                {coursRules[1] > 0 && (
                  <div className="nb-rv__track">
                    <span>Règles</span>
                    <ProgressRule value={coursRules[0]} max={coursRules[1]} label="Règles vérifiées" caption={`${coursRules[0]} / ${coursRules[1]}`} />
                  </div>
                )}
              </div>
            )}
          </Surface>
        )}
      </section>

      {/* ---- Le Registre ---- */}
      <section className="nb-rv__sec" aria-label="Le registre">
        <NbSectionHead t="Le registre" n={null} />
        {failed.stats && failed.grammar ? (
          <ArchiveNotice message="Le registre n’a pas pu être ouvert." onRetry={() => void load()} />
        ) : (
          <Surface className="nb-sec">
            <div className="nb-lines">
              {stats ? (
                <>
                  <Line label="Mots acquis" value={String(stats.words_mastered)} />
                  <Line label="Mots en cours" value={String(stats.words_learning)} />
                  <Line label="Mots à revoir aujourd’hui" value={String(stats.reviews_due_today)} />
                </>
              ) : (
                <p className="nb-gap">Le compte des mots n’a pas suivi cette fois-ci.</p>
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
                <p className="nb-gap">Le compte des règles n’a pas suivi cette fois-ci.</p>
              )}
            </div>
            {grammarBar.length > 0 && (
              <>
                <div
                  className="nb-bar"
                  role="img"
                  aria-label={
                    'Règles : ' + grammarBar.map((state) => `${state.n} ${state.label}`).join(', ')
                  }
                >
                  {grammarBar.map((state) => (
                    <i
                      key={state.key}
                      data-tone={state.tone}
                      style={{ width: (100 * state.n) / Math.max(1, grammarStarted) + '%' }}
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

      {/* ---- La Collection ---- */}
      <section className="nb-rv__sec" aria-label="La collection">
        <NbSectionHead
          t="La collection"
          n={collectionPieces > 0 ? `${collectionPieces} pièce${collectionPieces > 1 ? 's' : ''}` : null}
        />
        {failed.collection ? (
          <ArchiveNotice message="La collection n’a pas pu être sortie de sa boîte." onRetry={() => void load()} />
        ) : collectionPieces === 0 ? (
          <StateBlock
            tone="empty"
            title="Rien d’accroché encore"
            body="La collection commence avec la première édition bouclée."
          />
        ) : (
          <Surface className="nb-sec">
            {unlocked.length > 0 && (
              <div className="nb-lines">
                {unlocked.map((item) => {
                  const copy = ACHIEVEMENT_COPY[item.achievement_key];
                  const date = frenchDate(item.unlocked_at);
                  const tier = TIER_LABEL[item.tier] || null;
                  return (
                    <div className="nb-piece" key={item.achievement_id}>
                      <ShapeToken kind="reward" size="sm" />
                      <span className="nb-piece__main">
                        <span className="nb-piece__t">{copy?.title || 'Distinction de l’Atelier'}</span>
                        <span className="nb-piece__m">
                          {copy?.note || 'Décernée au fil des séances.'}{tier ? ` · ${tier}` : ''}
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

      <p className="nb-foot">{stamp ? `Le Relevé · arrêté au ${stamp}` : 'Le Relevé · vos chiffres, rien d’autre'}</p>
    </div>
  );
}
