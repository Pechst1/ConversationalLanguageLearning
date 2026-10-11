/**
 * WP-122 B · the result after «Bon à tirer»: the draft again, each seeded span in its
 * outcome's colour with the correction beside it (green = corrigée, blue = repérée,
 * red = manquée — and always the word too, never colour alone); a false alarm is
 * underlined in dots with «celui-là était bon», never a penalty. Then Romy's one
 * line, the list of the draft's mistakes with their grammar point, and «Dans le Relevé».
 */

import React from 'react';

import { CastPortrait } from '@/components/atelier-v2/ui';
import type { CrOutcome, CrResult as CrResultData } from '@/lib/correcteur-types';

import { fill, type CorrecteurCopy } from './correcteur-copy';
import { runs } from './correcteur-model';
import { CrPaper } from './CrPaper';

type Tag = { kind: 'seed'; outcome: CrOutcome; correctFr: string } | { kind: 'alarm' };

export function outcomeLabel(outcome: CrOutcome, copy: CorrecteurCopy): string {
  return outcome === 'repaired' ? copy.repaired : outcome === 'noticed' ? copy.noticed : copy.missed;
}

export function CrResultText({ result, copy }: { result: CrResultData; copy: CorrecteurCopy }) {
  return (
    <>
      {result.sentences.map((sentence, index) => {
        const tagged: { span: [number, number]; tag: Tag }[] = [
          ...result.outcomes
            .filter((o) => o.sentenceIndex === index)
            .map((o) => ({ span: o.span, tag: { kind: 'seed', outcome: o.outcome, correctFr: o.correctFr } as Tag })),
          ...result.falseAlarms.filter((f) => f.sentenceIndex === index).map((f) => ({ span: f.span, tag: { kind: 'alarm' } as Tag })),
        ];
        return (
          <span key={index} className="cr-sentence">
            {runs(sentence, tagged).map((run) => {
              if (!run.tag) return <React.Fragment key={run.start}>{run.text}</React.Fragment>;
              if (run.tag.kind === 'alarm') {
                return (
                  <span key={run.start} className="cr-alarm" data-outcome="false_alarm">
                    {run.text}
                    <span className="cr-alarm__note">{copy.false_alarm}</span>
                  </span>
                );
              }
              return (
                <span key={run.start} className="cr-out" data-outcome={run.tag.outcome}>
                  <s className="cr-out__wrong">{run.text}</s>{' '}
                  <span className="cr-out__right">{run.tag.correctFr}</span>
                  <span className="av2-sr"> ({outcomeLabel(run.tag.outcome, copy)})</span>
                </span>
              );
            })}
            {index < result.sentences.length - 1 ? ' ' : null}
          </span>
        );
      })}
    </>
  );
}

export function CrResultView({ result, kickerFr, titleFr, bylineFr, copy, onReleve }: {
  result: CrResultData;
  kickerFr: string;
  titleFr: string;
  bylineFr: string;
  copy: CorrecteurCopy;
  onReleve?: () => void;
}) {
  const { counts } = result;
  return (
    <div className="cr-result" data-correcteur-result="">
      <p className="av2-label">{copy.result_title}</p>
      <p className="cr-result__counts">{fill(copy.counts, { r: counts.repaired, n: counts.noticed, m: counts.missed })}</p>
      <CrPaper kickerFr={kickerFr} titleFr={titleFr} bylineFr={bylineFr}>
        <CrResultText result={result} copy={copy} />
      </CrPaper>
      <div className="cr-romy" role="status">
        <CastPortrait characterId="romy_tremblay" name="Romy" size="sm" ring />
        <p lang="fr">{result.romyLineFr}</p>
      </div>
      <section className="cr-errors" aria-label={copy.errors_title}>
        <h2 className="av2-label">{copy.errors_title}</h2>
        <ul className="cr-errors__rows">
          {result.outcomes.map((o) => (
            <li key={`${o.sentenceIndex}-${o.span[0]}`} className="cr-errors__row" data-outcome={o.outcome}>
              <span className="cr-errors__tag">{outcomeLabel(o.outcome, copy)}</span>
              <span className="cr-errors__pair" lang="fr">
                <s>{o.wrongFr}</s> → <strong>{o.correctFr}</strong>
              </span>
              <span className="cr-errors__point" lang="fr">{o.grammarPoint}</span>
            </li>
          ))}
          {result.falseAlarms.map((f) => (
            <li key={`fa-${f.sentenceIndex}-${f.span[0]}`} className="cr-errors__row" data-outcome="false_alarm">
              <span className="cr-errors__tag">{copy.false_alarm}</span>
              <span className="cr-errors__pair" lang="fr">{f.textFr}</span>
              <span className="cr-errors__point">{copy.false_alarm_body}</span>
            </li>
          ))}
        </ul>
      </section>
      <a
        className="av2-btn av2-btn--secondary cr-releve"
        href={result.releveHref}
        onClick={(event) => {
          if (onReleve) {
            event.preventDefault();
            onReleve();
          }
        }}
      >
        <span>{copy.releve}</span>
      </a>
    </div>
  );
}
