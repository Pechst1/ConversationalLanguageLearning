export type ProductSection = 'atelier' | 'notebook';

export type ProductTab = {
  id: ProductSection;
  label: string;
  href: string;
  icon: 'mark' | 'book';
  activeRoutes: string[];
};

export const PHONE_PRODUCT_TABS: ProductTab[] = [
  {
    id: 'atelier',
    label: 'Atelier',
    href: '/atelier',
    icon: 'mark',
    activeRoutes: [
      '/atelier',
      '/dashboard',
      '/daily-practice',
      '/learn',
      '/learn/new',
      '/learn/session/[id]',
      '/sessions',
      '/practice',
      '/audio-session',
      '/missions',
      '/graphic-novel',
      '/serial',
      '/serial/cast',
      '/serial/episode/[index]',
      '/bibliotheque',
      '/bibliotheque/[storyId]',
      '/bibliotheque/[storyId]/chapter/[chapterId]',
      '/stories',
      '/stories/[storyId]',
      '/stories/[storyId]/chapter/[chapterId]',
      '/story/[id]',
      '/vocabulary/review',
    ],
  },
  {
    id: 'notebook',
    label: 'Notebook',
    href: '/notebook',
    icon: 'book',
    activeRoutes: [
      '/notebook',
      '/grammar',
      '/vocabulary',
      '/progress',
      '/achievements',
      '/almanac',
    ],
  },
];

const OWN_SHELL_ROUTES = new Set([
  '/atelier',
  '/missions',
  '/graphic-novel',
  '/serial',
  '/serial/cast',
  '/serial/episode/[index]',
  '/bibliotheque',
  '/bibliotheque/[storyId]',
  '/bibliotheque/[storyId]/chapter/[chapterId]',
  '/grammar',
  '/notebook',
  '/almanac',
  '/vocabulary',
  '/vocabulary/review',
  '/learn',
  '/learn/new',
  '/learn/session/[id]',
  '/audio-session',
  '/stories',
  '/stories/[storyId]',
  '/stories/[storyId]/chapter/[chapterId]',
  '/story/[id]',
]);

export function routeUsesOwnProductShell(pathname: string) {
  return OWN_SHELL_ROUTES.has(pathname);
}

export function resolveProductSection(pathname: string): ProductSection | undefined {
  return PHONE_PRODUCT_TABS.find((item) => item.activeRoutes.includes(pathname))?.id;
}

export function resolveProductTitle(section: ProductSection | undefined, pathname: string) {
  if (pathname === '/learn/session/[id]' || pathname === '/sessions' || pathname === '/practice') {
    return 'Session';
  }
  if (
    pathname === '/bibliotheque'
    || pathname === '/bibliotheque/[storyId]'
    || pathname === '/bibliotheque/[storyId]/chapter/[chapterId]'
    || pathname === '/stories'
    || pathname === '/stories/[storyId]'
    || pathname === '/stories/[storyId]/chapter/[chapterId]'
    || pathname === '/story/[id]'
  ) {
    return 'Bibliothèque';
  }
  if (pathname === '/settings') return 'Settings';
  return PHONE_PRODUCT_TABS.find((item) => item.id === section)?.label || 'Atelier';
}
