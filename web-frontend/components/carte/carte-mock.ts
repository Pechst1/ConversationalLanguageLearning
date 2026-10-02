/**
 * WP-120 phase C · `/carte?mock=1` (never in a production build): six closed
 * Papiers and three «Mon quartier» places, so the map can be seen without data.
 *
 * Four Papiers in Paris at the gazetteer's coordinates (`app/data/geo/gazetteer.json`:
 * the marché d'Aligre, the Assemblée nationale, the Académie Goncourt at Drouant, and
 * «Paris» at city precision), one at ParisLongchamp (in the Bois de Boulogne, so it
 * joins the Paris cluster seen from France) and one in the vignoble de Bourgogne
 * (region precision). The pictograms are the authored fallbacks of
 * `app/services/revue/pictogram.py`.
 */

import type { CarteView } from '@/lib/carte-types';

const PICTO = {
  food: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><path d="M36.6 76.2L76.2 36.6Q76.9 23.1 63.4 23.8L23.8 63.4Q23.1 76.9 36.6 76.2Z" fill="#C2890F"/><path d="M36.6 76.2L76.2 36.6L72.6 33L33 72.6Z" fill="#F3C318"/><path d="M34 56.2L45.6 59.1L44.8 62.2L33.2 59.3Z" fill="#F1ECE1"/><path d="M43.9 46.3L55.5 49.2L54.7 52.3L43.1 49.4Z" fill="#F1ECE1"/><path d="M53.8 36.4L65.4 39.3L64.6 42.4L53 39.5Z" fill="#F1ECE1"/></svg>',
  politics: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect x="40" y="18" width="20" height="26" fill="#F1ECE1" stroke="#14110D" stroke-width="2"/><path d="M45 24L47 24L55 34L53 34Z" fill="#D8321A"/><path d="M53 24L55 24L47 34L45 34Z" fill="#D8321A"/><rect x="24" y="42" width="52" height="36" rx="2" fill="#1D3A8A"/><rect x="20" y="38" width="60" height="8" rx="2" fill="#14110D"/><rect x="38" y="40.5" width="24" height="3" fill="#F1ECE1"/><rect x="40" y="56" width="20" height="12" rx="2" fill="#F1ECE1"/></svg>',
  culture: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><path d="M50 38Q34 30 20 34L20 72Q34 68 50 76Q66 68 80 72L80 34Q66 30 50 38Z" fill="#1D3A8A"/><path d="M48 39Q36 33 24 36L24 68Q36 65 48 71Z" fill="#F1ECE1"/><path d="M52 39Q64 33 76 36L76 68Q64 65 52 71Z" fill="#F1ECE1"/><rect x="29" y="44" width="14" height="2" fill="#14110D"/><rect x="29" y="51" width="14" height="2" fill="#14110D"/><rect x="57" y="44" width="14" height="2" fill="#14110D"/><rect x="57" y="51" width="10" height="2" fill="#14110D"/><path d="M62 66L62 80L65 77L68 80L68 65Z" fill="#D8321A"/></svg>',
  sport: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="34" fill="#F1ECE1" stroke="#14110D" stroke-width="3"/><path d="M50 40L59.5 46.9L55.9 58.1L44.1 58.1L40.5 46.9Z" fill="#14110D"/><path d="M50 18.5L56.2 23L53.8 30.3L46.2 30.3L43.8 23Z" fill="#14110D"/><path d="M80 40.3L77.6 47.5L70 47.5L67.6 40.3L73.8 35.8Z" fill="#14110D"/><path d="M68.5 75.5L60.9 75.5L58.5 68.2L64.7 63.7L70.9 68.2Z" fill="#14110D"/><path d="M31.5 75.5L29.1 68.2L35.3 63.7L41.5 68.2L39.1 75.5Z" fill="#14110D"/><path d="M20 40.3L26.2 35.8L32.4 40.3L30 47.5L22.4 47.5Z" fill="#14110D"/></svg>',
  nature: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><path d="M50 14C74 28 78 58 50 82C22 58 26 28 50 14Z" fill="#2C6A5D"/><path d="M49 26L51 26L51.5 80L48.5 80Z" fill="#F1ECE1"/><path d="M50 44L64 36L65 38L50 48Z" fill="#F1ECE1"/><path d="M50 44L36 36L35 38L50 48Z" fill="#F1ECE1"/><path d="M50 58L64 50L65 52L50 62Z" fill="#F1ECE1"/><path d="M50 58L36 50L35 52L50 62Z" fill="#F1ECE1"/><path d="M48.5 80L51.5 80L52.5 88L47.5 88Z" fill="#14110D"/></svg>',
};

const PLATE = '/assets/serial/locations';

