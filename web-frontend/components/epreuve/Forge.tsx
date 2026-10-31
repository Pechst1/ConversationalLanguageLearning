/* WP-S6 — La Forge, beauty and clarity: the séance's own pieces.

   Owner, 2026-10-18 — less on every screen, and a progress one can read:

   - ForgeProgress: the top bar's quiet bar and «3/12». The surface's name is
     gone from it: the learner knows where they are.
   - ForgeLevel: the rule's level, 1 to 6 — six plain segments lit up to the
     rule's own. It replaces the staircase of shapes («I don't know what the
     triangles indicate»).
   - ForgeHead: the rule's name (once on the screen), its level, and the
     «La règle» pill. A tap on the level says what it means; the first time,
     it says so unasked.
   - ForgeDrillTag: a new format names itself («Trouve l'erreur», «Dictée»).
   - ForgeSheetTestOut: the épreuve's quiet way in, inside the rule sheet —
     never on every screen.
   - ForgeRecapRules: the recap's per-rule progress; ForgeTestOutOffer: the
     épreuve, offered every few days in the recap.

   Sans throughout: the screen's one Garamond line is the exercise prompt, or
   the rule card's example on its own screen, or the recap's headline. Every
   colour is an --av2-* token. */

import React from 'react';

import { Chip, ShapeToken } from '@/components/atelier-v2/ui';
import { fillForge, type ForgeCopy } from '@/lib/forge-copy';
import type { NamedDrill } from '@/lib/forge-drills';
import type { PortraitMood } from '@/lib/onboarding-portraits';
import { clampRung, levelExplain, levelSegments, levelText, type LevelRule, type RecapRuleRow } from '@/lib/forge-progress';

type Node = React.ReactNode;

/** A coach (WP-S5): a cast member who teaches the rule. */
export type ForgeCoach = { id: string; name?: string | null; mood?: PortraitMood | null };

/** The top bar's middle: how far the séance is, as a bar and «3/12». */
export function ForgeProgress({ n, total, label }: { n: number; total: number; label: string }) {
  if (!(total > 0)) return <span className="forge-progress" aria-hidden="true" />;
  const at = Math.max(0, Math.min(total, Math.floor(n)));
  return (
    <div className="forge-progress" role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={total} aria-valuenow={at}>
      <span className="forge-progress__track" aria-hidden="true">
        <span className="forge-progress__fill" style={{ width: `${Math.round((at / total) * 100)}%` }} />
      </span>
      <span className="forge-progress__n" aria-hidden="true">{at}/{total}</span>
    </div>
  );
}

/** Six plain segments, lit up to the rule's level; the newest lit one pops. */
export function ForgeLevel({ rung, size = 'md' }: { rung: number; size?: 'sm' | 'md' }) {
  const at = clampRung(rung);
  return (
    <span className="forge-level" data-size={size} data-level={at + 1} aria-hidden="true">
      {levelSegments(at).map((lit, index) => (
        <span
          // The level's own segment remounts when the level changes, so it pops once.
          key={index === at ? `at-${at}` : `s-${index}`}
          className="forge-level__seg"
          data-lit={lit ? 'true' : undefined}
          data-at={index === at ? 'true' : undefined}
        />
      ))}
    </span>
  );
}

const LEVEL_EXPLAINED = 'forge.level-explained';

/** The first time a learner meets the level, it explains itself unasked. */
function useFirstExplain(enabled: boolean): [boolean, (open: boolean) => void] {
  const [open, setOpen] = React.useState(false);
  React.useEffect(() => {
    if (!enabled) return;
    try {
      if (window.localStorage.getItem(LEVEL_EXPLAINED)) return;
      window.localStorage.setItem(LEVEL_EXPLAINED, '1');
    } catch {
      return; // No storage: the tap still explains it.
    }
    setOpen(true);
  }, [enabled]);
  return [open, setOpen];
}

