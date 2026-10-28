/* Fortschritt «Le cours» — the level plan (2026-10-24).
 *
 * Owner: «we always know exactly at which level the learner is currently so
 * that he also knows that exactly and knows what he has to do and how much
 * time he has to invest to advance further».
 *
 * One card, top to bottom: where the learner stands (the band and its percent,
 * the ladder of every band); what the next band still needs (rules held,
 * words known, the épreuve) and what today can move; how long it takes and
 * what that costs a day, with the pace that sets it; then, folded, the rules
 * one by one, the time already put in, and each criterion on its own.
 *
 *   GET /progress/level   (`level-plan-model.ts` says it; nothing is counted here)
 *
 * The pace opens La Une's own Tempo sheet, and the plan is read again after a
 * change. Presentation is the Atelier V2 system; every rule lives in
 * components/cahiers/CahierV2.tsx as `.av2 .nb-lv*`. Tokens only, both themes.
 */
import React, { useMemo, useState } from 'react';
import Link from 'next/link';

import { TempoSheet } from '@/components/atelier-v2/home/DaySession';
import { Action, ArrowRightIcon, CheckIcon, ProgressRule, Surface } from '@/components/atelier-v2/ui';
import type { LevelPlan } from '@/services/api';
import type { ControlLanguage } from '@/types/daily-journey';

import { levelPlanCopy } from './level-plan-copy';
import { levelPlanView } from './level-plan-model';

export default function LevelPlanCard({
  plan,
  language,
  status,
  howLabel,
  onChanged,
}: {
  plan: LevelPlan;
  language: ControlLanguage;
  /** WP-25: the Relevé's own line for a declared or placed level; null when measured. */
  status: string | null;
  howLabel: string;
  /** The pace was switched on the Tempo sheet: read the plan again. */
  onChanged: () => void;
}) {
  const view = useMemo(() => levelPlanView(plan, language), [plan, language]);
  const goalWord = levelPlanCopy(language).ladder_goal;
  const [tempoOpen, setTempoOpen] = useState(false);

  return (
    <>
      <Surface className="nb-lv">
        {/* ---- Where you are ---- */}
        <div className="nb-lv__where">
          <p className="av2-headline av2-headline--display">{view.headline}</p>
          {view.verified && <ProgressRule value={view.percent} max={100} label={view.percentLabel} />}
          {status && <p className="av2-body nb-rv__status">{status}</p>}
          {view.evidence && <p className="nb-lv__fine">{view.evidence}</p>}
          <p className="av2-body nb-lv__next">{view.next}</p>
          {view.percentRule && <p className="nb-lv__fine">{view.percentRule}</p>}
          <ol className="nb-lv__ladder" aria-label={view.ladderLabel}>
            {view.ladder.map((step) => (
              <li
                key={step.band}
                data-state={step.state}
                data-goal={step.goal ? 'true' : undefined}
                aria-current={step.state === 'current' ? 'step' : undefined}
              >
                {(step.state === 'passed' || step.state === 'credited') && <CheckIcon size={12} />}
                <span aria-hidden="true">{step.band}</span>
                {step.goal && (
                  <span className="nb-lv__goal" aria-hidden="true">
                    {goalWord}
                  </span>
                )}
                <span className="av2-sr">{step.label}</span>
              </li>
            ))}
          </ol>
        </div>

        {/* ---- What the next band still needs ---- */}
        <div className="nb-lv__block">
          <h3 className="nb-lv__h">{view.needsTitle}</h3>
          {view.soFar && <p className="nb-lv__fine">{view.soFar}</p>}
          {view.criteria.map((criterion) => (
            <div key={criterion.key} className="nb-lv__crit" data-met={criterion.met ? 'true' : undefined}>
              <div className="nb-lv__crit-head">
                <span className="nb-lv__crit-l">{criterion.label}</span>
                <span className="nb-lv__crit-v">{criterion.value}</span>
              </div>
              {/* WP-25: a bar only against a level the app has measured. */}
              {view.verified && criterion.need > 0 && (
                <ProgressRule value={criterion.have} max={criterion.need} label={criterion.label} />
              )}
              {criterion.notes.map((note) => (
                <p key={note} className="nb-lv__fine">
                  {note}
                </p>
              ))}
            </div>
          ))}
          {view.wordsNote && <p className="nb-lv__fine">{view.wordsNote}</p>}
          <div className="nb-lv__crit" data-met={view.test.ready ? 'true' : undefined}>
            <div className="nb-lv__crit-head">
              <span className="nb-lv__crit-l">{view.test.label}</span>
              <span className="nb-lv__crit-v">{view.test.value}</span>
            </div>
          </div>
          {view.today && <p className="av2-body nb-lv__today">{view.today}</p>}
        </div>

        {/* ---- How long, and what it costs ---- */}
        <div className="nb-lv__block">
          <h3 className="nb-lv__h">{view.time.title}</h3>
          {view.time.estimate && <p className="av2-body">{view.time.estimate}</p>}
          {view.time.basis && <p className="nb-lv__fine">{view.time.basis}</p>}
          {view.time.cost && <p className="av2-body">{view.time.cost}</p>}
          {view.time.earliest && <p className="nb-lv__fine">{view.time.earliest}</p>}
          {view.goal && <p className="av2-body">{view.goal}</p>}
          {view.time.pace && (
            <div className="nb-lv__pace">
              <span className="nb-lv__fine">{view.time.pace}</span>
              <Action tone="quiet" inline onClick={() => setTempoOpen(true)}>
                {view.time.changePace}
              </Action>
            </div>
          )}
        </div>

        {/* ---- Folded: the rules one by one, the time put in, each criterion alone ---- */}
        {view.rules.rows.length > 0 && (
          <details className="nb-lv__more">
            <summary>{view.rules.title}</summary>
            <ul className="nb-lv__rules">
              {view.rules.rows.map((row) => (
                <li key={row.id} className="nb-lv__rule">
                  <i className="nb-lv__dot" data-tone={row.tone} aria-hidden="true" />
                  <span className="nb-lv__rule-main">
                    <span className="nb-lv__rule-t" lang={row.lang}>
                      {row.title}
                    </span>
                    <span className="nb-lv__rule-m">{row.note}</span>
                  </span>
                </li>
              ))}
            </ul>
          </details>
        )}
        <details className="nb-lv__more">
          <summary>{view.invested.title}</summary>
          <div className="nb-lv__more-body">
            {view.invested.lines.map((line) => (
              <p key={line} className="nb-lv__fine">
                {line}
              </p>
            ))}
          </div>
        </details>
        {view.skills && (
          <details className="nb-lv__more">
            <summary>{view.skills.title}</summary>
            <div className="nb-lv__more-body">
              {view.skills.lines.map((line) => (
                <p key={line} className="nb-lv__fine">
                  {line}
                </p>
              ))}
            </div>
          </details>
        )}

        <Link className="av2-row nb-rv__how" href="/dossier">
          <span className="av2-row__main av2-label">{howLabel}</span>
          <ArrowRightIcon size={18} />
        </Link>
      </Surface>
      <TempoSheet open={tempoOpen} language={language} onClose={() => setTempoOpen(false)} onChanged={() => onChanged()} />
    </>
  );
}
