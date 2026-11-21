import { STORY_FEATURE_VISIBLE } from './launch-flags';
import { PLACES, placesInBuild } from './places';
import { resolveSettingsLanguage, settingsCopy } from './settings-copy';

export type ProductSection = 'atelier' | 'missions' | 'feuilleton' | 'notebook';

export type ProductTab = {
  id: ProductSection;
  label: string;
  href: string;
  icon: 'mark' | 'mission' | 'feuilleton' | 'book';
  activeRoutes: string[];
};

// S4 stage 1: which routes light a tab, which draw their own shell and which
// belong to Réglages all come from the register of places (lib/places.ts).
// Places a build does not contain (the Bibliothèque while its flag is off,
// the dev galleries in production) are left out, as they always were.
const STORY_ROUTES: string[] = PLACES
  .filter((place) => place.gate.kind === 'launch_flag' && place.gate.flag === 'storyFeatureVisible')
  .map((place) => place.route);

function sectionRoutes(section: ProductSection): string[] {
  return placesInBuild().filter((place) => place.section === section).map((place) => place.route);
}

function tabFor(section: ProductSection, icon: ProductTab['icon']): ProductTab {
  const tab = PLACES.find((place) => place.kind === 'tab' && place.section === section);
  if (!tab) throw new Error(`lib/places.ts has no tab for ${section}`);
  // The four tab names are French in every language (WP-109).
  return { id: section, label: tab.name.fr, href: tab.route, icon, activeRoutes: sectionRoutes(section) };
}

// WP-109 (F-3): «La Une · Feuilleton · Courrier · Cahier» — the story is the second tab,
// right beside the front page that headlines it. WP-83: one name per place.
export const PHONE_PRODUCT_TABS: ProductTab[] = [
  tabFor('atelier', 'mark'),
  tabFor('feuilleton', 'feuilleton'),
  tabFor('missions', 'mission'),
  tabFor('notebook', 'book'),
];

const OWN_SHELL_ROUTES = new Set(placesInBuild().filter((place) => place.ownShell).map((place) => place.route));

// The pages opened from Réglages (the Dossier, the rehearsal) belong to it.
const SETTINGS_ROUTES = new Set([
  '/settings',
  ...PLACES.filter((place) => place.parent === '/settings' && place.kind === 'child').map((place) => place.route),
]);

/** Réglages and the pages opened from it: no tab is lit for them. */
export function isSettingsRoute(pathname: string) {
  return SETTINGS_ROUTES.has(pathname);
}

export function routeUsesOwnProductShell(pathname: string) {
  return OWN_SHELL_ROUTES.has(pathname);
}

export function resolveProductSection(pathname: string): ProductSection | undefined {
  return PHONE_PRODUCT_TABS.find((item) => item.activeRoutes.includes(pathname))?.id;
}

/**
 * The title the phone header prints for a route.
 *
 * Every product section is French chrome — Atelier, Missions, Feuilleton,
 * Cahier, Bibliothèque — because the learner is reading a French publication.
 * Réglages is the one exception the owner carved out (WP-46): it is the
 * administrative surface, it follows the account's own `native_language`, and
 * it had been the only title in the app still reading «Settings» for a German
 * learner. `language` is the account's native language; with none known the
 * settings copy table's own floor, English, applies.
 */
export function resolveProductTitle(
  section: ProductSection | undefined,
  pathname: string,
  language?: unknown,
) {
  if (STORY_FEATURE_VISIBLE && STORY_ROUTES.includes(pathname)) {
    return 'Bibliothèque';
  }
  // The pages opened from Réglages (the Dossier, the rehearsal)
  // belong to it; they used to fall through to «La Une», a page they are not.
  if (SETTINGS_ROUTES.has(pathname)) return settingsCopy(resolveSettingsLanguage(language)).page_label;
  return PHONE_PRODUCT_TABS.find((item) => item.id === section)?.label || 'La Une';
}