export function ForgeHead({
  copy,
  title,
  rung,
  eyebrow,
  tag = null,
  ruleLabel,
  ruleOpen = false,
  onRule,
  itemKey = '',
  levelRule,
}: {
  copy: ForgeCopy;
  title: Node;
  rung: number;
  /** What a right and a wrong answer do to the level (`forge.level_rule`): the legend states it. */
  levelRule?: LevelRule;
  /** #169: an item of another rule names itself and why («Review · due today»). */
  tag?: string | null;
  /** The item on screen: the explanation shown unasked steps aside on the next one. */
  itemKey?: string;
  /** A test-out names itself here instead of the level. */
  eyebrow?: string | null;
  ruleLabel: string;
  ruleOpen?: boolean;
  onRule?: () => void;
}) {
  const [explain, setExplain] = useFirstExplain(!eyebrow);
  const at = clampRung(rung);
  // The explanation steps aside on the next item, or once the level moves (the
  // cheer says it then): a tap brings it back.
  const moment = `${at}:${itemKey}`;
  const shown = React.useRef(moment);
  React.useEffect(() => {
    if (shown.current === moment) return;
    shown.current = moment;
    setExplain(false);
  }, [moment, setExplain]);
  return (
    <div className="forge-head">
      <div className="forge-head__row">
        <div className="forge-head__text">
          {tag ? <p className="forge-head__tag" data-testid="forge-review-tag">{tag}</p> : null}
          <p className="forge-head__rule" lang="fr">{title}</p>
          {eyebrow ? (
            <p className="forge-head__eyebrow">{eyebrow}</p>
          ) : (
            <button
              type="button"
              className="forge-head__level"
              aria-expanded={explain}
              aria-label={fillForge(copy.level_label, { n: at + 1 })}
              onClick={() => setExplain(!explain)}
            >
              <ForgeLevel rung={at} />
              <span className="forge-head__level-n">{levelText(copy, at)}</span>
            </button>
          )}
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
      {explain && !eyebrow && <p className="forge-head__explain">{levelExplain(copy, levelRule)}</p>}
    </div>
  );
}

/** A format that asks for a new gesture says its name above the exercise. */
export function ForgeDrillTag({ drill, copy }: { drill: NamedDrill; copy: ForgeCopy }) {
  const name = copy[`drill_${drill}` as const];
  return (
    <p className="forge-tag" data-drill={drill}>
      <span className="forge-tag__mark" aria-hidden="true" />
      <span>{name}</span>
    </p>
  );
}