export const CARTE_MOCK_VIEW: CarteView = {
  pins: [
    {
      sessionId: 'mock-aligre',
      dossierId: '2026-w40-prix-produits-frais',
      week: '2026-W40',
      closedAt: '2026-10-01T10:00:00+02:00',
      placeLabelFr: "Place d'Aligre et marché Beauvau, Paris 12e",
      lat: 48.849,
      lon: 2.378,
      precision: 'exact',
      level: 'paris',
      headlineFr: 'Les fruits et légumes coûtent plus cher',
      keptWords: ['un étal', 'le prix', 'la récolte', 'augmenter'],
      contributionKind: 'reader_question',
      contributionFr: 'Est-ce que les prix au marché sont plus bas qu’au supermarché ?',
      contributionSpans: [[11, 43]],
      questionFr: 'Est-ce que les prix au marché sont plus bas qu’au supermarché ?',
      plateUrl: `${PLATE}/marche_canal.webp`,
      vignette: { ring: 'question', keptContribution: true, pictogramSvg: PICTO.food },
    },
    {
      sessionId: 'mock-assemblee',
      dossierId: '2026-w40-budget-2027',
      week: '2026-W39',
      closedAt: '2026-09-24T19:00:00+02:00',
      placeLabelFr: 'Assemblée nationale, Palais Bourbon',
      lat: 48.862,
      lon: 2.3185,
      precision: 'exact',
      level: 'paris',
      headlineFr: 'Le budget 2027 arrive à l’Assemblée',
      keptWords: ['le budget', 'un député', 'voter'],
      contributionKind: 'headline_choice',
      contributionFr: 'Le budget 2027 arrive à l’Assemblée',
      contributionSpans: [],
      questionFr: null,
      plateUrl: `${PLATE}/office_admin.webp`,
      vignette: { ring: 'headline', keptContribution: false, pictogramSvg: PICTO.politics },
    },
    {
      sessionId: 'mock-goncourt',
      dossierId: '2026-w40-goncourt-roman-retire',
      week: '2026-W38',
      closedAt: '2026-09-17T18:30:00+02:00',
      placeLabelFr: 'Académie Goncourt, restaurant Drouant',
      lat: 48.8687,
      lon: 2.3343,
      precision: 'exact',
      level: 'paris',
      headlineFr: 'Le Goncourt retire un roman de sa sélection',
      keptWords: ['un roman', 'la sélection', 'un jury'],
      contributionKind: 'short_report',
      contributionFr: 'Le jury a retiré un roman. Les libraires sont surpris.',
      contributionSpans: [[27, 54]],
      questionFr: null,
      plateUrl: `${PLATE}/newsroom.webp`,
      vignette: { ring: 'report', keptContribution: true, pictogramSvg: PICTO.culture },
    },
    {
      sessionId: 'mock-canicules',
      dossierId: '2026-w40-paris-plan-canicules',
      week: '2026-W37',
      closedAt: '2026-09-10T09:15:00+02:00',
      placeLabelFr: 'Paris',
      lat: 48.8566,
      lon: 2.3522,
      precision: 'city',
      level: 'paris',
      headlineFr: 'Paris se prépare aux prochaines canicules',
      keptWords: ['la chaleur', 'un arbre', 'l’ombre'],
      contributionKind: null,
      contributionFr: null,
      contributionSpans: [],
      questionFr: 'Combien d’arbres seront plantés ?',
      plateUrl: `${PLATE}/buttes_chaumont.webp`,
      vignette: null,
    },
    {
      sessionId: 'mock-longchamp',
      dossierId: '2026-w40-prix-de-l-arc-de-triomphe',
      week: '2026-W36',
      closedAt: '2026-09-03T17:00:00+02:00',
      placeLabelFr: 'Hippodrome de ParisLongchamp',
      lat: 48.8573,
      lon: 2.2338,
      precision: 'exact',
      level: 'paris',
      headlineFr: 'Seize chevaux pour le Prix de l’Arc de Triomphe',
      keptWords: ['un cheval', 'une course', 'gagner'],
      contributionKind: 'headline_write',
      contributionFr: 'Seize chevaux, un seul gagnant',
      contributionSpans: [[0, 30]],
      questionFr: null,
      plateUrl: `${PLATE}/metro_platform.webp`,
      vignette: { ring: 'headline', keptContribution: true, pictogramSvg: PICTO.sport },
    },
    {
      sessionId: 'mock-bourgogne',
      dossierId: 'evergreen-beaujolais-nouveau',
      week: '2026-W35',
      closedAt: '2026-08-27T11:00:00+02:00',
      placeLabelFr: 'Vignoble de Bourgogne',
      lat: 47.05,
      lon: 4.83,
      precision: 'region',
      level: 'france',
      headlineFr: 'Les vendanges commencent en Bourgogne',
      keptWords: ['la vigne', 'le raisin', 'les vendanges'],
      contributionKind: 'reader_question',
      contributionFr: 'Est-ce que la récolte sera bonne cette année ?',
      contributionSpans: [[0, 46]],
      questionFr: 'Est-ce que la récolte sera bonne cette année ?',
      plateUrl: `${PLATE}/brocante.webp`,
      vignette: { ring: 'question', keptContribution: false, pictogramSvg: PICTO.nature },
    },
  ],
  quartier: [
    { id: 'le_mistral', nameFr: 'Le Mistral', labelFr: 'Le Mistral, quai de Valmy, Paris 10e', lat: 48.8706, lon: 2.3632, plateUrl: `${PLATE}/le_mistral-counter.webp` },
    { id: 'quai_de_valmy', nameFr: 'Le quai de Valmy', labelFr: 'Quai de Valmy, Paris 10e', lat: 48.8712, lon: 2.3646, plateUrl: `${PLATE}/le_mistral-counter.webp` },
    { id: 'buttes_chaumont', nameFr: 'Le parc des Buttes-Chaumont', labelFr: 'Parc des Buttes-Chaumont, Paris 19e', lat: 48.8809, lon: 2.3828, plateUrl: `${PLATE}/buttes_chaumont.webp` },
  ],
  counts: { france: 6, idf: 5, paris: 5, unplaced: 0 },
};
