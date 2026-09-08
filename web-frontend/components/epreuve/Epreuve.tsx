/* Atelier — L'ÉPREUVE · the legacy exercise session, on the Atelier V2 design.
   Presentation only. Every exported component keeps the name and props that
   pages/atelier.tsx (SessionView / RecapModal) and pages/mobile-visual-qa.tsx
   wire behaviour into; the markup underneath is the Séance artboard of
   docs/design-reference/claude/Atelier App.dc.html, built from the primitives
   in components/atelier-v2/ui and the tokens/classes of styles/atelier-v2.css.

   Design mapping (Séance artboard):
     verbatim — round close control, blue progress rule on the line track, the
       red "● n" run on the right (printed only from a real value), the blue
       12px/700 step label, the "■ La règle" pill and the rounded rule card,
       the Garamond-italic 30px prompt with an inline underlined blank, the 56px
       option cards (2px edge, radius 16, 0 3px 0 press, 22px dot;
       selected/correct/wrong colouring), the tinted footer band with its round
       icon badge + Garamond verdict + 13px line, the one 3D-press primary
       (grey face until an option is chosen).
     extended from the primitives — word bank (tiles), classify boxes (tile
       groups), production well, confidence chips, correction cards, relecture
       notices, typed repair, listen/record controls, the early-mastery lock
       (reward surface), the recap, resume/skeleton/notice states, and the
       partial-close confirm on the quiet "Terminer" control.

   Every rule below is written `.av2 .ep-…` (0,2,0): pages/atelier.tsx has a
   `.atelier-page button { border: 0; background: transparent }` reset at
   (0,1,1) that a single class cannot outrank. The recap block doubles its
   selectors with `.ep-recap …` and bridges the tokens on `.ep-recap:not(.av2)`
   because RecapModal (outside this file) mounts its section without an
   AtelierV2Root; see the note above that block. */

import React from 'react';

import {
  AtelierMark,
  AtelierV2Root,
  CheckIcon,
  Chip,
  CrossIcon,
  IconAction,
  MicIcon,
  Notice,
  PendingIcon,
  ProgressRule,
  RepairIcon,
  ShapeToken,
  SpinnerToken,
  StopIcon,
  Surface,
} from '@/components/atelier-v2/ui';
import { pulseAppHaptic } from '@/lib/haptics';

type Node = React.ReactNode;

