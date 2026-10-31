/**
 * A development page that holds one La Forge miss on screen (#282), so the browser test
 * (e2e/miss-layout.mjs) can measure it without a database or a walk: the real
 * ExerciseFeedbackMoment (the correction, the part-by-part field, «Compare» and the verdict
 * sheet) under the real item frame, and the real CameoLayer from `_app`, which this page
 * sends «two mistakes in a row» to. Not in a production build.
 *
 * `?case=381` holds the live walk's line of 30 Oct instead («Je voudrais un tomate, sil te
 * plait.»), and «Compare» is checked here as the server checks it, so the test can type the
 * right repair and read the verdict band under «Line fixed» (#381).
 */
import Head from 'next/head';
import { useRouter } from 'next/router';
import React from 'react';

import { EpPrompt, EpShell, LEpreuveStyles } from '@/components/epreuve/Epreuve';
import { ForgeStyles } from '@/components/epreuve/Forge';
import { ForgeDrillStyles } from '@/components/epreuve/ForgeDrills';
import { emitCameo, CAMEO_CAST } from '@/lib/cameo';
import { gapIsFixed, repairParts } from '@/lib/repair-parts';
import { ExerciseFeedbackMoment } from '../atelier';

export async function getStaticProps() {
  if (process.env.NODE_ENV === 'production') {
    return { notFound: true };
  }
  return { props: {} };
}

const LINE = 'Il est à le marché aux puces avec Romy';
const WIDE_WRONG = 'à le marché aux puces';
const WIDE_FIX = 'au marché aux puces';

const FEEDBACK = {
  correct: false,
  learner: LINE,
  target: 'Il est au marché aux puces avec Romy',
  issues: [
    {
      display_label: 'à + le = au',
      learner_text: WIDE_WRONG,
      corrected_target: WIDE_FIX,
      why_wrong: '«à» and «le» merge into «au» before a masculine noun.',
      repair_hint: 'Replace «à le» with «au» here.',
    },
  ],
};

const CORRECTION = {
  corrected_answer: 'Il est au marché aux puces avec Romy',
  errata: [{ learner_text: WIDE_WRONG, corrected_target: WIDE_FIX }],
};

// #381: the walk's line, with the two corrections the model made.
const WALK_LINE = 'Je voudrais un tomate, sil te plait.';
const WALK_FIXED = "Je voudrais une tomate, s'il te plaît.";
const WALK_ERRATA = [
  { learner_text: 'un tomate', corrected_target: 'une tomate', why_wrong: '«tomate» is feminine: une tomate.', task_error_type: 'agreement' },
  { learner_text: 'sil te plait', corrected_target: "s'il te plaît", why_wrong: '«si» elides before «il»; «plaît» keeps its circumflex.', task_error_type: 'spelling' },
];
const WALK_FEEDBACK = {
  correct: false,
  learner: WALK_LINE,
  target: WALK_FIXED,
  issues: [{ display_label: '2 corrections', learner_text: WALK_LINE, corrected_target: WALK_FIXED, why_wrong: WALK_ERRATA.map((e) => e.why_wrong).join('\n') }],
};

/** «Compare» as `record_micro_repair` reads it: the model's line, or the learner's own with each gap fixed. */
function walkRepairStatus(typed: string): 'ok' | 'no' {
  const parts = repairParts(WALK_LINE, WALK_ERRATA);
  const ownFixed = parts ? parts.map((part) => ('text' in part ? part.text : part.fix)).join('') : null;
  return [WALK_FIXED, ownFixed].some((line) => line && typed.trim() && gapIsFixed(typed, line)) ? 'ok' : 'no';
}

export default function MissLayoutFixture() {
  const { query, isReady } = useRouter();
  if (!isReady) return null;
  return query.case === '381' ? <RepairedLineFixture /> : <MissFixture />;
}

