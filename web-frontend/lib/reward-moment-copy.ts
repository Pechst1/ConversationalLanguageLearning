/**
 * The reward moment (the edition's gilt seal) in the learner's chrome
 * language. Live walk #118: it was French only, with vous, in English and
 * German A1 sessions. German says du and French says tu, as the owner decided
 * for the whole app (#128). Owner, 2026-10-19: tokens (the bonus token, the
 * logo token) no longer pop up over the séance; only the seal keeps a moment.
 */

export type RewardMomentLanguage = 'en' | 'de' | 'fr';
export type RewardMomentKind = 'seal';

type RewardLines = { eyebrow: string; title: string; body: string };
type RewardCopy = Record<RewardMomentKind, RewardLines> & {
  continue: string;
};

const COPY: Record<RewardMomentLanguage, RewardCopy> = {
  en: {
    seal: {
      eyebrow: 'A flawless edition',
      title: 'Gold seal earned',
      body: 'Not a single slip in this edition. Today’s seal is stamped in gold.',
    },
    continue: 'Continue',
  },
  de: {
    seal: {
      eyebrow: 'Eine fehlerfreie Ausgabe',
      title: 'Goldsiegel verdient',
      body: 'Kein einziger Fehler in dieser Ausgabe. Das Siegel von heute ist in Gold geprägt.',
    },
    continue: 'Weiter',
  },
  fr: {
    seal: {
      eyebrow: 'Édition sans faute',
      title: 'Sceau doré gagné',
      body: 'Aucune coquille sur ce tirage. Le sceau du jour a été frappé en doré.',
    },
    continue: 'Continuer',
  },
};

export function rewardMomentCopy(language: unknown): RewardCopy {
  return language === 'de' || language === 'fr' ? COPY[language] : COPY.en;
}
