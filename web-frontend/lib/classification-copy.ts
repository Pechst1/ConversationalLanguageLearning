import type { ControlLanguage } from '@/types/daily-journey';

/** Stored classification labels are answer keys. Translate display only. */
const LABELS: Record<string, { fr: string; de: string }> = {
  'present condition': { fr: 'condition au présent', de: 'Bedingung im Präsens' },
  'future result': { fr: 'conséquence au futur', de: 'Folge im Futur' },
  'imperative result': { fr: 'conséquence à l’impératif', de: 'Folge im Imperativ' },
  'background/habit': { fr: 'contexte ou habitude', de: 'Hintergrund oder Gewohnheit' },
  'bounded event': { fr: 'événement achevé', de: 'Abgeschlossenes Ereignis' },
  'article changes': { fr: 'l’article change', de: 'Der Artikel ändert sich' },
};

export function classificationCopy(value: string, language: ControlLanguage): string {
  if (language === 'en') return value;
  let display = value;
  for (const [key, labels] of Object.entries(LABELS)) {
    display = display.split(key).join(labels[language]);
  }
  return display;
}

export function classificationGoal(language: ControlLanguage): string {
  return { en: 'Classify this form.', de: 'Ordne die Form zu.', fr: 'Classez cette forme.' }[language];
}
