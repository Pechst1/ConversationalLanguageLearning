/**
 * WP-119 · RvUneCard — the Revue on La Une (design §3.1, open question 1).
 *
 * One recommended story, «Autre sujet ?» opening the sheet with the two
 * alternatives and «Autre chose ?», and the red press under the card. It goes in
 * HomeScreen's `hero` slot as data (with `planHidden`): no change to HomeScreen.
 * WP-81's budget holds (home.test.js): the card drops the place, then the week,
 * then the topic until it fits 18 words beside a 7-word masthead.
 *
 * States: `offer` · `evergreen` (labelled «hors actualité» / «un classique de
 * saison») · `resume` (one clause from the state, «Reprendre avec Romy») ·
 * `filed` (the done square, the made headline with the learner's part, the
 * colophon — no press).
 */

import React from 'react';

import { Action, ArrowRightIcon, ShapeToken } from '@/components/atelier-v2/ui';
import type { RvMade, RvStoryCard, RvWeek } from '@/lib/revue-types';

import { fill, type RevueCopy } from './revue-copy';
import { uneCardParts, wordCount } from './revue-model';
import { RvStage, stageCast } from './RvStage';
import { ContributedText } from './RvThread';

export type RvUneCardState = 'offer' | 'evergreen' | 'resume' | 'filed';

export type RvUneCardProps = {
  story: RvStoryCard;
  week: RvWeek;
  state: RvUneCardState;
  resumeLine?: string | null;
  filed?: { made: RvMade | null; headlineFr?: string } | null;
  onOpen: () => void;
  onOtherSubject: () => void;
  copy: RevueCopy;
};

export function RvUneCard({ story, week, state, resumeLine = null, filed = null, onOpen, onOtherSubject, copy }: RvUneCardProps) {
  if (state === 'filed') {
    const made = filed?.made ?? null;
    const headline = made?.textFr ?? filed?.headlineFr ?? story.titleFr;
    // The same 18-word budget: the week leaves the kicker first, then the colophon.
    const colophon = 'La suite la semaine prochaine.';
    const marks = made?.contribution.length ? 1 : 0;
    const full = fill(copy.filed_kicker, { week: week.label.toLowerCase() });
    const kicker = wordCount(full) + wordCount(headline) + marks + wordCount(colophon) <= 18 ? full : copy.filed_kicker_short;
    const showColophon = wordCount(kicker) + wordCount(headline) + marks + wordCount(colophon) <= 18;
    return (
      <div className="rv-une-hero" data-revue-card="filed">
        <article className="rv-une">
          <div className="rv-une__filed">
            <p className="rv-une__filed-k">
              <ShapeToken kind="done" size="sm" />
              {kicker}
            </p>
            <p className="rv-une__filed-hl" lang="fr">
              <ContributedText text={headline} spans={made?.contribution ?? []} label={copy.contribution} />
            </p>
            {showColophon && (
              <p className="rv-une__colophon" lang="fr">
                {colophon}
              </p>
            )}
          </div>
        </article>
      </div>
    );
  }

  const evergreen = state === 'evergreen' || (state !== 'resume' && story.evergreen);
  const kicker = evergreen ? copy.evergreen_kicker : copy.revue;
  const topic = evergreen ? copy.evergreen_topic : copy.topic[story.topic];
  const press = state === 'resume' ? copy.resume : copy.join;
  const fixed = state === 'resume' ? [press, resumeLine ?? ''] : [press, copy.other_subject];
  const parts = uneCardParts({ title: story.titleFr, kicker, week: week.label, place: story.placeFr, topic, fixed });
  return (
    <div className="rv-une-hero" data-revue-card={state}>
      <article className="rv-une">
        <RvStage plateUrl={story.plateUrl ?? story.stage.plateUrl} size="une" cast={stageCast(story.stage.cast)} still />
        <div className="rv-une__body">
          <div className="rv-une__folio">
            <p className="av2-label av2-label--story">{kicker}</p>
            {parts.showWeek && <p className="av2-label">{week.label}</p>}
          </div>
          <h2 className="rv-une__title" lang="fr">
            {story.titleFr}
          </h2>
          {(parts.showPlace || parts.showTopic) && (
            <p className="rv-une__meta">
              {parts.showPlace && <span lang="fr">{story.placeFr}</span>}
              {parts.showPlace && parts.showTopic && <span className="rv-dot" aria-hidden="true" />}
              {parts.showTopic && <span>{topic}</span>}
            </p>
          )}
          {state === 'resume'
            ? resumeLine && <p className="av2-body">{resumeLine}</p>
            : (
              <Action tone="quiet" inline className="rv-une__other" aria-haspopup="dialog" onClick={onOtherSubject}>
                {copy.other_subject}
              </Action>
            )}
        </div>
      </article>
      <div className="rv-une__press">
        <Action tone="primary" iconAfter={<ArrowRightIcon size={18} />} onClick={onOpen}>
          {press}
        </Action>
      </div>
    </div>
  );
}

export default RvUneCard;
