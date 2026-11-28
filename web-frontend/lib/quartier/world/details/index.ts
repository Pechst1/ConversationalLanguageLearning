// One lazy import per detail of Le Mistral the forge wrote (`details.ts`).
import type { DetailSpec } from '../../details';

export const DETAIL_FILES: Record<string, () => Promise<DetailSpec>> = {
  banderole_lila: () => import('./banderole_lila.json').then((m) => (m.default ?? m) as unknown as DetailSpec),
  banderole_lila_seche: () => import('./banderole_lila_seche.json').then((m) => (m.default ?? m) as unknown as DetailSpec),
  carte_marchand: () => import('./carte_marchand.json').then((m) => (m.default ?? m) as unknown as DetailSpec),
  carte_odile: () => import('./carte_odile.json').then((m) => (m.default ?? m) as unknown as DetailSpec),
  carte_nom_odile: () => import('./carte_nom_odile.json').then((m) => (m.default ?? m) as unknown as DetailSpec),
  dessin_maitresse: () => import('./dessin_maitresse.json').then((m) => (m.default ?? m) as unknown as DetailSpec),
  manteau_mistral: () => import('./manteau_mistral.json').then((m) => (m.default ?? m) as unknown as DetailSpec),
  mur_odile: () => import('./mur_odile.json').then((m) => (m.default ?? m) as unknown as DetailSpec),
  mot_noel_marchand: () => import('./mot_noel_marchand.json').then((m) => (m.default ?? m) as unknown as DetailSpec),
  poele_odile: () => import('./poele_odile.json').then((m) => (m.default ?? m) as unknown as DetailSpec),
  tableau_omelette: () => import('./tableau_omelette.json').then((m) => (m.default ?? m) as unknown as DetailSpec),
  tasse_habituelle: () => import('./tasse_habituelle.json').then((m) => (m.default ?? m) as unknown as DetailSpec),
  tuque_romy: () => import('./tuque_romy.json').then((m) => (m.default ?? m) as unknown as DetailSpec),
};
