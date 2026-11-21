/**
 * WP-119 · RvChooser — `/revue`'s first state when the learner comes from the
 * chip (design §3.1 #full, WP-119 §5.1 in full): the recommendation with its
 * plate and the red press inside the card, «Ou bien» and the two alternatives,
 * and «Autre chose ?». «Au comptoir»: the question of the day in the title's place,
 * the regulars' faces under it, and «Au comptoir →».
 */

import React from 'react';

import { Action, ArrowRightIcon } from '@/components/atelier-v2/ui';
import { resolveMediaUrl } from '@/lib/media-url';
import type { RvMatchResult, RvStoryCard, RvWeek } from '@/lib/revue-types';

import { COMPTOIR_FR } from './comptoir/comptoir-copy';
import { PAPIER_FR } from './papier/papier-copy';
import { PpOpening } from './papier/PapierPrint';
import type { RevueCopy } from './revue-copy';
import { RvStage, stageCast } from './RvStage';
import { RvComptoirFaces } from './RvUneCard';
import { RvAsk } from './RvSubjectSheet';

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

/** Today, as the learner's own day («2026-11-21»). */
function todayIso(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/**
 * «La belle édition»: the other stories of the edition, set as teasers like the lead, smaller —
 * the kicker (the topic), the headline, one line of standfirst, the picture at the right.
 */
function PpAltTeasers({ stories, onPick, copy }: { stories: RvStoryCard[]; onPick: (dossierId: string) => void; copy: RevueCopy }) {
  if (!stories.length) return null;
  return (
    <ul className="pp-alts">
      {stories.map((story) => {
        const plate = story.plateUrl ?? story.stage.plateUrl;
        const src = plate ? resolveMediaUrl(plate) ?? plate : null;
        return (
          <li key={story.dossierId}>
            <button type="button" className="pp-alt rv-alt" data-dossier={story.dossierId} onClick={() => onPick(story.dossierId)}>
              <span>
                <span className="pp-alt__kicker">{story.evergreen ? copy.evergreen_topic : copy.topic[story.topic]}</span>
                <span className="pp-alt__hl" lang="fr">
                  {story.titleFr}
                </span>
                <span className="pp-alt__stand" lang="fr">
                  {story.summaryFr || story.placeFr}
                </span>
              </span>
              <span className="pp-alt__pic" aria-hidden="true">
                {/* eslint-disable-next-line @next/next/no-img-element -- a painted plate, already sized */}
                {src && <img src={src} alt="" loading="lazy" decoding="async" />}
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

export function RvChooser({ recommended, alternatives, week, onPick, onAsk, pending = false, copy }: RvChooserProps) {
  // «Au comptoir»: the question of the day and the faces lead; the story's title is the subject line.
  const comptoir = Boolean(recommended.questionFr && recommended.cast?.length);
  const press = comptoir ? COMPTOIR_FR.press : copy.join;
  const today = todayIso();
  return (
    <div className="rv-chooser">
      {/* «La belle édition» (2026-11-21): entering Le Papier opens today's paper — the masthead, its
          rule, the dateline; the week stays said for screen readers and in the Une's edition line. */}
      <PpOpening edition={{ dateIso: today, weekIso: week.iso }} section={PAPIER_FR.edition_today} step={week.range} />
      <p className="av2-sr" lang="fr">
        {`${copy.revue_full} · ${week.label.toLowerCase()} · ${week.range}`}
      </p>
      <article className="rv-une">
        <RvStage plateUrl={recommended.plateUrl ?? recommended.stage.plateUrl} size="une" cast={stageCast(recommended.stage.cast)} still />
        <div className="rv-une__body">
          <p className="av2-label av2-label--story" lang={comptoir ? 'fr' : undefined}>
            {comptoir ? COMPTOIR_FR.question_kicker : copy.romy_proposes}
          </p>
          <h2 className="rv-une__title" lang="fr">
            {comptoir && recommended.questionFr ? recommended.questionFr : recommended.titleFr}
          </h2>
          {recommended.summaryFr && recommended.summaryFr.trim() !== recommended.titleFr.trim() && (
            <p className="pp-teaser__stand" lang="fr">
              {recommended.summaryFr}
            </p>
          )}
          {comptoir && recommended.cast && <RvComptoirFaces cast={recommended.cast} copy={copy} />}
          {recommended.assignment && (
            <p className="rv-une__meta rv-une__assignment" data-assignment={recommended.assignment.key}>
              {copy.assignment_label} · <strong lang="fr">{recommended.assignment.nameFr}</strong>
            </p>
          )}
          <p className="rv-une__meta">
            <span lang="fr">{recommended.placeFr}</span>
            <span className="rv-dot" aria-hidden="true" />
            <span>{recommended.evergreen ? copy.evergreen_topic : copy.topic[recommended.topic]}</span>
          </p>
          <div style={{ marginTop: 10 }}>
            <Action
              tone="primary"
              lang={comptoir ? 'fr' : undefined}
              pending={pending}
              pendingLabel={press}
              iconAfter={<ArrowRightIcon size={18} />}
              onClick={() => onPick(null)}
            >
              {press}
            </Action>
          </div>
        </div>
      </article>
      {alternatives.length > 0 && <p className="pp-alts__k">{copy.or_else}</p>}
      <PpAltTeasers stories={alternatives} onPick={(id) => onPick(id)} copy={copy} />
      <RvAsk onAsk={onAsk} onPick={(id) => onPick(id)} copy={copy} />
    </div>
  );
}

export default RvChooser;
