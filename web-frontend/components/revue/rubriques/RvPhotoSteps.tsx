/**
 * «La photo» (WIRE §12, 2026-11-21) · «La planche», «La légende», «À toi».
 *
 * «La planche»: the story's pictures side by side, each printed with its credit; the learner
 * picks the one for the day's headline (a miss says, in the mother tongue, what the picked
 * picture shows; two tries, no answer before the second), then taps what THIS picture shows
 * among what the others show (a miss names the things that belong elsewhere and how many are
 * missing, never which). «La légende»: the picture and three captions; find the one with the
 * wrong fact, then say what is wrong (A1–A2 pick, B1+ rewrite). «À toi»: a picture of the
 * learner's choice and their own caption (A1 tiles, A2 frame, B1+ two sentences), Romy's marks,
 * the fix first.
 *
 * Built from the shared rubriques pieces only (RomyLine, FrLine, the comptoir's tiles and
 * options, the trap's word buttons, RvGalleryPicture, the proof block), so the «print» restyle
 * applies here as to «Le titre».
 */

import React, { useEffect, useState } from 'react';

import { Action, ArrowRightIcon } from '@/components/atelier-v2/ui';
import { textAnswerField } from '@/components/atelier-v2/ui/Choice';
import type { RvPhotoView } from '@/lib/revue-rubriques-types';

import { RomyLine } from '../comptoir/RvComptoirParts';
import { fill } from '../revue-copy';
import { RvGalleryPicture } from '../RvGallery';
import { RvTranslate } from '../RvThread';
import { photoMicroCopy, PM_LINES } from './photo-micro-copy';
import { a1Caption, asRvPicture } from './photo-micro-model';
import { ProofBlock, ProofFoot } from './RvProofBlock';
import { toggle, wordCount } from './rubriques-model';
import { FrLine, type RubriqueStepProps } from './RvRubriqueParts';

export type PhotoStepProps = RubriqueStepProps & { view: RvPhotoView };

/** The caption with its wrong words struck (as «L'intox express»'s correction). */
function struck(text: string, wrong: string): React.ReactNode {
  const at = wrong ? text.toLowerCase().indexOf(wrong.toLowerCase()) : -1;
  if (at < 0) return text;
  return (
    <>
      {text.slice(0, at)}
      <s className="ct-strike">{text.slice(at, at + wrong.length)}</s>
      {text.slice(at + wrong.length)}
    </>
  );
}

function Continue({ props }: { props: PhotoStepProps }) {
  const { copy, pending, onContinue } = props;
  return (
    <Action tone="primary" disabled={pending !== null} iconAfter={<ArrowRightIcon size={18} />} onClick={onContinue}>
      {copy.continue}
    </Action>
  );
}

// ---------------------------------------------------------------------------
// «La planche»
// ---------------------------------------------------------------------------

