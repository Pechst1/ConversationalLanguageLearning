/* WP-S6 — La Forge, beauty and clarity: the séance's own pieces.

   - ForgeStair: the rule's staircase — six steps drawn in the rule's shape,
     rising; done steps ink, the current step in the shape's colour, the rest
     ghosts in --av2-line-2. Flat fills, never a stroke (owner, 2026-09-22).
   - ForgeCount: the top bar's name and quiet «n of N» (replaces «0/20»).
   - ForgeHead: the rule row — staircase, the rule's name, «Step 3 of 6 ·
     build», the rule pill, and «Test out this rule» on its own row.
   - ForgeRuleChange: the small card when the séance moves to another rule —
     the rule's name and shape, and a coach portrait slot (WP-S5 passes
     `coach`; until then the rule card's speaker fills it).
   - ForgeRecapRules: the recap's per-rule progress (replaces the tally).

   Sans throughout: the screen's one Garamond line is the exercise prompt, or
   the rule card's example on its own screen, or the recap's headline. Every
   colour is an --av2-* token. */

import React from 'react';

import { CastPortrait, Chip, ShapeToken } from '@/components/atelier-v2/ui';
import { fillForge, type ForgeCopy } from '@/lib/forge-copy';
import type { PortraitMood } from '@/lib/onboarding-portraits';
import { comboTokens } from '@/lib/forge-combo';
import { FORGE_STEPS, staircase, type RecapRuleRow, type RuleShape } from '@/lib/forge-progress';

type Node = React.ReactNode;

/** A coach (WP-S5): a cast member who teaches the rule. */
export type ForgeCoach = { id: string; name?: string | null; mood?: PortraitMood | null };

/* WP-S7 (live check at 375 px): the steps were 8–18 units on a 14-unit pitch
   drawn into 72 px, so they touched and the three ghosts read as one grey
   block. Each step is now its own readable shape, 12 → 14 px, on a 17 px
   pitch (a clear gap of 3 px or more), and the stair rises 2 px a step. */
const STEP = 17;
const RISE = 2;
const BASE = 26;
const STAIR_WIDTH = STEP * FORGE_STEPS;
const STAIR_HEIGHT = BASE + 2;

function stepShape(shape: RuleShape, index: number) {
  const size = 12 + index * 0.4; // 12 … 14: each step reads on its own
  const cx = index * STEP + STEP / 2;
  const bottom = BASE - index * RISE; // the stair rises
  const top = bottom - size;
  if (shape === 'circle') return <circle cx={cx} cy={bottom - size / 2} r={size / 2} />;
  if (shape === 'triangle') {
    return <polygon points={`${cx},${top} ${cx + size / 2 + 1},${bottom} ${cx - size / 2 - 1},${bottom}`} />;
  }
  return <rect x={cx - size / 2} y={top} width={size} height={size} rx={3} />;
}

export function ForgeStair({ shape, rung, label, size = 'md' }: { shape: RuleShape; rung: number; label: string; size?: 'sm' | 'md' }) {
  const steps = staircase(rung);
  return (
    <svg
      className="forge-stair"
      data-shape={shape}
      data-size={size}
      viewBox={`0 0 ${STAIR_WIDTH} ${STAIR_HEIGHT}`}
      role="img"
      aria-label={label}
    >
      {steps.map((state, index) => (
        <g key={index} className="forge-stair__step" data-state={state}>
          {stepShape(shape, index)}
        </g>
      ))}
    </svg>
  );
}

/** The top bar's middle: the surface's name, then the séance's quiet count. */
export function ForgeCount({ copy, count }: { copy: ForgeCopy; count: string }) {
  return (
    <p className="forge-count">
      <span className="forge-count__name">{copy.surface_name}</span>
      {count && <span className="forge-count__n">{count}</span>}
    </p>
  );
}

