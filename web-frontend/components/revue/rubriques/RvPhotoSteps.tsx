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
import { resolveMediaUrl } from '@/lib/media-url';
import type { RvPhotoView } from '@/lib/revue-rubriques-types';

import { RomyLine } from '../comptoir/RvComptoirParts';
import { papierCopy } from '../papier/papier-copy';
import { PpDeleatur, PpFigure, PpLinks, PpPencilLoop, PpSheet, PpStet, type PpFrame } from '../papier/PapierPrint';
import { fill } from '../revue-copy';
import { pictureLinks } from '../revue-gallery';
import { RvTranslate } from '../RvThread';
import type { RvPhotoPicture } from '@/lib/revue-rubriques-types';
import { photoMicroCopy, PM_LINES } from './photo-micro-copy';
import { a1Caption, asRvPicture } from './photo-micro-model';
import { ProofBlock, ProofFoot } from './RvProofBlock';
import { toggle, wordCount } from './rubriques-model';
import { FrLine, type RubriqueStepProps } from './RvRubriqueParts';

export type PhotoStepProps = RubriqueStepProps & { view: RvPhotoView };

/** The caption with its wrong fact struck through with the proofreader's delete mark. */
function struck(text: string, wrong: string): React.ReactNode {
  const at = wrong ? text.toLowerCase().indexOf(wrong.toLowerCase()) : -1;
  if (at < 0) return text;
  return (
    <>
      {text.slice(0, at)}
      <s className="ct-strike pp-wrong">
        {text.slice(at, at + wrong.length)}
        <PpDeleatur />
      </s>
      {text.slice(at + wrong.length)}
    </>
  );
}

/** A picture of the desk as a frame of the contact sheet (its credit and licence links with it). */
function frameOf(picture: RvPhotoPicture, copy: PhotoStepProps['copy']): PpFrame {
  return {
    key: picture.key,
    url: picture.url,
    creditFr: picture.creditFr,
    links: <PpLinks links={pictureLinks(asRvPicture(picture), copy)} newTab={copy.new_tab} />,
  };
}

