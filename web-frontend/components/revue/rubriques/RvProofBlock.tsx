/**
 * «La photo» and «Le micro» · Romy's edit on screen, shared: the learner's French with her marks
 * (each opens its rule in the mother tongue with «Le pourquoi» on, never the answer), the fix
 * first (two tries, then «Corrige-le, Romy»), then the French as it prints with the settled
 * notes. The same pieces as «Le titre»'s «À toi» (RvProofMarks, RvProofNotes, RvComposer).
 */

import React from 'react';

import { Action } from '@/components/atelier-v2/ui';
import type { RvComptoirMark, RvComptoirNote, RvComptoirProof } from '@/lib/revue-types';

import { COMPTOIR_FR, COMPTOIR_LINES, inPaperLabel, unreadLine } from '../comptoir/comptoir-copy';
import { wordDiff } from '../comptoir/comptoir-model';
import { RomyLine } from '../comptoir/RvComptoirParts';
import { RvProofMarks } from '../comptoir/RvProofMarks';
import { RvProofNotes } from '../comptoir/RvProofNotes';
import { fill } from '../revue-copy';
import { RvComposer } from '../RvComposer';
import { RvTranslate } from '../RvThread';
import type { RubriqueStepProps } from './RvRubriqueParts';

export function ProofBlock({
  props,
  proof,
  draftFr,
  printedFr,
  marks,
  tries,
  notes,
  tiles,
}: {
  props: RubriqueStepProps;
  proof: RvComptoirProof | null;
  draftFr: string;
  printedFr: string | null;
  marks: RvComptoirMark[];
  tries: number;
  notes?: RvComptoirNote[];
  tiles: boolean;
}) {
  const { ccopy, copy, glossLanguage } = props;
  if (!proof) return null;
  if (proof === 'marked') {
    return (
      <>
        <RomyLine line={COMPTOIR_LINES.proof_marked} props={props} anchor="start" />
        <section className="ct-paper" data-proof="marked" aria-label={COMPTOIR_FR.proof_marked}>
          <p className="ct-paper__k" lang="fr">
            {COMPTOIR_FR.proof_marked}
          </p>
          <RvProofMarks key={`marks-${tries}`} draftFr={draftFr} marks={marks} kindLabels={ccopy.mark_kinds} copy={ccopy.pourquoi} whyLanguage={glossLanguage} idPrefix="pm" />
        </section>
      </>
    );
  }
  const printed = printedFr ?? draftFr;
  const label = inPaperLabel(proof, tiles);
  const paper = (
    <section className="ct-paper" data-ct-anchor="start" data-proof={proof} aria-label={label}>
      <p className="ct-paper__k" lang="fr">
        {label}
      </p>
      <p className="ct-paper__fr" lang="fr">
        {proof === 'corrected'
          ? wordDiff(draftFr, printed).map((segment, index) =>
              segment.changed ? (
                <mark key={index} className="ct-fix">
                  {segment.text}
                </mark>
              ) : (
                <React.Fragment key={index}>{segment.text}</React.Fragment>
              ),
            )
          : printed}
      </p>
      <RvTranslate textFr={printed} glossLanguage={glossLanguage} copy={copy} />
      <RvProofNotes notes={notes} kindLabels={ccopy.mark_kinds} copy={ccopy.pourquoi} whyLanguage={glossLanguage} />
    </section>
  );
  const unread = unreadLine(proof, tiles);
  return unread ? (
    <>
      <RomyLine line={unread} props={props} anchor="start" />
      {paper}
    </>
  ) : (
    paper
  );
}

export function ProofFoot({
  props,
  proof,
  draftFr,
  tries,
  maxTries,
  fixAct,
}: {
  props: RubriqueStepProps;
  proof: RvComptoirProof | null;
  draftFr: string;
  tries: number;
  maxTries: number;
  fixAct: 'build_fix' | 'review_fix';
}) {
  const { ccopy, copy, pending, readOnly, onAct, onContinue } = props;
  const busy = readOnly || pending !== null;
  if (proof === 'marked') {
    const tryNumber = Math.min(tries + 1, maxTries);
    return (
      <>
        <p className="ct-foot__hint">{fill(ccopy.fix_try, { n: String(tryNumber), max: String(maxTries) })}</p>
        <RvComposer
          key={`fix-${tries}`}
          initial={draftFr}
          label={ccopy.fix_label}
          placeholder={ccopy.fix_placeholder}
          disabled={busy}
          onSend={(value, how) =>
            void onAct(fixAct === 'build_fix' ? { act: 'build_fix', text: value, mode: how } : { act: 'review_fix', text: value, mode: how }, 'fix')
          }
          copy={copy}
        />
        {tries >= 1 && (
          <Action tone="quiet" pending={pending === 'romy'} pendingLabel={ccopy.fix_romy} disabled={busy} onClick={() => void onAct(fixAct === 'build_fix' ? { act: 'build_fix', value: 'romy' } : { act: 'review_fix', value: 'romy' }, 'romy')}>
            {ccopy.fix_romy}
          </Action>
        )}
      </>
    );
  }
  return (
    <Action tone="primary" pending={pending === 'close'} pendingLabel={ccopy.see_page} disabled={busy} onClick={onContinue}>
      {ccopy.see_page}
    </Action>
  );
}