export function ForgeHead({
  copy,
  title,
  shape,
  rung,
  step,
  stairLabel,
  reprise = false,
  eyebrow,
  ruleLabel,
  ruleOpen = false,
  onRule,
  testOut,
}: {
  copy: ForgeCopy;
  title: Node;
  shape: RuleShape;
  rung: number;
  step: string;
  stairLabel: string;
  reprise?: boolean;
  /** A test-out names itself here instead of the step. */
  eyebrow?: string | null;
  ruleLabel: string;
  ruleOpen?: boolean;
  onRule?: () => void;
  testOut?: { pending?: boolean; onClick: () => void } | null;
}) {
  return (
    <div className="forge-head">
      <div className="forge-head__row">
        <ForgeStair shape={shape} rung={rung} label={stairLabel} />
        <div className="forge-head__text">
          <p className="forge-head__rule" lang="fr">{title}</p>
          <p className="forge-head__step">
            <span>{eyebrow || step}</span>
            {reprise && <span className="forge-head__reprise"> · {copy.reprise}</span>}
          </p>
        </div>
        {onRule && (
          <Chip
            className="forge-head__pill"
            icon={<ShapeToken kind="reward" size="sm" />}
            aria-pressed={ruleOpen}
            aria-expanded={ruleOpen}
            onClick={onRule}
          >
            {ruleLabel}
          </Chip>
        )}
      </div>
      {testOut && (
        <button
          type="button"
          className="forge-head__test-out"
          disabled={testOut.pending}
          onClick={testOut.onClick}
        >
          {testOut.pending ? copy.test_out_starting : copy.test_out_action}
        </button>
      )}
    </div>
  );
}

export function ForgeRuleChange({
  copy,
  title,
  shape,
  coach,
}: {
  copy: ForgeCopy;
  title: Node;
  shape: RuleShape;
  /** WP-S5: the rule's coach; the slot stays empty without one. */
  coach?: ForgeCoach | null;
}) {
  return (
    <div className="forge-change" role="status" aria-live="polite">
      <span className="forge-change__shape" data-shape={shape} aria-hidden="true" />
      <div className="forge-change__text">
        <p className="forge-change__label">{copy.next_rule}</p>
        <p className="forge-change__rule" lang="fr">{title}</p>
        {coach?.name && <p className="forge-change__coach">{fillForge(copy.coach_label, { name: coach.name })}</p>}
      </div>
      {coach?.id && (
        <span className="forge-change__portrait">
          <CastPortrait characterId={coach.id} name={coach.name || undefined} mood={coach.mood || 'neutral'} size="sm" ring />
        </span>
      )}
    </div>
  );
}

export function ForgeRecapRules({
  copy,
  rows,
  proofRight,
  proofFixed,
}: {
  copy: ForgeCopy;
  rows: RecapRuleRow[];
  proofRight: string;
  proofFixed: string;
}) {
  if (!rows.length) return null;
  return (
    <ul className="forge-recap" aria-label={copy.recap_rules_label}>
      {rows.map((row) => (
        <li className="forge-recap__rule" key={row.conceptId}>
          <div className="forge-recap__head">
            <ForgeStair shape={row.shape} rung={row.rung} label={row.step} size="sm" />
            <div className="forge-recap__text">
              <p className="forge-recap__title" lang="fr">{row.title}</p>
              <p className="forge-recap__step">{row.step}</p>
            </div>
          </div>
          <p className="forge-recap__change" data-changed={row.changed ? 'true' : undefined}>{row.change}</p>
          {row.proof.length > 0 && (
            <ul className="forge-recap__proof">
              {row.proof.map((line, index) => (
                <li key={index} data-fixed={line.fixed ? 'true' : undefined}>
                  <ShapeToken kind={line.fixed ? 'action' : 'done'} size="sm" title={line.fixed ? proofFixed : proofRight} />
                  <span lang="fr">{line.fr}</span>
                </li>
              ))}
            </ul>
          )}
          <p className="forge-recap__due">{row.due}</p>
        </li>
      ))}
    </ul>
  );
}

/* ---------- WP-S7 · momentum ---------- */

/**
 * The combo: five tokens in the rule's shape, lit from the left by the run of
 * checked right answers (ghosts in --av2-line-2 otherwise), and the run's
 * number once it has started. The newest lit token pops (Reduce Motion: no
 * pop). It sits in the top bar where the red «● n» sat.
 */
