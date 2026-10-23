/* La Forge's new formats (owner, 2026-10-18: «more diverse exercise formats, a
   bit more fun», and a learner who learns fast). Each is a new gesture over an
   item the séance already grades by key (`lib/forge-drills.ts`):

   - ForgeTypedField: «Tape la forme» — the form is typed, not picked; the
     accents a phone hides sit on a bar under the field.
   - ForgeListen: «Dictée» — the sentence is heard (the server's voice, else
     the browser's), then built from the tiles; «Plus lent» slows it down.
   - ForgeSpot: «Trouve l'erreur» and «Ta phrase» — tap the word that is
     wrong, type it right; the answer is the sentence with the fix in it.
   - ForgeRafale: four judgements, one tap each, sent as one answer;
     ForgeRafaleResult: the four marks, the fixes, and the time it took.

   Sans for the chrome; the French is the exercise. Every colour is an --av2-*
   token, and nothing draws a border, an outline or a stroke. */

import React from 'react';

import { CheckIcon, RepairIcon, useControlLanguage } from '@/components/atelier-v2/ui';
import { EpBar, EpFoot, EpIco, EpOpt, EpOpts, EpPrompt, EpVerdict } from '@/components/epreuve/Epreuve';
import { judgementLabel } from '@/lib/classification-copy';
import { fillForge, spotHint, type ForgeCopy } from '@/lib/forge-copy';
import {
  ACCENTS,
  burstSeconds,
  insertAt,
  spotChanged,
  spotTokens,
  type BurstRow,
} from '@/lib/forge-drills';
import type { PortraitMood } from '@/lib/onboarding-portraits';

type Coach = { id: string; name: string };

/* ---------- «Tape la forme» ---------- */

