/**
 * A development page that holds La Forge's free-sentence item and its miss on screen
 * (owner, 2026-11-13), so e2e/forge-reading-shots.mjs can photograph them at phone size
 * in every chrome language without a database or a walk. The real OutputLadderPanel and
 * ExerciseFeedbackMoment; the corrections are what the server serves
 * (e2e/fixtures/forge-reading-miss.json, built from app/services/solution_gate.py):
 *
 *   ?case=item       the item before an answer
 *   ?case=withheld   the miss while the second chance is open (no solution served)
 *   ?case=shown      the miss once the chance is spent (the solution served)
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
type Case = 'item' | 'withheld' | 'shown' | 'before';

export default function ForgeReadingFixture() {
  const { query, isReady } = useRouter();
  if (!isReady) return null;
  const lang = (['de', 'en', 'fr'].includes(String(query.lang)) ? String(query.lang) : 'en') as Lang;
  const shot = (['item', 'withheld', 'shown', 'before'].includes(String(query.case)) ? String(query.case) : 'item') as Case;
  return <Fixture lang={lang} shot={shot} />;
}

function Fixture({ lang, shot }: { lang: Lang; shot: Case }) {
  const [answer, setAnswer] = React.useState(shot === 'item' ? '' : LINE);
  const [drafts, setDrafts] = React.useState<Record<string, string>>({});
  const submitted = shot !== 'item';
  const correction = submitted ? ((MISSES as Record<string, any>)[lang][shot] as Record<string, any>) : null;
  const feedback = feedbackFromFreeformCorrection(correction, '', LINE, epreuveCopy(lang));
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
            />
          </div>
          <ExerciseFeedbackMoment
            feedback={feedback}
            submitted={submitted}
            rule={RULE}
            correction={correction}
            repairDrafts={drafts}
            onSetRepairDraft={(key, value) => setDrafts((prev) => ({ ...prev, [key]: value }))}
            onSubmitRepair={() => undefined}
            repairSubmitting={{}}
            feedbackKey={`fixture:${shot}`}
            onNext={() => undefined}
            nextLabel={epreuveCopy(lang).continue}
            onTryAgain={() => undefined}
            onReport={() => undefined}
            production
            ruleShown={RULE}
            {...({ onRevealSolution: () => undefined } as Record<string, unknown>)}
          />
        </section>
      </EpShell>
    </>
  );
}
