/**
 * SPEED-1 «Vérification du lexique» — the check screen.
 *
 * `BandCheckView` is a pure renderer over one `BandCheckViewState` (the gallery
 * draws every state from fixtures); `BandCheckFlow` owns the three API calls and
 * the run. The pure logic — sequencing, answering, the result card — lives in
 * `band-check-state.ts` and is pinned by `band-check.test.js`.
 *
 * The screen, on the placement's scaffold (body, then a foot that is the last
 * thing in the flow): a kicker with the sub-band, a slim progress rule, the
 * French word as the one Garamond headline (nouns with their article), four
 * meaning cards in the learner's language and «Je ne sais pas» under them as a
 * full-weight answer, never a quiet escape. One tap answers and advances; the
 * keyboard does the same (1–4, 0, Backspace). Nothing is marked right or wrong
 * during the run: the server holds the key, and the result card says the score
 * once, honestly.
 */

import React from 'react';

import {
  Action,
  ArrowLeftIcon,
  ArrowRightIcon,
  AtelierV2Root,
  ChoiceList,
  Notice,
  ProgressRule,
  ScreenFoot,
  Skeleton,
  StateBlock,
  Surface,
} from '@/components/atelier-v2/ui';
import { useLearnerLanguage } from '@/lib/learner-language';
import api, { type BandCheckSubBand } from '@/services/api';
import type { ControlLanguage } from '@/types/daily-journey';

import { bandCheckCopy, bandCheckFill, passedTitle, type BandCheckCopy } from './band-check-copy';
import {
  answer,
  answersPayload,
  currentItem,
  isComplete,
  keyToChoice,
  markCredited,
  nextBand,
  progressOf,
  startRun,
  summarize,
  undo,
  type BandCheckChoice,
  type BandCheckRun,
  type BandCheckSummary,
} from './band-check-state';

export type BandCheckOrigin = 'placement' | 'lexique';

export type BandCheckViewState =
  | { phase: 'loading' }
  | { phase: 'error' }
  | { phase: 'none' }
  | { phase: 'intro'; run: BandCheckRun; bands: BandCheckSubBand[] }
  | { phase: 'question'; run: BandCheckRun; sending?: boolean; failed?: boolean }
  | { phase: 'result'; summary: BandCheckSummary };

export type BandCheckViewProps = {
  state: BandCheckViewState;
  language: ControlLanguage;
  origin: BandCheckOrigin;
  pending?: boolean;
  onBegin: () => void;
  onChoose: (choice: BandCheckChoice) => void;
  onUndo: () => void;
  onResend: () => void;
  onRetryOpen: () => void;
  onCheckBand: (subBand: string) => void;
  onLeave: () => void;
  /** The gallery draws several screens on one page: no global key handler there. */
  keyboard?: boolean;
};

function Frame({
  language,
  copy,
  children,
  foot,
}: {
  language: ControlLanguage;
  copy: BandCheckCopy;
  children: React.ReactNode;
  foot?: React.ReactNode;
}) {
  return (
    <AtelierV2Root as="main" language={language} className="av2-screen bc-screen" aria-label={copy.screen_aria}>
      <div className="av2-screen__body bc-body">{children}</div>
      {foot ? <ScreenFoot className="bc-foot">{foot}</ScreenFoot> : null}
      <BandCheckStyles />
    </AtelierV2Root>
  );
}

