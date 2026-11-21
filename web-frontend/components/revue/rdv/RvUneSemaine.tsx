/**
 * «La une de la semaine» (2026-11-21, `REVUE_UNE_ENABLED`): a front page composed ONLY from what
 * the learner filed that week, as the server composed it (`app/services/revue/une.py`: printed
 * text only, a «Le titre» leads, then the longest piece).
 *
 * «La belle édition» (2026-11-21): the same front page as «La page» — the masthead «Le Papier»,
 * «ÉDITION DE LA SEMAINE · Nº 47» between its rules, the lead at display size with its picture
 * (credit always printed), the first opinion or interview lifted as the pull quote, the other
 * pieces in a ruled column with their rubrique as kicker and «Par toi» signed in red, briefs
 * when there are many, the week's Lexique, and the count line as the page's footer rule
 * (`uneLayout`: no hole for 1, 2, 3–4 or 5–6 pieces). French for what the paper prints; the
 * count line and the empty state in the chrome language.
 */

import React from 'react';

import type { RvLanguage } from '@/lib/revue-types';
import type { RvUneItem, RvUneSemaine as RvUneSemaineData } from '@/lib/revue-rdv';

import { PAPIER_FR } from '../papier/papier-copy';
import { PpByline, PpDateline, PpFigure, PpLead, PpLinks } from '../papier/PapierPrint';
import { revueCopy } from '../revue-copy';
import { pictureLinks } from '../revue-gallery';
import { RDV_FR, countLine, fillRdv, rdvCopy, type RdvCopy } from './rdv-copy';
import { uneCount, uneLayout } from './rdv-model';

/** How the learner's piece is signed, by what it is (French, as printed). */
function bylineOf(item: RvUneItem): string {
  if (item.role === 'rectificatif') return PAPIER_FR.checked_by_you;
  if (item.role === 'quote') return PAPIER_FR.interview_by_you;
  if (item.role === 'caption') return PAPIER_FR.legende_by;
  if (item.role === 'vox' && item.stance) return `${PAPIER_FR.by_you} · ${RDV_FR.stance[item.stance]}`;
  return PAPIER_FR.by_you;
}

/** The week range of the dateline («du 16 au 22 nov.»): the edition's number is printed beside it already. */
function rangeOf(datelineFr: string): string {
  return datelineFr.replace(/^Semaine\s+\d+\s*·\s*/i, '').trim();
}

function Picture({ item, language, lead }: { item: RvUneItem; language: RvLanguage; lead: boolean }) {
  if (!item.picture) return null;
  const copy = revueCopy(language);
  return (
    <div className="une-item__fig">
      <PpFigure
        picture={{ url: item.picture.url, creditFr: item.picture.creditFr }}
        ratio={lead ? 'page' : 'wide'}
        alt={item.picture.altFr}
        legend={
          item.role === 'caption' ? (
            <span className="pp-legend">
              <span className="pp-legend__fr une-item__mine">{item.textFr}</span>
            </span>
          ) : null
        }
        links={<PpLinks links={pictureLinks(item.picture, copy)} newTab={copy.new_tab} />}
      />
    </div>
  );
}

