/**
 * The reward moment (bonus token, logo token, gilt seal) in the learner's
 * chrome language. Live walk #118: it was French only, with vous, in English
 * and German A1 sessions. German says du and French says tu, as the owner
 * decided for the whole app (#128).
 */

export type RewardMomentLanguage = 'en' | 'de' | 'fr';
export type RewardMomentKind = 'drafting' | 'logo' | 'seal';

type RewardLines = { eyebrow: string; title: string; body: string };
type RewardCopy = Record<RewardMomentKind, RewardLines> & {
  credit: (credit: number) => string;
  continue: string;
};

const COPY: Record<RewardMomentLanguage, RewardCopy> = {
  en: {
    drafting: {
      eyebrow: 'In your own words',
      title: 'Bonus token earned',
      body: 'You used today’s form in a sentence of your own. That harder work earns extra credit.',
    },
    logo: {
      eyebrow: 'A perfect screen',
      title: 'Logo token earned',
      body: 'All three forms are now part of the house mark. You’ll find them in your Almanach.',
    },
    seal: {
      eyebrow: 'A flawless edition',
      title: 'Gold seal earned',
      body: 'Not a single slip in this edition. Today’s seal is stamped in gold.',
    },
    credit: (credit) => `+${credit} credit`,
    continue: 'Continue',
  },
  de: {
    drafting: {
      eyebrow: 'In deinen eigenen Worten',
      title: 'Bonus-Token verdient',
      body: 'Du hast die Form von heute in einem eigenen Satz benutzt. Diese schwerere Arbeit zählt extra.',
    },
    logo: {
      eyebrow: 'Ein perfekter Durchgang',
      title: 'Logo-Token verdient',
      body: 'Alle drei Formen gehören jetzt zum Zeichen des Hauses. Du findest sie in deinem Almanach.',
    },
    seal: {
      eyebrow: 'Eine fehlerfreie Ausgabe',
      title: 'Goldsiegel verdient',
      body: 'Kein einziger Fehler in dieser Ausgabe. Das Siegel von heute ist in Gold geprägt.',
    },
    credit: (credit) => `+${credit} Punkte`,
    continue: 'Weiter',
  },
  fr: {
    drafting: {
      eyebrow: 'Composé de toutes pièces',
      title: 'Jeton bonus gagné',
      body: 'Tu as produit la forme visée avec tes propres mots : ce travail plus exigeant reçoit un crédit supplémentaire.',
    },
    logo: {
      eyebrow: 'Écran parfait',
      title: 'Jeton du logo gagné',
      body: 'Les trois formes ont rejoint la marque de la maison. Elles sont classées dans ton Almanach.',
    },
    seal: {
      eyebrow: 'Édition sans faute',
      title: 'Sceau doré gagné',
      body: 'Aucune coquille sur ce tirage. Le sceau du jour a été frappé en doré.',
    },
    credit: (credit) => `+${credit} crédit`,
    continue: 'Continuer',
  },
};

export function rewardMomentCopy(language: unknown): RewardCopy {
  return language === 'de' || language === 'fr' ? COPY[language] : COPY.en;
}
