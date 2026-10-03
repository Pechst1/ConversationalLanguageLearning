/**
 * WP-119 · the Revue's conversation: RvThread and its rows.
 *
 * The thread is an `<ol>` (design §6), reusing the WP-89 «Le fil» classes: Romy
 * on the left in a bubble with her face, the learner on the right in Garamond
 * with a hairline rule. Every row comes from the wire's `RvThreadItem` union;
 * the client adds only `claimsFolded`, `typing` and the resume marker.
 *
 *   RvNarration      the narrator, sans, no face
 *   RvListen         the read-aloud summary (the face is the play button)
 *   RvLine           a Romy line; the latest is the screen's headline, older ones small
 *   RvGlossText      French with glosses: `shown` (ruby under the first occurrence),
 *                    `tap` (every word opens the word sheet), `none`
 *   RvClaim          a sourced claim: kind by label + shape + rule, never colour alone
 *   RvSourceLine     «D'après …, 29 sept. ↗» + «La citation» disclosure
 *   RvUncertainty    what the sources do not say (the dashed «absence» surface)
 *   RvShift          a hairline status marker (simplify / angle / bouclage / bouclé)
 *   RvQuickReplies   chips whose label may differ from the French they send
 *
 * Phase 2 («Les invités», WIRE §6):
 *   RvGuestEntrance  «Margaux arrive.» + why she cares, tinted 12 % from her accent
 *   RvGuestLine      a guest's bubble: their face, their name in their colour, a
 *                    quiet tag (témoignage / pas d'accord), «a changé d'avis» marker
 *   RvRegisterNote   the rubric's register code, worded (vous → tu, tu → vous)
 *   Fallback lines carry `data-reason`; `model_down` gets the quiet notice first.
 */

import React, { useState } from 'react';

import { CastPortrait, Notice, ShapeToken } from '@/components/atelier-v2/ui';
import { useLineVoice } from '@/components/atelier-v2/journey/useLineVoice';
import type {
  RvClaim as RvClaimData,
  RvGloss,
  RvGuestItem,
  RvLanguage,
  RvMade,
  RvQuickReply,
  RvShiftItem,
  RvSource,
  RvSupport,
  RvThreadItem,
} from '@/lib/revue-types';

import { REGISTER_LINES_FR, fill, guestName, type RevueCopy } from './revue-copy';
import {
  contributionSegments,
  displayThread,
  foldedLabel,
  glossSegments,
  modelDownNotices,
  sourceDate,
  wordCount,
  type GlossSegment,
} from './revue-model';

const ROMY_ID = 'romy_tremblay';

export type RvWordEvent = { word: string; gloss: string | null; sentence: string };

// ---------------------------------------------------------------------------
// RvGlossText
// ---------------------------------------------------------------------------

export type RvGlossTextProps = {
  text: string;
  glosses: RvGloss[];
  mode: 'shown' | 'tap' | 'none';
  /** The language of the printed glosses (`lang` on the ruby). */
  glossLanguage?: RvLanguage;
  onWord?: (event: RvWordEvent) => void;
  /** The word whose sheet is open (lit in reward yellow). */
  openWord?: string | null;
};

export function RvGlossText({ text, glosses, mode, glossLanguage = 'en', onWord, openWord = null }: RvGlossTextProps) {
  const segments = glossSegments(text, glosses, onWord || mode !== 'tap' ? mode : 'none');
  // Punctuation straight after a word stays on its line («pareil.» never breaks before the stop).
  const glued = new Map<number, string>();
  segments.forEach((segment, index) => {
    const next = segments[index + 1];
    if (segment.kind !== 'text' && next && next.kind === 'text') {
      const lead = /^[^\s]+/.exec(next.text);
      if (lead) glued.set(index, lead[0]);
    }
  });
  return (
    <>
      {segments.map((segment, index) => {
        if (segment.kind === 'text') {
          const previous = glued.get(index - 1);
          const rest = previous ? segment.text.slice(previous.length) : segment.text;
          return rest ? <React.Fragment key={index}>{rest}</React.Fragment> : null;
        }
        const tail = glued.get(index);
        if (tail) {
          return (
            <span key={index} className="rv-nb">
              {renderGlossSegment(segment, index, glossLanguage, openWord, onWord, text)}
              {tail}
            </span>
          );
        }
        return renderGlossSegment(segment, index, glossLanguage, openWord, onWord, text);
      })}
    </>
  );
}

