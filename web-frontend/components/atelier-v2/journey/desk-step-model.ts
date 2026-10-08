/**
 * «Le bureau» (WP-121/122 follow-up) — the model of the DESK step.
 *
 * On an ordinary practice day the planner may deal one of the Revue's other desks
 * after the ending (at most one a day, each at most once a week, never on a tentpole
 * or the Papier day). The step is advanced, never answered here: each desk grades on
 * its own routes. Which surface mounts:
 *
 *   relecture   `CarteRelecture` on the offer the step carries (WP-121 §B);
 *   radio       the Radio bulletin of `dossier_id`, listen first, then the dictée (WP-122 §3);
 *   correcteur  `CorrecteurDesk` on a new draft of `dossier_id` (WP-122 §4).
 *
 * Pure: the component (`DeskStep.tsx`) and the node tests share it.
 */

import { parseRelectureOffer, type RelectureOffer } from '@/lib/carte-types';
import type { ControlLanguage, DeskKind, DeskStep } from '@/types/daily-journey';

export type DeskStepView =
  | { desk: 'relecture'; titleFr: string; offer: RelectureOffer }
  | { desk: 'radio'; titleFr: string; dossierId: string; seconds: number | null }
  | { desk: 'correcteur'; titleFr: string; dossierId: string }
  | { desk: 'none'; titleFr: string };

/** What the step can open; `none` when its target is missing (the step is then skippable only). */
export function deskStepView(step: Pick<DeskStep, 'prompt'> | null | undefined): DeskStepView {
  const prompt = step?.prompt;
  const titleFr = String(prompt?.title_fr ?? '').trim();
  if (!prompt) return { desk: 'none', titleFr };
  if (prompt.desk === 'relecture') {
    const offer = parseRelectureOffer(prompt.relecture);
    return offer ? { desk: 'relecture', titleFr: titleFr || offer.dossierTitleFr, offer } : { desk: 'none', titleFr };
  }
  const dossierId = String(prompt.dossier_id ?? '').trim();
  if (!dossierId) return { desk: 'none', titleFr };
  if (prompt.desk === 'radio') {
    return { desk: 'radio', titleFr, dossierId, seconds: typeof prompt.seconds === 'number' ? prompt.seconds : null };
  }
  if (prompt.desk === 'correcteur') return { desk: 'correcteur', titleFr, dossierId };
  return { desk: 'none', titleFr };
}

type DeskCopy = {
  kicker: Record<DeskKind, string>;
  lead: Record<DeskKind, string>;
  skip: string;
  done: string;
  unavailable: string;
  loading: string;
};

/** The desks' names are the newspaper's, in French on every chrome; the rest follows the chrome. */
const KICKER: Record<DeskKind, string> = {
  relecture: 'La Relecture',
  radio: 'La Radio',
  correcteur: 'Le Correcteur',
};

const COPY: Record<ControlLanguage, DeskCopy> = {
  fr: {
    kicker: KICKER,
    lead: {
      relecture: 'Il y a quelques semaines, tu as posé une question. Réponds-y encore.',
      radio: "Le bulletin de la semaine : écoute d'abord, lis ensuite, puis une dictée.",
      correcteur: 'Le brouillon de Romy part à l’impression. Trouve les fautes avant.',
    },
    skip: 'Passer',
    done: 'Continuer',
    unavailable: 'Ce bureau est fermé aujourd’hui.',
    loading: 'Un instant…',
  },
  en: {
    kicker: KICKER,
    lead: {
      relecture: 'A few weeks ago you asked a question. Answer it again.',
      radio: "This week's bulletin: listen first, read after, then one dictation.",
      correcteur: "Romy's draft is going to print. Find the mistakes first.",
    },
    skip: 'Skip',
    done: 'Continue',
    unavailable: 'This desk is closed today.',
    loading: 'One moment…',
  },
  de: {
    kicker: KICKER,
    lead: {
      relecture: 'Vor ein paar Wochen hast du eine Frage gestellt. Beantworte sie noch einmal.',
      radio: 'Das Bulletin der Woche: erst hören, dann lesen, dann ein Diktat.',
      correcteur: 'Romys Entwurf geht in den Druck. Finde vorher die Fehler.',
    },
    skip: 'Überspringen',
    done: 'Weiter',
    unavailable: 'Dieser Schreibtisch ist heute geschlossen.',
    loading: 'Einen Moment …',
  },
};

export function deskCopy(language: unknown): DeskCopy {
  return COPY[language === 'en' || language === 'de' ? language : 'fr'];
}

/** «La Radio · La grève des transports» — the step's kicker. */
export function deskKicker(view: DeskStepView, language: unknown): string {
  if (view.desk === 'none') return view.titleFr;
  return [deskCopy(language).kicker[view.desk], view.titleFr].filter(Boolean).join(' · ');
}
