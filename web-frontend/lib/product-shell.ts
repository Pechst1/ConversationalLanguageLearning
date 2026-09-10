import { STORY_FEATURE_VISIBLE } from './launch-flags';

export type ProductSection = 'atelier' | 'missions' | 'feuilleton' | 'notebook';

export type ProductTab = {
  id: ProductSection;
  label: string;
  href: string;
  icon: 'mark' | 'mission' | 'feuilleton' | 'book';
  activeRoutes: string[];
};

// WP-20 deleted the `/stories` and `/story/[id]` readers; the Bibliothèque is
// the whole of the reading flow now, and it is still parked behind the flag.
const STORY_ROUTES: string[] = [
  '/bibliotheque',
  '/bibliotheque/[storyId]',
  '/bibliotheque/[storyId]/chapter/[chapterId]',
];

export const PHONE_PRODUCT_TABS: ProductTab[] = [
  {
    id: 'atelier',
    label: 'Atelier',
    href: '/atelier',
    icon: 'mark',
    activeRoutes: [
      '/atelier',
      '/audio-session',
      ...(STORY_FEATURE_VISIBLE ? STORY_ROUTES : []),
      '/vocabulary/review',
    ],
  },
  {
    id: 'missions',
    label: 'Missions',
    href: '/missions',
    icon: 'mission',
    activeRoutes: [
      '/missions',
    ],
  },
  {
    id: 'feuilleton',
    label: 'Feuilleton',
    href: '/graphic-novel',
    icon: 'feuilleton',
    activeRoutes: [
      '/graphic-novel',
      '/serial',
      '/serial/cast',
      '/serial/episode',
      '/serial/episode/[index]',
    ],
  },
  {
    id: 'notebook',
    label: 'Cahier',
    href: '/notebook',
    icon: 'book',
    activeRoutes: [
      '/notebook',
      '/grammar',
      '/vocabulary',
      '/vocabulary/conjugation',
    ],
  },
];

const OWN_SHELL_ROUTES = new Set([
  '/atelier',
  '/missions',
  '/graphic-novel',
  '/serial',
  '/serial/cast',
  '/serial/episode',
  '/serial/episode/[index]',
  '/grammar',
  '/notebook',
  '/vocabulary',
  '/vocabulary/review',
  '/vocabulary/conjugation',
  '/audio-session',
  ...(STORY_FEATURE_VISIBLE ? STORY_ROUTES : []),
]);

export function routeUsesOwnProductShell(pathname: string) {
  return OWN_SHELL_ROUTES.has(pathname);
}

export function resolveProductSection(pathname: string): ProductSection | undefined {
  return PHONE_PRODUCT_TABS.find((item) => item.activeRoutes.includes(pathname))?.id;
}

export function resolveProductTitle(section: ProductSection | undefined, pathname: string) {
  if (STORY_FEATURE_VISIBLE && STORY_ROUTES.includes(pathname)) {
    return 'Bibliothèque';
  }
  if (pathname === '/settings') return 'Settings';
  return PHONE_PRODUCT_TABS.find((item) => item.id === section)?.label || 'Atelier';
}
