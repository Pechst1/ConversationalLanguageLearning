/**
 * «Papier · photos» (2026-11-20) · RvGallery — the story's other pictures, as a strip.
 *
 * The first picture stays where it was (the stage's plate, the «Lire» picture); the
 * others follow in a horizontal strip that scrolls on its own (never the page), each
 * printed the way RvPicture prints the story's picture: a hairline frame, an ink rule,
 * the credit right-aligned and always visible — «Illustration · Le Papier» for ours,
 * «Photo · {author} · {licence} · Wikimedia Commons» for a photo, French in every
 * chrome language — and, for a photo, its licence and its source as links (new tab).
 * A photo's caption, when the server could state one, is its text alternative; else
 * the image is decorative, as the story's picture is.
 *
 * `size`: `strip` in the reader, `compact` (smaller frames) on the Une card.
 */

import React, { useState } from 'react';

import { resolveMediaUrl } from '@/lib/media-url';
import type { RvPicture } from '@/lib/revue-types';

import type { RevueCopy } from './revue-copy';
import { galleryStrip, pictureLinks } from './revue-gallery';

export type RvGalleryProps = {
  pictures: readonly RvPicture[];
  /** The picture already printed above (the plate shown), left out of the strip. */
  mainUrl: string | null;
  size?: 'strip' | 'compact';
  copy: RevueCopy;
};

/** One picture printed as the gallery prints it (its frame, its credit, its links); «La photo»
 * (2026-11-21) prints its pictures with it too. */
export function RvGalleryPicture({ picture, copy }: { picture: RvPicture; copy: RevueCopy }) {
  const [failed, setFailed] = useState(false);
  const src = resolveMediaUrl(picture.url) ?? picture.url;
  const caption = (picture.captionFr ?? '').trim();
  const links = pictureLinks(picture, copy);
  return (
    <figure className="rv-gallery__pic" data-kind={picture.kind}>
      <div className="rv-picture__frame rv-gallery__frame">
        {!failed && (
          // eslint-disable-next-line @next/next/no-img-element -- a hot-linked Commons thumbnail or a painted print, already sized
          <img
            className="rv-picture__img"
            src={src}
            alt={picture.altFr}
            loading="lazy"
            decoding="async"
            referrerPolicy="no-referrer"
            width={picture.width ?? undefined}
            height={picture.height ?? undefined}
            onError={() => setFailed(true)}
          />
        )}
      </div>
      <figcaption className="rv-picture__cap rv-gallery__cap">
        {caption && (
          <span className="rv-gallery__fr" lang="fr">
            {caption}
          </span>
        )}
        <span className="rv-picture__credit rv-gallery__credit" lang="fr">
          {picture.creditFr}
        </span>
        {links.length > 0 && (
          <span className="rv-gallery__links">
            {links.map((link) => (
              <a key={link.kind} className="rv-gallery__link" href={link.href} target="_blank" rel="noopener noreferrer" data-link={link.kind}>
                {link.label}
                <span className="av2-sr"> ({copy.new_tab})</span>
              </a>
            ))}
          </span>
        )}
      </figcaption>
    </figure>
  );
}

export function RvGallery({ pictures, mainUrl, size = 'strip', copy }: RvGalleryProps) {
  const strip = galleryStrip(pictures, mainUrl);
  if (strip.length === 0) return null;
  return (
    <section className="rv-gallery" data-size={size} aria-label={copy.gallery_label}>
      <ul className="rv-gallery__strip">
        {strip.map((picture) => (
          <li key={picture.url} className="rv-gallery__item">
            <RvGalleryPicture picture={picture} copy={copy} />
          </li>
        ))}
      </ul>
    </section>
  );
}

export default RvGallery;