/** The piece's body: the learner's printed words, set by what they are. */
function Body({ item, lead, copy }: { item: RvUneItem; lead: boolean; copy: RdvCopy }) {
  switch (item.role) {
    case 'headline':
      return <p className="une-item__story">{item.storyTitleFr}</p>;
    case 'vox':
      return (
        <blockquote className="une-item__vox">
          <p>« {item.textFr} »</p>
        </blockquote>
      );
    case 'quote':
      return (
        <blockquote className="une-item__quote">
          <p>« {item.textFr} »</p>
        </blockquote>
      );
    case 'brief':
      return lead ? <PpLead text={item.textFr} className="une-item__brief pp-front__lead" /> : <p className="une-item__brief">{item.textFr}</p>;
    case 'rectificatif':
      return (
        <>
          <p className="une-item__score">{fillRdv(RDV_FR.score, { score: item.score ?? 0, total: item.total ?? 5 })}</p>
          {item.correctionsFr.length > 0 && (
            <ul className="une-item__fixes" aria-label={copy.une_rectified}>
              {item.correctionsFr.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          )}
        </>
      );
    default:
      return null;
  }
}

function Item({ item, place, copy, language }: { item: RvUneItem; place: 'lead' | 'column' | 'brief'; copy: RdvCopy; language: RvLanguage }) {
  const lead = place === 'lead';
  const Heading = lead ? 'h2' : 'h3';
  const kicker = `${RDV_FR.rubriques[item.rubrique]} · ${item.filedWeekdayFr}`;
  return (
    <article className="une-item" data-role={item.role} data-lead={lead ? '' : undefined} data-place={place} lang="fr">
      <p className="une-item__k">{kicker}</p>
      <Heading className="une-item__hl">{item.role === 'headline' ? item.textFr : item.storyTitleFr}</Heading>
      {item.role === 'headline' && <Body item={item} lead={lead} copy={copy} />}
      {/* A headline is signed under it, as a byline is; the other pieces after their words. */}
      {item.role === 'headline' && <PpByline text={bylineOf(item)} still />}
      {place !== 'brief' && <Picture item={item} language={language} lead={lead} />}
      {place === 'brief' && item.role === 'caption' ? <p className="une-item__brief">{item.textFr}</p> : item.role !== 'headline' && <Body item={item} lead={lead} copy={copy} />}
      {place === 'brief' && item.picture && <p className="une-item__credit">{item.picture.creditFr}</p>}
      {item.role !== 'headline' && <PpByline text={bylineOf(item)} still />}
    </article>
  );
}

/** The opinion or the interview, lifted out of the page as its pull quote (and signed). */
function Pull({ item }: { item: RvUneItem }) {
  const kicker = `${RDV_FR.rubriques[item.rubrique]} · ${item.filedWeekdayFr}`;
  return (
    <article className="une-item" data-role={item.role} data-pull="" lang="fr">
      <p className="une-item__k">{kicker}</p>
      <figure className="pp-pull une-item__pull" data-long={item.textFr.length > 90 ? '' : undefined}>
        <blockquote className="pp-pull__fr">{item.textFr}</blockquote>
        <figcaption className="pp-pull__by">
          <PpByline text={bylineOf(item)} still />
          <span className="une-item__about">{item.storyTitleFr}</span>
        </figcaption>
      </figure>
    </article>
  );
}

export function RvUneSemaine({ une, language }: { une: RvUneSemaineData; language: RvLanguage }) {
  const copy = rdvCopy(language);
  const layout = uneLayout(une.items);
  const count = `${uneCount(copy, une.rubriquesFiled, une.rubriquesTotal)} · ${countLine(copy, 'une_pieces', une.pieces)}`;
  const range = rangeOf(une.datelineFr);
  return (
    <div className="une pp-une" data-une-week={une.week.iso} data-count={une.items.length}>
      <header className="une__mast">
        <h1 className="av2-sr" lang="fr">
          {RDV_FR.une_title}
        </h1>
        <p className="pp-front__title" lang="fr" aria-hidden="true">
          {PAPIER_FR.masthead}
        </p>
        <p className="pp-dateline pp-front__date une__dateline" lang="fr">
          {PAPIER_FR.edition_week}
          <span className="pp-dateline__dot" aria-hidden="true">
            {' · '}
          </span>
          {`Nº ${une.week.iso.replace(/^\d{4}-W0?/, '')}`}
        </p>
        {range && (
          <p className="une__range" lang="fr">
            {range}
          </p>
        )}
      </header>
      {une.items.length === 0 ? (
        <p className="une__empty">{copy.une_empty}</p>
      ) : (
        <div className="une__items">
          {layout.lead && <Item item={layout.lead} place="lead" copy={copy} language={language} />}
          {layout.pull && <Pull item={layout.pull} />}
          {layout.column.length > 0 && (
            <div className="une__col" data-n={layout.column.length}>
              {layout.column.map((item) => (
                <Item key={item.sessionId} item={item} place="column" copy={copy} language={language} />
              ))}
            </div>
          )}
          {layout.briefs.length > 0 && (
            <div className="une__briefs" data-n={layout.briefs.length}>
              {layout.briefs.map((item) => (
                <Item key={item.sessionId} item={item} place="brief" copy={copy} language={language} />
              ))}
            </div>
          )}
        </div>
      )}
      {une.lexique.length > 0 && (
        <section className="une__lexique" aria-labelledby="une-lexique" lang="fr">
          <h2 id="une-lexique">{RDV_FR.lexique}</h2>
          <ul>
            {une.lexique.map((word) => (
              <li key={word}>{word}</li>
            ))}
          </ul>
        </section>
      )}
      <p className="une__count">{count}</p>
    </div>
  );
}

export default RvUneSemaine;