function RepairedLineFixture() {
  const [drafts, setDrafts] = React.useState<Record<string, string>>({});
  const [repairs, setRepairs] = React.useState<Record<string, { status: 'ok' | 'no'; typed: string }>>({});
  const correction = { corrected_answer: WALK_FIXED, errata: WALK_ERRATA, micro_repairs: repairs };
  return (
    <>
      <Head>
        <title>Repaired line</title>
      </Head>
      <EpShell className="atelier-do-mode" language="en">
        <LEpreuveStyles />
        <ForgeStyles />
        <ForgeDrillStyles />
        <section className="ep-sheet">
          <div className="ep-frame">
            <div className="ep-exercise ep-output ep-output-produce" data-fixture="miss">
              <EpPrompt cue="Order something at the market.">{WALK_LINE}</EpPrompt>
              <textarea className="av2-field" readOnly value={WALK_LINE} aria-label="Your line" rows={2} />
            </div>
          </div>
          <ExerciseFeedbackMoment
            feedback={WALK_FEEDBACK}
            submitted
            rule="Un, une : le genre du nom"
            correction={correction}
            repairDrafts={drafts}
            onSetRepairDraft={(key, value) => setDrafts((prev) => ({ ...prev, [key]: value }))}
            onSubmitRepair={(index) => {
              const typed = drafts[`fixture:381:${index}`] || '';
              setRepairs((prev) => ({ ...prev, [String(index)]: { status: walkRepairStatus(typed), typed } }));
            }}
            repairSubmitting={{}}
            feedbackKey="fixture:381"
            onNext={() => undefined}
            nextLabel="Next"
            onTryAgain={() => undefined}
            onReport={() => undefined}
            production
          />
          <output data-fixture="draft" hidden>{Object.values(drafts)[0] ?? ''}</output>
        </section>
      </EpShell>
    </>
  );
}

function MissFixture() {
  const [drafts, setDrafts] = React.useState<Record<string, string>>({});
  React.useEffect(() => {
    // The gallery's way to a cameo: everybody met, a right answer, then two misses.
    emitCameo({ type: 'met', ids: CAMEO_CAST.map((who) => who.id) });
    const ids = [
      window.setTimeout(() => emitCameo({ type: 'answer', correct: true }), 50),
      window.setTimeout(() => emitCameo({ type: 'answer', correct: false }), 100),
      window.setTimeout(() => emitCameo({ type: 'answer', correct: false }), 150),
    ];
    return () => ids.forEach((id) => window.clearTimeout(id));
  }, []);
  return (
    <>
      <Head>
        <title>Miss layout</title>
      </Head>
      <EpShell className="atelier-do-mode">
        <LEpreuveStyles />
        <ForgeStyles />
        <ForgeDrillStyles />
        <section className="ep-sheet">
          {/* What stands above the item on the real screen (top bar, the rule's head, the drill tag):
              enough that the verdict sheet, sticky at the bottom, lies over the correction. */}
          <div data-fixture="above" style={{ minHeight: 330 }} aria-hidden="true" />
          <div className="ep-frame">
            <div className="ep-exercise ep-output ep-output-produce" data-fixture="miss">
              <EpPrompt cue="Say where Romy and you are.">{LINE}</EpPrompt>
              <textarea className="av2-field" readOnly value={LINE} aria-label="Your line" rows={2} />
            </div>
          </div>
          <ExerciseFeedbackMoment
            feedback={FEEDBACK}
            submitted
            rule="à + le = au"
            correction={CORRECTION}
            repairDrafts={drafts}
            onSetRepairDraft={(key, value) => setDrafts((prev) => ({ ...prev, [key]: value }))}
            onSubmitRepair={() => undefined}
            repairSubmitting={{}}
            feedbackKey="fixture:1"
            onNext={() => undefined}
            nextLabel="Next"
            onTryAgain={() => undefined}
            production
            ruleShown="à + le = au"
          />
          {/* What «Compare» would send: the line the learner's typed words make. */}
          <output data-fixture="draft" hidden>{Object.values(drafts)[0] ?? ''}</output>
        </section>
      </EpShell>
    </>
  );
}
