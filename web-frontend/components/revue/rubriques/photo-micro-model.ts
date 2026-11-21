/**
 * «La photo» and «Le micro» · the players' pure model (node-tested): a picture as the gallery
 * prints it, the A1 caption as the server builds it, the refusals said in the right table,
 * what changed after an act (the player brings it into view).
 */

import type { RvMicroView, RvPhotoPicture, RvPhotoView, RvRubriqueError } from '@/lib/revue-rubriques-types';
import type { RvPicture, RvSessionView } from '@/lib/revue-types';

import { fill } from '../revue-copy';
import { PM_REASON_CODES, type PhotoMicroCopy } from './photo-micro-copy';

/** A picture of «La photo» in the gallery's shape (its frame, credit and links print as there). */
export function asRvPicture(picture: RvPhotoPicture): RvPicture {
  return {
    kind: picture.kind,
    url: picture.url,
    width: picture.width,
    height: picture.height,
    altFr: '',
    captionFr: null,
    creditFr: picture.creditFr,
    licence: picture.licence,
    licenceUrl: picture.licenceUrl,
    sourceUrl: picture.sourceUrl,
  };
}

/** A1's caption, as the server builds it: «Sur la photo, on voit {a thing}. {A fact}.» */
export function a1Caption(kind: 'illustration' | 'photo', seen: string | null, fact: string | null): string {
  if (!seen || !fact) return '';
  const opener = kind === 'photo' ? 'Sur la photo, on voit' : 'Sur l’image, on voit';
  const clean = (text: string) => text.trim().replace(/[\s.]+$/, '');
  return `${opener} ${clean(seen)}. ${clean(fact)}.`;
}

/** The refusal's words: a reason from the mother-tongue table, an instruction from the chrome's. */
export function pmErrorText(error: RvRubriqueError, chrome: PhotoMicroCopy, reasons: PhotoMicroCopy): string {
  const table = PM_REASON_CODES.has(error.code) ? reasons : chrome;
  const template = table.errors[error.code] ?? table.errors.too_short;
  return fill(template, { n: String(error.count ?? '') });
}

/** «Question 2 sur 3»: the turn the learner is on (never past the last). */
export function turnNumber(view: Pick<RvMicroView, 'interview'>): number {
  const interview = view.interview;
  if (!interview) return 1;
  return Math.min(interview.spent + 1, interview.total);
}

/** The witness's newest line (a resume shows it first), or null. */
export function lastTurn(view: Pick<RvMicroView, 'interview'>) {
  const turns = view.interview?.turns ?? [];
  return turns.length ? turns[turns.length - 1] : null;
}

/** What changed on screen after an act of «La photo» or «Le micro». */
export function photoMicroProgress(session: Pick<RvSessionView, 'photo' | 'micro' | 'closing'>): string {
  const photo: RvPhotoView | null = session.photo;
  const micro: RvMicroView | null = session.micro;
  const parts: Array<string | number> = [];
  if (photo) {
    parts.push('p', photo.step, photo.planche?.tries ?? '-', photo.planche?.seen?.tries ?? '-');
    parts.push(photo.legende?.tries ?? '-', photo.legende?.fix?.tries ?? '-', photo.build?.proof ?? '-', photo.build?.tries ?? '-');
  }
  if (micro) {
    parts.push('m', micro.step, micro.prepare?.chosen.length ?? '-', micro.interview?.turns.length ?? '-');
    for (const item of micro.notes?.items ?? []) parts.push(`${item.key}${item.tries}${item.resolved ? 'r' : ''}`);
    parts.push(micro.review?.proof ?? '-', micro.review?.tries ?? '-');
  }
  parts.push(session.closing ? 'c' : '');
  return parts.join('|');
}