export function RvPhotoPlanche(props: PhotoStepProps) {
  const { view, chrome, glossLanguage, copy, pending, readOnly, onAct, notice, footRef, rcopy } = props;
  const pm = photoMicroCopy(chrome);
  const px = photoMicroCopy(glossLanguage);
  const planche = view.planche!;
  const seen = planche.seen;
  const [chosen, setChosen] = useState<string | null>(null);
  const [taps, setTaps] = useState<number[]>([]);
  useEffect(() => setChosen(null), [planche.tries]);
  useEffect(() => setTaps([]), [seen?.tries]);
  const busy = readOnly || pending !== null;
  const lit = seen?.resolved ? seen.solution : taps;
  const shows = planche.shows.map((t) => t.tr ?? t.fr).join(', ');
  return (
    <>
      <div className="rv-body ct-body" data-step="planche">
        <RomyLine line={PM_LINES.planche_ask} props={props} past={planche.resolved} />
        <p className="ct-frame__k">{pm.planche_headline}</p>
        <p className="rb-line__fr rb-headline" lang="fr">
          {planche.headlineFr}
        </p>
        {!planche.resolved && <p className="ct-hint">{pm.planche_task}</p>}
        <ul className="rb-planche" role="radiogroup" aria-label={pm.planche_task}>
          {planche.pictures.map((picture, index) => {
            const tried = planche.picked.includes(picture.key) && picture.key !== planche.solution;
            const right = planche.resolved && picture.key === planche.solution;
            return (
              <li key={picture.key} className="rb-planche__item" data-tried={tried ? '' : undefined} data-right={right ? '' : undefined}>
                <RvGalleryPicture picture={asRvPicture(picture)} copy={copy} />
                <button
                  type="button"
                  role="radio"
                  className="ct-opt rb-planche__pick"
                  aria-checked={chosen === picture.key || right}
                  disabled={busy || planche.resolved || tried}
                  onClick={() => setChosen(picture.key)}
                >
                  {fill(pm.picture_n, { n: String(index + 1) })}
                </button>
              </li>
            );
          })}
        </ul>
        {!planche.resolved && planche.tries > 0 && (
          <div className="ct-why" lang={glossLanguage} data-ct-anchor="nearest">
            <p>{px.planche_wrong}</p>
            {shows && <p>{fill(px.planche_shows, { things: shows })}</p>}
          </div>
        )}
        {planche.resolved && (
          <p className="ct-why" data-ct-anchor={seen && seen.tries === 0 ? 'nearest' : undefined}>
            {planche.correct ? pm.planche_right : pm.planche_shown}
          </p>
        )}
        {seen && (
          <section className="ct-frame" aria-label={pm.seen_task}>
            <RomyLine line={PM_LINES.seen_ask} props={props} past={seen.resolved} />
            {!seen.resolved && <p className="ct-hint">{pm.seen_task}</p>}
            <p className="rb-trap" role="group" aria-label={pm.seen_task}>
              {seen.words.map((word) => (
                <button
                  key={word.index}
                  type="button"
                  className="rb-trap__w rb-seen__w"
                  lang="fr"
                  aria-pressed={lit.includes(word.index)}
                  data-wrong={!seen.resolved && seen.elsewhere.includes(word.index) && taps.length === 0 ? '' : undefined}
                  disabled={busy || seen.resolved}
                  onClick={() => setTaps((current) => toggle(current, word.index))}
                >
                  {word.text.fr}
                </button>
              ))}
            </p>
            {!seen.resolved && seen.tries > 0 && (
              <div className="ct-why" lang={glossLanguage} data-ct-anchor="nearest">
                {seen.elsewhere.length > 0 && (
                  <p>
                    {fill(px.seen_elsewhere, {
                      words: seen.words
                        .filter((w) => seen.elsewhere.includes(w.index))
                        .map((w) => `« ${w.text.fr} »`)
                        .join(', '),
                    })}
                  </p>
                )}
                {seen.missing > 0 && <p>{fill(px.seen_missing, { n: String(seen.missing) })}</p>}
              </div>
            )}
            {seen.resolved && (
              <p className="ct-why" data-ct-anchor="nearest">
                {seen.correct ? pm.seen_right : pm.seen_shown}
              </p>
            )}
          </section>
        )}
        {notice}
      </div>
      {!readOnly && (
        <div className="rv-foot ct-foot" ref={footRef}>
          {!planche.resolved ? (
            <>
              <p className="ct-foot__hint">{fill(rcopy.try_n, { n: String(planche.tries + 1), max: String(planche.maxTries) })}</p>
              <Action tone="primary" pending={pending === 'choose'} pendingLabel={rcopy.check} disabled={busy || !chosen} onClick={() => chosen && void onAct({ act: 'choose', key: chosen }, 'choose')}>
                {rcopy.check}
              </Action>
            </>
          ) : seen && !seen.resolved ? (
            <>
              <p className="ct-foot__hint">{fill(rcopy.try_n, { n: String(seen.tries + 1), max: String(seen.maxTries) })}</p>
              <Action tone="primary" pending={pending === 'seen'} pendingLabel={rcopy.check} disabled={busy || taps.length === 0} onClick={() => void onAct({ act: 'seen', words: taps }, 'seen')}>
                {rcopy.check}
              </Action>
            </>
          ) : (
            <Continue props={props} />
          )}
        </div>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// «La légende»
// ---------------------------------------------------------------------------

export function RvPhotoLegende(props: PhotoStepProps) {
  const { view, chrome, glossLanguage, copy, pending, readOnly, onAct, notice, footRef, rcopy } = props;
  const pm = photoMicroCopy(chrome);
  const px = photoMicroCopy(glossLanguage);
  const legende = view.legende!;
  const fix = legende.fix;
  const [chosen, setChosen] = useState<string | null>(null);
  const last = fix?.attempts[fix.attempts.length - 1] ?? '';
  const [text, setText] = useState(last);
  useEffect(() => setChosen(null), [legende.tries]);
  useEffect(() => setText(fix?.attempts[fix.attempts.length - 1] ?? ''), [fix?.tries, fix?.attempts]);
  const busy = readOnly || pending !== null;
  const lastPicked = !legende.resolved && legende.picked.length ? legende.picked[legende.picked.length - 1] : null;
  return (
    <>
      <div className="rv-body ct-body" data-step="legende">
        <RomyLine line={PM_LINES.legende_ask} props={props} past={legende.resolved} />
        <div className="rb-planche__solo">
          <RvGalleryPicture picture={asRvPicture(legende.picture)} copy={copy} />
        </div>
        {!legende.resolved && <p className="ct-hint">{pm.legende_task}</p>}
        <ol className="fl-strips rb-heads" role="radiogroup" aria-label={pm.legende_task}>
          {legende.captions.map((caption) => {
            const tried = legende.picked.includes(caption.key) && caption.key !== legende.solution;
            const wrong = legende.resolved && caption.key === legende.solution;
            return (
              <li key={caption.key} className="fl-strip rb-head" data-tried={tried ? '' : undefined} data-honest={wrong ? '' : undefined}>
                <button
                  type="button"
                  role="radio"
                  className="fl-strip__n"
                  aria-checked={chosen === caption.key || wrong}
                  aria-label={caption.text.fr}
                  disabled={busy || legende.resolved || tried}
                  onClick={() => setChosen(caption.key)}
                >
                  {caption.key.toUpperCase()}
                </button>
                <div className="fl-strip__text">
                  <FrLine text={caption.text} props={props} className="fl-strip__fr" />
                  {caption.role && <span className="rb-head__role">{pm.role[caption.role]}</span>}
                </div>
                {caption.key === lastPicked && (
                  <p className="ct-why" lang={glossLanguage} data-ct-anchor="nearest">
                    {caption.role === 'right' ? px.legende_right_picked : caption.why ? caption.why.tr ?? caption.why.fr : ''}
                  </p>
                )}
                {legende.resolved && caption.why && caption.role !== 'right' && (
                  <p className="ct-why" lang={caption.why.tr ? glossLanguage : 'fr'}>
                    {caption.why.tr ?? caption.why.fr}
                  </p>
                )}
              </li>
            );
          })}
        </ol>
        {legende.resolved && (
          <p className="ct-why" data-ct-anchor={fix && fix.tries === 0 ? 'nearest' : undefined}>
            {legende.correct ? pm.legende_found : pm.legende_shown}
          </p>
        )}
        {fix && (
          <section className="ct-frame rb-fix" aria-label={pm.fix_label} data-resolved={fix.resolved ? '' : undefined}>
            <RomyLine line={PM_LINES.fix_ask} props={props} past={fix.resolved} />
            <p className="rb-line__fr" lang="fr">
              {struck(fix.text.fr, fix.wrongFr)}
            </p>
            {!fix.resolved && <p className="ct-hint">{fix.input === 'pick' ? pm.fix_task_pick : pm.fix_task_write}</p>}
            {!fix.resolved && fix.input === 'pick' && (
              <div className="ct-opts" role="group" aria-label={pm.fix_task_pick}>
                {fix.options.map((option) => (
                  <button
                    key={option}
                    type="button"
                    className="ct-opt"
                    lang="fr"
                    data-state={fix.attempts.includes(option) ? 'no' : undefined}
                    aria-pressed={fix.attempts.includes(option)}
                    disabled={busy || fix.attempts.includes(option)}
                    onClick={() => void onAct({ act: 'caption_fix', value: option }, 'caption_fix')}
                  >
                    {option}
                  </button>
                ))}
              </div>
            )}
            {!fix.resolved && fix.input === 'write' && (
              <>
                {textAnswerField({ label: pm.fix_label, value: text, rows: 2, disabled: busy, onChange: setText })}
                <Action tone="secondary" pending={pending === 'caption_fix'} pendingLabel={rcopy.check} disabled={busy || !text.trim()} onClick={() => void onAct({ act: 'caption_fix', text }, 'caption_fix')}>
                  {rcopy.check}
                </Action>
              </>
            )}
            {!fix.resolved && fix.tries > 0 && (
              <>
                <p className="ct-why" lang={glossLanguage} data-ct-anchor="nearest">
                  {fix.input === 'write' && last ? <span lang="fr">« {last} » · </span> : null}
                  {px.fix_wrong}
                </p>
                <p className="ct-foot__hint">{fill(rcopy.try_n, { n: String(fix.tries + 1), max: String(fix.maxTries) })}</p>
              </>
            )}
            {fix.resolved && (
              <div className="ct-fb" data-correct={fix.correct ? '' : undefined} data-ct-anchor="nearest">
                {fix.fixed && (
                  <p className="ct-fb__fr" lang="fr">
                    {fix.fixed.fr}
                  </p>
                )}
                <p className="ct-fb__note">{fix.correct ? pm.fix_right : fill(pm.fix_shown, { right: fix.rightFr ?? '' })}</p>
                {fix.fixed && <RvTranslate textFr={fix.fixed.fr} translation={fix.fixed.tr} glossLanguage={glossLanguage} copy={copy} />}
              </div>
            )}
          </section>
        )}
        {notice}
      </div>
      {/* No empty foot while the correction is answered on the page (seen at 375 px). */}
      {!readOnly && (!legende.resolved || fix?.resolved) && (
        <div className="rv-foot ct-foot" ref={footRef}>
          {!legende.resolved ? (
            <>
              <p className="ct-foot__hint">{fill(rcopy.try_n, { n: String(legende.tries + 1), max: String(legende.maxTries) })}</p>
              <Action tone="primary" pending={pending === 'caption'} pendingLabel={rcopy.check} disabled={busy || !chosen} onClick={() => chosen && void onAct({ act: 'caption', key: chosen }, 'caption')}>
                {rcopy.check}
              </Action>
            </>
          ) : fix?.resolved ? (
            <Continue props={props} />
          ) : null}
        </div>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// «À toi»
// ---------------------------------------------------------------------------

export function RvPhotoBuild(props: PhotoStepProps) {
  const { view, chrome, glossLanguage, copy, ccopy, pending, readOnly, onAct, notice, footRef } = props;
  const pm = photoMicroCopy(chrome);
  const build = view.build!;
  const [key, setKey] = useState<string | null>(build.picture ?? (build.choices.length === 1 ? build.choices[0].picture.key : null));
  const [seenIndex, setSeenIndex] = useState<number | null>(null);
  const [fact, setFact] = useState<number | null>(null);
  const [text, setText] = useState(build.input === 'frame' && build.frame ? `${build.frame.fr} ` : '');
  useEffect(() => setSeenIndex(null), [key]);
  const busy = readOnly || pending !== null;
  const told = build.proof !== null;
  const choice = build.choices.find((row) => row.picture.key === key) ?? null;

  let composer: React.ReactNode = null;
  let ready = false;
  let send: () => void = () => undefined;
  if (!told) {
    const pictures = (
      <ul className="rb-planche" role="radiogroup" aria-label={pm.build_task_pick}>
        {build.choices.map((row, index) => (
          <li key={row.picture.key} className="rb-planche__item" data-right={row.picture.key === key ? '' : undefined}>
            <RvGalleryPicture picture={asRvPicture(row.picture)} copy={copy} />
            <button type="button" role="radio" className="ct-opt rb-planche__pick" aria-checked={row.picture.key === key} disabled={busy} onClick={() => setKey(row.picture.key)}>
              {fill(pm.picture_n, { n: String(index + 1) })}
            </button>
          </li>
        ))}
      </ul>
    );
    const bank = choice && (
      <div className="ct-tiles" role={build.input === 'tiles' ? 'radiogroup' : undefined} aria-label={pm.build_seen_label}>
        {choice.seen.map((tile, index) =>
          build.input === 'tiles' ? (
            <button key={index} type="button" role="radio" className="ct-tile" aria-checked={seenIndex === index} disabled={busy} onClick={() => setSeenIndex(index)}>
              <span className="ct-tile__fr" lang="fr">
                {tile.fr}
              </span>
              {tile.tr && (
                <span className="ct-tile__tr" lang={glossLanguage}>
                  {tile.tr}
                </span>
              )}
            </button>
          ) : (
            <span key={index} className="ct-tile" data-bank="">
              <span className="ct-tile__fr" lang="fr">
                {tile.fr}
              </span>
              {tile.tr && (
                <span className="ct-tile__tr" lang={glossLanguage}>
                  {tile.tr}
                </span>
              )}
            </span>
          ),
        )}
      </div>
    );
    if (build.input === 'tiles') {
      const built = choice ? a1Caption(choice.picture.kind, seenIndex === null ? null : choice.seen[seenIndex]?.fr ?? null, fact === null ? null : build.facts[fact]?.fr ?? null) : '';
      ready = Boolean(key) && seenIndex !== null && fact !== null;
      send = () => key && void onAct({ act: 'build', key, parts: [seenIndex as number, fact as number] }, 'build');
      composer = (
        <section className="ct-frame rb-build" aria-label={pm.build_label}>
          <p className="ct-hint">{pm.build_task_pick}</p>
          {pictures}
          {choice && (
            <>
              <p className="ct-frame__k">{pm.build_seen_label}</p>
              {bank}
              <p className="ct-frame__k">{pm.build_fact_label}</p>
              <div className="ct-tiles" role="radiogroup" aria-label={pm.build_fact_label}>
                {build.facts.map((tile, index) => (
                  <button key={index} type="button" role="radio" className="ct-tile" aria-checked={fact === index} disabled={busy} onClick={() => setFact(index)}>
                    <span className="ct-tile__fr" lang="fr">
                      {tile.fr}
                    </span>
                    {tile.tr && (
                      <span className="ct-tile__tr" lang={glossLanguage}>
                        {tile.tr}
                      </span>
                    )}
                  </button>
                ))}
              </div>
              <p className="ct-frame__k">
                {ccopy.phrase_label} · <span lang="fr">{build.phrase.fr}</span>
              </p>
              <p className="ct-frame__fr" lang="fr" aria-live="polite" data-built={built ? '' : undefined}>
                {built || '…'}
              </p>
            </>
          )}
        </section>
      );
    } else {
      const count = wordCount(text);
      ready = Boolean(key) && count >= 3 && count <= build.maxWords;
      send = () => key && void onAct({ act: 'build', key, text }, 'build');
      composer = (
        <section className="ct-frame rb-build" data-input={build.input} aria-label={pm.build_label}>
          <p className="ct-hint">{pm.build_task_pick}</p>
          {pictures}
          {choice && (
            <>
              <p className="ct-frame__k">{pm.build_seen_label}</p>
              {bank}
              <p className="ct-frame__k">
                {ccopy.phrase_label} · <span lang="fr">{build.phrase.fr}</span>
              </p>
              <p className="ct-hint">{build.input === 'frame' ? pm.build_task_frame : pm.build_task_free}</p>
              {textAnswerField({ label: pm.build_label, value: text, rows: 3, disabled: busy, onChange: setText })}
              <p className="ct-foot__hint" aria-live="polite">
                {fill(props.rcopy.words_count, { n: String(count), max: String(build.maxWords) })}
              </p>
            </>
          )}
        </section>
      );
    }
  }

  const printedPicture = told ? build.choices.find((row) => row.picture.key === build.picture)?.picture ?? null : null;
  return (
    <>
      <div className="rv-body ct-body" data-step="build" data-input={build.input}>
        <RomyLine line={PM_LINES.build_ask} props={props} past={told} />
        {composer}
        {told && printedPicture && (
          <div className="rb-planche__solo">
            <RvGalleryPicture picture={asRvPicture(printedPicture)} copy={copy} />
          </div>
        )}
        {told && (
          <ProofBlock
            props={props}
            proof={build.proof}
            draftFr={build.draftFr ?? build.learnerFr ?? ''}
            printedFr={build.printedFr}
            marks={build.marks}
            tries={build.tries}
            notes={build.notes}
            tiles={build.input === 'tiles'}
          />
        )}
        {notice}
      </div>
      {!readOnly && (
        <div className="rv-foot ct-foot" ref={footRef}>
          {!told ? (
            <>
              {!ready && <p className="ct-foot__hint">{build.input === 'tiles' ? pm.build_task_tiles : !key ? pm.build_task_pick : ''}</p>}
              <Action tone="primary" pending={pending === 'build'} pendingLabel={pm.build_send} disabled={!ready || busy} onClick={send}>
                {pm.build_send}
              </Action>
            </>
          ) : (
            <ProofFoot
              props={props}
              proof={build.proof}
              draftFr={build.draftFr ?? build.learnerFr ?? ''}
              tries={build.tries}
              maxTries={build.maxTries}
              fixAct="build_fix"
            />
          )}
        </div>
      )}
    </>
  );
}
