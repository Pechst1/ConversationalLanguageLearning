/**
 * WP-119 · RvChooser — `/revue`'s first state when the learner comes from the
 * chip (design §3.1 #full, WP-119 §5.1 in full): the recommendation with its
 * plate and the red press inside the card, «Ou bien» and the two alternatives,
 * and «Autre chose ?».
 */

import React from 'react';

import { Action, ArrowRightIcon } from '@/components/atelier-v2/ui';
import type { RvMatchResult, RvStoryCard, RvWeek } from '@/lib/revue-types';

import type { RevueCopy } from './revue-copy';
import { RvStage, stageCast } from './RvStage';
import { RvAltRows, RvAsk } from './RvSubjectSheet';

export type RvChooserProps = {
  recommended: RvStoryCard;
  alternatives: RvStoryCard[];
  week: RvWeek;
  /** `null` = the recommended story, started without a `dossier_id` (`chosen_by: recommended`). */
  onPick: (dossierId: string | null) => void;
  onAsk: (text: string) => Promise<RvMatchResult>;
  pending?: boolean;
  copy: RevueCopy;
};

export function RvChooser({ recommended, alternatives, week, onPick, onAsk, pending = false, copy }: RvChooserProps) {
  return (
    <div className="rv-chooser">
      <p className="rv-kicker" lang="fr">
        {`${copy.revue_full} · ${week.label.toLowerCase()} · ${week.range}`}
      </p>
      <article className="rv-une">
        <RvStage plateUrl={recommended.plateUrl ?? recommended.stage.plateUrl} size="une" cast={stageCast(recommended.stage.cast)} still />
        <div className="rv-une__body">
          <p className="av2-label av2-label--story">{copy.romy_proposes}</p>
          <h2 className="rv-une__title" lang="fr">
            {recommended.titleFr}
          </h2>
          <p className="rv-une__meta">
            <span lang="fr">{recommended.placeFr}</span>
            <span className="rv-dot" aria-hidden="true" />
            <span>{recommended.evergreen ? copy.evergreen_topic : copy.topic[recommended.topic]}</span>
          </p>
          <div style={{ marginTop: 10 }}>
            <Action tone="primary" pending={pending} pendingLabel={copy.join} iconAfter={<ArrowRightIcon size={18} />} onClick={() => onPick(null)}>
              {copy.join}
            </Action>
          </div>
        </div>
      </article>
      {alternatives.length > 0 && <p className="av2-label">{copy.or_else}</p>}
      <RvAltRows stories={alternatives} onPick={(id) => onPick(id)} copy={copy} />
      <RvAsk onAsk={onAsk} onPick={(id) => onPick(id)} copy={copy} />
    </div>
  );
}

export default RvChooser;