export function ForgeCombo({ shape, run, label }: { shape: RuleShape; run: number; label: string }) {
  const tokens = comboTokens(run);
  const lit = tokens.filter(Boolean).length;
  return (
    <span className="forge-combo" role="img" aria-label={label} data-shape={shape} data-run={run}>
      {tokens.map((on, index) => (
        <span
          // The newest lit token remounts with the run, so it pops once.
          key={index === lit - 1 ? `lit-${index}-${run}` : `t-${index}`}
          className="forge-combo__token"
          data-lit={on ? 'true' : undefined}
          data-new={index === lit - 1 ? 'true' : undefined}
          aria-hidden="true"
        />
      ))}
      {run > 0 && <span className="forge-combo__n" aria-hidden="true">{run}</span>}
    </span>
  );
}

/** The recap's best run of the séance, drawn with the same tokens. */
export function ForgeBestCombo({ shape, best, line }: { shape: RuleShape; best: number; line: string | null }) {
  if (!line || best <= 0) return null;
  return (
    <p className="forge-best">
      <ForgeCombo shape={shape} run={best} label={line} />
      <span className="forge-best__text">{line}</span>
    </p>
  );
}

/** A passed test-out's rare token: the yellow reward square on its press. */
export function ForgeRareToken({ title, sub }: { title: string; sub: string }) {
  return (
    <div className="forge-token" role="status">
      <span className="forge-token__mark" aria-hidden="true" />
      <div className="forge-token__text">
        <p className="forge-token__title">{title}</p>
        <p className="forge-token__sub">{sub}</p>
      </div>
    </div>
  );
}

/* Every rule is `.av2 .forge-…` or `.ep-recap .forge-…` (RecapModal's section
   bridges the tokens). Tokens only; no border, no outline, no stroke. */
