/**
 * Generated from app/services/cast_registry.py (scripts/export_cast.py).
 * Do not edit: change the registry, then run npm run cast:generate.
 */

export type CastPersonId = 'augustin_de_roncourt' | 'bastien_roux' | 'camille_marchand' | 'landlord_marchand' | 'lila_bonnet' | 'maitre_vasseur' | 'margaux_barman' | 'marin_leveque' | 'mme_diallo' | 'odile_ferrand' | 'romy_tremblay';

export type CastPerson = {
  id: CastPersonId;
  /** What the learner reads. */
  name: string;
  /** The season bible's full name; a speaker label prints `name`, not this. */
  fullName: string;
  /** What the person says when naming themselves. */
  spokenName: string;
  /** How the person opens with the learner, before the season moves it. */
  address: 'tu' | 'vous' | null;
  hasDrawnFace: boolean;
  /** (tentpole, day letter) of their first page. */
  firstDay: [number, string];
  /** Lowercase, unaccented words that mean this person, for reading a payload. */
  tokens: string[];
  /** Every way a text may spell them. */
  spellings: string[];
};

export const CAST: Record<CastPersonId, CastPerson> = {
  augustin_de_roncourt: {
    id: 'augustin_de_roncourt',
    name: 'Gus',
    fullName: 'Augustin « Gus » de Roncourt',
    spokenName: 'Gus',
    address: 'vous',
    hasDrawnFace: true,
    firstDay: [1, 'a'],
    tokens: ['augustin', 'gus', 'roncourt'],
    spellings: ['Augustin', 'Augustin « Gus » de Roncourt', 'Gus', 'augustin', 'gus'],
  },
  bastien_roux: {
    id: 'bastien_roux',
    name: 'Bastien Roux',
    fullName: 'Bastien Roux',
    spokenName: 'Bastien',
    address: 'vous',
    hasDrawnFace: false,
    firstDay: [2, 'b'],
    tokens: ['bastien', 'roux'],
    spellings: ['Bastien', 'Bastien Roux'],
  },
  camille_marchand: {
    id: 'camille_marchand',
    name: 'Camille',
    fullName: 'Camille Marchand',
    spokenName: 'Camille',
    address: 'vous',
    hasDrawnFace: true,
    firstDay: [1, 'b'],
    tokens: ['camille'],
    spellings: ['Camille', 'Camille Marchand', 'camille'],
  },
  landlord_marchand: {
    id: 'landlord_marchand',
    name: 'M. Marchand',
    fullName: 'M. Marchand',
    spokenName: 'Monsieur Marchand',
    address: 'vous',
    hasDrawnFace: true,
    firstDay: [4, 'a'],
    tokens: ['landlord', 'marchand', 'proprietaire'],
    spellings: ['M. Marchand', 'Monsieur Marchand', 'landlord', 'marchand', 'proprietaire'],
  },
  lila_bonnet: {
    id: 'lila_bonnet',
    name: 'Lila',
    fullName: 'Lila Bonnet',
    spokenName: 'Lila',
    address: 'tu',
    hasDrawnFace: true,
    firstDay: [1, 'a'],
    tokens: ['bonnet', 'lila'],
    spellings: ['Lila', 'Lila Bonnet', 'lila'],
  },
  maitre_vasseur: {
    id: 'maitre_vasseur',
    name: 'Maître Vasseur',
    fullName: 'Maître Vasseur',
    spokenName: 'Maître Vasseur',
    address: 'vous',
    hasDrawnFace: false,
    firstDay: [6, 'b'],
    tokens: ['vasseur'],
    spellings: ['Maître Vasseur'],
  },
  margaux_barman: {
    id: 'margaux_barman',
    name: 'Margaux',
    fullName: 'Margaux',
    spokenName: 'Margaux',
    address: 'tu',
    hasDrawnFace: true,
    firstDay: [1, 'a'],
    tokens: ['margaux'],
    spellings: ['Margaux', 'margaux'],
  },
  marin_leveque: {
    id: 'marin_leveque',
    name: 'Marin',
    fullName: 'Marin Lévêque',
    spokenName: 'Marin',
    address: 'tu',
    hasDrawnFace: true,
    firstDay: [1, 'a'],
    tokens: ['leveque', 'marin'],
    spellings: ['Marin', 'Marin Lévêque', 'marin'],
  },
  mme_diallo: {
    id: 'mme_diallo',
    name: 'Mme Diallo',
    fullName: 'Mme Diallo',
    spokenName: 'Madame Diallo',
    address: 'vous',
    hasDrawnFace: false,
    firstDay: [4, 'a'],
    tokens: ['diallo'],
    spellings: ['Madame Diallo', 'Mme Diallo'],
  },
  odile_ferrand: {
    id: 'odile_ferrand',
    name: 'Odile',
    fullName: 'Odile Ferrand',
    spokenName: 'Odile',
    address: 'tu',
    hasDrawnFace: true,
    firstDay: [4, 'b'],
    tokens: ['ferrand', 'odile'],
    spellings: ['Odile', 'Odile Ferrand', 'odile'],
  },
  romy_tremblay: {
    id: 'romy_tremblay',
    name: 'Romy',
    fullName: 'Romy Tremblay',
    spokenName: 'Romy',
    address: 'tu',
    hasDrawnFace: true,
    firstDay: [4, 'a'],
    tokens: ['romane', 'romy', 'tremblay'],
    spellings: ['Romy', 'Romy Tremblay', 'romane', 'romy'],
  },
};

/** The one name the learner reads, by id. */
export const CAST_NAMES: Record<CastPersonId, string> = {
  augustin_de_roncourt: 'Gus',
  bastien_roux: 'Bastien Roux',
  camille_marchand: 'Camille',
  landlord_marchand: 'M. Marchand',
  lila_bonnet: 'Lila',
  maitre_vasseur: 'Maître Vasseur',
  margaux_barman: 'Margaux',
  marin_leveque: 'Marin',
  mme_diallo: 'Mme Diallo',
  odile_ferrand: 'Odile',
  romy_tremblay: 'Romy',
};