/** Inside the rule sheet: the épreuve for a learner who knows the rule already. */
export function ForgeSheetTestOut({ copy, pending = false, onClick }: { copy: ForgeCopy; pending?: boolean; onClick: () => void }) {
  return (
    <button type="button" className="forge-sheet-test-out" disabled={pending} aria-busy={pending || undefined} onClick={onClick}>
      {pending ? copy.test_out_starting : copy.sheet_test_out}
    </button>
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
            <p className="forge-recap__title" lang="fr">{row.title}</p>
            <p className="forge-recap__level">
              <ForgeLevel rung={row.rung} size="sm" />
              <span>{row.level}</span>
            </p>
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

/** The recap's best run of the séance, in words. */
export function ForgeBestRun({ line }: { line: string | null }) {
  if (!line) return null;
  return <p className="forge-best">{line}</p>;
}

/** The recap's épreuve: one rule, a few questions, every few days. */
export function ForgeTestOutOffer({
  copy,
  title,
  items,
  pending = false,
  onStart,
}: {
  copy: ForgeCopy;
  title: Node;
  items: number;
  pending?: boolean;
  onStart: () => void;
}) {
  return (
    <section className="forge-offer" aria-label={copy.offer_title}>
      <span className="forge-offer__mark" aria-hidden="true" />
      <div className="forge-offer__text">
        <p className="forge-offer__title">{copy.offer_title}</p>
        <p className="forge-offer__rule" lang="fr">{title}</p>
        <p className="forge-offer__sub">{fillForge(copy.offer_sub, { n: items })}</p>
        <button
          type="button"
          className="av2-btn av2-btn--secondary av2-btn--inline forge-offer__go"
          disabled={pending}
          aria-busy={pending || undefined}
          onClick={onStart}
        >
          {pending ? copy.test_out_starting : copy.offer_action}
        </button>
      </div>
    </section>
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
/* The top bar: a quiet bar and «3/12», centred between close and Terminer. */
.av2 .forge-progress { flex: 1 1 auto; min-width: 0; display: flex; align-items: center; gap: 10px; margin: 0 6px; }
.av2 .forge-progress__track { position: relative; flex: 1 1 auto; height: 8px; border-radius: var(--av2-r-pill); background: var(--av2-line); overflow: hidden; }
.av2 .forge-progress__fill { position: absolute; inset: 0 auto 0 0; border-radius: var(--av2-r-pill); background: var(--av2-ink); transition: width 0.3s ease; }
.av2 .forge-progress__n { flex: none; font-size: var(--av2-t-meta); font-weight: 700; color: var(--av2-muted); font-variant-numeric: tabular-nums; }

/* The level: six plain segments, ink up to the rule's own, ghosts after. */
.av2 .forge-level, .ep-recap .forge-level { flex: none; display: inline-flex; align-items: center; gap: 3px; }
.av2 .forge-level__seg, .ep-recap .forge-level__seg { width: 14px; height: 8px; border-radius: 3px; background: var(--av2-line-2); transition: background-color 0.3s ease; }
.av2 .forge-level[data-size='sm'] .forge-level__seg, .ep-recap .forge-level[data-size='sm'] .forge-level__seg { width: 10px; height: 6px; border-radius: 2px; }
.av2 .forge-level__seg[data-lit='true'], .ep-recap .forge-level__seg[data-lit='true'] { background: var(--av2-ink); }
@media (prefers-reduced-motion: no-preference) {
  .av2 .forge-level__seg[data-at='true'] { animation: av2-pop 0.35s; }
}

/* QA-FORGE: an answer in the learner's own language («Stimmt so», «Muss
   korrigiert werden») is chrome, set in the sans; French options keep the
   Garamond italic. */
.av2 .ep-opt > span[lang]:not([lang='fr']) { font-family: var(--av2-sans); font-style: normal; font-weight: 600; }

.av2 .forge-head { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.av2 .forge-head__row { display: flex; align-items: flex-start; gap: 12px; min-width: 0; }
.av2 .forge-head__text { flex: 1 1 auto; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.av2 .forge-head__rule { margin: 0; font-size: var(--av2-t-body); font-weight: 700; line-height: 1.3; color: var(--av2-ink); overflow-wrap: anywhere; }
.av2 .forge-head__tag { margin: 0 0 2px; font-size: var(--av2-t-meta); font-weight: 600; line-height: 1.3; color: var(--av2-muted); }
.av2 .forge-head__eyebrow { margin: 0; font-size: var(--av2-t-meta); font-weight: 700; line-height: 1.3; color: var(--av2-blue); }
.av2 .forge-head__level {
  align-self: flex-start;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 32px;
  margin: 0;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--av2-ink-2);
  font: 700 var(--av2-t-meta)/1.2 var(--av2-sans);
  font-variant-numeric: tabular-nums;
  cursor: pointer;
}
.av2 .forge-head__explain {
  margin: 0;
  padding: 10px 12px;
  border-radius: 12px;
  background: var(--av2-card);
  font-size: var(--av2-t-label);
  line-height: 1.4;
  color: var(--av2-ink-2);
  animation: av2-fade 0.25s;
}
.av2 .forge-head__pill { flex: none; min-height: var(--av2-tap); font-size: var(--av2-t-meta); font-weight: 600; }
.av2 .forge-head__pill[aria-pressed='true'] { background: var(--av2-line); }

/* A new format's name: a small dot in its colour and the name, above the goal. */
.av2 .forge-tag { margin: 0; display: inline-flex; align-items: center; gap: 8px; align-self: flex-start; font-size: var(--av2-t-meta); font-weight: 700; color: var(--av2-ink-2); }
.av2 .forge-tag__mark { width: 10px; height: 10px; border-radius: 999px; background: var(--av2-blue); }
.av2 .forge-tag[data-drill='spot'] .forge-tag__mark,
.av2 .forge-tag[data-drill='rafale'] .forge-tag__mark { background: var(--av2-red); }
.av2 .forge-tag[data-drill='mine'] .forge-tag__mark { background: var(--av2-yellow); border-radius: 3px; }
.av2 .forge-tag[data-drill='typed'] .forge-tag__mark { background: var(--av2-green); }

.av2 .forge-sheet-test-out {
  align-self: flex-start;
  min-height: var(--av2-tap);
  margin: -4px 0 0;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--av2-ink-2);
  font: 600 var(--av2-t-label)/1.2 var(--av2-sans);
  text-decoration: underline;
  text-underline-offset: 3px;
  cursor: pointer;
}
.av2 .forge-sheet-test-out:disabled { color: var(--av2-muted); text-decoration: none; cursor: default; }

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
.av2 .forge-recap__head, .ep-recap .forge-recap__head { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.av2 .forge-recap__title, .ep-recap .forge-recap__title { margin: 0; font-size: var(--av2-t-body); font-weight: 700; line-height: 1.3; color: var(--av2-ink); overflow-wrap: anywhere; }
.av2 .forge-recap__level, .ep-recap .forge-recap__level { margin: 0; display: flex; align-items: center; gap: 8px; font-size: var(--av2-t-meta); font-weight: 700; color: var(--av2-muted); }
.av2 .forge-recap__change, .ep-recap .forge-recap__change { margin: 0; font-size: var(--av2-t-label); font-weight: 600; color: var(--av2-ink-2); }
.av2 .forge-recap__change[data-changed='true'], .ep-recap .forge-recap__change[data-changed='true'] { color: var(--av2-green); }
.av2 .forge-recap__proof, .ep-recap .forge-recap__proof { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.av2 .forge-recap__proof li, .ep-recap .forge-recap__proof li { display: flex; align-items: baseline; gap: 8px; font-size: var(--av2-t-body); line-height: 1.35; color: var(--av2-ink); overflow-wrap: anywhere; }
.av2 .forge-recap__proof .av2-shape, .ep-recap .forge-recap__proof .av2-shape { flex: none; align-self: center; }
.av2 .forge-recap__due, .ep-recap .forge-recap__due { margin: 0; font-size: var(--av2-t-meta); font-weight: 600; color: var(--av2-muted); }

.av2 .forge-recap__eclair, .ep-recap .forge-recap__eclair { align-self: flex-start; display: inline-flex; flex-direction: column; align-items: flex-start; gap: 2px; text-decoration: none; }
.av2 .forge-recap__eclair-pair, .ep-recap .forge-recap__eclair-pair { font-size: var(--av2-t-meta); font-weight: 600; color: var(--av2-muted); }
.av2 .forge-best, .ep-recap .forge-best { margin: 0; font-size: var(--av2-t-label); font-weight: 600; color: var(--av2-ink-2); }

/* The recap's épreuve offer: the reward square, the rule, one action. */
.av2 .forge-offer, .ep-recap .forge-offer {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 16px;
  border-radius: var(--av2-r-card);
  background: var(--av2-card);
  min-width: 0;
  animation: av2-fade 0.25s;
}
.av2 .forge-offer__mark, .ep-recap .forge-offer__mark {
  flex: none;
  width: 24px;
  height: 24px;
  margin-top: 2px;
  border-radius: 6px;
  background: var(--av2-yellow);
  box-shadow: 0 3px 0 var(--av2-yellow-deep);
}
.av2 .forge-offer__text, .ep-recap .forge-offer__text { min-width: 0; display: flex; flex-direction: column; align-items: flex-start; gap: 4px; }
.av2 .forge-offer__title, .ep-recap .forge-offer__title { margin: 0; font-size: var(--av2-t-meta); font-weight: 700; color: var(--av2-muted); }
.av2 .forge-offer__rule, .ep-recap .forge-offer__rule { margin: 0; font-size: var(--av2-t-body); font-weight: 700; line-height: 1.3; color: var(--av2-ink); overflow-wrap: anywhere; }
.av2 .forge-offer__sub, .ep-recap .forge-offer__sub { margin: 0 0 6px; font-size: var(--av2-t-label); line-height: 1.4; color: var(--av2-ink-2); }

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
