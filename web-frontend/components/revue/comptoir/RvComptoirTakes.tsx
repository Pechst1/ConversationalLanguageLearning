/**
 * «Au comptoir» · step 2, «Les avis» (§3 step 2): the counter, then the three
 * regulars' takes revealed one at a time — the first at once, each reaction
 * («d'accord» / «pas d'accord») brings the next. Each bubble: the face (it reacts
 * to yours), the name in their colour, POUR / CONTRE / ÇA DÉPEND, every word
 * tappable, «Traduire», ▶. «Continuer» after the three reactions; the quiet line
 * «3 avis · 1 intox cachée» says what is coming.
 */

import React from 'react';

import { Action } from '@/components/atelier-v2/ui';
import type { FaceMood } from '@/lib/onboarding-portraits';

import { fill } from '../revue-copy';
import { COUNTER_PLATE, REACTIONS_FR, revealedTakes, stepDone } from './comptoir-model';
import { ComptoirBubble, ComptoirPicture, type ComptoirStepProps } from './RvComptoirParts';

/** The face answers the learner's reaction: pleased when agreed with, surprised when not. */
function moodOf(reaction: 'agree' | 'disagree' | null): FaceMood {
  return reaction === 'agree' ? 'happy' : reaction === 'disagree' ? 'surprised' : 'neutral';
}

export function RvComptoirTakes(props: ComptoirStepProps) {
  const { view, copy, ccopy, glossLanguage, glosses, voice, pending, readOnly, onAct, onContinue, wordFor, notice, footRef } = props;
  const shown = view.cast.slice(0, revealedTakes(view.cast));
  const done = stepDone(view, 'takes');
  const hint = fill(view.hasIntox ? ccopy.takes_hint_intox : ccopy.takes_hint, { n: String(view.cast.length) });
  return (
    <>
      <div className="rv-body ct-body" data-step="takes">
        <ComptoirPicture url={COUNTER_PLATE} credit={false} band />
        <ol className="ct-takes">
          {shown.map((member, index) => (
            <li key={member.id} className="ct-takes__row">
              <ComptoirBubble
                castId={member.id}
                name={member.nameFr}
                textFr={member.take.fr}
                translation={member.take.tr}
                stance={member.stance}
                mood={moodOf(member.reaction)}
                glosses={glosses}
                glossLanguage={glossLanguage}
                voice={voice}
                voiceKey={`ct-take-${member.id}`}
                copy={copy}
                ccopy={ccopy}
                onWord={wordFor(member.id, member.nameFr)}
                anchor={index > 0 ? 'nearest' : undefined}
              >
                <div className="ct-react" role="group" aria-label={member.nameFr}>
                  {REACTIONS_FR.map((reaction) => (
                    <button
                      key={reaction.value}
                      type="button"
                      className="ct-react__b"
                      lang="fr"
                      aria-pressed={member.reaction === reaction.value}
                      disabled={readOnly || pending !== null}
                      onClick={() => void onAct({ act: 'react', guestId: member.id, value: reaction.value }, `react-${member.id}`)}
                    >
                      {reaction.fr}
                    </button>
                  ))}
                </div>
              </ComptoirBubble>
            </li>
          ))}
        </ol>
        {!done && <p className="ct-hint">{ccopy.react_hint}</p>}
        {notice}
      </div>
      {!readOnly && (
        <div className="rv-foot ct-foot" ref={footRef}>
          <p className="ct-foot__hint" data-ct-takes-hint="">
            {hint}
          </p>
          <Action tone="primary" disabled={!done || pending !== null} onClick={onContinue}>
            {copy.continue}
          </Action>
        </div>
      )}
    </>
  );
}

export default RvComptoirTakes;
