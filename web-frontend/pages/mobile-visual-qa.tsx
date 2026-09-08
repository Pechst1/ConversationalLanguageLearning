import React from 'react';
import Head from 'next/head';
import { ArrowRight, BookOpen, Check, X } from 'lucide-react';

import {
  ContextAnchor,
  FeedbackSlip,
  MobileBottomSheet,
  MobileChip,
  MobileMastheadAction,
  MobileRow,
  MobileSheet,
  StickyCTA,
  VocabularyCreditBadge,
} from '@/components/mobile';
import {
  Blank,
  EpBar,
  EpConcept,
  EpConfidence,
  EpEyebrow,
  EpFoot,
  EpGalley,
  EpLineFix,
  EpLock,
  EpMotif,
  EpOpt,
  EpOpts,
  EpPrompt,
  EpRule,
  EpShell,
  EpTopbar,
  EpVerdict,
  LEpreuveStyles,
} from '@/components/epreuve/Epreuve';
import {
  CahiersStyles,
  NcChips,
  NcFilingSummary,
  NcIndexRow,
  NcLedgerHead,
  NcMasthead,
  NcModeTabs,
  NcSec,
  NcExample,
  NcWordRow,
} from '@/components/cahiers/Cahiers';
import {
  LaUneStyles,
  LuDemain,
  LuEnBref,
  LuManchette,
  LuMasthead,
  LuPhraseDuJour,
} from '@/components/laune/LaUne';
// Feuilleton V2 reader harness (subagent B). Dev-only, like this page; drive it
// with ?reader=ready|printing|missing|stale|filed|answered.
import ReaderHarness from '@/components/feuilleton/reader/__fixtures__/ReaderHarness';

const positiveCorrection = {
  vocabulary_credit: {
    events: [
      { word_id: 1, event_type: 'produced_correct', word: 'dossier' },
      { word_id: 2, event_type: 'seen_context', word: 'rendez-vous' },
    ],
  },
};

const repairCorrection = {
  vocabulary_credit: {
    events: [
      { word_id: 3, event_type: 'missed_target', target: 'prévoir' },
    ],
  },
};

export async function getStaticProps() {
  if (process.env.NODE_ENV === 'production') {
    return { notFound: true };
  }
  return { props: {} };
}

// The whole front page in one composition, with every block populated. This is
// the density reference: docs/pilot-density-pass.md defines the hierarchy
// contract but was never verified against a real capture. It renders
// unconditionally because this page is statically generated and does not
// hydrate in the preview, so a query-param switch would never fire.
function LaUneFullPage() {
  return (
    <div className="lu">
      <LaUneStyles />
      <div className="lu-page">
        <LuMasthead
          name="L’Atelier"
          date="Jeudi 30 juillet 2026"
          edition="Éd. Nº 4"
          streak={3}
          niveau="A1.1"
        />
        <LuManchette
          ep={4}
          artMode="none"
          headline="Romy garde une porte ouverte."
          byline="Romy Tremblay"
          minutes={19}
          budgetMinutes={10}
          concept="Négation : ne … pas"
          because="parce que votre objectif « voyager » commence par une seule règle bien posée."
          onOpen={() => undefined}
          onCta={() => undefined}
        />
        <LuEnBref
          rows={[
            { id: 'seance', label: 'La séance', value: '3 règles · ~12 min', onClick: () => undefined },
            { id: 'lexique', label: 'Le lexique', value: '6 mots à revoir · 2 corrections', href: '/vocabulary/review' },
            { id: 'cours', label: 'Le cours', value: 'B1.1 · à vérifier', href: '/notebook?mode=releve' },
          ]}
        />
        <LuPhraseDuJour text="Je ne prends pas le métro ce matin." byline="Vincent" />
        <LuDemain focus="Articles partitifs" ep={5} epTease="Le carnet change de mains." />
      </div>
    </div>
  );
}

