/**
 * Atelier V2 design-system gallery — DEVELOPMENT ONLY.
 *
 * Gated exactly like `/mobile-visual-qa`: `getStaticProps` returns `notFound`
 * when `NODE_ENV === 'production'`, so the route does not exist in a production
 * build. It deliberately does **not** widen production auth or add a flag.
 *
 * Every state of every primitive is on this page, including the ones the design
 * has no artboard for — pending, unscored, reconciled, offline, error, empty,
 * broken artwork — so they can be reviewed at 320/390/440/768/1280 and at 200%
 * text without driving a real journey.
 *
 * The sample sentences are the design's own strings from
 * `Atelier App.dc.html`. Nothing here is presented as a learner's data: there
 * is no learner name, no streak, and no duration that a real screen would show.
 */

import React, { useState } from 'react';
import Head from 'next/head';

import {
  Action,
  Artwork,
  AtelierMark,
  AtelierV2Root,
  BottomSheet,
  Byline,
  CheckIcon,
  ChoiceList,
  Chip,
  Correction,
  CrossIcon,
  Dialog,
  DoneBadge,
  FeedbackBand,
  IconAction,
  MicIcon,
  Notice,
  Portrait,
  ProgressRule,
  Row,
  ShapeToken,
  StateBlock,
  StepProgress,
  Surface,
  TabBar,
  TextAnswer,
  WordTiles,
  type TabKey,
} from '@/components/atelier-v2/ui';
import { atelierCopy, CONTROL_LANGUAGES } from '@/lib/atelier-v2-copy';
import type { ControlLanguage } from '@/types/daily-journey';

export async function getStaticProps() {
  if (process.env.NODE_ENV === 'production') {
    return { notFound: true };
  }
  return { props: {} };
}

const OPTIONS = [
  { id: 'a', textFr: 'elle réussira' },
  { id: 'b', textFr: 'elle a réussi' },
  { id: 'c', textFr: 'elle réussit' },
];

const TILES = [
  { id: 't1', textFr: 'Si' },
  { id: 't2', textFr: 'tu' },
  { id: 't3', textFr: 'viens,' },
  { id: 't4', textFr: 'on' },
  { id: 't5', textFr: 'ira' },
];

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="gal-section">
      <h2 className="gal-h2">{title}</h2>
      <div className="av2-stack">{children}</div>
    </section>
  );
}

