/**
 * «Papier · le choix» (2026-11-22) · the paper's opening screen as a front page.
 *
 * Up to three stories, the top of pedagogy's ranking (different rubrics where possible), set as
 * a real front page: the masthead, the lead story under its picture at display size, a heavy rule,
 * then the two others side by side across a column rule. Each carries its rubric as the kicker
 * and, in the mother tongue, one honest line of why it is offered (`why`). The whole story is the
 * button: one tap starts it, no screen after.
 */

import React, { useState } from 'react';

import { resolveMediaUrl } from '@/lib/media-url';
import type { RvLanguage, RvStoryCard, RvWeek } from '@/lib/revue-types';

import { PAPIER_FR } from '../papier/papier-copy';
import { PpOpening } from '../papier/PapierPrint';
import type { RevueCopy } from '../revue-copy';
import { capitalised, choixCopy, whyLine, whyParts } from './choix-copy';

export type RvChoixProps = {
  choices: RvStoryCard[];
  week: RvWeek;
  /** The language the `why` lines are said in (the mother tongue). */
  whyLanguage: RvLanguage;
  /** The chrome language (the hint). */
  language: RvLanguage;
  onPick: (dossierId: string) => void;
  /** The story being started (its press shows it). */
  pending?: string | null;
  copy: RevueCopy;
};

function todayIso(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/** The plate, or the hatched blank when it is missing or fails to load. */
function ChoixPicture({ story }: { story: RvStoryCard }) {
  const plate = story.plateUrl ?? story.stage.plateUrl;
  const src = plate ? resolveMediaUrl(plate) ?? plate : null;
  const [failed, setFailed] = useState(false);
  return (
    <span className="pp-choix__pic" aria-hidden="true" data-blank={!src || failed ? '' : undefined}>
      {src && !failed && (
        // eslint-disable-next-line @next/next/no-img-element -- a painted plate, already sized
        <img src={src} alt="" loading="lazy" decoding="async" onError={() => setFailed(true)} />
      )}
    </span>
  );
}

/** The rubric as the kicker; the topic beside it on the lead only (a column keeps one line). */
function Kicker({ story, copy, lead = false }: { story: RvStoryCard; copy: RevueCopy; lead?: boolean }) {
  const topic = copy.topic[story.topic];
  return (
    <span className="pp-choix__kicker">
      {story.assignment ? (
        <>
          <b lang="fr">{story.assignment.nameFr}</b>
          {lead && <span className="pp-choix__topic">{topic}</span>}
        </>
      ) : (
        <b>{topic}</b>
      )}
    </span>
  );
}

/** Why it is offered, in the mother tongue: on the lead each reason on its line and the learner's
 *  own words under them, in French; in a column one line. */
function Why({ story, language, lead = false }: { story: RvStoryCard; language: RvLanguage; lead?: boolean }) {
  const parts = whyParts(story.why, language);
  if (!parts.length) return null;
  const due = lead ? story.why?.dueWords ?? [] : [];
  return (
    <span className="pp-choix__why">
      {lead ? (
        parts.map((part) => (
          <span key={part} lang={language}>
            {capitalised(part)}
          </span>
        ))
      ) : (
        <span lang={language}>{whyLine(story.why, language)}</span>
      )}
      {due.length > 0 && (
        <span className="pp-choix__words" lang="fr">
          {due.join(' · ')}
        </span>
      )}
    </span>
  );
}

export function RvChoix({ choices, week, whyLanguage, language, onPick, pending = null, copy }: RvChoixProps) {
  const [lead, ...rest] = choices.slice(0, 3);
  if (!lead) return null;
  const busy = pending !== null;
  const headline = (story: RvStoryCard) => (story.questionFr && story.assignment?.key === 'comptoir' ? story.questionFr : story.titleFr);
  return (
    <div className="rv-chooser pp-choix" data-choix={choices.length}>
      <PpOpening edition={{ dateIso: todayIso(), weekIso: week.iso }} section={PAPIER_FR.choix_section} step={null} />
      <p className="pp-choix__hint">{choixCopy(language).hint}</p>
      <button
        type="button"
        className="pp-choix__lead"
        data-dossier={lead.dossierId}
        data-pending={pending === lead.dossierId ? '' : undefined}
        disabled={busy}
        onClick={() => onPick(lead.dossierId)}
      >
        <ChoixPicture story={lead} />
        <Kicker story={lead} copy={copy} lead />
        <span className="pp-choix__hl" lang="fr">
          {headline(lead)}
        </span>
        {lead.summaryFr && lead.summaryFr.trim() !== headline(lead).trim() && (
          <span className="pp-choix__stand" lang="fr">
            {lead.summaryFr}
          </span>
        )}
        <Why story={lead} language={whyLanguage} lead />
        <span className="pp-choix__go" lang="fr" aria-hidden="true">
          {PAPIER_FR.choix_read}
        </span>
      </button>
      {rest.length > 0 && (
        <div className="pp-choix__cols" data-n={rest.length}>
          {rest.map((story) => (
            <button
              key={story.dossierId}
              type="button"
              className="pp-choix__col"
              data-dossier={story.dossierId}
              data-pending={pending === story.dossierId ? '' : undefined}
              disabled={busy}
              onClick={() => onPick(story.dossierId)}
            >
              <Kicker story={story} copy={copy} />
              <ChoixPicture story={story} />
              <span className="pp-choix__hl" lang="fr">
                {headline(story)}
              </span>
              <Why story={story} language={whyLanguage} />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default RvChoix;