// One drill sheet with every layer a learner meets: the round eyebrow, the
// concept head, the rule card, the prompt, the choices, the confidence ask and
// the correction. Same purpose as LaUneFullPage — a measurable capture.
function EpreuveSheet() {
  return (
    <div className="ep av2">
      <LEpreuveStyles />
      <EpTopbar groups={[{ total: 31, set: 12, current: true }]} cap={['12/31', '']} partial />
      <div className="ep-body">
        <section className="ep-sheet">
          <EpEyebrow round="Reconnaître" mode="Compléter" i={2} n={3} />
          <EpConcept title="Négation : ne … pas" motif={<EpMotif prims={[]} canvas={46} />} askOn />
          <EpRule
            lede="Le verbe conjugué se place entre ne et pas."
            examples={['Je ne mange pas de pain.']}
          />
          <EpPrompt cue="Choisissez la forme correcte.">
            Je <Blank>ne mange pas</Blank> de pain.
          </EpPrompt>
          <EpOpts>
            <EpOpt>ne mange pas</EpOpt>
            <EpOpt chosen>mange ne pas</EpOpt>
            <EpOpt>ne pas mange</EpOpt>
          </EpOpts>
          <EpConfidence value="sure" />
          <EpFoot><EpBar icon="check">Vérifier</EpBar></EpFoot>
          <EpVerdict tone="no">À recomposer</EpVerdict>
          <EpGalley anchor="Ordre des mots" why="Le verbe conjugué se place entre ne et pas.">
            <EpLineFix old="Je mange ne pas de pain." fix="Je ne mange pas de pain." />
          </EpGalley>
          <EpFoot><EpBar icon="check">Exercice suivant</EpBar></EpFoot>
        </section>
      </div>
    </div>
  );
}

// The notebook as a learner meets it: masthead, mode switch, filing summary,
// a filtered ledger and one opened fiche.
function CahiersSheet() {
  return (
    <div className="nc">
      <CahiersStyles />
      <div className="nc-page">
        <NcMasthead cefr="A1.1 en cours" />
        <NcModeTabs active="grammaire" library={false} />
        <NcFilingSummary items={[{ n: 42, label: 'règles' }, { n: 6, label: 'à revoir', tone: 'due' }]} />
        <NcChips chips={[{ l: 'Toutes', n: 42 }, { l: 'À revoir', n: 6 }, { l: 'Fragiles', n: 3 }]} active={0} />
        <NcLedgerHead t="Index des règles" n="42" />
        <NcIndexRow no={1} title="Négation : ne … pas" level="A1" cat="Syntaxe" mastery={7} state="solid" stateLabel="Solide" />
        <NcIndexRow no={2} title="Articles définis" level="A1" cat="Déterminants" mastery={3} state="fragile" stateLabel="Fragile" due errata={2} />
        <NcSec kick="La règle">
          <NcExample fr="Je ne mange pas de pain." de="Ich esse kein Brot." />
        </NcSec>
      </div>
    </div>
  );
}

