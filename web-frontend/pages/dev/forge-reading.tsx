/**
 * A development page that holds La Forge's free-sentence item and its miss on screen
 * (owner, 2026-11-13), so e2e/forge-reading-shots.mjs can photograph them at phone size
 * in every chrome language without a database or a walk. The real OutputLadderPanel and
 * ExerciseFeedbackMoment; the corrections are what the server serves
 * (e2e/fixtures/forge-reading-miss.json, built from app/services/solution_gate.py):
 *
 *   ?case=item       the item before an answer
 *   ?case=withheld   the miss while the second chance is open (no solution served): the line, marked
 *   ?case=shown      the miss once the chance is spent (the solution served)
 *   ?case=inplace    the same miss with only words wrong: fixed in place, in the field's place
 *   ?case=right      a right line: green where it was written
 *   ?case=choice     the miss on a picked answer: the hint in the band, nothing else
 *   ?case=before     the miss as the server sent it before the gate (full correction)
 *
 * and ?lang=de|en|fr. Not in a production build.
 */
import Head from 'next/head';
import { useRouter } from 'next/router';
import React from 'react';

import { EpShell, LEpreuveStyles } from '@/components/epreuve/Epreuve';
import { epreuveCopy } from '@/components/epreuve/epreuve-copy';
import { ForgeStyles } from '@/components/epreuve/Forge';
import { ForgeDrillStyles } from '@/components/epreuve/ForgeDrills';
import MISSES from '../../e2e/fixtures/forge-reading-miss.json';
import { solutionWithheld } from '@/lib/solution-gate';
import { ExerciseFeedbackMoment, feedbackFromFreeformCorrection, OutputLadderPanel } from '../atelier';

export async function getStaticProps() {
  if (process.env.NODE_ENV === 'production') {
    return { notFound: true };
  }
  return { props: {} };
}

const LINE = "Oui j'ai un carte bancaire";
const RULE = 'Je peux + infinitif';

const PAYLOAD = {
  output_ladder: {
    sentence: {
      items: [
        {
          id: 's1',
          prompt: 'Au marché, la vendeuse te demande : « Tu peux payer par carte ? » Réponds avec « je peux » et l’infinitif.',
          prompt_l10n: {
            de: 'Auf dem Markt fragt dich die Verkäuferin: « Tu peux payer par carte ? » Antworte mit « je peux » und dem Infinitiv.',
            en: 'At the market the stallholder asks you: « Tu peux payer par carte ? » Answer with « je peux » and the infinitive.',
            fr: 'Au marché, la vendeuse te demande : « Tu peux payer par carte ? » Réponds avec « je peux » et l’infinitif.',
          },
          min_words: 4,
          max_words: 10,
        },
      ],
    },
  },
};

type Lang = 'de' | 'en' | 'fr';
const CASES = ['item', 'withheld', 'inplace', 'shown', 'right', 'choice', 'before'] as const;
type Case = (typeof CASES)[number];

const RIGHT_LINE = 'Oui, je peux payer par carte.';
const RIGHT = { assessment_status: 'checked', verdict: 'correct', corrected_answer: RIGHT_LINE, errata: [] };

function correctionFor(lang: Lang, shot: Case): Record<string, any> | null {
  const misses = (MISSES as Record<string, any>)[lang];
  if (shot === 'item') return null;
  if (shot === 'right') return RIGHT;
  if (shot === 'choice') return misses.withheld;
  if (shot === 'inplace') {
    // The same miss with the words wrong and the task done: no task erratum.
    const errata = misses.withheld.errata.filter((item: Record<string, any>) => item.task_error_type !== 'task_compliance');
    return { ...misses.withheld, errata, notes_native: errata.map((item: Record<string, any>) => item.hint) };
  }
  return misses[shot];
}

export default function ForgeReadingFixture() {
  const { query, isReady } = useRouter();
  if (!isReady) return null;
  const lang = (['de', 'en', 'fr'].includes(String(query.lang)) ? String(query.lang) : 'en') as Lang;
  const shot = ((CASES as readonly string[]).includes(String(query.case)) ? String(query.case) : 'item') as Case;
  return <Fixture key={`${lang}:${shot}`} lang={lang} shot={shot} />;
}

function Fixture({ lang, shot }: { lang: Lang; shot: Case }) {
  const line = shot === 'right' ? RIGHT_LINE : LINE;
  const [answer, setAnswer] = React.useState(shot === 'item' ? '' : line);
  const [drafts, setDrafts] = React.useState<Record<string, string>>({});
  // «Try again» and a tap on the marked line open the line again, as the session does.
  const [open, setOpen] = React.useState(false);
  const submitted = shot !== 'item' && !open;
  const correction = submitted ? correctionFor(lang, shot) : null;
  const feedback = feedbackFromFreeformCorrection(correction, '', line, epreuveCopy(lang));
  const production = shot !== 'choice';
  const answerState = !submitted || !feedback ? null : feedback.correct ? 'right' as const : solutionWithheld(correction) ? 'open' as const : 'shown' as const;
  const retry = () => setOpen(true);
  return (
    <>
      <Head>
        <title>Forge reading</title>
      </Head>
      <EpShell className="atelier-do-mode" language={lang}>
        <LEpreuveStyles />
        <ForgeStyles />
        <ForgeDrillStyles />
        <section className="ep-sheet">
          <div className="ep-frame">
            <OutputLadderPanel
              payload={PAYLOAD}
              round="sentence"
              answer={answer}
              updateAnswer={setAnswer}
              correction={correction}
              submitted={submitted}
              answerState={shot === 'choice' ? null : answerState}
              onRetry={retry}
            />
          </div>
          <ExerciseFeedbackMoment
            feedback={feedback}
            submitted={submitted}
            rule={shot === 'right' ? undefined : RULE}
            correction={correction}
            repairDrafts={drafts}
            onSetRepairDraft={(key, value) => setDrafts((prev) => ({ ...prev, [key]: value }))}
            onSubmitRepair={() => undefined}
            repairSubmitting={{}}
            feedbackKey={`fixture:${shot}`}
            onNext={() => undefined}
            nextLabel={epreuveCopy(lang).continue}
            onTryAgain={retry}
            onReport={() => undefined}
            production={production}
            picked={shot === 'choice'}
            lineEchoed={production && Boolean(answerState) && !(shot === 'inplace')}
            ruleShown={RULE}
            onRevealSolution={() => undefined}
          />
        </section>
      </EpShell>
    </>
  );
}