export function ForgeStyles() {
  return (
    <style jsx global>{`
.av2 .forge-stair, .ep-recap .forge-stair { flex: none; width: 102px; height: 28px; overflow: visible; }
.av2 .forge-stair[data-size='sm'], .ep-recap .forge-stair[data-size='sm'] { width: 77px; height: 21px; }
.av2 .forge-stair__step, .ep-recap .forge-stair__step { fill: var(--av2-line-2); stroke: none; transition: fill 0.3s ease; }
.av2 .forge-stair__step[data-state='done'], .ep-recap .forge-stair__step[data-state='done'] { fill: var(--av2-ink); }
.av2 .forge-stair[data-shape='circle'] .forge-stair__step[data-state='current'],
.ep-recap .forge-stair[data-shape='circle'] .forge-stair__step[data-state='current'] { fill: var(--av2-blue); }
.av2 .forge-stair[data-shape='square'] .forge-stair__step[data-state='current'],
.ep-recap .forge-stair[data-shape='square'] .forge-stair__step[data-state='current'] { fill: var(--av2-yellow); }
.av2 .forge-stair[data-shape='triangle'] .forge-stair__step[data-state='current'],
.ep-recap .forge-stair[data-shape='triangle'] .forge-stair__step[data-state='current'] { fill: var(--av2-red); }
@media (prefers-reduced-motion: no-preference) {
  .av2 .forge-stair__step[data-state='current'] { animation: av2-pop 0.3s; transform-box: fill-box; transform-origin: 50% 100%; }
}

.av2 .forge-count { flex: 1 1 auto; min-width: 0; margin: 0; display: flex; align-items: baseline; justify-content: center; gap: 8px; white-space: nowrap; }
.av2 .forge-count__name { font-size: var(--av2-t-label); font-weight: 700; color: var(--av2-ink); }
.av2 .forge-count__n { font-size: var(--av2-t-meta); font-weight: 600; color: var(--av2-muted); font-variant-numeric: tabular-nums; }

.av2 .forge-head { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.av2 .forge-head__row { display: flex; align-items: center; gap: 12px; min-width: 0; }
.av2 .forge-head__text { flex: 1 1 auto; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.av2 .forge-head__rule { margin: 0; font-size: var(--av2-t-label); font-weight: 600; line-height: 1.3; color: var(--av2-ink-2); overflow-wrap: anywhere; }
.av2 .forge-head__step { margin: 0; font-size: var(--av2-t-meta); font-weight: 700; line-height: 1.3; color: var(--av2-muted); font-variant-numeric: tabular-nums; }
.av2 .forge-head__reprise { color: var(--av2-blue); }
.av2 .forge-head__pill { flex: none; min-height: var(--av2-tap); font-size: var(--av2-t-meta); font-weight: 600; }
.av2 .forge-head__pill[aria-pressed='true'] { background: var(--av2-line); }
.av2 .forge-head__test-out {
  align-self: flex-start;
  min-height: var(--av2-tap);
  margin: 0 0 0 114px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--av2-ink-2);
  font: 600 var(--av2-t-label)/1.2 var(--av2-sans);
  text-decoration: underline;
  text-underline-offset: 3px;
  cursor: pointer;
}
.av2 .forge-head__test-out:disabled { color: var(--av2-muted); text-decoration: none; cursor: default; }
@media (max-width: 360px) { .av2 .forge-head__test-out { margin-left: 0; } }

/* One Garamond line per screen: in the forge the exercise prompt is it, so the
   legacy rule panel (a rule with no authored card) is set in the sans. */
.av2 .forge-sheet .ep-rule .rule-panel > p:first-of-type,
.av2 .forge-sheet .ep-rule .examples p,
.av2 .forge-sheet .ep-rule .ep-rule__ex {
  font-family: var(--av2-sans);
  font-style: normal;
  font-weight: 600;
  font-size: var(--av2-t-body);
}

.av2 .forge-change {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: var(--av2-r-card);
  background: var(--av2-card);
  min-width: 0;
  animation: av2-fade 0.25s;
}
.av2 .forge-change__shape { flex: none; width: 22px; height: 22px; background: var(--av2-blue); border-radius: 999px; }
.av2 .forge-change__shape[data-shape='square'] { background: var(--av2-yellow); border-radius: 5px; }
.av2 .forge-change__shape[data-shape='triangle'] { background: var(--av2-red); border-radius: 0; clip-path: polygon(50% 0, 100% 100%, 0 100%); }
.av2 .forge-change__text { flex: 1 1 auto; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.av2 .forge-change__label { margin: 0; font-size: var(--av2-t-meta); font-weight: 700; color: var(--av2-muted); }
.av2 .forge-change__rule { margin: 0; font-size: var(--av2-t-body); font-weight: 700; line-height: 1.3; color: var(--av2-ink); overflow-wrap: anywhere; }
.av2 .forge-change__coach { margin: 0; font-size: var(--av2-t-meta); color: var(--av2-ink-2); }
.av2 .forge-change__portrait { flex: none; display: inline-flex; }

.av2 .forge-recap, .ep-recap .forge-recap { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; min-width: 0; }
.av2 .forge-recap__rule, .ep-recap .forge-recap__rule {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px 16px;
  border-radius: var(--av2-r-card);
  background: var(--av2-card);
  min-width: 0;
}
.av2 .forge-recap__head, .ep-recap .forge-recap__head { display: flex; align-items: center; gap: 12px; min-width: 0; }
.av2 .forge-recap__text, .ep-recap .forge-recap__text { min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.av2 .forge-recap__title, .ep-recap .forge-recap__title { margin: 0; font-size: var(--av2-t-body); font-weight: 700; line-height: 1.3; color: var(--av2-ink); overflow-wrap: anywhere; }
.av2 .forge-recap__step, .ep-recap .forge-recap__step { margin: 0; font-size: var(--av2-t-meta); font-weight: 600; color: var(--av2-muted); }
.av2 .forge-recap__change, .ep-recap .forge-recap__change { margin: 0; font-size: var(--av2-t-label); font-weight: 600; color: var(--av2-ink-2); }
.av2 .forge-recap__change[data-changed='true'], .ep-recap .forge-recap__change[data-changed='true'] { color: var(--av2-green); }
.av2 .forge-recap__proof, .ep-recap .forge-recap__proof { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.av2 .forge-recap__proof li, .ep-recap .forge-recap__proof li { display: flex; align-items: baseline; gap: 8px; font-size: var(--av2-t-body); line-height: 1.35; color: var(--av2-ink); overflow-wrap: anywhere; }
.av2 .forge-recap__proof .av2-shape, .ep-recap .forge-recap__proof .av2-shape { flex: none; align-self: center; }
.av2 .forge-recap__due, .ep-recap .forge-recap__due { margin: 0; font-size: var(--av2-t-meta); font-weight: 600; color: var(--av2-muted); }

/* WP-S7: at the narrowest phones the stair steps down a size (still ≥ 10 px a step). */
@media (max-width: 340px) {
  .av2 .forge-stair:not([data-size='sm']) { width: 90px; height: 25px; }
  .av2 .forge-head__test-out { margin-left: 0; }
}

/* WP-S7 · the combo: five flat tokens in the rule's shape, no stroke. */
.av2 .forge-combo, .ep-recap .forge-combo { flex: none; display: inline-flex; align-items: center; gap: 3px; min-height: 12px; }
.av2 .forge-combo__token, .ep-recap .forge-combo__token {
  width: 9px;
  height: 9px;
  border-radius: 999px;
  background: var(--av2-line-2);
  transition: background-color 0.2s ease;
}
.av2 .forge-combo[data-shape='square'] .forge-combo__token,
.ep-recap .forge-combo[data-shape='square'] .forge-combo__token { border-radius: 2px; }
.av2 .forge-combo[data-shape='triangle'] .forge-combo__token,
.ep-recap .forge-combo[data-shape='triangle'] .forge-combo__token { border-radius: 0; width: 10px; clip-path: polygon(50% 0, 100% 100%, 0 100%); }
.av2 .forge-combo[data-shape='circle'] .forge-combo__token[data-lit='true'],
.ep-recap .forge-combo[data-shape='circle'] .forge-combo__token[data-lit='true'] { background: var(--av2-blue); }
.av2 .forge-combo[data-shape='square'] .forge-combo__token[data-lit='true'],
.ep-recap .forge-combo[data-shape='square'] .forge-combo__token[data-lit='true'] { background: var(--av2-yellow); }
.av2 .forge-combo[data-shape='triangle'] .forge-combo__token[data-lit='true'],
.ep-recap .forge-combo[data-shape='triangle'] .forge-combo__token[data-lit='true'] { background: var(--av2-red); }
.av2 .forge-combo__n, .ep-recap .forge-combo__n {
  margin-left: 3px;
  font-size: var(--av2-t-meta);
  font-weight: 700;
  color: var(--av2-ink);
  font-variant-numeric: tabular-nums;
}
@media (prefers-reduced-motion: no-preference) {
  .av2 .forge-combo__token[data-new='true'] { animation: av2-pop 0.3s; }
}

.av2 .forge-recap__eclair, .ep-recap .forge-recap__eclair { align-self: flex-start; display: inline-flex; flex-direction: column; align-items: flex-start; gap: 2px; text-decoration: none; }
.av2 .forge-recap__eclair-pair, .ep-recap .forge-recap__eclair-pair { font-size: var(--av2-t-meta); font-weight: 600; color: var(--av2-muted); }
.av2 .forge-best, .ep-recap .forge-best { margin: 0; display: flex; align-items: center; gap: 10px; font-size: var(--av2-t-label); font-weight: 600; color: var(--av2-ink-2); }

.av2 .forge-token {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
  border-radius: var(--av2-r-card);
  background: var(--av2-card);
  animation: av2-fade 0.25s;
}
.av2 .forge-token__mark {
  flex: none;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  background: var(--av2-yellow);
  box-shadow: 0 4px 0 var(--av2-yellow-deep);
}
@media (prefers-reduced-motion: no-preference) {
  .av2 .forge-token__mark { animation: av2-pop 0.4s; }
}
.av2 .forge-token__text { min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.av2 .forge-token__title { margin: 0; font-size: var(--av2-t-body); font-weight: 700; color: var(--av2-ink); }
.av2 .forge-token__sub { margin: 0; font-size: var(--av2-t-meta); color: var(--av2-ink-2); }
    `}</style>
  );
}
