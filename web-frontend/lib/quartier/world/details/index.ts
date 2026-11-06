// One lazy import per detail of Le Mistral the forge wrote (`details.ts`).
import type { DetailSpec } from '../../details';

export const DETAIL_FILES: Record<string, () => Promise<DetailSpec>> = {
  tasse_habituelle: () => import('./tasse_habituelle.json').then((m) => (m.default ?? m) as unknown as DetailSpec),
};