export default function MobileVisualQA() {
  if (process.env.NODE_ENV === 'production') {
    return null;
  }

  return (
    <>
      <Head>
        <title>Mobile Visual QA</title>
        <meta name="robots" content="noindex" />
      </Head>
      <ReaderHarness />
      <main className="mobile-qa-page" data-mobile-visual-qa>
        <header className="qa-topbar" aria-label="Mobile QA header">
          <div>
            <span>L’Atelier</span>
            <strong>Today&apos;s practice</strong>
          </div>
          <MobileMastheadAction label="Rules" aria-label="Open rules">
            <BookOpen />
          </MobileMastheadAction>
        </header>

        <section className="qa-hero" aria-label="Practice summary">
          <p>REFERENCE LAYER</p>
          <h1>Mobile QA</h1>
          <div className="qa-metrics">
            <span><strong>6</strong> due</span>
            <span><strong>3</strong> fragile</span>
            <span><strong>2</strong> new</span>
          </div>
        </section>

        <nav className="qa-chips" aria-label="QA chip states">
          <MobileChip active>All</MobileChip>
          <MobileChip tone="blue">Due</MobileChip>
          <MobileChip tone="red">Errata</MobileChip>
          <MobileChip tone="yellow">New</MobileChip>
        </nav>

        <MobileSheet
          eyebrow="Today"
          title="Target words"
          description="Rows should hold long labels without squeezing controls."
          action={<span className="qa-count">4</span>}
        >
          <ContextAnchor
            compact
            label="Vocabulary context"
            title="rendez-vous · der Termin"
            text="« Est-ce que je peux fixer un rendez-vous demain ? »"
            translation="Can I schedule an appointment tomorrow?"
            quote
          />
          <MobileRow
            leading={<span className="qa-dot red" />}
            kicker="FR -> DE"
            title="dossier"
            description="die Akte · due now"
            trailing={<ArrowRight size={16} />}
          />
          <MobileRow
            leading={<span className="qa-dot blue" />}
            kicker="Context"
            title="rendez-vous administratif"
            description="A deliberately longer phrase for wrapping checks"
            selected
            trailing={<Check size={16} />}
          />
          <MobileRow
            leading={<span className="qa-rank">42</span>}
            kicker="Deck"
            title="prévoir"
            description="planen, vorsehen"
            trailing={<ArrowRight size={16} />}
          />
        </MobileSheet>

        <section className="qa-stack" aria-label="Feedback states">
          <FeedbackSlip tone="correct" label="Accepted" stamp="+credit" title="Strong production">
            <p>Le dossier est prêt pour le rendez-vous.</p>
            <VocabularyCreditBadge correction={positiveCorrection} />
          </FeedbackSlip>
          <FeedbackSlip tone="error" label="Needs work" stamp="+erratum" title="Target missing">
            <p>Use the target verb before moving the card forward.</p>
            <VocabularyCreditBadge correction={repairCorrection} compact />
          </FeedbackSlip>
        </section>

        {/* Honest-edition states. These three carry promises about the learner's
            time, so they are checkable here without a signed-in /atelier. */}
        <section className="qa-honest" aria-label="Honest edition states">
          <div className="lu lu-page">
            <LaUneStyles />
            <LuManchette
              ep={4}
              headline="Romy garde une porte ouverte."
              byline="Romy"
              minutes={19}
              budgetMinutes={10}
              replyMode="speak"
              concept="Négation : ne … pas"
              onCta={() => undefined}
            />
          </div>
          <div className="ep av2">
            <LEpreuveStyles />
            <EpTopbar groups={[{ total: 31, set: 12, current: true }]} cap={['12/31', '']} partial />
            <EpLock title="Négation : ne … pas" retired={6} />
          </div>
        </section>

        <StickyCTA
          eyebrow="Next"
          title="Continue the mobile session"
          description="Sticky action should stay readable above the safe area."
          secondary={<button type="button">Later</button>}
          primary={<button type="button" className="primary">Begin</button>}
        />

        <section className="qa-honest" aria-label="La Une density reference">
          <LaUneFullPage />
        </section>

        <section className="qa-honest" aria-label="Epreuve density reference">
          <EpreuveSheet />
        </section>

        <section className="qa-honest" aria-label="Cahiers density reference">
          <CahiersSheet />
        </section>
      </main>

      <MobileBottomSheet
        ariaLabel="Static mobile sheet sample"
        onClose={() => undefined}
        eyebrow="Step 2 of 3"
        title="Target concepts"
        description="Bottom sheets share one handle, scrim, title scale, and safe-area rhythm."
        displayTitle
      >
        <ContextAnchor
          compact
          label="Sheet context"
          title="dossier · die Akte"
          text="« Je vous envoie le dossier avant midi. »"
          translation="I will send you the file before noon."
          quote
        />
      </MobileBottomSheet>

      <style jsx>{`
        .mobile-qa-page {
          --paper: var(--app-paper);
          --paper-2: var(--app-paper-2);
          --sheet: var(--app-sheet);
          --ink: var(--app-ink);
          --ink-2: var(--app-ink-2);
          --ink-3: var(--app-ink-3);
          --red: var(--app-red);
          --blue: var(--app-blue);
          --yellow: var(--app-yellow);
          min-height: 100vh;
          background: var(--paper);
          color: var(--ink);
          padding-bottom: 18px;
        }
        .qa-topbar {
          position: sticky;
          top: 0;
          z-index: 20;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 16px;
          border-bottom: 1px solid var(--ink);
          background: color-mix(in srgb, var(--paper) 92%, transparent);
          padding: 10px 16px;
          backdrop-filter: blur(10px);
        }
        .qa-topbar div,
        .qa-hero,
        .qa-stack {
          min-width: 0;
        }
        .qa-topbar span,
        .qa-hero p,
        .qa-count {
          color: var(--ink-3);
          font: 900 10px/1 var(--app-mono, "Inter", "Helvetica Neue", Arial, sans-serif);
          letter-spacing: .12em;
          text-transform: uppercase;
        }
        .qa-topbar strong {
          display: block;
          margin-top: 4px;
          overflow-wrap: anywhere;
          font-size: 15px;
          line-height: 1.1;
        }
        .qa-hero {
          padding: 20px 16px 14px;
        }
        .qa-hero p {
          margin: 0;
        }
        .qa-hero h1 {
          margin: 6px 0 0;
          font-family: var(--app-serif);
          font-size: 46px;
          font-style: italic;
          font-weight: 500;
          line-height: .95;
          letter-spacing: 0;
        }
        .qa-metrics {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 12px;
          margin-top: 16px;
        }
        .qa-metrics span {
          border-top: 1px solid var(--ink);
          padding-top: 7px;
          color: var(--ink-2);
          font-size: 11px;
          font-weight: 900;
          text-transform: uppercase;
        }
        .qa-metrics strong {
          display: block;
          color: var(--ink);
          font-size: 26px;
          line-height: 1;
        }
        .qa-chips {
          display: flex;
          gap: 8px;
          overflow-x: auto;
          padding: 0 16px 14px;
          scrollbar-width: none;
        }
        .qa-chips::-webkit-scrollbar {
          display: none;
        }
        .qa-count {
          display: inline-grid;
          min-width: 32px;
          min-height: 32px;
          place-items: center;
          border: 1px solid var(--ink);
          color: var(--ink);
        }
        .qa-dot {
          width: 10px;
          height: 10px;
          border: 1px solid var(--ink);
          background: var(--yellow);
        }
        .qa-dot.red {
          background: var(--red);
        }
        .qa-dot.blue {
          background: var(--blue);
        }
        .qa-rank {
          display: inline-grid;
          min-width: 28px;
          min-height: 24px;
          place-items: center;
          border: 1px solid var(--ink);
          font-size: 11px;
          font-weight: 900;
        }
        .qa-stack {
          display: grid;
          gap: 12px;
          padding: 14px 16px 0;
        }
        /* La Une sizes itself to the phone shell
           (min(--app-viewport-width, --phone-shell-max)), which would overflow
           this padded reference page. Narrow the shell variables for the demo
           instead of overriding the component's own width rule. */
        .qa-honest {
          display: grid;
          gap: 12px;
          padding: 14px 16px 0;
          --app-viewport-width: 100%;
          --phone-shell-max: 100%;
          --app-viewport-height: auto;
        }
        .qa-stack p {
          margin: 0;
        }
        button {
          min-height: 42px;
          border: 1px solid var(--ink);
          background: var(--sheet);
          color: var(--ink);
          font-weight: 900;
        }
        button.primary {
          background: var(--ink);
          color: var(--paper);
        }
      `}</style>
    </>
  );
}