export default function AtelierV2Gallery() {
  const [theme, setTheme] = useState<'light' | 'dark'>('light');
  const [language, setLanguage] = useState<ControlLanguage>('en');
  const [sheetOpen, setSheetOpen] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [choice, setChoice] = useState<string | null>('a');
  const [placed, setPlaced] = useState<string[]>(['t1', 't2']);
  const [text, setText] = useState('');
  const [tab, setTab] = useState<TabKey>('atelier');

  const copy = atelierCopy(language);
  const statusLabels = {
    selected: copy.status_selected,
    correct: copy.status_correct,
    wrong: copy.status_wrong,
  };

  return (
    <>
      <Head>
        <title>Atelier V2 gallery (dev)</title>
        <meta name="robots" content="noindex" />
      </Head>

      <div className="gal-controls">
        <label>
          Theme{' '}
          <select value={theme} onChange={(e) => setTheme(e.target.value as 'light' | 'dark')}>
            <option value="light">light</option>
            <option value="dark">dark</option>
          </select>
        </label>
        <label>
          Language{' '}
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value as ControlLanguage)}
          >
            {CONTROL_LANGUAGES.map((code) => (
              <option key={code} value={code}>
                {code}
              </option>
            ))}
          </select>
        </label>
        <span>Set text size in L’administration → Apparence; this page is rem-based.</span>
      </div>

      <AtelierV2Root as="main" language={language} forceTheme={theme} className="gal-root">
        <div className="av2-screen__body">
          <header className="av2-byline">
            <AtelierMark title="Atelier" />
            <h1 className="av2-headline av2-headline--display">Atelier V2</h1>
          </header>

          <Section title="Shape vocabulary">
            <div className="av2-help__actions">
              <Chip icon={<ShapeToken kind="done" size="sm" />}>ink square · done</Chip>
              <Chip icon={<ShapeToken kind="story" size="sm" />}>blue circle · story</Chip>
              <Chip icon={<ShapeToken kind="reward" size="sm" />}>yellow square · reward</Chip>
              <Chip icon={<ShapeToken kind="action" size="sm" />}>red triangle · action</Chip>
            </div>
          </Section>

          <Section title="Actions — one primary per composition">
            <Action tone="primary">{copy.action_check}</Action>
            <Action tone="done">{copy.action_finish}</Action>
            <Action tone="story">{copy.action_continue}</Action>
            <Action tone="reward">{copy.action_start}</Action>
            <Action tone="secondary">{copy.action_retry}</Action>
            <Action tone="quiet" inline>
              {copy.dismiss}
            </Action>
            <Action tone="primary" disabled>
              disabled — label stays legible
            </Action>
            <Action tone="primary" pending pendingLabel={copy.status_pending}>
              {copy.action_send}
            </Action>
            <div className="av2-help__actions">
              <IconAction label={copy.close}>
                <CrossIcon size={16} />
              </IconAction>
              <IconAction label={copy.record_start} tone="action" pressable>
                <MicIcon size={18} />
              </IconAction>
              <IconAction label={copy.record_stop} tone="recording" pressable>
                <CheckIcon size={18} />
              </IconAction>
              <IconAction label={copy.status_pending} pending>
                <MicIcon size={18} />
              </IconAction>
            </div>
          </Section>

          <Section title="Progress — real plan data only">
            <ProgressRule value={2} max={5} label={copy.progress_none} caption="2 / 5" />
            <StepProgress
              label="steps"
              caption="Step 3 of 5"
              steps={[
                { id: '1', state: 'done' },
                { id: '2', state: 'done' },
                { id: '3', state: 'active' },
                { id: '4', state: 'pending' },
                { id: '5', state: 'skipped' },
              ]}
            />
            <ProgressRule value={0} max={0} label="unknown plan" />
          </Section>

          <Section title="Choice cards">
            <ChoiceList
              options={OPTIONS}
              selectedId={choice}
              label="Choose one"
              onSelect={setChoice}
              statusLabels={statusLabels}
            />
            <ChoiceList
              options={[
                { ...OPTIONS[0], state: 'correct' },
                { ...OPTIONS[1], state: 'wrong' },
                OPTIONS[2],
              ]}
              selectedId={null}
              label="Graded, and locked"
              disabled
              onSelect={() => {}}
              statusLabels={statusLabels}
            />
          </Section>

          <Section title="Word tiles">
            <WordTiles
              options={TILES}
              placed={placed}
              label="Build the sentence"
              emptyHint={copy.tiles_empty}
              removeLabel={copy.remove_last}
              onPlace={(id) => setPlaced((c) => [...c, id])}
              onRemoveLast={() => setPlaced((c) => c.slice(0, -1))}
            />
          </Section>

          <Section title="Field">
            <TextAnswer
              label={copy.answer_label}
              value={text}
              placeholder={copy.answer_placeholder}
              onChange={setText}
            />
            <TextAnswer
              label={`${copy.answer_label} — refused as empty`}
              value=""
              invalid
              onChange={() => {}}
            />
            <TextAnswer
              label={`${copy.answer_label} — closed after grading`}
              value="Si tu viens, on ira."
              disabled
              onChange={() => {}}
            />
          </Section>

          <Section title="Feedback — only a graded verdict gets the band">
            <div className="av2-graded" data-state="correct">
              <FeedbackBand tone="correct" title={copy.correct} detail="Parfait, à tout à l’heure !" />
            </div>
            <div className="av2-graded" data-state="supported">
              <FeedbackBand tone="supported" title={copy.supported} detail="Presque : une petite reprise.">
                <Correction
                  label={copy.correction}
                  spanFr="je prends"
                  correctedFr="je prendrai"
                  noteNative="After si + present, the consequence goes to the future."
                />
              </FeedbackBand>
            </div>
            <div className="av2-graded" data-state="wrong">
              <FeedbackBand tone="wrong" title={copy.wrong} />
            </div>
            <FeedbackBand tone="neutral" title={copy.still_grading} />
          </Section>

          <Section title="Notices — never a verdict">
            <Notice shape="story">
              <p>{copy.retrying}</p>
            </Notice>
            <Notice tone="alert" live="alert" shape="action">
              <p>{copy.empty_answer}</p>
            </Notice>
            <Notice shape="story">
              <p>{copy.reconciled}</p>
            </Notice>
            <Notice tone="quiet" shape="story">
              <p>{copy.offline_cached}</p>
            </Notice>
            <Notice tone="alert" live="alert" shape="action">
              <p>{copy.transport_error}</p>
              <Action tone="secondary" inline>
                {copy.retry}
              </Action>
            </Notice>
          </Section>

          <Section title="States">
            <StateBlock tone="loading" title={copy.loading} body={copy.preparing_body} />
            <StateBlock tone="empty" title={copy.empty_title} body={copy.empty_body} />
            <StateBlock
              tone="error"
              title={copy.error_title}
              body={copy.transport_error}
              action={{ label: copy.retry, onSelect: () => {} }}
            />
          </Section>

          <Section title="Surfaces, artwork and characters">
            <Surface shape="episode">
              {/* A URL that cannot resolve, to show the graceful failure. */}
              <Artwork
                url="/does-not-exist.png"
                alt=""
                fallbackLabel={copy.artwork_unavailable}
              />
              <div className="journey-today-card__body av2-stack">
                <p className="av2-label av2-label--story">Feuilleton · Épisode 3</p>
                <h3 className="av2-headline av2-headline--title" lang="fr">
                  Une lettre attend ta réponse.
                </h3>
                <Byline name="Monsieur Marchand" meta="8 min" />
              </div>
            </Surface>
            <Surface tone="blue">
              <p className="av2-label">Story surface</p>
              <p className="av2-headline av2-headline--rule" lang="fr">
                Si tu viens, on ira.
              </p>
            </Surface>
            <Surface tone="outline">
              <p className="av2-label">Outlined — locked or nothing yet</p>
            </Surface>
            <div className="av2-help__actions">
              {['Marin', 'Lila', 'Gus', 'Romy', 'Margaux', 'Monsieur Marchand', 'Inconnu'].map(
                (name) => (
                  <Portrait key={name} name={name} />
                ),
              )}
            </div>
            <Row
              eyebrow="Épisode 2 · lu"
              title={<span lang="fr">Le marché du samedi</span>}
              badge={<DoneBadge label={copy.status_done} />}
              onSelect={() => {}}
            />
          </Section>

          <Section title="Overlays">
            <div className="av2-help__actions">
              <Action tone="secondary" inline onClick={() => setSheetOpen(true)}>
                Open bottom sheet
              </Action>
              <Action tone="secondary" inline onClick={() => setDialogOpen(true)}>
                Open dialog
              </Action>
            </div>
          </Section>

          <Section title="Navigation">
            <TabBar
              label={copy.nav_label}
              active={tab}
              tabs={[
                { key: 'atelier', label: copy.nav_atelier, onSelect: () => setTab('atelier') },
                { key: 'missions', label: copy.nav_missions, onSelect: () => setTab('missions') },
                { key: 'serial', label: copy.nav_serial, onSelect: () => setTab('serial') },
                { key: 'notebook', label: copy.nav_notebook, onSelect: () => setTab('notebook') },
              ]}
            />
          </Section>
        </div>

        <BottomSheet
          open={sheetOpen}
          eyebrow={copy.today_edition}
          title={copy.rule_card}
          onClose={() => setSheetOpen(false)}
        >
          <div className="av2-stack">
            <p className="av2-headline av2-headline--rule" lang="fr">
              Si + présent → futur simple
            </p>
            <p className="av2-body av2-body--lg">
              Escape closes this. Tab cycles inside it. Focus returns to the control that
              opened it.
            </p>
            <Action tone="primary" onClick={() => setSheetOpen(false)}>
              {copy.action_continue}
            </Action>
          </div>
        </BottomSheet>

        <Dialog
          open={dialogOpen}
          title={copy.finish_early}
          body={copy.more_practice_note}
          onClose={() => setDialogOpen(false)}
          actions={
            <>
              <Action tone="primary" onClick={() => setDialogOpen(false)}>
                {copy.action_finish}
              </Action>
              <Action tone="secondary" onClick={() => setDialogOpen(false)}>
                {copy.dismiss}
              </Action>
            </>
          }
        />
      </AtelierV2Root>

      <style jsx global>{`
        .gal-controls {
          display: flex;
          flex-wrap: wrap;
          gap: 12px;
          align-items: center;
          padding: 10px 16px;
          font: 13px/1.4 system-ui, sans-serif;
          background: #222;
          color: #fff;
          position: sticky;
          top: 0;
          z-index: 80;
        }
        .gal-controls select {
          font: inherit;
        }
        .gal-root {
          min-height: 100vh;
        }
        .gal-section {
          padding: 18px 0;
          border-top: 1px solid var(--av2-line);
          min-width: 0;
        }
        .gal-h2 {
          margin: 0 0 12px;
          font-size: var(--av2-t-meta);
          font-weight: 700;
          color: var(--av2-muted);
        }
      `}</style>
    </>
  );
}