function renderGlossSegment(
  segment: Exclude<GlossSegment, { kind: 'text' }>,
  index: number,
  glossLanguage: RvLanguage,
  openWord: string | null,
  onWord: ((event: RvWordEvent) => void) | undefined,
  text: string,
) {
  if (segment.kind === 'gloss') {
    return (
      <ruby key={index} className="rv-gloss">
        <span className="rv-target">{segment.text}</span>
        <rt lang={glossLanguage}>{segment.gloss}</rt>
      </ruby>
    );
  }
  return (
    <button
      key={index}
      type="button"
      className="rv-word"
      data-target={segment.gloss ? '' : undefined}
      data-open={openWord === segment.text ? '' : undefined}
      onClick={() => onWord?.({ word: segment.text, gloss: segment.gloss, sentence: text })}
    >
      {segment.text}
    </button>
  );
}

// ---------------------------------------------------------------------------
// RvContribution
// ---------------------------------------------------------------------------

/** The learner's own words: a yellow underline plus «toi» — never colour alone. */
export function RvContribution({ children, label = 'toi' }: { children: React.ReactNode; label?: string }) {
  return (
    <span className="rv-yours">
      {children}
      <sup>{label}</sup>
    </span>
  );
}

/** `text` with the contribution spans marked. */
export function ContributedText({ text, spans, label }: { text: string; spans: Array<[number, number]>; label: string }) {
  return (
    <>
      {contributionSegments(text, spans).map((segment, index) =>
        segment.mine ? (
          <RvContribution key={index} label={label}>
            {segment.text}
          </RvContribution>
        ) : (
          <React.Fragment key={index}>{segment.text}</React.Fragment>
        ),
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Rows
// ---------------------------------------------------------------------------

export function RvNarration({ textFr }: { textFr: string }) {
  return (
    <p className="rv-narr" lang="fr">
      {textFr}
    </p>
  );
}

/** The summary, read aloud in the device's French voice; the text shows while it plays (never a gate). */
export function RvListen({ id, textFr, copy }: { id: string; textFr: string; copy: RevueCopy }) {
  const voice = useLineVoice();
  const [shown, setShown] = useState(false);
  const key = `revue-summary-${id}`;
  const speaking = voice.speakingKey === key;
  const seconds = Math.max(5, Math.round(wordCount(textFr) / 2.4));
  const toggle = () => {
    setShown(true);
    if (speaking) voice.stop();
    else if (voice.supported) voice.speak({ key, text_fr: textFr, character_id: ROMY_ID });
  };
  return (
    <div>
      <button type="button" className="rv-listen" aria-pressed={speaking} onClick={toggle}>
        <span className="rv-listen__play" aria-hidden="true">
          <CastPortrait characterId={ROMY_ID} name="Romy" size="sm" ring />
          <b />
        </span>
        <span>
          {speaking ? copy.listen_stop : copy.listen_summary}
          <span className="rv-listen__meta">{fill(copy.listen_meta, { s: seconds })}</span>
        </span>
        <span className="rv-listen__wave" aria-hidden="true">
          {[6, 12, 8, 16, 10, 14, 7, 12, 9, 15, 6, 11].map((h, index) => (
            <i key={index} style={{ height: h }} />
          ))}
        </span>
      </button>
      {shown && (
        <p className="rv-summary" lang="fr">
          {textFr}
        </p>
      )}
    </div>
  );
}

export type RvLineProps = {
  speaker?: string;
  textFr: string;
  past: boolean;
  translation?: string | null;
  support: RvSupport;
  glosses: RvGloss[];
  glossLanguage?: RvLanguage;
  copy: RevueCopy;
  onWord?: (event: RvWordEvent) => void;
};

export function RvLine({ textFr, past, translation = null, support, glosses, glossLanguage = 'en', copy, onWord }: RvLineProps) {
  const [open, setOpen] = useState(false);
  const canTranslate = Boolean(translation) && support.translation !== 'none';
  const long = !past && wordCount(textFr) > 18;
  return (
    <div className={`av2-speech${past ? ' av2-speech--past' : ''}`} data-mood="neutral">
      <span className="av2-speech__face" aria-hidden="true">
        <CastPortrait characterId={ROMY_ID} name="Romy" size={past ? 'xs' : 'sm'} ring />
      </span>
      <div className="av2-speech__bubble" data-long={long ? '' : undefined}>
        <span className="rv-who">
          {copy.romy}
          <span className="av2-sr"> : </span>
        </span>
        <p className={past ? 'av2-thread__text av2-fr' : 'av2-headline'} lang="fr">
          <RvGlossText text={textFr} glosses={glosses} mode={support.glosses} glossLanguage={glossLanguage} onWord={onWord} />
        </p>
        {canTranslate && (
          <>
            <div className="rv-line__tools">
              <button type="button" className="rv-chip" aria-pressed={open} onClick={() => setOpen((value) => !value)}>
                <span className="sq" aria-hidden="true" />
                {open ? copy.translation_hide : copy.translate}
              </button>
            </div>
            {open && (
              <p className="rv-translation" lang={glossLanguage}>
                {translation}
              </p>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export function RvSourceLine({ source, quote, copy, now }: { source: RvSource; quote?: string | null; copy: RevueCopy; now?: Date }) {
  const [open, setOpen] = useState(false);
  const date = sourceDate(source.publishedAt, now);
  const name = source.name.replace(/\s*\(.*\)$/, '');
  return (
    <>
      <p className="rv-source">
        <a
          href={source.url}
          target="_blank"
          rel="noopener noreferrer"
          aria-label={fill(copy.opens_new_tab, { source: name, date })}
        >
          {fill(copy.according_to, { source: name, date })}&nbsp;↗
        </a>
        {quote && (
          <button type="button" aria-expanded={open} onClick={() => setOpen((value) => !value)}>
            {copy.the_quote}
          </button>
        )}
      </p>
      {quote && open && (
        <blockquote className="rv-quote" lang="fr">
          « {quote} »
        </blockquote>
      )}
    </>
  );
}

export function RvClaim({
  claim,
  support,
  glosses,
  band = 'A2',
  glossLanguage = 'en',
  copy,
  onWord,
  now,
}: {
  claim: RvClaimData;
  support: RvSupport;
  glosses: RvGloss[];
  band?: string;
  glossLanguage?: RvLanguage;
  copy: RevueCopy;
  onWord?: (event: RvWordEvent) => void;
  now?: Date;
}) {
  const label = claim.kind === 'fact' ? copy.fact : claim.kind === 'forecast' ? copy.forecast : copy.interpretation;
  const own = glosses.filter((gloss) => !gloss.claimId || gloss.claimId === claim.id);
  return (
    <article className="rv-claim" data-kind={claim.kind}>
      <p className="rv-claim__kind">
        <ShapeToken kind={claim.kind === 'fact' ? 'done' : 'story'} size="sm" />
        {label}
      </p>
      <p className="rv-claim__fr" lang="fr" data-band={band === 'B1' || band === 'B2' ? 'b1' : undefined}>
        <RvGlossText text={claim.fr} glosses={own} mode={support.glosses} glossLanguage={glossLanguage} onWord={onWord} />
      </p>
      {claim.attributedTo && claim.kind !== 'fact' && (
        // The attribution is the dossier's French («d'après plusieurs vignerons cités»).
        <p className="rv-claim__by" lang="fr">
          {claim.kind === 'forecast' ? `selon ${claim.attributedTo}` : `d'après ${claim.attributedTo}`}
        </p>
      )}
      <RvSourceLine source={claim.source} quote={claim.quote} copy={copy} now={now} />
    </article>
  );
}

export function RvUncertainty({ textFr, copy }: { textFr: string; copy: RevueCopy }) {
  return (
    <div className="rv-unknown">
      <p className="rv-unknown__k">
        <span className="rv-ring" aria-hidden="true" />
        {copy.uncertain}
      </p>
      <p className="rv-unknown__fr" lang="fr">
        {textFr}
      </p>
    </div>
  );
}

export function shiftLabel(item: Pick<RvShiftItem, 'reason' | 'angle'>, copy: RevueCopy): string {
  if (item.reason === 'simplify') return copy.shift_simplify;
  if (item.reason === 'angle') return fill(copy.shift_angle, { angle: item.angle?.fr ?? '' });
  if (item.reason === 'boucle') return copy.shift_boucle;
  return copy.shift_bouclage;
}

export function RvShift({ label }: { label: string }) {
  return (
    <p className="rv-shift" role="status">
      {label}
    </p>
  );
}

export function RvQuickReplies({ replies, onSend, disabled = false }: { replies: RvQuickReply[]; onSend: (fr: string) => void; disabled?: boolean }) {
  if (!replies.length) return null;
  return (
    <div className="rv-quick">
      {replies.map((reply) => (
        <button key={reply.sendFr} type="button" className="av2-chip" lang="fr" disabled={disabled} onClick={() => onSend(reply.sendFr)}>
          {reply.label}
        </button>
      ))}
    </div>
  );
}

export function madeLabel(kind: RvMade['kind'], copy: RevueCopy): string {
  if (kind === 'reader_question') return copy.made_question;
  if (kind === 'short_report') return copy.made_report;
  return copy.made_headline;
}

export function RvMadeCard({ made, copy }: { made: RvMade; copy: RevueCopy }) {
  return (
    <div className="rv-made" data-made={made.kind}>
      <p className="av2-label">{madeLabel(made.kind, copy)}</p>
      <p className="rv-made__fr" lang="fr">
        <ContributedText text={made.textFr} spans={made.contribution} label={copy.contribution} />
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Phase 2 · the guest
// ---------------------------------------------------------------------------

/** «Margaux arrive.» and why she cares (French), tinted 12 % from her accent on card. */
export function RvGuestEntrance({ castId, name, reasonFr, copy }: { castId: string; name: string; reasonFr: string | null; copy: RevueCopy }) {
  return (
    <p className="rv-entrance" data-char={castId} role="status">
      <b>{fill(copy.guest_arrives, { name })}</b>
      {reasonFr && (
        <>
          {' '}
          <span lang="fr">{reasonFr}</span>
        </>
      )}
    </p>
  );
}

export type RvGuestLineProps = {
  item: Pick<RvGuestItem, 'castId' | 'textFr' | 'move' | 'glosses' | 'reason'>;
  past: boolean;
  support: RvSupport;
  glossLanguage?: RvLanguage;
  copy: RevueCopy;
  onWord?: (event: RvWordEvent) => void;
};

/**
 * A guest's line: a speech bubble, never a claim card (a testimony, not a
 * source). Their face and their name in their colour; the move is a quiet tag.
 * An authored stand-in line (`reason`) looks like any other guest line.
 */
export function RvGuestLine({ item, past, support, glossLanguage = 'en', copy, onWord }: RvGuestLineProps) {
  const name = guestName(item.castId);
  const tag = item.move === 'disagree' ? copy.guest_disagrees : item.move === 'follow_up' ? copy.guest_asks : copy.guest_testimony;
  const long = !past && wordCount(item.textFr) > 18;
  return (
    <div className={`av2-speech rv-guest${past ? ' av2-speech--past' : ''}`} data-mood="neutral" data-char={item.castId} data-move={item.move}>
      <span className="av2-speech__face" aria-hidden="true">
        <CastPortrait characterId={item.castId} name={name} size={past ? 'xs' : 'sm'} ring />
      </span>
      <div className="av2-speech__bubble" data-long={long ? '' : undefined}>
        <span className="rv-who">
          {name}
          <span className="rv-guest__tag"> · {tag}</span>
          <span className="av2-sr"> : </span>
        </span>
        <p className={past ? 'av2-thread__text av2-fr' : 'av2-headline'} lang="fr">
          <RvGlossText text={item.textFr} glosses={item.glosses} mode={support.glosses} glossLanguage={glossLanguage} onWord={onWord} />
        </p>
      </div>
    </div>
  );
}

/** The quiet notice before an authored line that stands in because the model is down (design §3.7). */
export function RvModelDownNotice({ copy }: { copy: RevueCopy }) {
  return (
    <Notice tone="quiet" shape="action">
      <p>{copy.model_down}</p>
    </Notice>
  );
}

/** The rubric's register code, worded: one French line and why, in the learner's language (as WP-66 shows it). */
export function RvRegisterNote({ note, copy }: { note: 'vous_to_tu' | 'tu_to_vous'; copy: RevueCopy }) {
  return (
    <Notice shape="story">
      <p className="av2-label" data-state="register">
        {copy.register_label}
      </p>
      <p className="av2-fr av2-body" lang="fr">
        {REGISTER_LINES_FR[note]}
      </p>
      <p className="av2-body">{copy.register_reason[note]}</p>
    </Notice>
  );
}

export function RvTyping({ copy }: { copy: RevueCopy }) {
  return (
    <div className="rv-typing" role="status" aria-live="polite">
      <CastPortrait characterId={ROMY_ID} name="Romy" size="xs" ring />
      <p>
        <span>{copy.typing}</span>
        <span className="rv-dots" aria-hidden="true">
          <i />
          <i />
          <i />
        </span>
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// RvThread
// ---------------------------------------------------------------------------

export type RvThreadProps = {
  items: RvThreadItem[];
  support: RvSupport;
  copy: RevueCopy;
  /** Plan vocabulary: a claim's target words (the wire sends glosses on lines only). */
  vocabulary?: RvGloss[];
  band?: string;
  glossLanguage?: RvLanguage;
  onWord?: (event: RvWordEvent) => void;
  /** Romy is answering: the typing row closes the thread. */
  typing?: boolean;
  /** A learner line on its way (grey Garamond, `data-pending`). */
  pendingMine?: string | null;
  /** «Hier · tu reprends ici» before today's first row (resume). */
  resumeToday?: string | null;
  resumeLabel?: string;
  /** Rows the page appends after the thread (Romy's client lines, the make step). */
  after?: React.ReactNode;
  /** Phase 2: the register note a turn's evidence carried, by the learner line's id (never replayed). */
  registerNotes?: Record<string, 'vous_to_tu' | 'tu_to_vous'>;
  now?: Date;
};

export function RvThread({
  items,
  support,
  copy,
  vocabulary = [],
  band = 'A2',
  glossLanguage = 'en',
  onWord,
  typing = false,
  pendingMine = null,
  resumeToday = null,
  resumeLabel = '',
  after = null,
  registerNotes = {},
  now,
}: RvThreadProps) {
  const [opened, setOpened] = useState<Set<string>>(() => new Set());
  const rows = displayThread(items, { opened, resumeToday, resumeLabel });
  const notices = modelDownNotices(items);
  const reopen = (id: string) =>
    setOpened((current) => {
      const next = new Set(current);
      next.add(id);
      return next;
    });
  return (
    <ol className="av2-thread rv-thread" aria-live="polite">
      {rows.map((row) => {
        if (row.kind === 'resume') {
          return (
            <li key={row.id} className="av2-thread__line" data-kind="resume">
              <RvShift label={row.label} />
            </li>
          );
        }
        if (row.kind === 'claimsFolded') {
          return (
            <li key={`fold-${row.id}`} className="av2-thread__line" data-kind="claimsFolded">
              <button type="button" className="rv-folded" aria-expanded={false} onClick={() => reopen(row.id)}>
                <ShapeToken kind="done" size="sm" />
                {foldedLabel(row.claims, copy)}
              </button>
            </li>
          );
        }
        const { item, past } = row;
        switch (item.kind) {
          case 'narration':
            return (
              <li key={item.id} className="av2-thread__line rv-thread__line" data-kind="narration">
                <RvNarration textFr={item.textFr} />
              </li>
            );
          case 'summary':
            return (
              <li key={item.id} className="av2-thread__line" data-kind="summary">
                <RvListen id={item.id} textFr={item.textFr} copy={copy} />
              </li>
            );
          case 'line':
            return (
              <li
                key={item.id}
                className="av2-thread__line"
                data-kind="line"
                data-role={item.role}
                data-reason={item.reason ?? undefined}
                data-speaker="romy"
              >
                {notices.has(item.id) && <RvModelDownNotice copy={copy} />}
                <RvLine
                  speaker={item.speaker}
                  textFr={item.textFr}
                  past={past}
                  translation={item.translation}
                  support={support}
                  glosses={item.glosses}
                  glossLanguage={glossLanguage}
                  copy={copy}
                  onWord={onWord}
                />
              </li>
            );
          case 'guest':
            return (
              <li
                key={item.id}
                className="av2-thread__line"
                data-kind="guest"
                data-move={item.move}
                data-reason={item.reason ?? undefined}
                data-speaker={item.castId}
              >
                {notices.has(item.id) && <RvModelDownNotice copy={copy} />}
                {item.move === 'enter' && <RvGuestEntrance castId={item.castId} name={guestName(item.castId)} reasonFr={item.reasonFr} copy={copy} />}
                <RvGuestLine item={item} past={past} support={support} glossLanguage={glossLanguage} copy={copy} onWord={onWord} />
                {item.move === 'moved' && <RvShift label={fill(copy.guest_moved, { name: guestName(item.castId) })} />}
              </li>
            );
          case 'mine': {
            // This visit's note first; else the one the server replays on the line (a reload).
            const note = registerNotes[item.id] ?? item.registerNote;
            return (
              <React.Fragment key={item.id}>
                <li className="av2-thread__line" data-kind="mine" data-speaker="learner">
                  <p className="rv-thread__mine" lang="fr">
                    <span className="av2-sr">{copy.you} : </span>
                    {item.textFr}
                  </p>
                </li>
                {note && (
                  <li className="av2-thread__line" data-kind="register">
                    <RvRegisterNote note={note} copy={copy} />
                  </li>
                )}
              </React.Fragment>
            );
          }
          case 'claims':
            return (
              <li key={item.id} className="av2-thread__line" data-kind="claims">
                <div className="rv-claims">
                  {item.claims.map((claim) => (
                    <RvClaim
                      key={claim.id}
                      claim={claim}
                      support={support}
                      glosses={vocabulary}
                      band={band}
                      glossLanguage={glossLanguage}
                      copy={copy}
                      onWord={onWord}
                      now={now}
                    />
                  ))}
                </div>
              </li>
            );
          case 'uncertainty':
            return (
              <li key={item.id} className="av2-thread__line" data-kind="uncertainty">
                <RvUncertainty textFr={item.textFr} copy={copy} />
              </li>
            );
          case 'shift':
            return (
              <li key={item.id} className="av2-thread__line" data-kind="shift">
                <RvShift label={shiftLabel(item, copy)} />
              </li>
            );
          case 'made':
            return (
              <li key={item.id} className="av2-thread__line" data-kind="made">
                <RvMadeCard made={item.made} copy={copy} />
              </li>
            );
          default:
            return null;
        }
      })}
      {pendingMine && (
        <li className="av2-thread__line" data-kind="mine" data-speaker="learner">
          <p className="rv-thread__mine" lang="fr" data-pending="">
            <span className="av2-sr">{copy.you} : </span>
            {pendingMine}
          </p>
        </li>
      )}
      {typing && (
        <li className="av2-thread__line" data-kind="typing">
          <RvTyping copy={copy} />
        </li>
      )}
      {after}
    </ol>
  );
}

export default RvThread;
