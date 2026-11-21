/**
 * «Papier · photos» (2026-11-20) · the pure half of RvGallery: which of the story's
 * pictures the strip shows, and the links each one carries. No React here; the node
 * tests read it directly.
 *
 * The stage (or the «Lire» picture) already prints the first picture, so the strip
 * shows the others, in the server's order (painted shots, then Commons photos), once
 * each. A photo carries a link to its licence and one to its file page on Commons;
 * an illustration is ours and carries none. Only https links reach the page.
 */

import type { RvPicture } from '@/lib/revue-types';

import type { RevueCopy } from './revue-copy';

/** The strip: every picture but the one already shown (`mainUrl`), each URL once. */
export function galleryStrip(pictures: readonly RvPicture[], mainUrl: string | null): RvPicture[] {
  const seen = new Set<string>(mainUrl ? [mainUrl] : []);
  const out: RvPicture[] = [];
  for (const picture of pictures) {
    if (!picture.url || seen.has(picture.url)) continue;
    seen.add(picture.url);
    out.push(picture);
  }
  return out;
}

export type RvPictureLink = { kind: 'licence' | 'source'; href: string; label: string };

/** A photo's tappable links: its licence (named by its short name) and its source page. */
export function pictureLinks(picture: RvPicture, copy: Pick<RevueCopy, 'picture_licence' | 'picture_source'>): RvPictureLink[] {
  if (picture.kind !== 'photo') return [];
  const links: RvPictureLink[] = [];
  if (picture.licenceUrl) links.push({ kind: 'licence', href: picture.licenceUrl, label: picture.licence || copy.picture_licence });
  if (picture.sourceUrl && picture.sourceUrl !== picture.licenceUrl) links.push({ kind: 'source', href: picture.sourceUrl, label: copy.picture_source });
  return links;
}
