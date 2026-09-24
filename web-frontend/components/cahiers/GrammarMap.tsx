/* WP-S7 — the grammar map (Cahier → Règles).

   The syllabus drawn with the mark's shapes, one shape per rule, by sub-band.
   A rule's shape fills as it lives: ghost (not met, the solid shape in
   --av2-line) → a tint of its colour (introduced) → half colour (proficient)
   → ink (held). Flat fills, never an outline or a stroke. Tapping a rule opens
   its sheet: the rule card, the coach slot, «Forge this rule» (the one 3D
   primary) and «Test out this rule». Éclair sits under the map once a pair of
   contrasting rules is open.

   Sans throughout: the Cahier's head is the screen's one Garamond line. */

import React, { useEffect, useId, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import Router from 'next/router';
import useSWR from 'swr';
import toast from 'react-hot-toast';

import { Action, CastPortrait, Surface } from '@/components/atelier-v2/ui';
import { RuleCard, RULE_CARD_SPEAKERS } from '@/components/atelier-v2/rule/RuleCard';
import { forgeCopy } from '@/lib/forge-copy';
import type { RuleShape } from '@/lib/forge-progress';
import {
  eclairHref,
  eclairPairs,
  visibleBands,
  findMapRule,
  forgeHref,
  grammarMapEnabled,
  mapBands,
  mapCounts,
  mapFill,
  mapRuleShape,
  mapStageOf,
  MAP_STAGES,
  type GrammarMapPayload,
  type GrammarMapRule,
  type MapFill,
} from '@/lib/grammar-map';
import { fillMomentum, momentumCopy, type MapStage, type MomentumCopy } from '@/lib/momentum-copy';
import { usableCard } from '@/lib/rule-card';
import type { ControlLanguage } from '@/types/daily-journey';
import api from '@/services/api';

const SHAPE_PATHS: Record<RuleShape, string> = {
  circle: 'M 2,12 a 10,10 0 1,0 20,0 a 10,10 0 1,0 -20,0 Z',
  square: 'M 5,2 h 14 a 3,3 0 0 1 3,3 v 14 a 3,3 0 0 1 -3,3 h -14 a 3,3 0 0 1 -3,-3 v -14 a 3,3 0 0 1 3,-3 Z',
  triangle: 'M 12,2 L 23,22 L 1,22 Z',
};

/** One rule's shape at its stage. Pure SVG: filled paths, no stroke. */
export function MapShape({ shape, fill, size = 24 }: { shape: RuleShape; fill: MapFill; size?: number }) {
  const clip = `gm-half-${useId().replace(/:/g, '')}`;
  const d = SHAPE_PATHS[shape] || SHAPE_PATHS.circle;
  return (
    <svg className="gm-shape" data-shape={shape} data-fill={fill} width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      {fill === 'half' && (
        <defs>
          <clipPath id={clip}>
            <rect x="0" y="12" width="24" height="12" />
          </clipPath>
        </defs>
      )}
      <path className="gm-shape__base" d={d} />
      {fill === 'half' && <path className="gm-shape__half" d={d} clipPath={`url(#${clip})`} />}
    </svg>
  );
}

function stageLine(copy: MomentumCopy, rule: GrammarMapRule): string {
  const stage = mapStageOf(rule);
  return [
    copy.stages[stage],
    rule.due && stage !== 'ghost' ? copy.map_due : null,
    rule.tested_out ? copy.map_tested_out : null,
  ].filter(Boolean).join(' · ');
}

function coachOf(rule: GrammarMapRule): { id: string; name: string | null } | null {
  if (rule.coach?.id) return { id: rule.coach.id, name: rule.coach.name ?? null };
  const speaker = rule.rule_card?.speaker ? String(rule.rule_card.speaker) : '';
  return speaker ? { id: speaker, name: RULE_CARD_SPEAKERS[speaker] ?? null } : null;
}

function MapRuleSheet({
  rule,
  language,
  copy,
  onClose,
  onOpenPage,
}: {
  rule: GrammarMapRule;
  language: ControlLanguage;
  copy: MomentumCopy;
  onClose: () => void;
  onOpenPage?: (conceptId: number) => void;
}) {
  const fc = forgeCopy(language);
  const [pending, setPending] = useState(false);
  const shape = mapRuleShape(rule);
  const stage = mapStageOf(rule);
  const card = usableCard(rule.rule_card) ? rule.rule_card : null;
  // The card already shows its speaker; the coach row is WP-S5's own coach,
  // or the speaker of a rule whose card cannot be shown.
  const coach = rule.coach?.id || !card ? coachOf(rule) : null;
  const headingId = `gm-sheet-${rule.concept_id}`;

  const testOut = async () => {
    if (pending) return;
    setPending(true);
    try {
      const started = await api.startForgeTestOut(rule.concept_id);
      await Router.push(`/atelier?testout=${started.session_id}`);
    } catch (error) {
      console.error(error);
      toast.error(fc.test_out_failed_start);
      setPending(false);
    }
  };

  return (
    <section className="gm-sheet" aria-labelledby={headingId}>
      <div className="gm-sheet__head">
        <MapShape shape={shape} fill={mapFill(stage)} size={32} />
        <div className="gm-sheet__text">
          <p className="gm-sheet__title" id={headingId} lang="fr">{rule.title_fr}</p>
          <p className="gm-sheet__stage">{stageLine(copy, rule)}</p>
        </div>
        <button type="button" className="gm-sheet__close" onClick={onClose} aria-label={copy.map_close}>×</button>
      </div>
      {coach && (
        <div className="gm-sheet__coach">
          <CastPortrait characterId={coach.id} name={coach.name || undefined} size="sm" ring />
          {coach.name && <span>{fillMomentum(copy.map_coach, { name: coach.name })}</span>}
        </div>
      )}
      {card && <RuleCard card={card} language={language} variant="inline" conceptId={rule.concept_id} />}
      <div className="gm-sheet__actions">
        <Link className="av2-btn av2-btn--primary gm-sheet__forge" href={forgeHref(rule.concept_id)}>
          {copy.map_forge}
        </Link>
        <Action tone="secondary" inline pending={pending} pendingLabel={fc.test_out_starting} onClick={testOut}>
          {fc.test_out_action}
        </Action>
        {onOpenPage && (
          <button type="button" className="gm-sheet__page" onClick={() => onOpenPage(rule.concept_id)}>
            {copy.map_open_page}
          </button>
        )}
      </div>
    </section>
  );
}

export function GrammarMapView({
  payload,
  language,
  selectedId,
  onSelect,
  onOpenPage,
}: {
  payload: GrammarMapPayload;
  language: ControlLanguage;
  selectedId: number | null;
  onSelect: (conceptId: number | null) => void;
  onOpenPage?: (conceptId: number) => void;
}) {
  const copy = momentumCopy(language);
  const [expanded, setExpanded] = useState(false);
  const allBands = mapBands(payload);
  const bands = visibleBands(allBands, expanded);
  const counts = mapCounts(payload);
  const selected = findMapRule(payload, selectedId);
  const pairs = eclairPairs(payload);
  return (
    <Surface as="section" className="gm" aria-label={copy.map_label}>
      <div className="gm-head">
        <p className="gm-title">{copy.map_title}</p>
        <p className="gm-counts">{fillMomentum(copy.map_counts, counts)}</p>
      </div>
      {bands.map((band) => (
        <div className="gm-band" key={band.band}>
          <p className="gm-band__label" aria-label={fillMomentum(copy.map_band_label, { band: band.band })}>{band.band}</p>
          <ul className="gm-rules">
            {band.rules.map((rule) => {
              const stage = mapStageOf(rule);
              const on = selected?.concept_id === rule.concept_id;
              return (
                <li key={rule.concept_id}>
                  <button
                    type="button"
                    className="gm-rule"
                    data-stage={stage}
                    data-due={rule.due && stage !== 'ghost' ? 'true' : undefined}
                    aria-pressed={on}
                    aria-label={fillMomentum(copy.map_rule_aria, { title: rule.title_fr, stage: stageLine(copy, rule) })}
                    onClick={() => onSelect(on ? null : rule.concept_id)}
                  >
                    <MapShape shape={mapRuleShape(rule)} fill={mapFill(stage)} />
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
      {allBands.length > bands.length || expanded ? (
        <button type="button" className="gm-more" aria-expanded={expanded} onClick={() => setExpanded((value) => !value)}>
          {expanded ? copy.map_show_less : copy.map_show_all}
        </button>
      ) : null}
      <ul className="gm-legend" aria-hidden="true">
        {MAP_STAGES.map((stage: MapStage) => (
          <li key={stage}>
            <MapShape shape="square" fill={mapFill(stage)} size={14} />
            <span>{copy.stages[stage]}</span>
          </li>
        ))}
      </ul>
      {selected && (
        <MapRuleSheet
          key={selected.concept_id}
          rule={selected}
          language={language}
          copy={copy}
          onClose={() => onSelect(null)}
          onOpenPage={onOpenPage}
        />
      )}
      {pairs.length > 0 && (
        <div className="gm-eclair">
          <p className="gm-eclair__title">{copy.map_eclair_title}</p>
          <p className="gm-eclair__hint">{copy.eclair_hint}</p>
          <ul className="gm-eclair__pairs">
            {pairs.slice(0, 3).map((pair) => (
              <li key={pair.pair}>
                <Link className="gm-eclair__pair" href={eclairHref(pair.pair)}>
                  <span className="gm-eclair__names" lang="fr">
                    {fillMomentum(copy.eclair_pair_label, { a: pair.rules[0]?.title_fr || '', b: pair.rules[1]?.title_fr || '' })}
                  </span>
                  <span className="gm-eclair__best">
                    {pair.plays > 0 ? fillMomentum(copy.eclair_best, { n: pair.best }) : copy.eclair_best_none}
                  </span>
                  <span className="gm-eclair__go">{copy.eclair_action}</span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Surface>
  );
}

/** The map as the Règles tab shows it: fetched, the open recorded once. */
export default function GrammarMap({
  language,
  onOpenPage,
}: {
  language: ControlLanguage;
  onOpenPage?: (conceptId: number) => void;
}) {
  const { data } = useSWR<GrammarMapPayload | null>('/atelier/forge/map', async () => {
    try {
      return await api.getGrammarMap();
    } catch {
      return null; // the map is an addition: the index still works without it
    }
  });
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const recorded = useRef(false);
  const visible = Boolean(data && grammarMapEnabled(data) && mapBands(data).length > 0);
  useEffect(() => {
    if (!visible || recorded.current) return;
    recorded.current = true;
    void api.recordGrammarMapOpened();
  }, [visible]);
  const payload = useMemo(() => data ?? null, [data]);
  if (!payload || !visible) return null;
  return (
    <>
      <GrammarMapStyles />
      <GrammarMapView
        payload={payload}
        language={language}
        selectedId={selectedId}
        onSelect={setSelectedId}
        onOpenPage={onOpenPage}
      />
    </>
  );
}

/* Tokens only; no border, no outline, no stroke on any shape. */
export function GrammarMapStyles() {
  return (
    <style jsx global>{`
.av2 .gm { display: flex; flex-direction: column; gap: 14px; padding: 16px; min-width: 0; }
.av2 .gm-head { display: flex; flex-direction: column; gap: 2px; }
.av2 .gm-title { margin: 0; font-size: var(--av2-t-body); font-weight: 700; color: var(--av2-ink); }
.av2 .gm-counts { margin: 0; font-size: var(--av2-t-meta); font-weight: 600; color: var(--av2-muted); font-variant-numeric: tabular-nums; }
.av2 .gm-band { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.av2 .gm-band__label { margin: 0; font-size: var(--av2-t-meta); font-weight: 700; color: var(--av2-muted); font-variant-numeric: tabular-nums; }
.av2 .gm-rules { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 0; }
.av2 .gm-rule {
  display: grid;
  place-items: center;
  width: var(--av2-tap);
  height: var(--av2-tap);
  padding: 0;
  border: 0;
  border-radius: 12px;
  background: transparent;
  cursor: pointer;
}
.av2 .gm-rule[aria-pressed='true'] { box-shadow: inset 0 0 0 2px var(--av2-blue); }
.av2 .gm-rule:focus-visible { box-shadow: 0 0 0 3px var(--av2-focus); outline: none; }
.av2 .gm-rule { position: relative; }
.av2 .gm-rule[data-due='true']::after {
  content: '';
  position: absolute;
  top: 8px;
  right: 8px;
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: var(--av2-red);
}

.av2 .gm-shape { display: block; overflow: visible; }
.av2 .gm-shape path { stroke: none; }
.av2 .gm-shape[data-fill='ghost'] .gm-shape__base { fill: var(--av2-line); }
.av2 .gm-shape[data-fill='ink'] .gm-shape__base { fill: var(--av2-ink); }
.av2 .gm-shape[data-fill='tint'] .gm-shape__base,
.av2 .gm-shape[data-fill='half'] .gm-shape__base { fill-opacity: 0.32; }
.av2 .gm-shape[data-shape='circle'] .gm-shape__base,
.av2 .gm-shape[data-shape='circle'] .gm-shape__half { fill: var(--av2-blue); }
.av2 .gm-shape[data-shape='square'] .gm-shape__base,
.av2 .gm-shape[data-shape='square'] .gm-shape__half { fill: var(--av2-yellow); }
.av2 .gm-shape[data-shape='triangle'] .gm-shape__base,
.av2 .gm-shape[data-shape='triangle'] .gm-shape__half { fill: var(--av2-red); }
.av2 .gm-shape[data-fill='ghost'][data-shape] .gm-shape__base { fill: var(--av2-line); fill-opacity: 1; }
.av2 .gm-shape[data-fill='ink'][data-shape] .gm-shape__base { fill: var(--av2-ink); fill-opacity: 1; }

.av2 .gm-more {
  align-self: flex-start;
  min-height: var(--av2-tap);
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--av2-ink-2);
  font: 600 var(--av2-t-label)/1.2 var(--av2-sans);
  text-decoration: underline;
  text-underline-offset: 3px;
  cursor: pointer;
}
.av2 .gm-legend { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 6px 14px; }
.av2 .gm-legend li { display: inline-flex; align-items: center; gap: 6px; font-size: var(--av2-t-meta); font-weight: 600; color: var(--av2-muted); }

.av2 .gm-sheet {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px;
  border-radius: var(--av2-r-card);
  background: var(--av2-paper);
  animation: av2-fade 0.2s;
  min-width: 0;
}
.av2 .gm-sheet__head { display: flex; align-items: center; gap: 12px; min-width: 0; }
.av2 .gm-sheet__text { flex: 1 1 auto; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.av2 .gm-sheet__title { margin: 0; font-size: var(--av2-t-body); font-weight: 700; line-height: 1.3; color: var(--av2-ink); overflow-wrap: anywhere; }
.av2 .gm-sheet__stage { margin: 0; font-size: var(--av2-t-meta); font-weight: 600; color: var(--av2-muted); }
.av2 .gm-sheet__close {
  flex: none;
  width: var(--av2-tap);
  height: var(--av2-tap);
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: var(--av2-ink-2);
  font: 600 22px/1 var(--av2-sans);
  cursor: pointer;
}
.av2 .gm-sheet__coach { display: flex; align-items: center; gap: 10px; font-size: var(--av2-t-label); font-weight: 600; color: var(--av2-ink-2); }
.av2 .gm-sheet__actions { display: flex; flex-direction: column; align-items: stretch; gap: 10px; }
.av2 .gm-sheet__actions .av2-btn--secondary { align-self: flex-start; }
.av2 .gm-sheet__page {
  align-self: flex-start;
  min-height: var(--av2-tap);
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--av2-ink-2);
  font: 600 var(--av2-t-label)/1.2 var(--av2-sans);
  text-decoration: underline;
  text-underline-offset: 3px;
  cursor: pointer;
}

.av2 .gm-eclair { display: flex; flex-direction: column; gap: 6px; }
.av2 .gm-eclair__title { margin: 0; font-size: var(--av2-t-label); font-weight: 700; color: var(--av2-ink); }
.av2 .gm-eclair__hint { margin: 0; font-size: var(--av2-t-meta); color: var(--av2-ink-2); }
.av2 .gm-eclair__pairs { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.av2 .gm-eclair__pair {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 2px 12px;
  align-items: center;
  min-height: var(--av2-tap);
  padding: 10px 14px;
  border-radius: var(--av2-r-tile);
  background: var(--av2-paper);
  box-shadow: 0 3px 0 var(--av2-line-2);
  color: var(--av2-ink);
  text-decoration: none;
}
.av2 .gm-eclair__names { font-size: var(--av2-t-label); font-weight: 700; overflow-wrap: anywhere; }
.av2 .gm-eclair__best { grid-column: 1; font-size: var(--av2-t-meta); font-weight: 600; color: var(--av2-muted); }
.av2 .gm-eclair__go { grid-column: 2; grid-row: 1 / span 2; font-size: var(--av2-t-meta); font-weight: 700; color: var(--av2-red); white-space: nowrap; }
@media (prefers-reduced-motion: reduce) {
  .av2 .gm-sheet { animation: none; }
}
    `}</style>
  );
}