export function ForgeTypedField({
  value,
  onChange,
  onSubmit,
  submitted = false,
  verdict = null,
  copy,
}: {
  value: string;
  onChange: (value: string) => void;
  /** Return on the keyboard checks the answer. */
  onSubmit?: () => void;
  submitted?: boolean;
  verdict?: 'right' | 'wrong' | null;
  copy: ForgeCopy;
}) {
  const field = React.useRef<HTMLInputElement | null>(null);
  const type = (letter: string) => {
    const input = field.current;
    const next = insertAt(value, input?.selectionStart, input?.selectionEnd, letter);
    onChange(next.value);
    // The caret stays after the letter, and the keyboard stays up.
    window.requestAnimationFrame(() => {
      input?.focus();
      input?.setSelectionRange(next.caret, next.caret);
    });
  };
  return (
    <div className="forge-typed" data-verdict={submitted && verdict ? verdict : undefined}>
      <input
        ref={field}
        className="forge-typed__input"
        type="text"
        lang="fr"
        value={value}
        placeholder={copy.typed_placeholder}
        aria-label={copy.hint_typed}
        autoComplete="off"
        autoCorrect="off"
        autoCapitalize="none"
        spellCheck={false}
        enterKeyHint="done"
        readOnly={submitted}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key !== 'Enter') return;
          event.preventDefault();
          if (!submitted) onSubmit?.();
        }}
      />
      {!submitted && (
        <div className="forge-accents" role="group" aria-label={copy.accents_label}>
          {ACCENTS.map((letter) => (
            <button
              key={letter}
              type="button"
              className="forge-accent"
              lang="fr"
              // A tap on a letter never takes the focus from the field.
              onPointerDown={(event) => event.preventDefault()}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => type(letter)}
            >
              {letter}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/* ---------- «Dictée» ---------- */

type Synthesize = (text: string) => Promise<ArrayBuffer>;

function browserVoice(text: string, slow: boolean, done: () => void): boolean {
  if (typeof window === 'undefined' || !('speechSynthesis' in window)) return false;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = 'fr-FR';
  utterance.rate = slow ? 0.7 : 1;
  utterance.onend = done;
  utterance.onerror = done;
  window.speechSynthesis.speak(utterance);
  return true;
}

/**
 * The sentence's voice, asked for on the first tap, as every listen button in
 * the app asks: nothing is synthesized (or paid for) before the learner wants
 * it, and a deployment without a server voice fails that tap, not every
 * dictation shown. The clip is kept, so a replay or «Plus lent» plays at once,
 * inside its own tap. Without a clip the browser reads the sentence.
 */
function useFrenchVoice(text: string, synthesize?: Synthesize) {
  const [playing, setPlaying] = React.useState(false);
  const asked = React.useRef<Promise<string | null> | null>(null);
  const clip = React.useRef<string | null>(null);
  const audio = React.useRef<HTMLAudioElement | null>(null);
  const turn = React.useRef(0);
  React.useEffect(() => () => {
    audio.current?.pause();
    audio.current = null;
    const pending = asked.current;
    asked.current = null;
    clip.current = null;
    void pending?.then((url) => {
      if (url) URL.revokeObjectURL(url);
    });
    // The next sentence starts silent, even if this one's voice never came.
    setPlaying(false);
  }, [text]);
  const play = (slow = false) => {
    if (!text) return;
    turn.current += 1;
    const mine = turn.current;
    const done = () => setPlaying(false);
    const read = () => {
      if (!browserVoice(text, slow, done)) done();
    };
    const sound = (url: string) => {
      const player = new Audio(url);
      player.playbackRate = slow ? 0.75 : 1;
      player.onended = done;
      audio.current = player;
      player.play().catch(read);
    };
    audio.current?.pause();
    setPlaying(true);
    if (clip.current) {
      sound(clip.current);
      return;
    }
    if (!synthesize) {
      read();
      return;
    }
    if (!asked.current) {
      asked.current = synthesize(text)
        .then((bytes) => (bytes.byteLength ? URL.createObjectURL(new Blob([bytes], { type: 'audio/mpeg' })) : null))
        .catch(() => null);
    }
    const pending = asked.current;
    void pending.then((url) => {
      // Another tap, or the next item, has come since: it speaks instead.
      if (asked.current !== pending || turn.current !== mine) return;
      clip.current = url;
      if (url) sound(url);
      else read();
    });
  };
  return { playing, play };
}

export function ForgeListen({ text, copy, synthesize }: { text: string; copy: ForgeCopy; synthesize?: Synthesize }) {
  const voice = useFrenchVoice(text, synthesize);
  return (
    <div className="forge-listen" data-playing={voice.playing ? 'true' : undefined}>
      <button type="button" className="forge-listen__play" onClick={() => voice.play(false)}>
        <span className="forge-listen__icon" aria-hidden="true">{EpIco.play}</span>
        <span>{copy.listen}</span>
      </button>
      <button type="button" className="forge-listen__slow" onClick={() => voice.play(true)}>
        {copy.listen_slow}
      </button>
    </div>
  );
}

/* ---------- «Trouve l'erreur» · «Ta phrase» ---------- */

export function ForgeSpot({
  sentence,
  edits,
  onEdits,
  submitted = false,
  copy,
  fixWords,
}: {
  sentence: string;
  edits: Record<number, string>;
  onEdits: (edits: Record<number, string>) => void;
  submitted?: boolean;
  copy: ForgeCopy;
  /** How many words are wrong, when it is more than one (#300). */
  fixWords?: number | null;
}) {
  const tokens = React.useMemo(() => spotTokens(sentence), [sentence]);
  const [editing, setEditing] = React.useState<number | null>(null);
  const [draft, setDraft] = React.useState('');
  const has = (index: number) => Object.prototype.hasOwnProperty.call(edits, index);
  const start = (index: number) => {
    if (submitted) return;
    setEditing(index);
    setDraft(has(index) ? edits[index] : tokens[index].word);
  };
  const commit = () => {
    if (editing === null) return;
    const value = draft.replace(/\s+/g, ' ').trim();
    const next = { ...edits };
    if (value === tokens[editing].word) delete next[editing];
    else next[editing] = value;
    setEditing(null);
    onEdits(next);
  };
  return (
    <div className="forge-spot">
      <p className="forge-spot__line" lang="fr">
        {tokens.map((token, index) => (
          <React.Fragment key={index}>
            {token.lead && <span className="forge-spot__punct">{token.lead}</span>}
            {token.word && editing === index && (
              <input
                className="forge-spot__input"
                type="text"
                lang="fr"
                value={draft}
                size={Math.max(4, draft.length + 1)}
                aria-label={fillForge(copy.spot_edit_label, { word: token.word })}
                autoFocus
                autoComplete="off"
                autoCorrect="off"
                autoCapitalize="none"
                spellCheck={false}
                enterKeyHint="done"
                onChange={(event) => setDraft(event.target.value)}
                onBlur={commit}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    event.preventDefault();
                    commit();
                  } else if (event.key === 'Escape') {
                    setEditing(null);
                  }
                }}
              />
            )}
            {token.word && editing !== index && (
              <button
                type="button"
                className="forge-spot__word"
                data-edited={has(index) ? 'true' : undefined}
                disabled={submitted}
                onClick={() => start(index)}
              >
                {has(index) ? (
                  <>
                    <s className="forge-spot__was">{token.word}</s>
                    {edits[index] && <span className="forge-spot__now">{edits[index]}</span>}
                  </>
                ) : token.word}
              </button>
            )}
            {token.trail && <span className="forge-spot__punct">{token.trail}</span>}
            {token.space ? ' ' : null}
          </React.Fragment>
        ))}
      </p>
      {!submitted && (spotChanged(tokens, edits) ? (
        <button type="button" className="forge-spot__undo" onClick={() => onEdits({})}>
          {copy.spot_undo}
        </button>
      ) : editing === null && (
        // The gesture is said until it is made.
        <p className="forge-spot__hint">{spotHint(copy, fixWords)}</p>
      ))}
    </div>
  );
}

/* ---------- «Rafale» ---------- */

type Judged = Record<string, any>;

/**
 * Four judgements, one at a time; each tap moves on. The fourth sends all four
 * as one answer (`onDone`), with the time the learner took.
 */
export function ForgeRafale({
  items,
  copy,
  sending = false,
  onDone,
  resendLabel,
}: {
  items: Judged[];
  copy: ForgeCopy;
  sending?: boolean;
  onDone: (answers: Record<string, string>, ms: number) => void;
  /** Shown when the four were picked but could not be sent: send them again. */
  resendLabel?: string;
}) {
  const language = useControlLanguage();
  const [at, setAt] = React.useState(0);
  const [answers, setAnswers] = React.useState<Record<string, string>>({});
  const started = React.useRef<number | null>(null);
  const took = React.useRef(0);
  React.useEffect(() => {
    started.current = Date.now();
  }, []);
  const item = items[Math.min(at, items.length - 1)] || {};
  const finished = at >= items.length;
  const pick = (label: string) => {
    if (finished || sending) return;
    const next = { ...answers, [String(item.id)]: label };
    setAnswers(next);
    setAt(at + 1);
    if (at + 1 >= items.length) {
      took.current = Date.now() - (started.current ?? Date.now());
      onDone(next, took.current);
    }
  };
  const labels: string[] = Array.isArray(item.labels) ? item.labels : [];
  return (
    <div className="ep-exercise forge-rafale" aria-busy={sending || undefined}>
      <p className="av2-goal ep-goal" data-goal="goal">{copy.hint_rafale}</p>
      <ol className="forge-rafale__dots" aria-label={fillForge(copy.count_of, { n: Math.min(at + 1, items.length), total: items.length })}>
        {items.map((entry, index) => (
          <li key={String(entry.id)} data-state={index < at ? 'done' : index === at ? 'now' : undefined} />
        ))}
      </ol>
      <div className="forge-rafale__card" key={String(item.id)}>
        <EpPrompt>{String(item.prompt || '')}</EpPrompt>
      </div>
      <EpOpts>
        {labels.map((label) => (
          <EpOpt
            key={label}
            chosen={answers[String(item.id)] === label}
            disabled={finished || sending}
            onClick={() => pick(label)}
            contentLang={language}
          >
            {judgementLabel(label, language, item.label_l10n)}
          </EpOpt>
        ))}
      </EpOpts>
      {finished && !sending && resendLabel && (
        <EpFoot tone="neutral">
          <EpBar tone="go" icon="check" onClick={() => onDone(answers, took.current)}>{resendLabel}</EpBar>
        </EpFoot>
      )}
    </div>
  );
}

export function ForgeRafaleResult({
  rows,
  items = [],
  ms,
  copy,
  cheer,
  coach,
  coachMood,
  onNext,
  nextLabel,
}: {
  rows: BurstRow[];
  items?: Judged[];
  ms?: number | null;
  copy: ForgeCopy;
  cheer?: string | null;
  coach?: Coach | null;
  coachMood?: PortraitMood;
  onNext: () => void;
  nextLabel: string;
}) {
  const language = useControlLanguage();
  const right = rows.filter((row) => row.correct).length;
  const perfect = rows.length > 0 && right === rows.length;
  const seconds = burstSeconds(ms, language);
  const sub = [seconds ? fillForge(copy.rafale_time, { s: seconds }) : null, cheer || null].filter(Boolean).join(' · ');
  return (
    <div className="ep-feedback forge-rafale-result" data-verdict={perfect ? 'correct' : 'wrong'}>
      <ul className="forge-rafale__rows">
        {rows.map((row) => {
          const item = items.find((entry) => String(entry.id) === row.itemId);
          return (
            <li key={row.itemId} data-correct={row.correct ? 'true' : 'false'}>
              <span className="forge-rafale__mark" aria-hidden="true">
                {row.correct ? <CheckIcon size={12} /> : <RepairIcon size={12} />}
              </span>
              <div className="forge-rafale__text">
                <p className="forge-rafale__sentence" lang="fr">{row.sentence}</p>
                {!row.correct && row.expected && (
                  <p className="forge-rafale__was">{judgementLabel(row.expected, language, item?.label_l10n)}</p>
                )}
                {row.correctedFr && <p className="forge-rafale__fix" lang="fr">{row.correctedFr}</p>}
              </div>
            </li>
          );
        })}
      </ul>
      <EpFoot tone={perfect ? 'correct' : 'wrong'}>
        <EpVerdict tone={perfect ? 'go' : 'no'} sub={sub || undefined} coach={coach} coachMood={coachMood}>
          {perfect ? copy.rafale_perfect : fillForge(copy.rafale_score, { correct: right, total: rows.length })}
        </EpVerdict>
        <EpBar icon="check" onClick={onNext}>{nextLabel}</EpBar>
      </EpFoot>
    </div>
  );
}

/* Tokens only; no border, no outline, no stroke. */
export function ForgeDrillStyles() {
  return (
    <style jsx global>{`
.av2 .forge-typed { display: flex; flex-direction: column; gap: 10px; min-width: 0; }
.av2 .forge-typed__input {
  width: 100%;
  min-height: 56px;
  padding: 12px 16px;
  border: 0;
  border-radius: var(--av2-r-card);
  background: var(--av2-card);
  box-shadow: 0 var(--av2-press-sm) 0 var(--av2-line-2);
  color: var(--av2-ink);
  font-family: var(--av2-serif);
  font-style: italic;
  font-size: var(--av2-t-option);
  -webkit-appearance: none;
  appearance: none;
}
.av2 .forge-typed__input::placeholder { color: var(--av2-muted); font-family: var(--av2-sans); font-style: normal; font-size: var(--av2-t-body-lg); }
.av2 .forge-typed[data-verdict='right'] .forge-typed__input { background: var(--av2-tint-correct); box-shadow: none; }
.av2 .forge-typed[data-verdict='wrong'] .forge-typed__input { background: var(--av2-tint-wrong); box-shadow: none; }
.av2 .forge-accents { display: flex; flex-wrap: wrap; gap: 6px; }
.av2 .forge-accent {
  min-width: 34px;
  height: 36px;
  padding: 0 8px;
  border: 0;
  border-radius: 10px;
  background: var(--av2-card);
  box-shadow: 0 2px 0 var(--av2-line-2);
  color: var(--av2-ink);
  font: 600 var(--av2-t-body-lg)/1 var(--av2-sans);
  cursor: pointer;
  touch-action: manipulation;
}
.av2 .forge-accent:active { transform: translateY(2px); box-shadow: none; }

.av2 .forge-listen { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.av2 .forge-listen__play {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-height: 52px;
  padding: 0 20px 0 14px;
  border: 0;
  border-radius: var(--av2-r-pill);
  background: var(--av2-blue);
  box-shadow: 0 var(--av2-press-md) 0 var(--av2-blue-deep);
  color: var(--av2-on-blue);
  font: 700 var(--av2-t-body)/1 var(--av2-sans);
  cursor: pointer;
  touch-action: manipulation;
}
.av2 .forge-listen__play:active { transform: translateY(var(--av2-press-md)); box-shadow: none; }
.av2 .forge-listen__icon { display: inline-flex; width: 26px; height: 26px; align-items: center; justify-content: center; }
.av2 .forge-listen__icon svg { width: 18px; height: 18px; }
.av2 .forge-listen__slow {
  min-height: var(--av2-tap);
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--av2-ink-2);
  font: 600 var(--av2-t-label)/1.2 var(--av2-sans);
  text-decoration: underline;
  text-underline-offset: 3px;
  cursor: pointer;
}
@media (prefers-reduced-motion: no-preference) {
  .av2 .forge-listen[data-playing='true'] .forge-listen__icon { animation: av2-pop 0.6s infinite alternate; }
}

.av2 .forge-spot { display: flex; flex-direction: column; gap: 10px; min-width: 0; }
.av2 .forge-spot__line {
  margin: 0;
  font-family: var(--av2-serif);
  font-style: italic;
  font-size: var(--av2-t-head);
  line-height: 1.5;
  color: var(--av2-ink);
  overflow-wrap: anywhere;
}
.av2 .forge-spot__word {
  display: inline;
  margin: 0;
  padding: 0 3px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: inherit;
  font: inherit;
  line-height: inherit;
  text-decoration: underline;
  text-decoration-color: var(--av2-line-2);
  text-decoration-thickness: 2px;
  text-underline-offset: 6px;
  cursor: pointer;
  touch-action: manipulation;
}
.av2 .forge-spot__word:hover:not(:disabled) { background: var(--av2-card); }
.av2 .forge-spot__word:disabled { cursor: default; text-decoration: none; }
.av2 .forge-spot__word[data-edited='true'] { background: var(--av2-card); text-decoration: none; }
.av2 .forge-spot__was { margin-right: 6px; color: var(--av2-muted); text-decoration-color: var(--av2-red); text-decoration-thickness: 2px; }
.av2 .forge-spot__now { color: var(--av2-blue); }
.av2 .forge-spot__punct { color: var(--av2-ink); }
.av2 .forge-spot__input {
  max-width: 100%;
  padding: 0 6px;
  border: 0;
  border-radius: 8px;
  background: var(--av2-card);
  box-shadow: 0 2px 0 var(--av2-blue);
  color: var(--av2-blue);
  font: inherit;
  line-height: 1.2;
}
.av2 .forge-spot__undo {
  align-self: flex-start;
  min-height: var(--av2-tap);
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--av2-ink-2);
  font: 600 var(--av2-t-label)/1.2 var(--av2-sans);
  text-decoration: underline;
  text-underline-offset: 3px;
  cursor: pointer;
}
.av2 .forge-spot__hint { margin: 0; min-height: var(--av2-tap); display: flex; align-items: center; font-size: var(--av2-t-label); font-weight: 600; color: var(--av2-ink-2); }
@media (max-width: 380px) { .av2 .forge-spot__line { font-size: var(--av2-t-title); } }

.av2 .forge-rafale { display: flex; flex-direction: column; gap: 14px; min-width: 0; }
.av2 .forge-rafale__dots { list-style: none; margin: 0; padding: 0; display: flex; gap: 6px; }
.av2 .forge-rafale__dots li { flex: 1 1 0; height: 6px; border-radius: var(--av2-r-pill); background: var(--av2-line); transition: background-color 0.2s ease; }
.av2 .forge-rafale__dots li[data-state='done'] { background: var(--av2-ink); }
.av2 .forge-rafale__dots li[data-state='now'] { background: var(--av2-red); }
@media (prefers-reduced-motion: no-preference) {
  .av2 .forge-rafale__card { animation: av2-fade 0.2s; }
}
.av2 .forge-rafale__rows { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; }
.av2 .forge-rafale__rows li { display: flex; align-items: flex-start; gap: 10px; padding: 12px 14px; border-radius: var(--av2-r-card); background: var(--av2-card); }
.av2 .forge-rafale__mark {
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  margin-top: 2px;
  border-radius: 999px;
  background: var(--av2-green);
  color: var(--av2-on-green);
}
.av2 .forge-rafale__rows li[data-correct='false'] .forge-rafale__mark { background: var(--av2-red); color: var(--av2-on-red); }
.av2 .forge-rafale__text { min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.av2 .forge-rafale__sentence { margin: 0; font-family: var(--av2-serif); font-style: italic; font-size: var(--av2-t-option); line-height: 1.3; color: var(--av2-ink); overflow-wrap: anywhere; }
.av2 .forge-rafale__was { margin: 0; font-size: var(--av2-t-meta); font-weight: 700; color: var(--av2-muted); }
.av2 .forge-rafale__fix { margin: 0; font-size: var(--av2-t-body); font-weight: 600; color: var(--av2-green); overflow-wrap: anywhere; }
    `}</style>
  );
}
