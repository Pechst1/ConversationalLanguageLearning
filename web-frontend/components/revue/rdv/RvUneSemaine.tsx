/**
 * «La une de la semaine» (2026-11-21, `REVUE_UNE_ENABLED`): a front page composed ONLY from what
 * the learner filed that week, as the server composed it (`app/services/revue/une.py`: printed
 * text only, a «Le titre» leads, then the longest piece).
 *
 * Plain semantic structure — masthead (`header`), dateline, one `article` per piece, the
 * «Lexique», the count line — and almost no CSS: the Papier's print art direction (the shared
 * «print» components) styles it afterwards. French for what the paper prints; the count line and
 * the empty state in the chrome language.
 */

import React from 'react';

import { resolveMediaUrl } from '@/lib/media-url';
import type { RvLanguage } from '@/lib/revue-types';
import type { RvUneItem, RvUneSemaine as RvUneSemaineData } from '@/lib/revue-rdv';

import { RDV_FR, countLine, fillRdv, rdvCopy, type RdvCopy } from './rdv-copy';
import { uneCount } from './rdv-model';

function Picture({ item }: { item: RvUneItem }) {
  if (!item.picture) return null;
  const src = resolveMediaUrl(item.picture.url) ?? item.picture.url;
  return (
    <figure className="une-item__fig">
      {/* eslint-disable-next-line @next/next/no-img-element -- a story picture, already sized */}
      <img src={src} alt={item.picture.altFr} loading="lazy" decoding="async" />
      <figcaption lang="fr">
        {item.role === 'caption' ? <span className="une-item__mine">{item.textFr}</span> : null}
        <small className="une-item__credit">{item.picture.creditFr}</small>
      </figcaption>
    </figure>
  );
}

function Item({ item, lead, copy }: { item: RvUneItem; lead: boolean; copy: RdvCopy }) {
  const Heading = lead ? 'h2' : 'h3';
  const kicker = `${RDV_FR.rubriques[item.rubrique]} · ${item.filedWeekdayFr}`;
  return (
    <article className="une-item" data-role={item.role} data-lead={lead ? '' : undefined} lang="fr">
      <p className="une-item__k">{kicker}</p>
      {item.role === 'headline' ? (
        <>
          <Heading className="une-item__hl">{item.textFr}</Heading>
          <p className="une-item__story">{item.storyTitleFr}</p>
        </>
      ) : (
        <Heading className="une-item__hl">{item.storyTitleFr}</Heading>
      )}
      <Picture item={item} />
      {item.role === 'vox' && (
        <blockquote className="une-item__vox">
          <p>« {item.textFr} »</p>
          <footer>
            {RDV_FR.toi}
            {item.stance ? ` · ${RDV_FR.stance[item.stance]}` : ''}
          </footer>
        </blockquote>
      )}
      {item.role === 'quote' && (
        <blockquote className="une-item__quote">
          <p>« {item.textFr} »</p>
        </blockquote>
      )}
      {item.role === 'brief' && <p className="une-item__brief">{item.textFr}</p>}
      {item.role === 'rectificatif' && (
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
      )}
    </article>
  );
}

export function RvUneSemaine({ une, language }: { une: RvUneSemaineData; language: RvLanguage }) {
  const copy = rdvCopy(language);
  return (
    <div className="une" data-une-week={une.week.iso}>
      <header className="une__mast">
        <h1 className="une__title" lang="fr">
          {RDV_FR.une_title}
        </h1>
        <p className="une__dateline" lang="fr">
          {une.datelineFr}
        </p>
        <p className="une__count">
          {uneCount(copy, une.rubriquesFiled, une.rubriquesTotal)} · {countLine(copy, 'une_pieces', une.pieces)}
        </p>
      </header>
      {une.items.length === 0 ? (
        <p className="une__empty">{copy.une_empty}</p>
      ) : (
        <div className="une__items">
          {une.items.map((item, index) => (
            <Item key={item.sessionId} item={item} lead={index === 0} copy={copy} />
          ))}
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
    </div>
  );
}

export default RvUneSemaine;