/** A picture printed large in its press frame, its credit and licence under it. */
function Print({ picture, copy, legend = null }: { picture: RvPhotoPicture; copy: PhotoStepProps['copy']; legend?: React.ReactNode }) {
  return (
    <PpFigure
      picture={{ url: picture.url, creditFr: picture.creditFr }}
      ratio="wide"
      legend={legend}
      links={<PpLinks links={pictureLinks(asRvPicture(picture), copy)} newTab={copy.new_tab} />}
    />
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
  const { session, view, chrome, glossLanguage, copy, pending, readOnly, onAct, notice, footRef, rcopy } = props;
  const pm = photoMicroCopy(chrome);
  const px = photoMicroCopy(glossLanguage);
  const pcopy = papierCopy(chrome);
  const planche = view.planche!;
  const seen = planche.seen;
  const [chosen, setChosen] = useState<string | null>(null);
  const [taps, setTaps] = useState<number[]>([]);
  useEffect(() => setChosen(null), [planche.tries]);
  useEffect(() => setTaps([]), [seen?.tries]);
  const busy = readOnly || pending !== null;
  const lit = seen?.resolved ? seen.solution : taps;
  const shows = planche.shows.map((t) => t.tr ?? t.fr).join(', ');
  const refused = planche.picked.filter((key) => key !== planche.solution);
  const print = planche.resolved ? planche.pictures.find((picture) => picture.key === planche.solution) ?? null : null;
  const label = (word: NonNullable<typeof seen>['words'][number], pinned: boolean) => (
    <button
      key={word.index}
      type="button"
      className="rb-seen__w pp-label"
      lang="fr"
      aria-pressed={pinned}
      data-wrong={!seen!.resolved && seen!.elsewhere.includes(word.index) && taps.length === 0 ? '' : undefined}
      disabled={busy || seen!.resolved}
      onClick={() => setTaps((current) => toggle(current, word.index))}
    >
      {word.text.fr}
    </button>
  );
  return (
    <>
      <div className="rv-body ct-body" data-step="planche">
        <RomyLine line={PM_LINES.planche_ask} props={props} past={planche.resolved} />
        {/* The day's headline, pinned over the sheet as the slug the picture must go with. */}
        <div className="pp-slugline">
          <p className="pp-slugline__k">{pm.planche_headline}</p>
          <p className="rb-line__fr rb-headline pp-slugline__hl" lang="fr">
            {planche.headlineFr}
          </p>
        </div>
        {!planche.resolved && <p className="ct-hint">{pm.planche_task}</p>}
        <PpSheet
          frames={planche.pictures.map((picture) => frameOf(picture, copy))}
          seed={session.id}
          label={pcopy.contact_sheet_aria}
          frameLabel={(n) => fill(pm.picture_n, { n: String(n) })}
          chosen={planche.resolved ? null : chosen}
          tried={refused}
          right={planche.resolved ? planche.solution : null}
          disabled={(key) => busy || planche.resolved || refused.includes(key)}
          onPick={setChosen}
          still={readOnly}
          pickLabel={planche.resolved ? pcopy.kept : pcopy.your_pick}
          refusedLabel={pcopy.refused}
        />
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
          <section className="pp-pinboard" aria-label={pm.seen_task}>
            <RomyLine line={PM_LINES.seen_ask} props={props} past={seen.resolved} />
            {!seen.resolved && <p className="ct-hint">{pm.seen_task}</p>}
            {/* «Qu'est-ce qu'on voit ?»: small caption labels, pinned on the print when tapped. */}
            <div className="pp-print" data-ct-anchor={seen.tries > 0 || seen.resolved ? undefined : 'nearest'}>
              {print && (
                <div className="pp-print__frame">
                  {/* eslint-disable-next-line @next/next/no-img-element -- the picture just chosen, already sized */}
                  <img src={resolveMediaUrl(print.url) ?? print.url} alt="" decoding="async" referrerPolicy="no-referrer" />
                </div>
              )}
              <p className="pp-pins" role="group" aria-label={pm.seen_task} data-empty={lit.length ? undefined : ''}>
                {seen.words.filter((word) => lit.includes(word.index)).map((word) => label(word, true))}
              </p>
            </div>
            <p className="pp-labels" role="group" aria-label={pm.seen_task}>
              {seen.words.filter((word) => !lit.includes(word.index)).map((word) => label(word, false))}
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
  const { session, view, chrome, glossLanguage, copy, pending, readOnly, onAct, notice, footRef, rcopy } = props;
  const pm = photoMicroCopy(chrome);
  const pcopy = papierCopy(chrome);
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
        {/* The print, then its three captions set as caption proofs under it. */}
        <div className="pp-captioned">
          <Print picture={legende.picture} copy={copy} />
          {!legende.resolved && <p className="ct-hint">{pm.legende_task}</p>}
          <ol className="fl-strips rb-heads pp-captions" role="radiogroup" aria-label={pm.legende_task}>
            {legende.captions.map((caption) => {
              const tried = legende.picked.includes(caption.key) && caption.key !== legende.solution;
              const wrong = legende.resolved && caption.key === legende.solution;
              const picked = chosen === caption.key && !tried;
              return (
                <li key={caption.key} className="fl-strip rb-head pp-caption" data-tried={tried ? '' : undefined} data-honest={wrong ? '' : undefined} data-role={caption.role ?? undefined}>
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
                    {wrong && fix ? (
                      // Found: the wrong fact struck with the proofreader's delete mark, the loop kept round it.
                      <div className="rb-line">
                        <p className="fl-strip__fr" lang="fr">
                          {struck(caption.text.fr, fix.wrongFr)}
                          <PpPencilLoop seed={`${session.id}:${caption.key}`} label={pcopy.your_pick} still />
                        </p>
                      </div>
                    ) : (
                      <FrLine
                        text={caption.text}
                        props={props}
                        className="fl-strip__fr"
                        inSet
                        overlay={
                          picked || wrong ? (
                            <PpPencilLoop seed={`${session.id}:${caption.key}`} label={pcopy.your_pick} still={readOnly} />
                          ) : tried && caption.role === 'right' ? (
                            // Suspected, but it stands: the proofreader's «stet».
                            <PpStet label={pcopy.stet} />
                          ) : null
                          // A refused caption (it belongs to the other picture) is struck line by line in
                          // the CSS: a caption runs to three lines, the block slash is for headlines.
                        }
                      />
                    )}
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
        </div>
        {legende.resolved && (
          <p className="ct-why" data-ct-anchor={fix && fix.tries === 0 ? 'nearest' : undefined}>
            {legende.correct ? pm.legende_found : pm.legende_shown}
          </p>
        )}
        {fix && (
          <section className="ct-frame rb-fix" aria-label={pm.fix_label} data-resolved={fix.resolved ? '' : undefined}>
            <RomyLine line={PM_LINES.fix_ask} props={props} past={fix.resolved} />
            <p className="rb-line__fr pp-caption-proof" lang="fr">
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
  const { session, view, chrome, glossLanguage, copy, ccopy, pending, readOnly, onAct, notice, footRef } = props;
  const pm = photoMicroCopy(chrome);
  const pcopy = papierCopy(chrome);
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
      <PpSheet
        frames={build.choices.map((row) => frameOf(row.picture, copy))}
        seed={`${session.id}:build`}
        label={pm.build_task_pick}
        frameLabel={(n) => fill(pm.picture_n, { n: String(n) })}
        chosen={key}
        disabled={() => busy}
        onPick={setKey}
        still={readOnly}
        pickLabel={pcopy.your_pick}
      />
    );
    // The learner's caption, set under the print as they write it.
    const live = (caption: string) =>
      choice && (
        <Print
          picture={choice.picture}
          copy={copy}
          legend={
            <span className="pp-legend" data-live="" aria-live="polite">
              <span className="pp-legend__k" lang={chrome}>
                {pcopy.legend_live}
              </span>
              <span className="pp-legend__fr" lang="fr" data-empty={caption.trim() ? undefined : ''}>
                {caption.trim() || pcopy.legend_empty}
              </span>
            </span>
          }
        />
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
        <section className="rb-build pp-desk" aria-label={pm.build_label}>
          <p className="ct-hint">{pm.build_task_pick}</p>
          {pictures}
          {choice && (
            <>
              {live(built)}
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
            </>
          )}
        </section>
      );
    } else {
      const count = wordCount(text);
      ready = Boolean(key) && count >= 3 && count <= build.maxWords;
      send = () => key && void onAct({ act: 'build', key, text }, 'build');
      composer = (
        <section className="rb-build pp-desk" data-input={build.input} aria-label={pm.build_label}>
          <p className="ct-hint">{pm.build_task_pick}</p>
          {pictures}
          {choice && (
            <>
              {live(text)}
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
        {told && printedPicture && <Print picture={printedPicture} copy={copy} />}
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
