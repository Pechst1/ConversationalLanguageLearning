import Head from 'next/head';
import { ArrowRight } from 'lucide-react';

import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { ExerciseShell } from '@/components/ui/ExerciseShell';
import { FeedbackSheet } from '@/components/ui/FeedbackSheet';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { AtelierForms } from '@/components/ui/AtelierForms';
import { ReactForm, Seal, SealMini, LogoToken } from '@/components/ui/Seal';

export async function getStaticProps() {
  if (process.env.NODE_ENV === 'production') {
    return { notFound: true };
  }
  return { props: {} };
}

export default function AtelierStyleguidePage() {
  return (
    <>
      <Head>
        <title>Atelier Styleguide</title>
      </Head>
      <main className="styleguide-page">
        <section className="styleguide-hero">
          <span>Atelier design system</span>
          <h1>The daily edition, beautifully simple.</h1>
        </section>

        <section className="styleguide-grid">
          <Card>
            <CardHeader>
              <CardTitle>Color roles</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="swatches">
                <i style={{ background: 'var(--app-ink)' }} />
                <i style={{ background: 'var(--accent-action)' }} />
                <i style={{ background: 'var(--accent-alert)' }} />
                <i style={{ background: 'var(--accent-info)' }} />
                <i style={{ background: 'var(--accent-reward)' }} />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Button</CardTitle>
            </CardHeader>
            <CardContent>
              <Button rightIcon={<ArrowRight size={16} />}>Continue</Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Read Surface</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="styleguide-read-card">Flat editorial card</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Do Shadow</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="styleguide-do-card">Exercise-only accent</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Progress</CardTitle>
            </CardHeader>
            <CardContent>
              <ProgressBar value={42} label="Press run" />
            </CardContent>
          </Card>
        </section>

        <ExerciseShell eyebrow="Do mode" title="One exercise, one action">
          <p className="styleguide-prompt">Si elle appelle, je ____ tout de suite.</p>
          <div className="styleguide-choice-row">
            <button>réponds</button>
            <button className="selected">répondrai</button>
            <button>répondrais</button>
          </div>
        </ExerciseShell>

        <div className="styleguide-feedback-demo">
          <FeedbackSheet
            status="wrong"
            title="Almost."
            explanation="You put the future inside the si-clause."
            repair="Keep the si-clause in the present, then use future for the result."
            rule="si + present -> future"
          />
        </div>

        <section className="styleguide-press">
          <span className="styleguide-eyebrow">Press run · reward primitives</span>
          <div className="press-row">
            <div className="press-cell">
              <AtelierForms react="neutral" motion={false} />
              <small>Forms · neutral</small>
            </div>
            <div className="press-cell">
              <AtelierForms react="correct" motion={false} />
              <small>Forms · correct</small>
            </div>
            <div className="press-cell">
              <AtelierForms react="wrong" motion={false} />
              <small>Forms · wrong</small>
            </div>
            <div className="press-cell">
              <div className="press-trio">
                <ReactForm shape="circle" state="grin" />
                <ReactForm shape="square" state="sad" />
                <ReactForm shape="triangle" state="grin" />
              </div>
              <small>Scorekeepers · 2/3</small>
            </div>
          </div>
          <div className="press-row">
            <div className="press-cell">
              <Seal variant="row" no={12} date="Vendredi 30 mai" />
              <small>Seal · En ligne</small>
            </div>
            <div className="press-cell">
              <Seal variant="orbit" no={13} date="Samedi 31 mai" />
              <small>Seal · L&apos;orbite</small>
            </div>
            <div className="press-cell">
              <LogoToken />
              <small>Logo token</small>
            </div>
            <div className="press-cell">
              <div className="press-trio">
                <SealMini no={12} variant="row" state="earned" />
                <SealMini variant="row" state="future" />
                <SealMini variant="row" state="empty" />
              </div>
              <small>Almanac states</small>
            </div>
          </div>
        </section>
      </main>
      <style jsx>{`
        .styleguide-page {
          min-height: 100vh;
          background: var(--app-paper);
          color: var(--app-ink);
          padding: clamp(24px, 5vw, 72px);
        }
        .styleguide-hero {
          max-width: 760px;
          margin-bottom: 40px;
        }
        .styleguide-hero span {
          color: var(--app-red);
          font-family: var(--mono);
          font-size: var(--type-mono);
          font-weight: var(--weight-medium);
          letter-spacing: 0.14em;
          text-transform: uppercase;
        }
        .styleguide-hero h1 {
          margin: 8px 0 0;
          font-family: var(--app-serif);
          font-size: var(--type-display);
          font-style: italic;
          font-weight: var(--weight-medium);
          line-height: 0.95;
          letter-spacing: 0;
        }
        .styleguide-grid {
          display: grid;
          grid-template-columns: repeat(5, minmax(0, 1fr));
          gap: 16px;
          margin-bottom: 32px;
        }
        .swatches {
          display: grid;
          grid-template-columns: repeat(5, 1fr);
          gap: 8px;
        }
        .swatches i {
          display: block;
          aspect-ratio: 1;
          border: 1px solid var(--app-ink);
        }
        .styleguide-read-card,
        .styleguide-do-card {
          min-height: 74px;
          display: grid;
          place-items: center;
          border: 1px solid var(--app-ink);
          background: var(--app-sheet);
          color: var(--app-ink-2);
          font-family: var(--mono);
          font-size: var(--type-mono);
          font-weight: var(--weight-medium);
          letter-spacing: 0.1em;
          text-transform: uppercase;
        }
        .styleguide-do-card {
          box-shadow: var(--shadow-do);
          background: var(--app-paper);
          color: var(--app-ink);
        }
        .styleguide-prompt {
          margin: 0 0 20px;
          font-family: var(--app-serif);
          font-size: clamp(28px, 6vw, 48px);
          font-style: italic;
          line-height: 1.08;
        }
        .styleguide-choice-row {
          display: flex;
          flex-wrap: wrap;
          gap: 10px;
        }
        .styleguide-choice-row button {
          min-height: 44px;
          border: 1px solid var(--app-ink);
          background: var(--app-paper);
          padding: 0 16px;
          font-family: var(--app-serif);
          font-size: 20px;
          font-style: italic;
        }
        .styleguide-choice-row .selected {
          background: var(--accent-action);
          color: #fff;
        }
        .styleguide-feedback-demo {
          position: relative;
          min-height: 260px;
        }
        .styleguide-feedback-demo :global(.atelier-feedback-sheet) {
          position: absolute;
          right: auto;
          bottom: auto;
          left: 0;
          top: 32px;
        }
        .styleguide-press {
          margin-top: 40px;
        }
        .styleguide-eyebrow {
          display: block;
          margin-bottom: 18px;
          color: var(--app-red);
          font-family: var(--mono);
          font-size: var(--type-mono);
          font-weight: var(--weight-medium);
          letter-spacing: 0.14em;
          text-transform: uppercase;
        }
        .press-row {
          display: flex;
          flex-wrap: wrap;
          gap: 16px;
          margin-bottom: 16px;
        }
        .press-cell {
          display: grid;
          justify-items: center;
          align-content: start;
          gap: 14px;
          min-width: 120px;
          flex: 0 0 auto;
          border: 1px solid var(--app-ink);
          background: var(--app-sheet);
          padding: 22px 18px;
        }
        .press-cell small {
          color: var(--app-ink-3);
          font-family: var(--mono);
          font-size: var(--type-mono);
          letter-spacing: 0.08em;
          text-transform: uppercase;
        }
        .press-trio {
          display: flex;
          align-items: center;
          gap: 16px;
          min-height: 64px;
        }
        @media (max-width: 760px) {
          .styleguide-grid {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </>
  );
}