export function BandCheckView({
  state,
  language,
  origin,
  pending = false,
  onBegin,
  onChoose,
  onUndo,
  onResend,
  onRetryOpen,
  onCheckBand,
  onLeave,
  keyboard = true,
}: BandCheckViewProps) {
  const copy = bandCheckCopy(language);
  const backLabel = origin === 'placement' ? copy.back_day : copy.back_lexique;

  // The keyboard answers exactly like a tap: 1–4, 0 for «je ne sais pas»,
  // Backspace for the previous word. Only while a question is on screen.
  const question = state.phase === 'question' && !state.sending ? currentItem(state.run) : null;
  const optionCount = question?.options.length ?? 0;
  React.useEffect(() => {
    if (!keyboard || !question) return undefined;
    const onKey = (event: KeyboardEvent) => {
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      const target = event.target as HTMLElement | null;
      if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) return;
      const action = keyToChoice(event.key, optionCount);
      if (!action) return;
      event.preventDefault();
      if (action.kind === 'undo') onUndo();
      else onChoose(action.choice);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [keyboard, question, optionCount, onChoose, onUndo]);

  if (state.phase === 'loading') {
    return (
      <Frame language={language} copy={copy}>
        <Skeleton />
        <Skeleton />
      </Frame>
    );
  }

  if (state.phase === 'error') {
    return (
      <Frame language={language} copy={copy}>
        <StateBlock
          tone="error"
          title={copy.screen_aria}
          body={copy.failed_open}
          action={{ label: copy.retry, onSelect: onRetryOpen }}
        />
        <button type="button" className="av2-btn av2-btn--quiet" onClick={onLeave}>
          {backLabel}
        </button>
      </Frame>
    );
  }

  if (state.phase === 'none') {
    return (
      <Frame
        language={language}
        copy={copy}
        foot={
          <Action tone="primary" onClick={onLeave} iconAfter={<ArrowRightIcon size={14} />}>
            {backLabel}
          </Action>
        }
      >
        <span className="av2-label">{copy.screen_aria}</span>
        <h1 className="av2-headline av2-headline--screen">{copy.none_title}</h1>
        <p className="bc-lead">{copy.none_lead}</p>
      </Frame>
    );
  }

  if (state.phase === 'intro') {
    const { run, bands } = state;
    return (
      <Frame
        language={language}
        copy={copy}
        foot={
          <>
            <Action
              tone="primary"
              pending={pending}
              pendingLabel={copy.opening}
              onClick={onBegin}
              iconAfter={<ArrowRightIcon size={14} />}
            >
              {copy.begin}
            </Action>
            <button type="button" className="av2-btn av2-btn--quiet" onClick={onLeave}>
              {copy.later}
            </button>
          </>
        }
      >
        <span className="av2-label">{bandCheckFill(copy.kicker, { band: run.subBand })}</span>
        <h1 className="av2-headline av2-headline--screen">{copy.intro_title}</h1>
        <p className="bc-lead">
          {bandCheckFill(copy.intro_lead, { n: run.items.length, band: run.subBand })}
        </p>
        <Surface tone="outline">
          <p className="bc-fine">
            {bandCheckFill(copy.intro_fine, { pct: Math.round(run.passShare * 100) })}
          </p>
        </Surface>
        {bands.length > 1 && (
          <div className="bc-bands">
            <span className="av2-label">{copy.bands_label}</span>
            <ul className="bc-bands__list">
              {bands.map((row) => (
                <li
                  key={row.sub_band}
                  className="bc-bands__row"
                  data-current={row.sub_band === run.subBand ? 'true' : undefined}
                  aria-current={row.sub_band === run.subBand ? 'step' : undefined}
                >
                  <span>{row.sub_band}</span>
                  {row.credited && <span className="bc-bands__mark">{copy.credited_mark}</span>}
                </li>
              ))}
            </ul>
          </div>
        )}
      </Frame>
    );
  }

  if (state.phase === 'question') {
    const { run } = state;
    const progress = progressOf(run);
    const item = currentItem(run);
    const sending = Boolean(state.sending) || (isComplete(run) && !state.failed);
    return (
      <Frame language={language} copy={copy}>
        <div className="bc-head">
          <span className="av2-label">{bandCheckFill(copy.kicker, { band: run.subBand })}</span>
          {run.index > 0 && !sending && (
            <button type="button" className="av2-btn av2-btn--quiet av2-btn--inline bc-undo" onClick={onUndo}>
              <ArrowLeftIcon size={12} />
              <span>{copy.undo}</span>
            </button>
          )}
        </div>
        <ProgressRule
          value={progress.done}
          max={progress.total}
          label={copy.progress_aria}
          caption={bandCheckFill(copy.progress_caption, { n: progress.done, total: progress.total })}
        />
        {item && !sending ? (
          <>
            <h1 className="av2-headline av2-headline--screen bc-word" lang="fr" aria-live="polite">
              {item.fr}
            </h1>
            <ChoiceList
              key={item.id}
              label={copy.options_label}
              selectedId={null}
              options={item.options.map((text, index) => ({ id: String(index), textFr: text, lang: null }))}
              onSelect={(id) => onChoose(Number(id))}
              statusLabels={{
                selected: copy.status_selected,
                correct: copy.status_correct,
                wrong: copy.status_wrong,
              }}
            />
            {/* A real answer, on the same footing as the four: the same full
                width, a paper face, no apology. */}
            <Action tone="secondary" className="bc-dontknow" onClick={() => onChoose(null)}>
              {copy.dont_know}
            </Action>
            <p className="bc-keys" aria-hidden="true">{copy.keys_hint}</p>
          </>
        ) : state.failed ? (
          <>
            <Notice tone="alert" live="alert">{copy.failed_send}</Notice>
            <Action tone="primary" pending={pending} pendingLabel={copy.sending} onClick={onResend}>
              {copy.retry}
            </Action>
          </>
        ) : (
          <StateBlock tone="loading" title={copy.sending} />
        )}
      </Frame>
    );
  }

  // ---- the result card ---------------------------------------------------
  const { summary } = state;
  const passed = summary.tone === 'passed';
  return (
    <Frame
      language={language}
      copy={copy}
      foot={
        passed && summary.next ? (
          <>
            <Action
              tone="primary"
              pending={pending}
              pendingLabel={copy.opening}
              onClick={() => onCheckBand(summary.next as string)}
              iconAfter={<ArrowRightIcon size={14} />}
            >
              {bandCheckFill(copy.next_band, { band: summary.next })}
            </Action>
            <button type="button" className="av2-btn av2-btn--quiet" onClick={onLeave}>
              {backLabel}
            </button>
          </>
        ) : (
          <>
            <Action tone="primary" onClick={onLeave} iconAfter={<ArrowRightIcon size={14} />}>
              {backLabel}
            </Action>
            {!passed && summary.next && (
              <button
                type="button"
                className="av2-btn av2-btn--quiet"
                onClick={() => onCheckBand(summary.next as string)}
              >
                {bandCheckFill(copy.next_anyway, { band: summary.next })}
              </button>
            )}
          </>
        )
      }
    >
      <span className="av2-label">{bandCheckFill(copy.kicker, { band: summary.subBand })}</span>
      <h1 className="av2-headline av2-headline--screen">
        {passed
          ? passedTitle(copy, summary.credited, summary.subBand)
          : bandCheckFill(copy.failed_title, { correct: summary.correct, total: summary.total })}
      </h1>
      {passed ? (
        <>
          <p className="bc-lead">{summary.credited > 0 ? copy.passed_lead : copy.passed_none_lead}</p>
          <Surface tone="outline">
            <p className="bc-fine">
              {bandCheckFill(copy.score_line, { correct: summary.correct, total: summary.total })}
              {summary.missed > 0 ? ` ${copy.passed_missed_note}` : ''}
            </p>
          </Surface>
        </>
      ) : (
        <p className="bc-lead">
          {bandCheckFill(copy.failed_lead, { band: summary.subBand, needed: summary.needed })}
        </p>
      )}
    </Frame>
  );
}

// ---------------------------------------------------------------------------
// The flow: three calls, one run
// ---------------------------------------------------------------------------

/** A second tap inside this window is the same finger landing twice. */
const TAP_GUARD_MS = 160;

export function BandCheckFlow({
  origin,
  initialBand,
  onLeave,
}: {
  origin: BandCheckOrigin;
  initialBand?: string | null;
  onLeave: () => void;
}) {
  const language = useLearnerLanguage();
  const [state, setState] = React.useState<BandCheckViewState>({ phase: 'loading' });
  const [pending, setPending] = React.useState(false);
  const bandsRef = React.useRef<BandCheckSubBand[] | null>(null);
  const lastTap = React.useRef(0);
  const sentRef = React.useRef<string | null>(null);

  /** Open a band: the intro the first time, straight into the words after a result. */
  const open = React.useCallback(async (band: string | null | undefined, direct: boolean) => {
    setPending(true);
    if (!direct) setState({ phase: 'loading' });
    try {
      const bands = bandsRef.current ?? (await api.getBandChecks());
      bandsRef.current = bands;
      const wanted = band && bands.some((row) => row.sub_band === band && !row.credited) ? band : nextBand(bands);
      if (!wanted) {
        setState({ phase: 'none' });
        return;
      }
      const start = await api.startBandCheck(wanted);
      if (!start.items.length) {
        setState({ phase: 'none' });
        return;
      }
      const run = startRun(start.sub_band, start.items, start.pass_share);
      sentRef.current = null;
      setState(direct ? { phase: 'question', run } : { phase: 'intro', run, bands });
    } catch {
      setState({ phase: 'error' });
    } finally {
      setPending(false);
    }
  }, []);

  React.useEffect(() => {
    void open(initialBand, false);
  }, [open, initialBand]);

  React.useEffect(() => {
    if (typeof window !== 'undefined') window.scrollTo({ top: 0 });
  }, [state.phase]);

  const submit = React.useCallback(async (run: BandCheckRun) => {
    setPending(true);
    setState({ phase: 'question', run, sending: true });
    try {
      const result = await api.submitBandCheck(run.subBand, answersPayload(run));
      if (result.passed && bandsRef.current) bandsRef.current = markCredited(bandsRef.current, run.subBand);
      setState({ phase: 'result', summary: summarize(result, bandsRef.current, run.passShare) });
    } catch {
      sentRef.current = null;
      setState({ phase: 'question', run, failed: true });
    } finally {
      setPending(false);
    }
  }, []);

  const choose = React.useCallback(
    (choice: BandCheckChoice) => {
      const now = Date.now();
      if (now - lastTap.current < TAP_GUARD_MS) return;
      lastTap.current = now;
      setState((current) => {
        if (current.phase !== 'question' || current.sending || current.failed) return current;
        return { phase: 'question', run: answer(current.run, choice) };
      });
    },
    [],
  );

  const stepBack = React.useCallback(() => {
    setState((current) =>
      current.phase === 'question' && !current.sending ? { phase: 'question', run: undo(current.run) } : current,
    );
  }, []);

  // The last answer sends the run, once.
  React.useEffect(() => {
    if (state.phase !== 'question' || state.sending || state.failed) return;
    if (!isComplete(state.run)) return;
    const key = `${state.run.subBand}:${JSON.stringify(state.run.answers)}`;
    if (sentRef.current === key) return;
    sentRef.current = key;
    void submit(state.run);
  }, [state, submit]);

  return (
    <BandCheckView
      state={state}
      language={language}
      origin={origin}
      pending={pending}
      onBegin={() => {
        if (state.phase === 'intro') setState({ phase: 'question', run: state.run });
      }}
      onChoose={choose}
      onUndo={stepBack}
      onResend={() => {
        if (state.phase === 'question') void submit(state.run);
      }}
      onRetryOpen={() => void open(initialBand, false)}
      onCheckBand={(band) => void open(band, true)}
      onLeave={onLeave}
    />
  );
}

function BandCheckStyles() {
  return (
    <style jsx global>{`
      /* The placement's scaffold: a column that fills the shell, a body that
         carries the reading, a foot that is the last thing in the flow. */
      .av2.bc-screen {
        display: flex;
        flex: 1 1 auto;
        flex-direction: column;
        min-height: 100%;
        min-width: 0;
        background: var(--av2-paper);
      }
      @media (max-width: 760px) {
        .av2 .bc-foot {
          --av2-safe-bottom: 0px;
        }
      }
      .av2 .bc-body {
        flex: 1 1 auto;
        gap: 16px;
        width: 100%;
        max-width: 460px;
        margin: 0 auto;
        padding-top: calc(24px + env(safe-area-inset-top, 0px));
        padding-bottom: 20px;
      }
      .av2 .bc-foot {
        display: flex;
        flex-direction: column;
        align-items: stretch;
        gap: 4px;
      }
      .av2 .bc-foot > * {
        width: 100%;
        max-width: 460px;
        margin-left: auto;
        margin-right: auto;
      }
      .av2 .bc-lead {
        margin: 0;
        font-size: var(--av2-t-body);
        line-height: 1.45;
        color: var(--av2-ink-2);
      }
      .av2 .bc-fine {
        margin: 0;
        font-size: var(--av2-t-label);
        line-height: 1.45;
        color: var(--av2-muted);
      }
      .av2 .bc-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        min-height: var(--av2-tap);
      }
      .av2 .bc-undo {
        display: inline-flex;
        align-items: center;
        gap: 6px;
      }
      .av2 .bc-word {
        margin: 8px 0 4px;
        text-align: center;
        overflow-wrap: anywhere;
      }
      .av2 .bc-dontknow {
        width: 100%;
      }
      .av2 .bc-keys {
        margin: 0;
        font-size: var(--av2-t-meta);
        color: var(--av2-muted);
        text-align: center;
      }
      /* The hint is for a keyboard; a phone has none. */
      @media (hover: none) {
        .av2 .bc-keys {
          display: none;
        }
      }
      .av2 .bc-bands {
        display: flex;
        flex-direction: column;
        gap: 8px;
      }
      .av2 .bc-bands__list {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin: 0;
        padding: 0;
        list-style: none;
      }
      .av2 .bc-bands__row {
        display: inline-flex;
        align-items: baseline;
        gap: 6px;
        padding: 4px 12px;
        border: 1px solid var(--av2-line-2);
        border-radius: var(--av2-r-pill);
        font-size: var(--av2-t-label);
        font-variant-numeric: tabular-nums;
        color: var(--av2-ink-2);
      }
      .av2 .bc-bands__row[data-current='true'] {
        border-color: var(--av2-ink);
        color: var(--av2-ink);
      }
      .av2 .bc-bands__mark {
        font-size: var(--av2-t-meta);
        color: var(--av2-muted);
      }
    `}</style>
  );
}

export default BandCheckFlow;
