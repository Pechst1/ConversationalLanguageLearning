/**
 * «Au comptoir» · step 1, «Lire» (WP-119-AU-COMPTOIR §3 step 1): the story's
 * picture (it scrolls away), «Ce qui s'est passé · <dateline>», the lead at the
 * learner's band with every word tappable, «Traduire», ▶ and the source, then
 * «La question du jour» and the gut vote. «Au comptoir →» once voted; the vote
 * can change until «Ton avis».
 */

import React from 'react';

import { Action, ArrowRightIcon } from '@/components/atelier-v2/ui';

import { RvGlossText, RvSourceLine, RvTranslate } from '../RvThread';
import { COMPTOIR_FR } from './comptoir-copy';
import { GUT_VOTES_FR } from './comptoir-model';
import { ComptoirPicture, ListenChip, type ComptoirStepProps } from './RvComptoirParts';

export function RvComptoirRead(props: ComptoirStepProps) {
  const { session, view, copy, ccopy, glossLanguage, glosses, voice, pending, readOnly, onAct, onContinue, wordFor, notice, footRef } = props;
  const lead = view.read.lead;
  const source = view.read.sources[0] ?? null;
  const voted = view.vote !== null;
  return (
    <>
      <div className="rv-body ct-body" data-step="read">
        <ComptoirPicture url={session.stage.plateUrl} credit={session.stage.plateKind === 'story'} />
        <section className="rv-lead ct-lead" aria-label={copy.lead_kicker}>
          <p className="rv-lead__k">
            {copy.lead_kicker}
            {view.read.datelineFr && (
              <>
                {' · '}
                <span lang="fr">{view.read.datelineFr}</span>
              </>
            )}
          </p>
          <p className="rv-lead__fr" lang="fr">
            <RvGlossText text={lead.fr} glosses={glosses} mode={session.plan.support.glosses} glossLanguage={glossLanguage} onWord={wordFor(null)} />
          </p>
          <RvTranslate
            textFr={lead.fr}
            translation={lead.tr}
            glossLanguage={glossLanguage}
            copy={copy}
            before={<ListenChip voice={voice} voiceKey={`ct-lead-${session.id}`} textFr={lead.fr} castId="romy_tremblay" copy={copy} ccopy={ccopy} />}
          />
          {source && <RvSourceLine source={source} copy={copy} />}
        </section>
        <section className="ct-q" aria-label={COMPTOIR_FR.question_kicker}>
          <p className="ct-q__k" lang="fr">
            {COMPTOIR_FR.question_kicker}
          </p>
          <p className="ct-q__fr" lang="fr">
            <RvGlossText text={view.question.fr} glosses={glosses} mode="tap" glossLanguage={glossLanguage} onWord={wordFor(null)} />
          </p>
          <RvTranslate textFr={view.question.fr} translation={view.question.tr} glossLanguage={glossLanguage} copy={copy} />
          <div className="ct-votes" role="group" aria-label={COMPTOIR_FR.question_kicker}>
            {GUT_VOTES_FR.map((vote) => (
              <button
                key={vote.value}
                type="button"
                className="ct-vote"
                lang="fr"
                data-stance={vote.value}
                aria-pressed={view.vote === vote.value}
                disabled={readOnly || pending !== null}
                onClick={() => void onAct({ act: 'vote', value: vote.value }, 'vote')}
              >
                {vote.fr}
              </button>
            ))}
          </div>
        </section>
        {notice}
      </div>
      {!readOnly && (
        <div className="rv-foot ct-foot" ref={footRef}>
          {!voted && <p className="ct-foot__hint">{ccopy.read_hint}</p>}
          <Action tone="primary" lang="fr" disabled={!voted || pending !== null} iconAfter={<ArrowRightIcon size={18} />} onClick={onContinue}>
            {COMPTOIR_FR.press}
          </Action>
        </div>
      )}
    </>
  );
}

export default RvComptoirRead;