/* ---------- icons (2.4–3px strokes, currentColor, like the system's own) ---------- */
const ico = (stroke: number, children: React.ReactNode, fill = 'none') => (
  <svg viewBox="0 0 24 24" width="16" height="16" fill={fill} stroke="currentColor" strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">{children}</svg>
);
export const EpIco: Record<string, React.ReactElement> = {
  close: ico(2.6, <path d="M6 6l12 12M18 6L6 18" />),
  ask: ico(2.4, <><path d="M9 9a3 3 0 1 1 4 2.8c-1 .5-1.5 1-1.5 2.2" /><circle cx="11.5" cy="18" r="1.1" fill="currentColor" stroke="none" /></>),
  arrow: ico(2.8, <path d="M4 12h15M13 6l6 6-6 6" />),
  check: ico(3, <path d="M4.5 12.5l5 5 10-11" />),
  play: ico(2.6, <path d="M8 5l11 7-11 7z" />, 'currentColor'),
  mic: ico(2.4, <><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" /></>),
  home: ico(2.4, <path d="M4 11l8-6 8 6v8H4z" />),
  book: ico(2.4, <path d="M4 5h7v14H4zM13 5h7v14h-7z" />),
  pencil: ico(2.4, <><path d="M4 20l1-4L16 5l3 3L8 19z" /><path d="M14 7l3 3" /></>),
  retry: ico(2.6, <path d="M4 11a8 8 0 0 1 14-5l2 2M20 5v4h-4" />),
};

/* ---------- shell ---------- */
/* The session root. `AtelierV2Root` carries the `.av2` scope (tokens, fonts,
   dark mode, the rounded form wells); `av2-screen` gives the design's
   header / body / footer column. */
export function EpShell({ children, style, className = '', as = 'main' }: { children: Node; style?: React.CSSProperties; className?: string; as?: 'div' | 'main' | 'section' | 'article' }) {
  return (
    <AtelierV2Root as={as} className={`ep-shell av2-screen ${className}`.trim()} style={style}>
      {children}
    </AtelierV2Root>
  );
}

/* ---------- progress (the design's blue rule on the line track) ---------- */
export type EpStickGroup = { total: number; set: number; current?: boolean };
export type EpStickLabel = { name: string; state?: string };
export function EpStick({ groups, cap, full, labels }: { groups: EpStickGroup[]; cap?: [string, string | number]; full?: boolean; labels?: EpStickLabel[] }) {
  const total = groups.reduce((sum, g) => sum + Math.max(0, g.total), 0);
  const set = groups.reduce((sum, g) => sum + Math.max(0, Math.min(g.set, g.total)), 0);
  const caption = cap ? [cap[0], cap[1]].filter((part) => part !== '' && part != null).join(' ') : undefined;
  return (
    <div className={'ep-stick' + (full ? ' ep-stick--full' : '')}>
      <ProgressRule value={set} max={total} label="Progression de la séance" caption={caption || undefined} />
      {full && labels && labels.length > 0 && (
        <div className="ep-stick__concepts">
          {labels.map((l, i) => (
            <span key={i} className="av2-byline ep-stick__concept" data-state={l.state || undefined}>
              <ShapeToken kind={l.state === 'done' ? 'done' : 'story'} size="sm" />
              <span className="av2-label">{l.name}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

/* ---------- header ---------- */
/* `partial` means the learner is stopping before the end of the edition. Their
   work is already banked either way, so the control asks once rather than
   refusing: an edition you cannot put down is an edition you stop opening.
   `run` is the session's own count of consecutive correct answers; the red
   "● n" prints only when it is a real, positive number. */
export function EpTopbar({
  groups,
  cap,
  onClose,
  onFinish,
  finishDisabled,
  partial = false,
  run,
}: {
  groups: EpStickGroup[];
  cap?: [string, string | number];
  onClose?: () => void;
  onFinish?: () => void;
  finishDisabled?: boolean;
  partial?: boolean;
  run?: number;
}) {
  const [confirming, setConfirming] = React.useState(false);
  React.useEffect(() => {
    if (!confirming) return;
    const timer = window.setTimeout(() => setConfirming(false), 4000);
    return () => window.clearTimeout(timer);
  }, [confirming]);

  const finish = () => {
    if (partial && !confirming) {
      setConfirming(true);
      return;
    }
    setConfirming(false);
    onFinish?.();
  };

  const runCount = Math.max(0, Math.floor(Number(run) || 0));

  return (
    <header className="av2-session__head ep-top">
      <IconAction label="Fermer la séance" onClick={onClose}>
        <CrossIcon size={16} />
      </IconAction>
      <EpStick groups={groups} cap={cap} />
      {runCount > 0 && (
        <span className="ep-run" role="img" aria-label={`${runCount} ${runCount === 1 ? 'bonne réponse' : 'bonnes réponses'} de suite`}>
          <span className="av2-shape av2-shape--dot ep-run__dot" aria-hidden="true" />
          {runCount}
        </span>
      )}
      <button
        type="button"
        className={'av2-btn av2-btn--quiet av2-btn--inline ep-finish' + (confirming ? ' ep-finish--confirming' : '')}
        onClick={finish}
        disabled={finishDisabled}
        title={partial ? 'Clore l’édition sur ce qui est déjà classé' : 'Clore l’édition'}
      >
        {confirming ? 'Clore ici ?' : 'Terminer'}
      </button>
    </header>
  );
}

/* ---------- step label ---------- */
export function EpEyebrow({ round, mode, i, n, retour }: { round: string; mode?: string; i: number | string; n: number | string; retour?: boolean }) {
  return (
    <div className="ep-eyebrow">
      <p className="av2-label av2-label--story ep-eyebrow__step">
        {round}{mode ? ` · ${mode}` : ''} · {i}/{n}
      </p>
      {retour && (
        <span className="av2-chip av2-chip--quiet ep-retour">
          <ShapeToken kind="story" size="sm" />
          <span>Retour · déjà corrigé</span>
        </span>
      )}
    </div>
  );
}

export function EpProvenance({ children }: { children: Node }) {
  return (
    <div className="ep-prov">
      <Notice tone="quiet" shape="story">
        <p>{children}</p>
      </Notice>
    </div>
  );
}

/* Concept row: the motif, the concept name, and the design's "■ La règle" pill
   (yellow square = reward) that discloses the rule card. */
export function EpConcept({ title, motif, askOn, onAsk }: { title: Node; motif?: Node; askOn?: boolean; onAsk?: () => void }) {
  return (
    <div className="ep-concept">
      {motif}
      <p className="ep-concept__title" lang="fr">{title}</p>
      <Chip
        className="ep-concept__ask"
        icon={<ShapeToken kind="reward" size="sm" />}
        aria-pressed={Boolean(askOn)}
        aria-expanded={Boolean(askOn)}
        onClick={onAsk || (() => undefined)}
      >
        La règle
      </Chip>
    </div>
  );
}

/* ---------- assembling motif ---------- */
export type MotifPrim = { shape: 'circle' | 'square' | 'triangle' | 'block'; cx: number; cy: number; s: number; printed?: boolean; printing?: boolean; role?: string };
function epShape(p: MotifPrim, key: number) {
  const cls = 'shp ' + ({ circle: 'c-circle', square: 'c-square', triangle: 'c-tri', block: 'c-block' }[p.shape]);
  if (p.shape === 'circle') return <circle key={key} className={cls} cx={p.cx} cy={p.cy} r={p.s / 2} />;
  if (p.shape === 'triangle') {
    const half = p.s / 2;
    const pts = `${p.cx},${p.cy - half} ${p.cx + half},${p.cy + half} ${p.cx - half},${p.cy + half}`;
    return <polygon key={key} className={cls} points={pts} />;
  }
  return <rect key={key} className={cls} x={p.cx - p.s / 2} y={p.cy - p.s / 2} width={p.s} height={p.s} rx={p.s / 6} />;
}
export function EpMotif({ prims = [], done, canvas = 46 }: { prims?: MotifPrim[]; done?: boolean; canvas?: number }) {
  return (
    <div className={'ep-motif' + (done ? ' ep-motif--done' : '')} aria-hidden="true">
      <svg viewBox={`0 0 ${canvas} ${canvas}`}>
        {prims.map((p, i) => (
          <g key={i} className={'prim' + (p.printed ? '' : ' ghost') + (p.printing ? ' print-in' : '')}>
            {epShape(p, i)}
          </g>
        ))}
      </svg>
    </div>
  );
}

/* ---------- rule card ---------- */
/* The design's disclosed card: Garamond-italic title, 13px muted body, blue
   Garamond example. The lede is usually the page's ConceptRulePanel, whose
   own markup is restyled under `.ep-rule` below. The pill toggles the card,
   so the card carries no close control of its own. */
export function EpRule({ lede, examples = [] }: { kicker?: string; lede?: Node; examples?: Node[]; onClose?: () => void }) {
  return (
    <Surface className="ep-rule" role="region" aria-label="La règle">
      <div className="ep-rule__body">{lede}</div>
      {examples.length > 0 && (
        <div className="ep-rule__anchor">
          {examples.map((e, i) => <p className="ep-rule__ex" key={i}>{e}</p>)}
        </div>
      )}
    </Surface>
  );
}

/* ---------- prompt + cue ---------- */
/* The one Garamond-italic headline of the screen; the cue (instruction or
   meaning) is the 15px body under it. A block child (the word-bank line) is
   legal because this is a div, not an h-element. */
export function EpPrompt({ children, cue }: { children: Node; cue?: Node }) {
  return (
    <div className="ep-prompt">
      <div className="av2-headline ep-line" lang="fr">{children}</div>
      {cue && <p className="av2-body av2-body--lg ep-cue">{cue}</p>}
    </div>
  );
}
export function Blank({ children, set }: { children?: Node; set?: boolean }) {
  return <span className="ep-blank" data-set={set ? 'true' : undefined}>{children || ' '}</span>;
}

/* ---------- recognize / fill: the design's option cards ---------- */
export function EpOpts({ children }: { children: Node }) {
  return <div className="av2-choices ep-opts" role="group" aria-label="Choix">{children}</div>;
}
export function EpOpt({ chosen, right, wrong, children, onClick, disabled }: { chosen?: boolean; right?: boolean; wrong?: boolean; children: Node; onClick?: () => void; disabled?: boolean }) {
  const state = right ? 'correct' : wrong ? 'wrong' : chosen ? 'selected' : 'idle';
  const word = right ? 'juste' : wrong ? 'faux' : chosen ? 'choisi' : null;
  return (
    <button
      type="button"
      className="av2-choice ep-opt"
      data-state={state}
      aria-pressed={Boolean(chosen)}
      onClick={onClick}
      disabled={disabled}
    >
      <span lang="fr">{children}</span>
      <span className="av2-choice__dot" aria-hidden="true">
        {right ? <CheckIcon size={13} /> : null}
        {wrong ? <RepairIcon size={13} /> : null}
      </span>
      {word && <span className="av2-sr"> · {word}</span>}
    </button>
  );
}
export function EpChoices({ children }: { children: Node }) { return <div className="av2-help__actions ep-choices">{children}</div>; }

/* ---------- movable type (word bank) → the system's word tiles ---------- */
export function EpSlug({ children, spent, set, onClick, disabled }: { children: Node; spent?: boolean; set?: boolean; onClick?: () => void; disabled?: boolean }) {
  return (
    <button
      type="button"
      className="av2-tile ep-slug"
      lang="fr"
      data-state={set ? 'placed' : undefined}
      data-spent={spent ? 'true' : undefined}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
      {spent && <span className="av2-sr"> · déjà placé</span>}
    </button>
  );
}
export function EpSetLine({ empty, children }: { empty?: boolean; children?: Node }) {
  return (
    <div className="av2-tiles__line ep-setline" data-empty={empty ? 'true' : undefined} aria-live="polite" aria-label="La ligne composée">
      {empty && <span className="ep-setline__hint">Réglez la ligne ici</span>}
      {children}
    </div>
  );
}
export function EpCase({ label, count, children }: { label: Node; count?: number | null; children?: Node }) {
  return (
    <div className="ep-case">
      <div className="ep-case__cap">
        <span className="av2-label">{label}</span>
        {count != null && <span className="av2-label">{count} sortes</span>}
      </div>
      <div className="av2-tiles__bank">{children}</div>
    </div>
  );
}
/* Classify: each label is a tile-group surface holding its "Placer ici" card. */
export function EpCases({ boxes }: { boxes: { label: Node; slugs: Node[] }[] }) {
  return (
    <div className="ep-cases" role="group" aria-label="Classer">
      {boxes.map((b, i) => (
        <div className="av2-surface av2-surface--tile ep-casebox" key={i}>
          <p className="av2-label ep-casebox__label" lang="fr">{b.label}</p>
          <div className="ep-casebox__body">{b.slugs.map((s, j) => <React.Fragment key={j}>{s}</React.Fragment>)}</div>
        </div>
      ))}
    </div>
  );
}

/* ---------- produce (display well; the page's textarea carries the input) ---------- */
export function EpProduce({ typed, placeholder, caret = true }: { typed?: Node; placeholder?: Node; caret?: boolean }) {
  return (
    <div className="ep-produce">
      <div className="ep-field" lang="fr">
        {typed ? <span>{typed}</span> : <span className="ep-field__ph">{placeholder}</span>}
        {caret && <span className="ep-field__caret" aria-hidden="true"></span>}
      </div>
    </div>
  );
}

/* ---------- confidence tap ---------- */
export function EpConfidence({ value, onPick }: { value?: 'sure' | 'unsure' | null; onPick?: (v: 'sure' | 'unsure') => void }) {
  return (
    <div className="ep-conf" role="group" aria-label="Votre confiance">
      <span className="av2-label">Vous êtes…</span>
      <Chip tone={value === 'sure' ? 'story' : 'plain'} aria-pressed={value === 'sure'} onClick={() => onPick?.('sure')}>sûr·e</Chip>
      <Chip tone={value === 'unsure' ? 'story' : 'plain'} aria-pressed={value === 'unsure'} onClick={() => onPick?.('unsure')}>pas sûr·e</Chip>
    </div>
  );
}

/* ---------- verdict band + the one primary ---------- */
/* The footer's feedback band: round icon badge, Garamond verdict, 13px line.
   `tone` keeps its legacy values: "go" = correct, anything else = wrong. */
export function EpVerdict({ tone = 'go', children, sub }: { tone?: string; children: Node; sub?: Node }) {
  const correct = tone === 'go';
  return (
    <div className="av2-feedback ep-verdict" data-tone={correct ? 'correct' : 'wrong'} role="status" aria-live="polite">
      <span className="av2-feedback__icon" aria-hidden="true">
        {correct ? <CheckIcon size={15} /> : <RepairIcon size={15} />}
      </span>
      <div className="ep-verdict__text">
        <p className="av2-feedback__title">{children}</p>
        {sub && <p className="av2-feedback__sub">{sub}</p>}
      </div>
    </div>
  );
}
/* The 3D press. `tone="ghost"` is the secondary (paper face); everything else
   is the red primary. The face dims while disabled; the label never does. */
export function EpBar({ children, tone, disabled, icon, onClick, pending }: { children: Node; tone?: string; disabled?: boolean; icon?: string | null; onClick?: () => void; pending?: boolean }) {
  return (
    <button
      type="button"
      className={'av2-btn ep-bar ' + (tone === 'ghost' ? 'av2-btn--secondary' : 'av2-btn--primary')}
      disabled={disabled || pending}
      aria-busy={pending || undefined}
      data-pending={pending ? 'true' : undefined}
      data-icon={icon || undefined}
      onClick={onClick}
    >
      {pending && <SpinnerToken />}
      <span>{children}</span>
    </button>
  );
}
/* The tinted footer band: mint when correct, blush when wrong, paper otherwise. */
export function EpFoot({ children, tone }: { children: Node; tone?: 'correct' | 'wrong' | 'neutral' }) {
  return <div className="av2-screen__foot ep-foot" data-tone={tone || undefined}>{children}</div>;
}

/* ---------- corrections ---------- */
export function EpFix({ old, fix }: { old: Node; fix: Node }) {
  return (
    <span className="ep-fix">
      <span className="av2-correction__span" lang="fr">{old}</span>
      {' '}<span aria-hidden="true">→</span>{' '}
      <span className="av2-correction__fix" lang="fr">{fix}</span>
    </span>
  );
}
export function EpIns({ fix }: { fix: Node }) {
  return (
    <span className="ep-ins">
      <span className="ep-ins__mark" aria-hidden="true">+</span>{' '}
      <span className="av2-correction__fix" lang="fr">{fix}</span>
      <span className="av2-sr"> (à ajouter)</span>
    </span>
  );
}
/* label-vs-label correction (classify): two stacked lines, because the chosen
   and correct category names run too long to sit on one. */
export function EpLabelFix({ old, fix }: { old: Node; fix: Node }) {
  return (
    <div className="ep-labelfix">
      <p><span className="av2-label ep-labelfix__k">Classé</span><span className="av2-correction__span" lang="fr">{old}</span></p>
      <p><span className="av2-label ep-labelfix__k">Correct</span><span className="av2-correction__fix" lang="fr">{fix}</span></p>
    </div>
  );
}
/* full-line rewrite: the learner's line struck through, the corrected line
   beneath — both WRAP within the column. */
export function EpLineFix({ old, fix }: { old: Node; fix: Node }) {
  return (
    <div className="ep-linefix">
      {old ? <p className="av2-correction__span" lang="fr">{old}</p> : null}
      <p className="av2-correction__fix ep-linefix__new" lang="fr">{fix}</p>
    </div>
  );
}
/* `repair` is the corrector's concrete next action (repair_hint); it sits
   under the why, quieter than it, with the red triangle = action. */
export function EpGalley({ anchor, children, why, repair, relecture }: { anchor?: Node; children: Node; why?: Node; repair?: Node; relecture?: Node }) {
  return (
    <div className="av2-correction ep-galley">
      {anchor && <p className="av2-label ep-galley__anchor">{anchor}</p>}
      <div className="ep-gline">{children}</div>
      {why && <p className="ep-why">{why}</p>}
      {repair && (
        <p className="ep-repair-hint">
          <ShapeToken kind="action" size="sm" />
          <span>{repair}</span>
        </p>
      )}
      {relecture}
    </div>
  );
}
/* The second look. `failed` is a real state: the endpoint to ask again exists,
   so the note must resolve into a retry rather than hang. */
export function EpRelecture({ status = 'pending', children, onRetry, retrying }: {
  status?: 'pending' | 'done' | 'failed';
  children?: Node;
  onRetry?: () => void;
  retrying?: boolean;
}) {
  if (status === 'pending') {
    return (
      <div className="ep-relecture" data-status="pending">
        <Notice tone="quiet" shape="story">
          <p className="ep-relecture__line"><PendingIcon size={14} /> Relecture en cours…</p>
        </Notice>
      </div>
    );
  }
  if (status === 'failed') {
    return (
      <div className="ep-relecture" data-status="failed">
        <Notice tone="alert" live="alert" shape="action">
          <p>Relecture interrompue.</p>
          {onRetry && (
            <button type="button" className="av2-btn av2-btn--secondary av2-btn--inline ep-relecture__again" onClick={onRetry} disabled={retrying} aria-busy={retrying || undefined}>
              {retrying ? 'Relance…' : 'Relancer'}
            </button>
          )}
        </Notice>
      </div>
    );
  }
  return (
    <div className="ep-relecture" data-status="done">
      <Notice tone="quiet" shape="done">
        <p>{children}</p>
      </Notice>
    </div>
  );
}

/* ---------- the correct moment ---------- */
export function EpBonStamp({ struck }: { struck?: boolean }) {
  return (
    <span className="av2-byline ep-bon-stamp" data-struck={struck ? 'true' : undefined}>
      <ShapeToken kind="done" size="sm" />
      <span className="av2-label">Bon à tirer</span>
    </span>
  );
}
export function EpCorrect({ said, struck }: { said: Node; struck?: boolean }) {
  return (
    <div className="av2-correction ep-correct">
      <EpBonStamp struck={struck} />
      <p className="av2-fr ep-correct__said" lang="fr">{said}</p>
    </div>
  );
}

/* ---------- typed micro-repair ---------- */
export function EpRepair({
  target,
  typed = '',
  status,
  errFrom,
  onChange,
  onSubmit,
  submitting,
  disabled,
}: {
  target: string;
  typed?: string;
  status?: 'ok' | 'no' | null;
  errFrom?: number | null;
  onChange?: (value: string) => void;
  onSubmit?: () => void;
  submitting?: boolean;
  disabled?: boolean;
}) {
  const ghost = target.slice(typed.length);
  const okChars = errFrom == null ? typed.length : errFrom;
  const good = typed.slice(0, okChars);
  const bad = errFrom == null ? '' : typed.slice(errFrom);
  const inputId = React.useId();
  return (
    <Surface className="ep-repair" data-status={status || undefined}>
      <label className="av2-field">
        <span className="av2-field__label">Recopie la correction</span>
        {onChange ? (
          <input
            id={inputId}
            className="av2-field__control ep-repair__input"
            lang="fr"
            value={typed}
            onChange={(event) => onChange(event.target.value)}
            // The correction is already visible in the card above; the
            // placeholder is a generic prompt, not the answer itself, so
            // retyping stays a real recall exercise instead of copying.
            placeholder="Tapez la ligne corrigée…"
            disabled={disabled || status === 'ok'}
            aria-invalid={status === 'no' || undefined}
            autoCapitalize="sentences"
            autoCorrect="off"
            autoComplete="off"
            spellCheck={false}
          />
        ) : (
          <span className="av2-field__control ep-repair__ghostline" lang="fr">
            <span>{good}</span>
            {bad && <span className="ep-repair__err">{bad}</span>}
            {status !== 'ok' && <span className="ep-field__caret" aria-hidden="true"></span>}
            <span className="ep-repair__ghost">{ghost}</span>
          </span>
        )}
      </label>
      {onSubmit && status !== 'ok' && (
        <button
          type="button"
          className="av2-btn av2-btn--secondary av2-btn--inline ep-repair__submit"
          onClick={onSubmit}
          disabled={disabled || submitting || !typed.trim()}
          aria-busy={submitting || undefined}
        >
          {submitting ? 'Comparaison…' : 'Comparer la ligne'}
        </button>
      )}
      {status === 'ok' && (
        <Notice tone="quiet" shape="done">
          <p>Ligne recomposée · juste.</p>
        </Notice>
      )}
      {status === 'no' && (
        <Notice tone="alert" live="alert" shape="action">
          <p>La lettre diffère · reprenez la ligne.</p>
        </Notice>
      )}
    </Surface>
  );
}

/* ---------- écouter + shadowing ---------- */
export function EpListen({ fr, disabled, playing, onPlay }: { fr: Node; disabled?: boolean; playing?: boolean; onPlay?: () => void }) {
  const label = disabled ? 'Voix indisponible' : playing ? 'Lecture…' : 'Écouter le modèle';
  return (
    <div className="ep-listen" data-disabled={disabled ? 'true' : undefined} data-playing={playing ? 'true' : undefined}>
      <IconAction label={label} pressable onClick={onPlay} disabled={disabled} pending={playing}>
        {playing ? <SpinnerToken /> : EpIco.play}
      </IconAction>
      <div className="ep-listen__text">
        <p className="av2-label">{label}</p>
        <p className="av2-fr ep-listen__fr" lang="fr">{fr}</p>
      </div>
    </div>
  );
}
export function EpRecord({ status = 'idle', onToggle, disabled }: { status?: 'idle' | 'recording' | 'transcribing'; onToggle?: () => void; disabled?: boolean }) {
  const st = ({ idle: 'Appuyez pour répéter', recording: 'Enregistrement… appuyez pour arrêter', transcribing: 'Transcription…' } as Record<string, string>)[status];
  return (
    <div className="ep-record" data-status={status}>
      <IconAction
        label={status === 'recording' ? 'Arrêter l’enregistrement' : 'Enregistrer'}
        tone={status === 'recording' ? 'recording' : 'action'}
        pressable
        pending={status === 'transcribing'}
        onClick={onToggle}
        disabled={disabled}
      >
        {status === 'recording' ? <StopIcon size={18} /> : <MicIcon size={18} />}
      </IconAction>
      <p className="av2-label ep-record__st" role="status" aria-live="polite">{st}</p>
    </div>
  );
}

/* ---------- early mastery lock ---------- */
/* `retired` is how many drills the lock actually removed from the edition. The
   copy must not promise a closed concept when only one rung was retired.
   Yellow = reward: mastery ahead of schedule is the day's reward moment. */
export function EpLock({ motif, title, retired = 0 }: { motif?: Node; title: Node; retired?: number }) {
  const count = Math.max(0, Math.round(retired));
  return (
    <Surface tone="reward" shape="hero" className="ep-lock" role="status">
      <p className="av2-label ep-lock__k">Maîtrise anticipée</p>
      {motif && <div className="ep-lock__plate">{motif}</div>}
      <h2 className="av2-headline av2-headline--title ep-lock__title" lang="fr">{title}</h2>
      <p className="av2-body av2-body--lg ep-lock__p">
        {count > 0
          ? `Tout était propre — ${count} exercice${count === 1 ? '' : 's'} retiré${count === 1 ? '' : 's'} de l’édition du jour.`
          : 'Tout était propre — cette épreuve se ferme en avance.'}
      </p>
      <span className="av2-byline ep-lock__promo">
        <ShapeToken kind="done" size="sm" />
        <span className="av2-label">Classé sans faute</span>
      </span>
    </Surface>
  );
}

/* ---------- completion stamp ---------- */
export function EpBatStage({ sub }: { sub?: Node }) {
  React.useEffect(() => {
    pulseAppHaptic('complete');
  }, []);

  return (
    <div className="ep-bat-stage">
      <Surface shape="hero" className="ep-bat">
        <AtelierMark size={34} title="Atelier" />
        <p className="av2-label ep-bat__d">Édition prête</p>
        <h2 className="av2-headline av2-headline--screen ep-bat__m">Bon à tirer</h2>
        {sub && <p className="av2-body av2-body--lg ep-bat__sub">{sub}</p>}
      </Surface>
    </div>
  );
}

/* ---------- recap · l'épreuve ---------- */
export function EpRecapHead({ date }: { date: Node }) {
  return (
    <div className="ep-recap-head">
      <p className="av2-label ep-recap-head__folio">Atelier · La séance · L’épreuve</p>
      {/* The recap is a dialog over the séance, so its title is the dialog's
          heading; the screen's own `h1` belongs to the séance (WP-20 D-11). */}
      <h2 className="av2-headline av2-headline--display ep-recap-head__title">L’épreuve</h2>
      <p className="av2-label ep-recap-head__date">{date}</p>
    </div>
  );
}
export function EpTally({ items }: { items: { n: Node; l: Node }[] }) {
  return (
    <div className="ep-tally">
      {items.map((it, i) => (
        <div className="av2-surface av2-surface--tile ep-tally__t" key={i}>
          <p className="ep-tally__n">{it.n}</p>
          <p className="av2-label ep-tally__l">{it.l}</p>
        </div>
      ))}
    </div>
  );
}
export function EpProof({ lines }: { lines: { fr: Node; tag: Node; re?: boolean }[] }) {
  return (
    <ul className="ep-proof">
      {lines.map((l, i) => (
        <li className="ep-proof__pl" key={i} data-re={l.re ? 'true' : undefined}>
          <ShapeToken kind={l.re ? 'action' : 'done'} size="sm" title={l.re ? 'Corrigé' : 'Juste'} />
          <span className="av2-fr ep-proof__fr" lang="fr">{l.fr}</span>
          <span className="av2-label ep-proof__tag">{l.tag}</span>
        </li>
      ))}
    </ul>
  );
}
export function EpPhrase({ quote, by }: { quote: Node; by: Node }) {
  return (
    <Surface tone="blue" className="ep-phrase">
      <p className="av2-label ep-phrase__flag">À paraître demain</p>
      <p className="av2-headline av2-headline--title ep-phrase__q" lang="fr">« {quote} »</p>
      <p className="av2-label ep-phrase__by">{by}</p>
    </Surface>
  );
}
export function EpToken() {
  return (
    <span className="av2-surface av2-surface--tile ep-token" aria-hidden="true">
      <ShapeToken kind="story" size="sm" />
      <ShapeToken kind="reward" size="sm" />
      <ShapeToken kind="action" size="sm" />
    </span>
  );
}
export function EpMint({ note, tokens = 2 }: { note?: Node; tokens?: number }) {
  return (
    <div className="ep-mint">
      <div className="ep-mint__tx">
        <p className="av2-label ep-mint__b">Jetons frappés</p>
        {note && <p className="av2-body ep-mint__note">{note}</p>}
      </div>
      <div className="ep-mint__tokens">{Array.from({ length: tokens }).map((_, i) => <EpToken key={i} />)}</div>
    </div>
  );
}
/* The seal: the Atelier mark on a round medallion — yellow (reward) when gilt. */
export function EpSeal({ gilt, label = 'Atelier · Bon à tirer', stamp }: { gilt?: boolean; label?: string; stamp?: boolean }) {
  return (
    <div className="ep-seal" data-gilt={gilt ? 'true' : undefined} data-stamp={stamp ? 'true' : undefined} role="img" aria-label={gilt ? `${label} · doré` : label}>
      <span className="ep-seal__med">
        <AtelierMark size={44} />
      </span>
    </div>
  );
}
/* The arrow is a claim that the count moved. A second edition filed on a day
   already counted leaves the streak where it was, and "1 → 1" reads as a bug;
   show the standing figure alone instead. */
export function EpStreak({ was, now, rules = 5, on = 4 }: { was: Node; now: Node; rules?: number; on?: number }) {
  const advanced = was !== now;
  return (
    <Surface className="ep-streak" role="status">
      <div className="ep-streak__row">
        {advanced && <span className="ep-streak__n ep-streak__n--was">{was}</span>}
        {advanced && <span className="ep-streak__arw" aria-hidden="true">{EpIco.arrow}</span>}
        <span className="ep-streak__n">{now}</span>
        <span className="av2-body ep-streak__l"><b>{now} {now === 1 ? 'jour' : 'jours'}</b> de suite — l’édition ne rate pas.</span>
      </div>
      <span className="ep-streak__rules" aria-hidden="true">
        {Array.from({ length: rules }).map((_, i) => <i key={i} data-on={i < on ? 'true' : undefined}></i>)}
      </span>
    </Surface>
  );
}
/* `label` is the whole call to action ("Réviser maintenant", "Ouvrir la
   mission"); with none, the single way out is home. */
export function EpHandoff({ label, onRead, onHome }: { label?: Node; onRead?: () => void; onHome?: () => void }) {
  return (
    <div className="ep-handoff">
      {label ? (
        <button type="button" className="av2-btn av2-btn--primary" onClick={onRead}>
          <span>{label}</span>
        </button>
      ) : null}
      <button type="button" className="av2-btn av2-btn--secondary" onClick={onHome}>
        <span>Revenir à La Une</span>
      </button>
    </div>
  );
}

/* ---------- system states ---------- */
export function EpResume({ groups, cap, onResume }: { groups: EpStickGroup[]; cap?: [string, string | number]; onResume?: () => void }) {
  return (
    <Surface shape="hero" className="ep-resume" role="status">
      <p className="av2-label av2-label--story">Séance en cours</p>
      <h2 className="av2-headline av2-headline--title">La ligne était à moitié réglée.</h2>
      <p className="av2-body av2-body--lg">Reprenez là où le plomb attend.</p>
      <div className="ep-resume__stick"><EpStick groups={groups} cap={cap} /></div>
      <button type="button" className="av2-btn av2-btn--primary" onClick={onResume}>
        <span>Reprendre la composition</span>
      </button>
    </Surface>
  );
}
export function EpSkeleton() {
  return (
    <div className="ep-skel" role="status" aria-busy="true">
      <div className="av2-skeleton" style={{ width: '38%', height: 14 }} aria-hidden="true"></div>
      <div className="av2-skeleton" style={{ width: '72%', height: 34 }} aria-hidden="true"></div>
      <div className="av2-skeleton" style={{ height: 56 }} aria-hidden="true"></div>
      <div className="av2-skeleton" style={{ height: 56 }} aria-hidden="true"></div>
      <div className="av2-skeleton" style={{ height: 56 }} aria-hidden="true"></div>
      <p className="av2-label ep-skel__press">On compose la séance…</p>
    </div>
  );
}
export function EpNotice({ msg = 'La séance n’a pas pu être composée. Le texte est sauvegardé ; la rédaction réessaie.', onRetry }: { msg?: Node; onRetry?: () => void }) {
  return (
    <div className="ep-notice">
      <Notice tone="alert" live="alert" shape="action">
        <p className="av2-label">Avis de la rédaction</p>
        <p>{msg}</p>
        {onRetry && (
          <button type="button" className="av2-btn av2-btn--secondary av2-btn--inline" onClick={onRetry}>
            {EpIco.retry}<span>Réessayer</span>
          </button>
        )}
      </Notice>
    </div>
  );
}

export function LEpreuveStyles() {
  return (
    <style jsx global>{`
/* ============================================================
   SHELL — header · body · sticky tinted footer. The phone bottom
   navigation is the app shell's; the footer sits above it.
   ============================================================ */
.av2.ep-shell {
  width: 100%;
  max-width: 720px;
  margin: 0 auto;
  min-height: var(--app-viewport-height, 100vh);
  padding: 0 0 calc(16px + var(--phone-bottom-nav-space, 0px));
}
.av2 .ep-body {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding-top: 20px;
  padding-bottom: 0;
  gap: 0;
}
.av2 .ep-sheet {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}
.av2 .ep-sheet > :last-child { flex: 1 1 auto; display: flex; flex-direction: column; }
.av2 .ep-frame { display: flex; flex-direction: column; gap: 16px; min-width: 0; }
.av2 .ep-exercise { display: flex; flex-direction: column; gap: 16px; min-width: 0; }

/* ============================================================
   HEADER — close · blue rule · red run · quiet Terminer
   ============================================================ */
.av2 .ep-top { padding-top: calc(12px + env(safe-area-inset-top, 0px)); gap: 12px; }
.av2 .ep-top .ep-stick { flex: 1 1 auto; min-width: 0; }
.av2 .ep-stick__concepts { display: flex; flex-wrap: wrap; gap: 6px 14px; margin-top: 8px; }
.av2 .ep-stick__concept[data-state='done'] .av2-label { color: var(--av2-ink); }
.av2 .ep-run {
  flex: none;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 0.875rem; /* design 14px */
  font-weight: 700;
  color: var(--av2-red);
  font-variant-numeric: tabular-nums;
}
.av2 .ep-run__dot { width: 12px; height: 12px; color: var(--av2-red); }
.av2 .ep-finish { flex: none; padding-left: 8px; padding-right: 8px; white-space: nowrap; }
.av2 .ep-finish--confirming { color: var(--av2-red); font-weight: 700; }
.av2 .ep-finish:disabled { text-decoration: none; }

/* ============================================================
   STEP LABEL · CONCEPT ROW · RULE CARD
   ============================================================ */
.av2 .ep-eyebrow { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; min-width: 0; }
.av2 .ep-eyebrow__step { font-variant-numeric: tabular-nums; }
.av2 .ep-retour { min-height: 0; padding: 0; }
.av2 .ep-prov .av2-notice p { font-family: var(--av2-serif); font-style: italic; font-size: var(--av2-t-body); }
.av2 .ep-prov .av2-notice b { font-style: normal; font-weight: 700; }

.av2 .ep-concept { display: flex; align-items: center; gap: 10px; min-width: 0; }
.av2 .ep-concept__title {
  flex: 1 1 auto;
  min-width: 0;
  margin: 0;
  font-size: var(--av2-t-label);
  font-weight: 600;
  line-height: 1.3;
  color: var(--av2-ink-2);
  overflow-wrap: anywhere;
}
.av2 .ep-concept__ask { flex: none; min-height: var(--av2-tap); font-size: var(--av2-t-meta); font-weight: 600; }
.av2 .ep-concept__ask[aria-pressed='true'] { background: var(--av2-line); }

/* the assembling motif: the four shapes in their semantic colours */
.av2 .ep-motif { position: relative; width: 32px; height: 32px; flex: none; }
.av2 .ep-lock__plate .ep-motif { width: 56px; height: 56px; margin: 6px 0 2px; }
.av2 .ep-motif svg { position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible; }
.av2 .ep-motif .prim { transition: opacity 0.5s ease, transform 0.5s ease; transform-origin: 50% 50%; }
.av2 .ep-motif .prim .shp { stroke: none; }
.av2 .ep-motif .prim .c-circle { fill: var(--av2-blue); }
.av2 .ep-motif .prim .c-square { fill: var(--av2-yellow); }
.av2 .ep-motif .prim .c-tri { fill: var(--av2-red); }
.av2 .ep-motif .prim .c-block { fill: var(--av2-ink); }
.av2 .ep-motif .prim.ghost .shp { fill: var(--av2-line-2); }
.av2 .ep-motif .prim.ghost { opacity: 0.8; }
@media (prefers-reduced-motion: no-preference) {
  .av2 .ep-motif .prim.print-in { animation: ep-print 0.5s ease both; }
  .av2 .ep-motif--done { animation: ep-motif-settle 180ms ease-out both; }
}
@keyframes ep-print { from { opacity: 0; transform: scale(0.94); } to { opacity: 1; transform: scale(1); } }
@keyframes ep-motif-settle { 0% { transform: scale(0.9); opacity: 0.55; } 65% { transform: scale(1.06); opacity: 1; } 100% { transform: scale(1); opacity: 1; } }

/* the rule card, and the page's ConceptRulePanel markup inside it */
.av2 .ep-rule { padding: 14px 16px; animation: av2-fade 0.2s; }
.av2 .ep-rule .rule-panel { border: 0; padding: 0; background: transparent; }
.av2 .ep-rule .between { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.av2 .ep-rule .t-mono {
  font-family: inherit;
  font-size: var(--av2-t-meta);
  font-weight: 700;
  letter-spacing: normal;
  text-transform: none;
  color: var(--av2-blue);
}
.av2 .ep-rule .notebook-link {
  margin: 0;
  font-family: inherit;
  font-size: var(--av2-t-label);
  font-weight: 600;
  letter-spacing: normal;
  text-transform: none;
  color: var(--av2-ink-2);
  text-decoration: underline;
  text-underline-offset: 3px;
  min-height: var(--av2-tap);
  display: inline-flex;
  align-items: center;
}
.av2 .ep-rule .rule-panel p {
  margin: 6px 0 0;
  font-size: var(--av2-t-label);
  line-height: 1.45;
  color: var(--av2-ink-2);
  font-weight: 400;
}
.av2 .ep-rule .rule-panel > p:first-of-type {
  margin-top: 8px;
  font-family: var(--av2-serif);
  font-style: italic;
  font-weight: 500;
  font-size: var(--av2-t-rule);
  line-height: 1.15;
  color: var(--av2-ink);
}
.av2 .ep-rule .rule-panel p strong { font-weight: 700; color: var(--av2-ink); }
.av2 .ep-rule .examples { margin-top: 8px; padding: 0; border: 0; }
.av2 .ep-rule .examples p,
.av2 .ep-rule .ep-rule__ex {
  margin: 4px 0 0;
  font-family: var(--av2-serif);
  font-style: italic;
  font-size: var(--av2-t-body);
  line-height: 1.35;
  color: var(--av2-blue);
}
.av2 .ep-rule .rule-bridge {
  margin: 10px 0 0;
  padding: 0;
  border: 0;
  font-size: var(--av2-t-label);
  font-weight: 500;
  color: var(--av2-ink-2);
}
.av2 .ep-rule__body .ep-rule__lede { font-family: var(--av2-serif); font-style: italic; font-size: var(--av2-t-rule); }
.av2 .ep-rule__anchor { margin-top: 8px; }

/* ============================================================
   PROMPT — the one Garamond headline, with the inline blank
   ============================================================ */
.av2 .ep-prompt { display: flex; flex-direction: column; gap: 10px; min-width: 0; }
.av2 .ep-line { margin: 0; }
.av2 .ep-cue { margin: 0; }
.av2 .ep-cue b { font-weight: 700; color: var(--av2-ink); }
.av2 .ep-blank {
  display: inline-block;
  min-width: 5em;
  margin: 0 0.2em;
  border-bottom: 2.5px solid var(--av2-ink);
  vertical-align: baseline;
  text-align: center;
  color: var(--av2-blue);
  font-style: italic;
  line-height: 1;
}
.av2 .ep-blank[data-set='true'] { color: var(--av2-blue); }

/* option cards: everything is the system's .av2-choice */
.av2 .ep-opts { margin-top: 4px; }
.av2 .ep-choices { min-width: 0; }

/* ============================================================
   WORD BANK · CLASSIFY
   ============================================================ */
.av2 .ep-setline { min-height: max(var(--av2-tap), 3.5rem); }
.av2 .ep-setline__hint { color: var(--av2-muted); }
.av2 .ep-setline .ep-slug { min-height: 36px; padding: 0.25rem 0.75rem; }
.av2 .ep-typecase { display: flex; flex-wrap: wrap; gap: 8px; min-width: 0; }
.av2 .ep-slug[data-spent='true'] {
  background: var(--av2-line);
  border-color: transparent;
  box-shadow: none;
  color: var(--av2-ink-2);
  text-decoration: line-through;
  text-decoration-thickness: 2px;
}
.av2 .ep-case { display: flex; flex-direction: column; gap: 8px; }
.av2 .ep-case__cap { display: flex; justify-content: space-between; gap: 8px; }
.av2 .ep-cases { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; min-width: 0; }
.av2 .ep-casebox { display: flex; flex-direction: column; gap: 10px; }
.av2 .ep-casebox__label { color: var(--av2-ink); }
.av2 .ep-casebox__body { display: flex; flex-direction: column; gap: 8px; }
.av2 .ep-casebox .av2-choice { font-size: var(--av2-t-body); padding: 0.5rem 0.875rem; }
@media (max-width: 360px) { .av2 .ep-cases { grid-template-columns: 1fr; } }

/* ============================================================
   PRODUCE — the answer well (the page's textarea, and the display well)
   ============================================================ */
.av2 .ep-composed-input,
.av2 .ep-field {
  width: 100%;
  min-height: 7.5rem;
  padding: 0.75rem 1rem;
  border-radius: var(--av2-r-card);
  background: var(--av2-card);
  color: var(--av2-ink);
  font-family: var(--av2-serif);
  font-style: italic;
  font-size: var(--av2-t-option);
  line-height: 1.4;
  resize: vertical;
  outline: 0;
}
.av2 .ep-composed-input::placeholder { color: var(--av2-muted); font-style: italic; }
.av2 .ep-composed-input[readonly] { color: var(--av2-ink-2); }
.av2 .ep-field__ph { color: var(--av2-muted); }
.av2 .ep-field__caret { display: inline-block; width: 2px; height: 1.05em; background: var(--av2-red); vertical-align: -2px; margin-left: 1px; }
@media (prefers-reduced-motion: no-preference) { .av2 .ep-field__caret { animation: ep-blink 1s step-end infinite; } }
@keyframes ep-blink { 50% { opacity: 0; } }
.av2 .word-count { margin: -6px 0 0; text-align: right; font-size: var(--av2-t-meta); font-weight: 700; color: var(--av2-muted); font-variant-numeric: tabular-nums; }
.av2 .target-chips,
.av2 .target-word-strip { display: flex; flex-wrap: wrap; gap: 8px; margin: 0; min-width: 0; }
.av2 .target-chips span,
.av2 .target-word-strip span {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  min-height: 32px;
  padding: 4px 12px;
  border: 0;
  border-radius: var(--av2-r-pill);
  background: var(--av2-card);
  color: var(--av2-ink);
  font-family: inherit;
  font-size: var(--av2-t-label);
  font-weight: 700;
  font-style: normal;
  letter-spacing: normal;
  text-transform: none;
  line-height: 1.3;
}
.av2 .target-word-strip span { font-family: var(--av2-serif); font-style: italic; font-size: var(--av2-t-body); font-weight: 500; }
.av2 .target-word-strip em { font-family: var(--av2-sans); font-style: normal; font-size: var(--av2-t-meta); font-weight: 400; color: var(--av2-muted); }

/* conversation: the character byline and the world's reply */
.av2 .ep-character-byline {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding: 0;
  border: 0;
  min-width: 0;
}
.av2 .ep-character-byline span { font-family: var(--av2-serif); font-style: italic; font-size: var(--av2-t-rule); line-height: 1.15; color: var(--av2-ink); }
.av2 .ep-character-byline em { font-family: var(--av2-sans); font-style: normal; font-size: var(--av2-t-meta); font-weight: 700; letter-spacing: normal; text-transform: none; color: var(--av2-blue); }
.av2 .ep-world-reply {
  margin: 0;
  padding: 14px 16px;
  border: 0;
  border-radius: var(--av2-r-card);
  background: var(--av2-card);
  color: var(--av2-ink);
  min-width: 0;
}
.av2 .ep-world-reply > span { display: block; font-size: var(--av2-t-meta); font-weight: 700; letter-spacing: normal; text-transform: none; color: var(--av2-blue); }
.av2 .ep-world-reply p { margin: 6px 0 0; font-family: var(--av2-serif); font-style: italic; font-size: var(--av2-t-rule); line-height: 1.3; }

/* ============================================================
   CONFIDENCE
   ============================================================ */
.av2 .ep-conf { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; min-width: 0; }
.av2 .ep-conf .av2-chip { min-height: var(--av2-tap); }

/* ============================================================
   FOOTER — tinted band, verdict, the one primary. Sticky above the
   app's bottom navigation; pushed to the bottom when the sheet is short.
   ============================================================ */
.av2 .ep-foot {
  position: sticky;
  bottom: var(--phone-bottom-nav-space, 0px);
  z-index: 5;
  margin: auto calc(-1 * var(--av2-gutter)) 0;
  padding-bottom: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.av2 .ep-foot[data-tone='correct'] { background: var(--av2-tint-correct); }
.av2 .ep-foot[data-tone='wrong'] { background: var(--av2-tint-wrong); }
.av2 .ep-foot .ep-verdict { margin: 0; }
.av2 .ep-verdict__text { min-width: 0; }
.av2 .ep-bar { margin: 0; }

/* ============================================================
   FEEDBACK BODY — corrections, relecture, repair, correct moment
   ============================================================ */
.av2 .ep-feedback { display: flex; flex-direction: column; gap: 14px; min-width: 0; }
.av2 .ep-galley { margin: 0; display: flex; flex-direction: column; gap: 8px; }
.av2 .ep-galley__anchor { margin: 0; }
.av2 .ep-gline { font-family: var(--av2-serif); font-style: italic; font-size: var(--av2-t-option); line-height: 1.35; color: var(--av2-ink); overflow-wrap: anywhere; }
.av2 .ep-gline .av2-correction__span { color: var(--av2-ink-2); }
.av2 .ep-why { margin: 0; font-size: var(--av2-t-label); line-height: 1.45; color: var(--av2-ink-2); }
.av2 .ep-repair-hint { margin: 0; display: flex; align-items: flex-start; gap: 8px; font-size: var(--av2-t-label); line-height: 1.45; color: var(--av2-ink-2); }
.av2 .ep-repair-hint .av2-shape { margin-top: 5px; }
.av2 .ep-labelfix { display: flex; flex-direction: column; gap: 4px; }
.av2 .ep-labelfix p { margin: 0; display: flex; gap: 10px; align-items: baseline; flex-wrap: wrap; }
.av2 .ep-labelfix__k { flex: none; width: 4rem; }
.av2 .ep-linefix { display: flex; flex-direction: column; gap: 4px; }
.av2 .ep-linefix p { margin: 0; overflow-wrap: anywhere; }
.av2 .ep-relecture { margin-top: 2px; }
.av2 .ep-relecture__line { display: inline-flex; align-items: center; gap: 6px; }
.av2 .ep-relecture .av2-notice { padding: 8px 12px; }
.av2 .ep-relecture__again { min-height: var(--av2-tap); }
.av2 .ep-correct { margin: 0; display: flex; flex-direction: column; gap: 6px; }
.av2 .ep-correct__said { margin: 0; font-size: var(--av2-t-option); color: var(--av2-green); }
.av2 .ep-bon-stamp[data-struck='true'] { animation: av2-pop 0.3s; }
.av2 .ep-bon-stamp .av2-label { color: var(--av2-ink); }
.av2 .ep-rulenote { margin: 0; font-size: var(--av2-t-meta); font-weight: 700; color: var(--av2-muted); }
.av2 .ep-notebook-add {
  margin: 0;
  padding: 12px 14px;
  border-radius: var(--av2-r-card);
  background: var(--av2-card);
  min-width: 0;
}
.av2 .ep-notebook-add .nh { display: block; margin-bottom: 6px; font-size: var(--av2-t-meta); font-weight: 700; color: var(--av2-green); }
.av2 .ep-notebook-add ul { margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 4px; }
.av2 .ep-notebook-add li { font-family: var(--av2-serif); font-style: italic; font-size: var(--av2-t-body); line-height: 1.3; color: var(--av2-ink); }
.av2 .ep-notebook-add li b { font-weight: 700; }
.av2 .ep-notebook-add li em { color: var(--av2-muted); }
.av2 .ep-fb-links { display: flex; flex-wrap: wrap; justify-content: center; gap: 4px 12px; margin: 0; }
.av2 .ep-fb-links button {
  min-height: var(--av2-tap);
  padding: 0.5rem 0.75rem;
  border: 0;
  background: transparent;
  color: var(--av2-ink-2);
  font-family: inherit;
  font-size: var(--av2-t-label);
  font-weight: 600;
  letter-spacing: normal;
  text-transform: none;
  text-decoration: underline;
  text-underline-offset: 3px;
  cursor: pointer;
}

/* typed micro-repair */
.av2 .ep-repair { display: flex; flex-direction: column; gap: 10px; padding: 14px 16px; }
.av2 .ep-repair__input { font-family: var(--av2-serif); font-style: italic; font-size: var(--av2-t-option); }
.av2 .ep-repair__ghostline { display: block; font-family: var(--av2-serif); font-style: italic; font-size: var(--av2-t-option); }
.av2 .ep-repair__err { color: var(--av2-red); text-decoration: underline; text-decoration-thickness: 2px; }
.av2 .ep-repair__ghost { color: var(--av2-muted); }
.av2 .ep-repair__submit { align-self: flex-start; }
.av2 .ep-repair .av2-notice { padding: 8px 12px; }

/* ============================================================
   LISTEN · RECORD
   ============================================================ */
.av2 .ep-listen { display: flex; align-items: center; gap: 12px; min-width: 0; }
.av2 .ep-listen__text { min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.av2 .ep-listen__text p { margin: 0; }
.av2 .ep-listen__fr { font-size: var(--av2-t-rule); color: var(--av2-ink); }
.av2 .ep-listen[data-disabled='true'] .ep-listen__fr { color: var(--av2-ink-2); }
.av2 .ep-record { display: flex; align-items: center; gap: 12px; min-width: 0; }
.av2 .ep-record__st { margin: 0; }
.av2 .ep-record[data-status='recording'] .ep-record__st { color: var(--av2-ink); }

/* ============================================================
   LOCK — the early-mastery reward surface
   ============================================================ */
.av2 .ep-lock { display: flex; flex-direction: column; align-items: flex-start; gap: 8px; padding: 18px 20px; margin-top: 4px; }
.av2 .ep-lock__k, .av2 .ep-lock__promo .av2-label { color: var(--av2-on-yellow); }
.av2 .ep-lock__plate { display: flex; }
.av2 .ep-lock__title { margin: 0; color: var(--av2-on-yellow); }
.av2 .ep-lock__p { margin: 0; color: var(--av2-on-yellow); }
.av2 .ep-lock__promo .av2-shape--square { color: var(--av2-on-yellow); }

/* ============================================================
   NOTICE · SKELETON · RESUME
   ============================================================ */
.av2 .ep-notice { min-width: 0; }
.av2 .ep-notice .av2-btn { gap: 6px; }
.av2 .ep-skel { display: flex; flex-direction: column; gap: 12px; min-width: 0; }
.av2 .ep-skel__press { margin: 4px 0 0; }
.av2 .ep-resume { display: flex; flex-direction: column; gap: 10px; padding: 20px; }
.av2 .ep-resume h2, .av2 .ep-resume p { margin: 0; }
.av2 .ep-resume__stick { margin: 6px 0; }

/* ============================================================
   RECAP — L'ÉPREUVE. RecapModal (pages/atelier.tsx) mounts
   <section class="ep ep-recap"> without an AtelierV2Root, so every
   recap selector is doubled with .ep-recap … and the design tokens
   are bridged from the app's own theme tokens on that section. The
   bridge mirrors the token table in styles/atelier-v2.css; it becomes
   dead the moment that section carries the av2 class.
   ============================================================ */
.ep-recap:not(.av2) {
  --av2-paper: var(--app-paper);
  --av2-card: var(--app-sheet);
  --av2-line: var(--app-paper-2);
  --av2-line-2: var(--app-paper-3);
  --av2-ink: var(--app-ink);
  --av2-ink-2: var(--app-ink-2);
  --av2-muted: var(--app-ink-3);
  --av2-on-dark: var(--app-sheet);
  --av2-on-red: var(--app-sheet);
  --av2-on-blue: var(--app-sheet);
  --av2-on-green: var(--app-sheet);
  --av2-on-yellow: var(--app-ink);
  --av2-on-ink: var(--app-sheet);
  --av2-red: var(--app-red);
  --av2-red-deep: color-mix(in srgb, var(--app-red) 72%, var(--app-ink));
  --av2-blue: var(--app-blue);
  --av2-blue-deep: color-mix(in srgb, var(--app-blue) 72%, var(--app-ink));
  --av2-yellow: var(--app-yellow);
  --av2-yellow-deep: color-mix(in srgb, var(--app-yellow) 72%, var(--app-ink));
  --av2-green: var(--app-green);
  --av2-green-deep: color-mix(in srgb, var(--app-green) 72%, var(--app-ink));
  --av2-ink-deep: color-mix(in srgb, var(--app-ink) 60%, var(--app-paper));
  --av2-tint-correct: color-mix(in srgb, var(--app-green) 14%, var(--app-paper));
  --av2-tint-wrong: color-mix(in srgb, var(--app-red) 14%, var(--app-paper));
  --av2-tint-neutral: var(--app-paper);
  --av2-r-pill: 999px;
  --av2-r-button: 16px;
  --av2-r-card: 16px;
  --av2-r-tile: 18px;
  --av2-r-episode: 22px;
  --av2-r-hero: 24px;
  --av2-r-vocab: 28px;
  --av2-r-sheet: 28px;
  --av2-press: 5px;
  --av2-press-sm: 3px;
  --av2-press-md: 4px;
  --av2-press-lg: 8px;
  --av2-press-dur: 0.08s;
  --av2-serif: 'AtelierSerif', var(--app-serif);
  --av2-sans: 'AtelierSans', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
  --av2-t-meta: 0.75rem;
  --av2-t-label: 0.8125rem;
  --av2-t-body: 0.9375rem;
  --av2-t-body-lg: 1rem;
  --av2-t-action: 1.0625rem;
  --av2-t-rule: 1.1875rem;
  --av2-t-option: 1.25rem;
  --av2-t-title: 1.5rem;
  --av2-t-head: 1.875rem;
  --av2-t-screen: 2rem;
  --av2-t-display: 2.125rem;
  --av2-gutter: 20px;
  --av2-gap: 12px;
  --av2-tap: 44px;
  --av2-safe-bottom: max(20px, env(safe-area-inset-bottom));
  --av2-focus: var(--app-ink);
  font-family: var(--av2-sans);
  color: var(--av2-ink);
  text-transform: none;
  letter-spacing: normal;
}
.ep-recap:not(.av2) *, .ep-recap:not(.av2) *::before, .ep-recap:not(.av2) *::after { box-sizing: border-box; }
.ep-recap:not(.av2) .av2-surface { background: var(--av2-card); border-radius: var(--av2-r-card); padding: 16px 18px; color: var(--av2-ink); min-width: 0; }
.ep-recap:not(.av2) .av2-surface--tile { border-radius: var(--av2-r-tile); padding: 12px 14px; }
.ep-recap:not(.av2) .av2-surface--hero { border-radius: var(--av2-r-hero); padding: 0; overflow: hidden; }
.ep-recap:not(.av2) .av2-surface--blue { background: var(--av2-blue); color: var(--av2-on-blue); }
.ep-recap:not(.av2) .av2-surface--blue .av2-label, .ep-recap:not(.av2) .av2-surface--blue .av2-headline { color: inherit; }
.ep-recap:not(.av2) .av2-headline { margin: 0; font-family: var(--av2-serif); font-style: italic; font-weight: 500; font-size: var(--av2-t-head); line-height: 1.15; color: var(--av2-ink); text-wrap: pretty; overflow-wrap: anywhere; }
.ep-recap:not(.av2) .av2-headline--screen { font-size: var(--av2-t-screen); line-height: 1; }
.ep-recap:not(.av2) .av2-headline--display { font-size: var(--av2-t-display); line-height: 1.05; }
.ep-recap:not(.av2) .av2-headline--title { font-size: var(--av2-t-title); line-height: 1.1; font-weight: 600; }
.ep-recap:not(.av2) .av2-label { margin: 0; font-size: var(--av2-t-meta); font-weight: 700; line-height: 1.3; color: var(--av2-muted); }
.ep-recap:not(.av2) .av2-body { margin: 0; font-size: var(--av2-t-label); line-height: 1.45; color: var(--av2-ink-2); }
.ep-recap:not(.av2) .av2-body--lg { font-size: var(--av2-t-body); }
.ep-recap:not(.av2) .av2-fr { font-family: var(--av2-serif); font-style: italic; line-height: 1.35; overflow-wrap: anywhere; }
.ep-recap:not(.av2) .av2-byline { display: inline-flex; align-items: center; gap: 8px; min-width: 0; }
.ep-recap:not(.av2) .av2-shape { display: inline-block; flex: none; width: 12px; height: 12px; background: currentColor; }
.ep-recap:not(.av2) .av2-shape--square { border-radius: 2px; color: var(--av2-ink); }
.ep-recap:not(.av2) .av2-shape--circle { border-radius: 999px; color: var(--av2-blue); }
.ep-recap:not(.av2) .av2-shape--reward { border-radius: 3px; color: var(--av2-yellow); }
.ep-recap:not(.av2) .av2-shape--triangle { color: var(--av2-red); clip-path: polygon(50% 0, 100% 100%, 0 100%); }
.ep-recap:not(.av2) .av2-shape--sm { width: 8px; height: 8px; }
.ep-recap:not(.av2) .av2-btn {
  --av2-btn-face: var(--av2-card);
  --av2-btn-fg: var(--av2-ink);
  --av2-btn-shadow: var(--av2-line-2);
  --av2-btn-depth: var(--av2-press);
  display: inline-flex; align-items: center; justify-content: center; gap: 8px;
  width: 100%; min-height: max(var(--av2-tap), 3.5rem); padding: 0.75rem 1.25rem;
  border: 0; border-radius: var(--av2-r-button);
  background: var(--av2-btn-face); color: var(--av2-btn-fg);
  box-shadow: 0 var(--av2-btn-depth) 0 var(--av2-btn-shadow);
  font-family: inherit; font-size: var(--av2-t-action); font-weight: 700; line-height: 1.25;
  letter-spacing: normal; text-transform: none; cursor: pointer;
  transition: transform var(--av2-press-dur), box-shadow var(--av2-press-dur);
}
.ep-recap:not(.av2) .av2-btn:not(:disabled):active { transform: translateY(var(--av2-btn-depth)); box-shadow: 0 0 0 transparent; }
.ep-recap:not(.av2) .av2-btn--primary { --av2-btn-face: var(--av2-red); --av2-btn-fg: var(--av2-on-red); --av2-btn-shadow: var(--av2-red-deep); }
.ep-recap:not(.av2) .av2-btn--secondary { --av2-btn-depth: var(--av2-press-md); font-size: var(--av2-t-body-lg); }
.ep-recap:not(.av2) .av2-mark { display: block; }

/* the recap's own layout (both scopes) */
.av2 .ep-recap, .ep.ep-recap {
  position: relative;
  width: min(100%, 510px);
  max-height: min(90dvh, 780px);
  overflow: auto;
  border: 0;
  border-radius: var(--av2-r-sheet);
  background: var(--av2-paper);
  color: var(--av2-ink);
  box-shadow: none;
  display: flex;
  flex-direction: column;
}
.av2 .ep-recap-close, .ep-recap .ep-recap-close {
  position: absolute;
  z-index: 2;
  right: 12px;
  top: 12px;
  display: grid;
  place-items: center;
  width: var(--av2-tap);
  height: var(--av2-tap);
  padding: 0;
  border: 0;
  border-radius: var(--av2-r-pill);
  background: var(--av2-card);
  color: var(--av2-ink);
  font-size: var(--av2-t-title);
  line-height: 1;
  cursor: pointer;
}
.av2 .ep-bat-stage, .ep.ep-recap .ep-bat-stage { padding: 20px 20px 0; text-align: left; background: transparent; }
.av2 .ep-bat, .ep-recap .ep-bat { display: flex; flex-direction: column; align-items: flex-start; gap: 6px; padding: 18px 20px; animation: av2-pop 0.3s; }
.av2 .ep-bat__d, .ep-recap .ep-bat__d { margin-top: 6px; }
.av2 .ep-bat__m, .ep-recap .ep-bat__m { margin: 0; }
.av2 .ep-bat__sub, .ep-recap .ep-bat__sub { margin: 4px 0 0; }
.av2 .ep-recap-head, .ep-recap .ep-recap-head { display: flex; flex-direction: column; gap: 4px; padding: 20px 20px 0; }
.av2 .ep-recap-head__title, .ep-recap .ep-recap-head__title { margin: 2px 0 0; }
.av2 .ep-recap-body, .ep-recap .ep-recap-body { display: flex; flex-direction: column; gap: 14px; padding: 18px 20px 24px; }
.av2 .ep-tally, .ep-recap .ep-tally { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; min-width: 0; }
.av2 .ep-tally__t, .ep-recap .ep-tally__t { display: flex; flex-direction: column; gap: 4px; }
.av2 .ep-tally__n, .ep-recap .ep-tally__n { margin: 0; font-family: var(--av2-serif); font-style: italic; font-weight: 600; font-size: var(--av2-t-title); line-height: 1; color: var(--av2-ink); }
.av2 .ep-tally__l, .ep-recap .ep-tally__l { margin: 0; }
.av2 .ep-proof, .ep-recap .ep-proof { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; min-width: 0; }
.av2 .ep-proof__pl, .ep-recap .ep-proof__pl { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: baseline; gap: 10px; }
.av2 .ep-proof__pl .av2-shape, .ep-recap .ep-proof__pl .av2-shape { align-self: center; }
.av2 .ep-proof__fr, .ep-recap .ep-proof__fr { font-size: var(--av2-t-body); color: var(--av2-ink); }
.av2 .ep-proof__fr del, .ep-recap .ep-proof__fr del { color: var(--av2-ink-2); }
.av2 .ep-proof__fr ins, .ep-recap .ep-proof__fr ins { text-decoration: none; color: var(--av2-green); }
.av2 .ep-proof__tag, .ep-recap .ep-proof__tag { white-space: nowrap; }
.av2 .ep-phrase, .ep-recap .ep-phrase { display: flex; flex-direction: column; gap: 8px; }
.av2 .ep-phrase__q, .ep-recap .ep-phrase__q { margin: 0; text-wrap: balance; }
.av2 .ep-recap-rewards, .ep-recap .ep-recap-rewards { display: flex; align-items: center; gap: 16px; margin: 0; padding: 4px 0; border: 0; min-width: 0; }
.av2 .ep-recap-rewards .ep-mint, .ep-recap .ep-recap-rewards .ep-mint { flex: 1 1 auto; }
.av2 .ep-seal, .ep-recap .ep-seal { flex: none; display: inline-grid; place-items: center; }
.av2 .ep-seal__med, .ep-recap .ep-seal__med { display: grid; place-items: center; width: 84px; height: 84px; border-radius: var(--av2-r-pill); background: var(--av2-card); }
.av2 .ep-seal[data-gilt='true'] .ep-seal__med, .ep-recap .ep-seal[data-gilt='true'] .ep-seal__med { background: var(--av2-yellow); }
@media (prefers-reduced-motion: no-preference) { .av2 .ep-seal[data-stamp='true'] .ep-seal__med, .ep-recap .ep-seal[data-stamp='true'] .ep-seal__med { animation: av2-pop 0.4s; } }
.av2 .ep-mint, .ep-recap .ep-mint { display: flex; align-items: center; justify-content: space-between; gap: 12px; min-width: 0; }
.av2 .ep-mint__tx, .ep-recap .ep-mint__tx { min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.av2 .ep-mint__b, .ep-recap .ep-mint__b { color: var(--av2-ink); }
.av2 .ep-mint__tokens, .ep-recap .ep-mint__tokens { display: flex; gap: 6px; flex: none; }
.av2 .ep-token, .ep-recap .ep-token { display: inline-flex; align-items: center; gap: 3px; padding: 10px 8px; }
.av2 .ep-streak, .ep-recap .ep-streak { display: flex; flex-direction: column; gap: 10px; }
.av2 .ep-streak__row, .ep-recap .ep-streak__row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; min-width: 0; }
.av2 .ep-streak__n, .ep-recap .ep-streak__n { font-family: var(--av2-serif); font-style: italic; font-weight: 600; font-size: var(--av2-t-title); line-height: 1; color: var(--av2-ink); }
.av2 .ep-streak__n--was, .ep-recap .ep-streak__n--was { color: var(--av2-muted); }
.av2 .ep-streak__arw, .ep-recap .ep-streak__arw { display: inline-flex; color: var(--av2-muted); }
.av2 .ep-streak__l, .ep-recap .ep-streak__l { flex: 1 1 10rem; }
.av2 .ep-streak__rules, .ep-recap .ep-streak__rules { display: flex; gap: 5px; }
.av2 .ep-streak__rules i, .ep-recap .ep-streak__rules i { display: block; width: 12px; height: 12px; border-radius: 2px; background: var(--av2-line); }
.av2 .ep-streak__rules i[data-on='true'], .ep-recap .ep-streak__rules i[data-on='true'] { background: var(--av2-ink); }
.av2 .ep-handoff, .ep-recap .ep-handoff { display: flex; flex-direction: column; gap: 10px; margin-top: 4px; }
@media (max-width: 480px) {
  .av2 .ep-recap, .ep.ep-recap { width: 100%; max-height: calc(var(--app-viewport-height, 100vh) - 24px); }
  .av2 .ep-composed-input { min-height: 6.5rem; }
}
    `}</style>
  );
}
