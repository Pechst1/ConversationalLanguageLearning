/**
 * WP-119 §8.4 · RvPicture — the story's own picture, printed like a press photograph.
 *
 * The house print (the same risograph screen print as the plates, painted once at the
 * morning intake for every learner) in a hairline frame at the painter's 3:2, the caption
 * under it on an ink rule (Garamond italic, the learner's words marked «toi», never colour
 * alone), and the credit «Illustration · Le Papier»: it is an illustration, never a
 * photograph, and it says so.
 *
 * The caption: `captionFr` printed; `draft` prints it grey (the learner's caption as they
 * write it, or the pick on its way); none is a dotted blank line, the caption still to
 * find («La légende»). A caption that arrives is inked in (240 ms, none under Reduce
 * Motion). The picture itself is decorative (`alt=""`): Romy's «Regarde» line says what it
 * shows, and the caption is the task.
 *
 * Three places print it the same way: «La légende» (`RvCaption`), the dispatch at the
 * close, and Le Relevé.
 */

import React, { useState } from 'react';

import { resolveMediaUrl } from '@/lib/media-url';
import type { RvSpan } from '@/lib/revue-types';

import type { RevueCopy } from './revue-copy';
import { ContributedText } from './RvThread';

/** The credit is the publication's, French in every chrome language (design §5). */
export const PICTURE_CREDIT_FR = 'Illustration · Le Papier';

export type RvPictureProps = {
  url: string;
  captionFr?: string | null;
  /** The learner's part of the caption («toi»). */
  contribution?: RvSpan[];
  /** The caption is not filed yet: printed grey. */
  draft?: boolean;
  size?: 'full' | 'small';
  copy: RevueCopy;
};

export function RvPicture({ url, captionFr = null, contribution = [], draft = false, size = 'full', copy }: RvPictureProps) {
  const [failed, setFailed] = useState(false);
  const src = resolveMediaUrl(url) ?? url;
  const caption = (captionFr ?? '').trim();
  return (
    <figure className="rv-picture" data-size={size} data-picture="">
      <div className="rv-picture__frame">
        {!failed && (
          // eslint-disable-next-line @next/next/no-img-element -- a painted print, already sized
          <img className="rv-picture__img" src={src} alt="" decoding="async" onError={() => setFailed(true)} />
        )}
      </div>
      <figcaption className="rv-picture__cap">
        {caption ? (
          <span key={draft ? 'draft' : caption} className="rv-picture__fr" lang="fr" data-draft={draft ? '' : undefined}>
            {draft ? caption : <ContributedText text={caption} spans={contribution} label={copy.contribution} />}
          </span>
        ) : (
          <span className="rv-picture__blank" aria-hidden="true" />
        )}
        <span className="rv-picture__credit" lang="fr">
          {PICTURE_CREDIT_FR}
        </span>
      </figcaption>
    </figure>
  );
}

export default RvPicture;
