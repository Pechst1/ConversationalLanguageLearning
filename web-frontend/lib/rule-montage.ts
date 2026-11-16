/**
 * Le Montage (grammar pilot, owner's choice of 9 November 2026): a rule built in five taps, on one
 * sentence about people the learner knows, instead of read off a card. A beat is data: what is
 * asked, what is tapped, the sentence the tap makes and the line that then explains it.
 *
 * The subject is a member of the cast on purpose: «Gus» then «Romy» says why the ending changes
 * without a word about grammatical gender. `[…]` marks what carries the rule, as on the rule card.
 */

import type { ControlLanguage } from '@/types/daily-journey';

export type MontageLine = Record<ControlLanguage, string>;
export type MontageCast = { id: string; name: string };

export type MontageToken = {
  /** The word's identity: a kept key glides to its new place, a new key drops in. */
  k: string;
  text: string;
  /** No space follows (the participle before its full stop). */
  tight?: boolean;
  /** The empty place a tile flies into. */
  gap?: boolean;
  /** A helper that no longer fits: greyed, struck and tappable. */
  off?: boolean;
};

export type MontageTap =
  | { kind: 'tile'; label: string }
  | { kind: 'token'; k: string }
  | { kind: 'cast'; cast: MontageCast };

export type MontageBeat = {
  ask: MontageLine;
  tap: MontageTap;
  then: MontageToken[];
  /** The token the tapped tile flies into. */
  flyInto?: string;
  /** The token that shakes because it no longer fits. */
  wobble?: string;
  /** Who the sentence is now about. */
  subject?: MontageCast;
  /** The subject's shape runs along these words; it prints the ending, or it stops. */
  thread?: { through: string[]; blocked?: boolean; prints?: { k: string; text: string } };
  say?: MontageLine;
  /** How long the line holds before the next beat. A tap anywhere ends it. */
  hold: number;
};

export type RuleMontageScript = {
  unit: string;
  subject: MontageCast;
  start: MontageToken[];
  beats: MontageBeat[];
  /** The example sentences it ends on, each with the person it is about. */
  examples: Array<{ cast: MontageCast; fr: string }>;
};

const GUS: MontageCast = { id: 'augustin_de_roncourt', name: 'Gus' };
const ROMY: MontageCast = { id: 'romy_tremblay', name: 'Romy' };

const HIER: MontageToken = { k: 'hier', text: 'Hier,' };
const STOP: MontageToken = { k: 'stop', text: '.' };
const S_GUS: MontageToken = { k: 's-gus', text: 'Gus' };
const S_ROMY: MontageToken = { k: 's-romy', text: 'Romy' };
const MANGE: MontageToken = { k: 'v-mange', text: 'mangé', tight: true };
const PARTI: MontageToken = { k: 'v-parti', text: 'parti', tight: true };

const PC_ETRE: RuleMontageScript = {
  unit: 'FR2_A21_PC_ETRE',
  subject: GUS,
  start: [HIER, S_GUS, { k: 'gap', text: '', gap: true }, MANGE, STOP],
  beats: [
    {
      ask: {
        en: 'Two pieces: a helper and the participle. Tap the helper.',
        de: 'Zwei Teile: ein Hilfsverb und das Partizip. Tippe auf das Hilfsverb.',
        fr: 'Deux pièces : un auxiliaire et le participe. Touche l’auxiliaire.',
      },
      tap: { kind: 'tile', label: 'a' },
      then: [HIER, S_GUS, { k: 'h-a', text: '[a]' }, MANGE, STOP],
      flyInto: 'h-a',
      say: {
        en: 'Most verbs take avoir.',
        de: 'Die meisten Verben nehmen avoir.',
        fr: 'La plupart des verbes prennent avoir.',
      },
      hold: 1500,
    },
    {
      ask: {
        en: 'Now a verb of going. Tap it.',
        de: 'Jetzt ein Verb des Gehens. Tippe darauf.',
        fr: 'Maintenant, un verbe de mouvement. Touche-le.',
      },
      tap: { kind: 'tile', label: 'partir' },
      then: [HIER, S_GUS, { k: 'h-a', text: 'a', off: true }, PARTI, STOP],
      wobble: 'h-a',
      hold: 0,
    },
    {
      ask: {
        en: 'This helper no longer fits. Tap it.',
        de: 'Dieses Hilfsverb passt nicht mehr. Tippe darauf.',
        fr: 'Cet auxiliaire ne va plus. Touche-le.',
      },
      tap: { kind: 'token', k: 'h-a' },
      then: [HIER, S_GUS, { k: 'h-est', text: '[est]' }, PARTI, STOP],
      say: {
        en: 'Coming, going, staying, becoming: être.',
        de: 'Kommen, gehen, bleiben, werden: être.',
        fr: 'Venir, partir, rester, devenir : être.',
      },
      hold: 1500,
    },
    {
      ask: {
        en: 'Now Romy. Tap her.',
        de: 'Jetzt Romy. Tippe auf sie.',
        fr: 'Maintenant, Romy. Touche-la.',
      },
      tap: { kind: 'cast', cast: ROMY },
      then: [HIER, S_ROMY, { k: 'h-est', text: '[est]' }, PARTI, STOP],
      subject: ROMY,
      thread: { through: ['s-romy', 'h-est', 'v-parti'], prints: { k: 'v-parti', text: 'parti[e]' } },
      say: {
        en: 'With être, the participle follows the subject.',
        de: 'Mit être richtet sich das Partizip nach dem Subjekt.',
        fr: 'Avec être, le participe suit le sujet.',
      },
      hold: 1800,
    },
    {
      ask: {
        en: 'Back to manger.',
        de: 'Zurück zu manger.',
        fr: 'Retour à manger.',
      },
      tap: { kind: 'tile', label: 'manger' },
      then: [HIER, S_ROMY, { k: 'h-a2', text: '[a]' }, { ...MANGE, k: 'v-mange2' }, STOP],
      thread: { through: ['s-romy', 'h-a2'], blocked: true },
      say: {
        en: 'With avoir, it does not.',
        de: 'Mit avoir nicht.',
        fr: 'Avec avoir, non.',
      },
      hold: 1900,
    },
  ],
  examples: [
    { cast: GUS, fr: 'Gus [est] parti à huit heures.' },
    { cast: ROMY, fr: 'Romy [est] parti[e] à huit heures.' },
    { cast: ROMY, fr: 'Romy [a] mangé au Mistral.' },
  ],
};

const LILA: MontageCast = { id: 'lila_bonnet', name: 'Lila' };
const MARIN: MontageCast = { id: 'marin_leveque', name: 'Marin' };

/* Step 2 (owner's approval of 10 November 2026): three more rules of the same family, each held to
   its rule card. The pronominal and the negation build on the pilot's être; the object pronoun
   stays in the present, as its card does. */

const MATIN: MontageToken = { k: 'matin', text: 'Ce matin,' };
const REVEILLE: MontageToken = { k: 'v-reveille', text: 'réveillé', tight: true };

const PC_PRONOMINAL: RuleMontageScript = {
  unit: 'FR2_A21_PC_PRONOMINAL',
  subject: MARIN,
  start: [MATIN, { k: 's-marin', text: 'Marin' }, { k: 'h-a', text: 'a' }, { k: 'v-reveille', text: 'réveillé' }, { k: 'o-lila', text: 'Lila', tight: true }, STOP],
  beats: [
    {
      ask: {
        en: 'Marin woke Lila. Now he wakes himself: tap se.',
        de: 'Marin hat Lila geweckt. Jetzt weckt er sich selbst: Tippe auf se.',
        fr: 'Marin a réveillé Lila. Maintenant, il se réveille lui-même : touche se.',
      },
      tap: { kind: 'tile', label: 'se' },
      then: [MATIN, { k: 's-marin', text: 'Marin' }, { k: 'se', text: '[s’]', tight: true }, { k: 'h-a', text: 'a', off: true }, REVEILLE, STOP],
      flyInto: 'se',
      wobble: 'h-a',
      hold: 0,
    },
    {
      ask: {
        en: 'With se, this helper no longer fits. Tap it.',
        de: 'Mit se passt dieses Hilfsverb nicht mehr. Tippe darauf.',
        fr: 'Avec se, cet auxiliaire ne va plus. Touche-le.',
      },
      tap: { kind: 'token', k: 'h-a' },
      then: [MATIN, { k: 's-marin', text: 'Marin' }, { k: 'se', text: '[s’]', tight: true }, { k: 'h-est', text: '[est]' }, REVEILLE, STOP],
      say: {
        en: 'Verbs with se take être.',
        de: 'Verben mit se nehmen être, anders als „ich habe mich“.',
        fr: 'Les verbes avec se prennent être.',
      },
      hold: 1600,
    },
    {
      ask: {
        en: 'Now Lila. Tap her.',
        de: 'Jetzt Lila. Tippe auf sie.',
        fr: 'Maintenant, Lila. Touche-la.',
      },
      tap: { kind: 'cast', cast: LILA },
      then: [MATIN, { k: 's-lila', text: 'Lila' }, { k: 'se', text: '[s’]', tight: true }, { k: 'h-est', text: '[est]' }, REVEILLE, STOP],
      subject: LILA,
      thread: { through: ['s-lila', 'se', 'h-est', 'v-reveille'], prints: { k: 'v-reveille', text: 'réveillé[e]' } },
      say: {
        en: 'The participle follows the subject, as with aller.',
        de: 'Das Partizip richtet sich nach dem Subjekt, wie bei aller.',
        fr: 'Le participe suit le sujet, comme avec aller.',
      },
      hold: 1800,
    },
    {
      ask: {
        en: 'Now Romy and Margaux.',
        de: 'Jetzt Romy und Margaux.',
        fr: 'Maintenant, Romy et Margaux.',
      },
      tap: { kind: 'tile', label: 'Romy et Margaux' },
      then: [MATIN, { k: 's-pl', text: 'Romy et Margaux' }, { k: 'se2', text: '[se]' }, { k: 'h-sont', text: '[sont]' }, { k: 'v-reveille2', text: 'réveillé', tight: true }, STOP],
      flyInto: 's-pl',
      subject: ROMY,
      thread: { through: ['s-pl', 'se2', 'h-sont', 'v-reveille2'], prints: { k: 'v-reveille2', text: 'réveillé[es]' } },
      say: {
        en: 'Two women: se sont, and -es.',
        de: 'Zwei Frauen: se sont und -es.',
        fr: 'Deux femmes : se sont, et -es.',
      },
      hold: 1900,
    },
  ],
  examples: [
    { cast: LILA, fr: 'Hier, Lila [s’est] couché[e] tard.' },
    { cast: MARIN, fr: 'Marin [s’est] levé à six heures.' },
    { cast: ROMY, fr: 'Romy et Margaux [se sont] réveillé[es] tôt.' },
  ],
};

const NE: MontageToken = { k: 'ne', text: '[n’]', tight: true };
const PAS: MontageToken = { k: 'pas', text: '[pas]' };

const PC_NEGATION: RuleMontageScript = {
  unit: 'FR2_A21_PC_NEGATION',
  subject: GUS,
  start: [HIER, S_GUS, { k: 'h-a', text: 'a' }, { k: 'v-vu', text: 'vu' }, { k: 'o-film', text: 'le film', tight: true }, STOP],
  beats: [
    {
      ask: {
        en: 'Make it negative. Tap ne.',
        de: 'Mach den Satz negativ. Tippe auf ne.',
        fr: 'Mets la phrase au négatif. Touche ne.',
      },
      tap: { kind: 'tile', label: 'ne' },
      then: [HIER, S_GUS, NE, { k: 'h-a', text: 'a' }, { k: 'v-vu', text: 'vu' }, { k: 'o-film', text: 'le film', tight: true }, STOP],
      flyInto: 'ne',
      say: {
        en: 'Ne goes before the helper. Before a vowel: n’.',
        de: 'Ne steht vor dem Hilfsverb. Vor einem Vokal: n’.',
        fr: 'Ne se met devant l’auxiliaire. Devant une voyelle : n’.',
      },
      hold: 1500,
    },
    {
      ask: {
        en: 'Now pas. Tap it.',
        de: 'Jetzt pas. Tippe darauf.',
        fr: 'Maintenant, pas. Touche-le.',
      },
      tap: { kind: 'tile', label: 'pas' },
      then: [HIER, S_GUS, NE, { k: 'h-a', text: 'a' }, PAS, { k: 'v-vu', text: 'vu' }, { k: 'o-film', text: 'le film', tight: true }, STOP],
      flyInto: 'pas',
      say: {
        en: 'Ne…pas wraps the helper. The participle comes after pas.',
        de: 'Ne…pas umschließt das Hilfsverb. Das Partizip kommt nach pas.',
        fr: 'Ne…pas entoure l’auxiliaire. Le participe vient après pas.',
      },
      hold: 1800,
    },
    {
      ask: {
        en: 'A verb with être: tap partir.',
        de: 'Ein Verb mit être: Tippe auf partir.',
        fr: 'Un verbe avec être : touche partir.',
      },
      tap: { kind: 'tile', label: 'partir' },
      then: [HIER, S_GUS, NE, { k: 'h-est', text: 'est' }, PAS, PARTI, STOP],
      say: {
        en: 'Same with être: ne…pas goes round est.',
        de: 'Genauso mit être: ne…pas steht um est herum.',
        fr: 'Pareil avec être : ne…pas entoure est.',
      },
      hold: 1600,
    },
    {
      ask: {
        en: 'Never? Tap jamais.',
        de: 'Nie? Tippe auf jamais.',
        fr: 'Jamais ? Touche jamais.',
      },
      tap: { kind: 'tile', label: 'jamais' },
      then: [S_GUS, NE, { k: 'h-est', text: 'est' }, { k: 'jamais', text: '[jamais]' }, PARTI, STOP],
      flyInto: 'jamais',
      say: {
        en: 'Jamais takes the place of pas.',
        de: 'Jamais steht an der Stelle von pas.',
        fr: 'Jamais prend la place de pas.',
      },
      hold: 1800,
    },
  ],
  examples: [
    { cast: MARIN, fr: 'Désolé, je [n’]ai [pas] reçu ton message.' },
    { cast: GUS, fr: 'Hier, Gus [n’]est [pas] parti.' },
    { cast: ROMY, fr: 'Romy [n’]a [jamais] pris l’avion.' },
  ],
};

const COD: RuleMontageScript = {
  unit: 'FR2_A21_COD',
  subject: ROMY,
  start: [S_ROMY, { k: 'v-regarde', text: 'regarde' }, { k: 'o-film', text: 'le film', tight: true }, STOP],
  beats: [
    {
      ask: {
        en: 'Le film comes right after the verb. Tap it.',
        de: 'Le film steht direkt nach dem Verb. Tippe darauf.',
        fr: 'Le film vient juste après le verbe. Touche-le.',
      },
      tap: { kind: 'token', k: 'o-film' },
      then: [S_ROMY, { k: 'p-le', text: '[le]' }, { k: 'v-regarde', text: 'regarde', tight: true }, STOP],
      say: {
        en: 'It becomes le, and le goes before the verb.',
        de: 'Daraus wird le, und le steht vor dem Verb.',
        fr: 'Il devient le, et le se place devant le verbe.',
      },
      hold: 1700,
    },
    {
      ask: {
        en: 'Now la série. Tap it.',
        de: 'Jetzt la série. Tippe darauf.',
        fr: 'Maintenant, la série. Touche-la.',
      },
      tap: { kind: 'tile', label: 'la série' },
      then: [S_ROMY, { k: 'p-la', text: '[la]' }, { k: 'v-regarde', text: 'regarde', tight: true }, STOP],
      flyInto: 'p-la',
      say: { en: 'Feminine: la.', de: 'Weiblich: la.', fr: 'Au féminin : la.' },
      hold: 1300,
    },
    {
      ask: {
        en: 'Now les infos. Tap it.',
        de: 'Jetzt les infos. Tippe darauf.',
        fr: 'Maintenant, les infos. Touche-les.',
      },
      tap: { kind: 'tile', label: 'les infos' },
      then: [S_ROMY, { k: 'p-les', text: '[les]' }, { k: 'v-regarde', text: 'regarde', tight: true }, STOP],
      flyInto: 'p-les',
      say: { en: 'Plural: les.', de: 'Plural: les.', fr: 'Au pluriel : les.' },
      hold: 1300,
    },
    {
      ask: {
        en: 'Back to le film, with adorer. Tap it.',
        de: 'Zurück zu le film, mit adorer. Tippe darauf.',
        fr: 'Retour au film, avec adorer. Touche-le.',
      },
      tap: { kind: 'tile', label: 'adorer' },
      then: [S_ROMY, { k: 'p-l', text: '[l’]', tight: true }, { k: 'v-adore', text: 'adore', tight: true }, STOP],
      say: {
        en: 'Before a vowel, le and la become l’.',
        de: 'Vor einem Vokal werden le und la zu l’.',
        fr: 'Devant une voyelle, le et la deviennent l’.',
      },
      hold: 1800,
    },
  ],
  examples: [
    { cast: MARIN, fr: 'Le rapport ? Je [le] finis ce soir.' },
    { cast: ROMY, fr: 'La série ? Romy [la] regarde le soir.' },
    { cast: GUS, fr: 'Ses clés ? Gus [les] cherche partout.' },
  ],
};

/* Step 3 (owner's «Next Montage batch», 16 November 2026): ten A1/A2 rules that change something you
   can see in the sentence. Each stays inside its rule card; the one wrong sentence on the way is the
   card's own contrast, struck and tapped away. */

const MARGAUX: MontageCast = { id: 'margaux_barman', name: 'Margaux' };

const S_LILA: MontageToken = { k: 's-lila', text: 'Lila' };
const S_MARIN: MontageToken = { k: 's-marin', text: 'Marin' };
const S_MARGAUX: MontageToken = { k: 's-margaux', text: 'Margaux' };

const ADJ_AGREEMENT: RuleMontageScript = {
  unit: 'FR2_A11_ADJ_AGREEMENT',
  subject: GUS,
  start: [S_GUS, { k: 'v-prend', text: 'prend' }, { k: 'n-cafe', text: 'un café' }, { k: 'a-noir', text: 'noir', tight: true }, STOP],
  beats: [
    {
      ask: { en: 'Now Lila. Tap her.', de: 'Jetzt Lila. Tippe auf sie.', fr: 'Maintenant, Lila. Touche-la.' },
      tap: { kind: 'cast', cast: LILA },
      then: [S_LILA, { k: 'v-prend', text: 'prend' }, { k: 'n-cafe', text: 'un café' }, { k: 'a-noir', text: 'noir', tight: true }, STOP],
      subject: LILA,
      thread: { through: ['s-lila', 'n-cafe', 'a-noir'], blocked: true },
      say: {
        en: 'Noir stays: the person does not decide.',
        de: 'Noir bleibt: Die Person entscheidet nicht.',
        fr: 'Noir ne change pas : la personne ne décide pas.',
      },
      hold: 1700,
    },
    {
      ask: { en: 'A cup instead. Tap une tasse.', de: 'Lieber eine Tasse. Tippe auf une tasse.', fr: 'Plutôt une tasse. Touche une tasse.' },
      tap: { kind: 'tile', label: 'une tasse' },
      then: [S_LILA, { k: 'v-prend', text: 'prend' }, { k: 'n-tasse', text: 'une tasse' }, { k: 'a-noir', text: 'noir', tight: true }, STOP],
      flyInto: 'n-tasse',
      thread: { through: ['n-tasse', 'a-noir'], prints: { k: 'a-noir', text: 'noir[e]' } },
      say: {
        en: 'The noun decides: tasse is feminine, so -e.',
        de: 'Das Nomen entscheidet: tasse ist weiblich, also -e.',
        fr: 'Le nom décide : tasse est féminin, donc -e.',
      },
      hold: 1700,
    },
    {
      ask: { en: 'Two cups. Tap deux tasses.', de: 'Zwei Tassen. Tippe auf deux tasses.', fr: 'Deux tasses. Touche deux tasses.' },
      tap: { kind: 'tile', label: 'deux tasses' },
      then: [S_LILA, { k: 'v-prend', text: 'prend' }, { k: 'n-tasses', text: 'deux tasse[s]' }, { k: 'a-noir', text: 'noire', tight: true }, STOP],
      flyInto: 'n-tasses',
      thread: { through: ['n-tasses', 'a-noir'], prints: { k: 'a-noir', text: 'noire[s]' } },
      say: {
        en: 'Plural: -s on the noun and on the adjective.',
        de: 'Plural: -s am Nomen und am Adjektiv.',
        fr: 'Au pluriel : -s au nom et à l’adjectif.',
      },
      hold: 1700,
    },
    {
      ask: { en: 'And the size? Tap petit.', de: 'Und die Größe? Tippe auf petit.', fr: 'Et la taille ? Touche petit.' },
      tap: { kind: 'tile', label: 'petit' },
      then: [S_LILA, { k: 'v-prend', text: 'prend' }, { k: 'd-deux', text: 'deux' }, { k: 'a-petites', text: '[petites]' }, { k: 'n-tasses2', text: 'tasses' }, { k: 'a-noir', text: 'noires', tight: true }, STOP],
      flyInto: 'a-petites',
      say: {
        en: 'A few short ones go before the noun: petit, grand, bon, beau.',
        de: 'Ein paar kurze stehen vor dem Nomen: petit, grand, bon, beau.',
        fr: 'Quelques adjectifs courts vont devant le nom : petit, grand, bon, beau.',
      },
      hold: 1900,
    },
  ],
  examples: [
    { cast: LILA, fr: 'Lila a une petit[e] table blanch[e].' },
    { cast: ROMY, fr: 'Romy porte une veste noir[e].' },
    { cast: GUS, fr: 'Gus a deux chat[s] noir[s].' },
  ],
};

const V_BOIT: MontageToken = { k: 'v-boit', text: 'boit' };
const CAFE: MontageToken = { k: 'n-cafe', text: 'café', tight: true };

const NEGATION: RuleMontageScript = {
  unit: 'FR2_A11_NEGATION',
  subject: MARGAUX,
  start: [S_MARGAUX, V_BOIT, { k: 'a-du', text: 'du' }, CAFE, STOP],
  beats: [
    {
      ask: { en: 'Make it negative. Tap ne.', de: 'Mach den Satz negativ. Tippe auf ne.', fr: 'Mets la phrase au négatif. Touche ne.' },
      tap: { kind: 'tile', label: 'ne' },
      then: [S_MARGAUX, { k: 'ne', text: '[ne]' }, V_BOIT, { k: 'a-du', text: 'du' }, CAFE, STOP],
      flyInto: 'ne',
      say: { en: 'Ne goes before the verb.', de: 'Ne steht vor dem Verb.', fr: 'Ne se met avant le verbe.' },
      hold: 1300,
    },
    {
      ask: { en: 'Now pas. Tap it.', de: 'Jetzt pas. Tippe darauf.', fr: 'Maintenant, pas. Touche-le.' },
      tap: { kind: 'tile', label: 'pas' },
      then: [S_MARGAUX, { k: 'ne', text: '[ne]' }, V_BOIT, { k: 'pas', text: '[pas]' }, { k: 'a-du', text: 'du', off: true }, CAFE, STOP],
      flyInto: 'pas',
      wobble: 'a-du',
      say: {
        en: 'Ne…pas wraps the verb. But du no longer fits.',
        de: 'Ne…pas umklammert das Verb. Aber du passt nicht mehr.',
        fr: 'Ne…pas entoure le verbe. Mais du ne va plus.',
      },
      hold: 1500,
    },
    {
      ask: { en: 'Tap du.', de: 'Tippe auf du.', fr: 'Touche du.' },
      tap: { kind: 'token', k: 'a-du' },
      then: [S_MARGAUX, { k: 'ne', text: '[ne]' }, V_BOIT, { k: 'pas', text: '[pas]' }, { k: 'a-de', text: '[de]' }, CAFE, STOP],
      say: {
        en: 'After pas, un, une, des, du and de la become de.',
        de: 'Nach pas werden un, une, des, du und de la zu de.',
        fr: 'Après pas, un, une, des, du et de la deviennent de.',
      },
      hold: 1800,
    },
    {
      ask: { en: 'Now aimer. Tap it.', de: 'Jetzt aimer. Tippe darauf.', fr: 'Maintenant, aimer. Touche-le.' },
      tap: { kind: 'tile', label: 'aimer' },
      then: [S_MARGAUX, { k: 'ne', text: '[n’]', tight: true }, { k: 'v-aime', text: 'aime' }, { k: 'pas', text: '[pas]' }, { k: 'a-le', text: 'le' }, CAFE, STOP],
      say: {
        en: 'Before a vowel: n’. And le stays after pas.',
        de: 'Vor einem Vokal: n’. Und le bleibt nach pas.',
        fr: 'Devant une voyelle : n’. Et le reste après pas.',
      },
      hold: 1800,
    },
  ],
  examples: [
    { cast: MARGAUX, fr: 'Je [ne] bois [pas] [de] café le soir.' },
    { cast: GUS, fr: 'Gus [n’]aime [pas] le thé.' },
    { cast: ROMY, fr: 'Romy [n’]a [pas] [de] voiture.' },
  ],
};

const MARCHE: MontageToken = { k: 'n-marche', text: 'marché', tight: true };

const CONTRACTIONS: RuleMontageScript = {
  unit: 'FR2_A11_CONTRACTIONS',
  subject: MARIN,
  start: [S_MARIN, { k: 'v-va', text: 'va' }, { k: 'p-a', text: 'à' }, { k: 'd-la', text: 'la' }, { k: 'n-gare', text: 'gare', tight: true }, STOP],
  beats: [
    {
      ask: { en: 'Now the market. Tap le marché.', de: 'Jetzt der Markt. Tippe auf le marché.', fr: 'Maintenant, le marché. Touche le marché.' },
      tap: { kind: 'tile', label: 'le marché' },
      then: [S_MARIN, { k: 'v-va', text: 'va' }, { k: 'p-ale', text: 'à le', off: true }, MARCHE, STOP],
      wobble: 'p-ale',
      hold: 0,
    },
    {
      ask: { en: 'À and le cannot stand side by side. Tap them.', de: 'À und le stehen nie nebeneinander. Tippe darauf.', fr: 'À et le ne restent pas côte à côte. Touche-les.' },
      tap: { kind: 'token', k: 'p-ale' },
      then: [S_MARIN, { k: 'v-va', text: 'va' }, { k: 'p-au', text: '[au]' }, MARCHE, STOP],
      say: { en: 'À + le melt into au.', de: 'À + le verschmelzen zu au.', fr: 'À + le se contractent en au.' },
      hold: 1500,
    },
    {
      ask: { en: 'Coming back. Tap rentrer.', de: 'Zurück. Tippe auf rentrer.', fr: 'Le retour. Touche rentrer.' },
      tap: { kind: 'tile', label: 'rentrer' },
      then: [S_MARIN, { k: 'v-rentre', text: 'rentre' }, { k: 'p-du', text: '[du]' }, MARCHE, STOP],
      say: {
        en: 'De + le melt into du. With les: aux, des.',
        de: 'De + le verschmelzen zu du. Mit les: aux, des.',
        fr: 'De + le se contractent en du. Avec les : aux, des.',
      },
      hold: 1700,
    },
    {
      ask: { en: 'Now la poste. Tap it.', de: 'Jetzt la poste. Tippe darauf.', fr: 'Maintenant, la poste. Touche-la.' },
      tap: { kind: 'tile', label: 'la poste' },
      then: [S_MARIN, { k: 'v-rentre', text: 'rentre' }, { k: 'p-de', text: 'de' }, { k: 'd-la2', text: 'la' }, { k: 'n-poste', text: 'poste', tight: true }, STOP],
      thread: { through: ['p-de', 'd-la2'], blocked: true },
      say: { en: 'La and l’ never melt: de la, à la.', de: 'La und l’ verschmelzen nie: de la, à la.', fr: 'La et l’ ne se contractent jamais : de la, à la.' },
      hold: 1800,
    },
  ],
  examples: [
    { cast: MARIN, fr: 'Marin rentre [du] bureau à sept heures.' },
    { cast: ROMY, fr: 'Romy va [au] cinéma ce soir.' },
    { cast: GUS, fr: 'Gus parle [aux] voisins.' },
  ],
};

const CHERCHE: MontageToken = { k: 'v-cherche', text: 'cherche' };

const POSSESSIVES: RuleMontageScript = {
  unit: 'FR2_A11_POSSESSIVES',
  subject: GUS,
  start: [S_GUS, CHERCHE, { k: 'p-son', text: 'son' }, { k: 'n-tel', text: 'téléphone', tight: true }, STOP],
  beats: [
    {
      ask: { en: 'Now it is Romy’s phone. Tap her.', de: 'Jetzt ist es Romys Handy. Tippe auf sie.', fr: 'Maintenant, c’est le téléphone de Romy. Touche-la.' },
      tap: { kind: 'cast', cast: ROMY },
      then: [S_ROMY, CHERCHE, { k: 'p-son', text: 'son' }, { k: 'n-tel', text: 'téléphone', tight: true }, STOP],
      subject: ROMY,
      thread: { through: ['s-romy', 'p-son'], blocked: true },
      say: {
        en: 'Still son: the owner does not decide.',
        de: 'Immer noch son: Der Besitzer entscheidet nicht.',
        fr: 'Toujours son : le propriétaire ne décide pas.',
      },
      hold: 1700,
    },
    {
      ask: { en: 'Now her key. Tap clé.', de: 'Jetzt ihr Schlüssel. Tippe auf clé.', fr: 'Maintenant, la clé. Touche clé.' },
      tap: { kind: 'tile', label: 'clé' },
      then: [S_ROMY, CHERCHE, { k: 'p-sa', text: '[sa]' }, { k: 'n-cle', text: 'clé', tight: true }, STOP],
      flyInto: 'n-cle',
      say: { en: 'The thing decides: clé is feminine, so sa.', de: 'Die Sache entscheidet: clé ist weiblich, also sa.', fr: 'La chose décide : clé est féminin, donc sa.' },
      hold: 1700,
    },
    {
      ask: { en: 'All her keys. Tap clés.', de: 'Alle ihre Schlüssel. Tippe auf clés.', fr: 'Toutes les clés. Touche clés.' },
      tap: { kind: 'tile', label: 'clés' },
      then: [S_ROMY, CHERCHE, { k: 'p-ses', text: '[ses]' }, { k: 'n-cles', text: 'clés', tight: true }, STOP],
      flyInto: 'n-cles',
      say: { en: 'Plural: ses.', de: 'Plural: ses.', fr: 'Au pluriel : ses.' },
      hold: 1300,
    },
    {
      ask: { en: 'Now her address. Tap adresse.', de: 'Jetzt ihre Adresse. Tippe auf adresse.', fr: 'Maintenant, l’adresse. Touche adresse.' },
      tap: { kind: 'tile', label: 'adresse' },
      then: [S_ROMY, CHERCHE, { k: 'p-sa2', text: 'sa', off: true }, { k: 'n-adresse', text: 'adresse', tight: true }, STOP],
      flyInto: 'n-adresse',
      wobble: 'p-sa2',
      hold: 0,
    },
    {
      ask: { en: 'Sa before a vowel does not fit. Tap it.', de: 'Sa vor einem Vokal passt nicht. Tippe darauf.', fr: 'Sa devant une voyelle ne va pas. Touche-le.' },
      tap: { kind: 'token', k: 'p-sa2' },
      then: [S_ROMY, CHERCHE, { k: 'p-son2', text: '[son]' }, { k: 'n-adresse', text: 'adresse', tight: true }, STOP],
      say: {
        en: 'Feminine, but before a vowel: son.',
        de: 'Weiblich, aber vor einem Vokal: son.',
        fr: 'Féminin, mais devant une voyelle : son.',
      },
      hold: 1800,
    },
  ],
  examples: [
    { cast: LILA, fr: '[Mon] frère et [ma] sœur arrivent ce soir.' },
    { cast: GUS, fr: 'Gus cherche [sa] clé et [son] téléphone.' },
    { cast: ROMY, fr: 'Romy a oublié [ses] lunettes.' },
  ],
};

const SOIR: MontageToken = { k: 'soir', text: 'Ce soir,' };
const CHEZ: MontageToken = { k: 'chez', text: 'chez Margaux', tight: true };

const FUTUR_PROCHE: RuleMontageScript = {
  unit: 'FR2_A12_FUTUR_PROCHE',
  subject: ROMY,
  start: [SOIR, S_ROMY, { k: 'v-dine', text: 'dîne' }, CHEZ, STOP],
  beats: [
    {
      ask: { en: 'It is a plan. Tap aller.', de: 'Es ist ein Plan. Tippe auf aller.', fr: 'C’est un projet. Touche aller.' },
      tap: { kind: 'tile', label: 'aller' },
      then: [SOIR, S_ROMY, { k: 'h-va', text: '[va]' }, { k: 'v-dine', text: 'dîne', off: true }, CHEZ, STOP],
      flyInto: 'h-va',
      wobble: 'v-dine',
      hold: 0,
    },
    {
      ask: { en: 'The second verb no longer fits. Tap it.', de: 'Das zweite Verb passt nicht mehr. Tippe darauf.', fr: 'Le deuxième verbe ne va plus. Touche-le.' },
      tap: { kind: 'token', k: 'v-dine' },
      then: [SOIR, S_ROMY, { k: 'h-va', text: '[va]' }, { k: 'v-diner', text: '[dîner]' }, CHEZ, STOP],
      say: {
        en: 'Aller + the infinitive: what is going to happen.',
        de: 'Aller + Infinitiv: was gleich passiert.',
        fr: 'Aller + l’infinitif : ce qui va se passer.',
      },
      hold: 1700,
    },
    {
      ask: { en: 'Gus comes too. Tap Gus et Romy.', de: 'Gus kommt mit. Tippe auf Gus et Romy.', fr: 'Gus vient aussi. Touche Gus et Romy.' },
      tap: { kind: 'tile', label: 'Gus et Romy' },
      then: [SOIR, { k: 's-pl', text: 'Gus et Romy' }, { k: 'h-vont', text: '[vont]' }, { k: 'v-diner', text: 'dîner' }, CHEZ, STOP],
      flyInto: 's-pl',
      thread: { through: ['s-pl', 'h-vont', 'v-diner'], blocked: true },
      say: {
        en: 'Only aller changes. Dîner stays as it is.',
        de: 'Nur aller ändert sich. Dîner bleibt, wie es ist.',
        fr: 'Seul aller change. Dîner reste à l’infinitif.',
      },
      hold: 1800,
    },
    {
      ask: { en: 'Plans change. Tap ne…pas.', de: 'Pläne ändern sich. Tippe auf ne…pas.', fr: 'Les projets changent. Touche ne…pas.' },
      tap: { kind: 'tile', label: 'ne…pas' },
      then: [SOIR, { k: 's-pl', text: 'Gus et Romy' }, { k: 'ne', text: '[ne]' }, { k: 'h-vont', text: 'vont' }, { k: 'pas', text: '[pas]' }, { k: 'v-diner', text: 'dîner' }, CHEZ, STOP],
      say: {
        en: 'Negative: ne…pas goes round aller.',
        de: 'Verneint: ne…pas steht um aller herum.',
        fr: 'À la forme négative, ne…pas encadre aller.',
      },
      hold: 1800,
    },
  ],
  examples: [
    { cast: ROMY, fr: 'Ce soir, Romy [va dîner] chez Margaux.' },
    { cast: MARIN, fr: 'Marin [va appeler] Lila demain.' },
    { cast: GUS, fr: 'Demain, Gus [va prendre] le train.' },
  ],
};

const PREND: MontageToken = { k: 'v-prend', text: 'prend' };

const PARTITIVE: RuleMontageScript = {
  unit: 'FR2_A11_PARTITIVE',
  subject: MARGAUX,
  start: [S_MARGAUX, { k: 'v-aime', text: 'aime' }, { k: 'a-le', text: 'le' }, { k: 'n-pain', text: 'pain', tight: true }, STOP],
  beats: [
    {
      ask: {
        en: 'Margaux likes bread. Now she takes some: tap prendre.',
        de: 'Margaux mag Brot. Jetzt nimmt sie welches: Tippe auf prendre.',
        fr: 'Margaux aime le pain. Maintenant, elle se sert : touche prendre.',
      },
      tap: { kind: 'tile', label: 'prendre' },
      then: [S_MARGAUX, PREND, { k: 'a-dele', text: 'de le', off: true }, { k: 'n-pain', text: 'pain', tight: true }, STOP],
      wobble: 'a-dele',
      hold: 0,
    },
    {
      ask: { en: 'De le does not exist. Tap it.', de: 'De le gibt es nicht. Tippe darauf.', fr: 'De le n’existe pas. Touche-le.' },
      tap: { kind: 'token', k: 'a-dele' },
      then: [S_MARGAUX, PREND, { k: 'a-du', text: '[du]' }, { k: 'n-pain', text: 'pain', tight: true }, STOP],
      say: {
        en: 'Some of what you don’t count: du.',
        de: 'Eine Menge, die man nicht zählt: du.',
        fr: 'Une quantité qu’on ne compte pas : du.',
      },
      hold: 1700,
    },
    {
      ask: { en: 'Now soup. Tap la soupe.', de: 'Jetzt Suppe. Tippe auf la soupe.', fr: 'Maintenant, la soupe. Touche la soupe.' },
      tap: { kind: 'tile', label: 'la soupe' },
      then: [S_MARGAUX, PREND, { k: 'a-dela', text: '[de la]' }, { k: 'n-soupe', text: 'soupe', tight: true }, STOP],
      flyInto: 'n-soupe',
      say: { en: 'Feminine: de la.', de: 'Weiblich: de la.', fr: 'Au féminin : de la.' },
      hold: 1300,
    },
    {
      ask: { en: 'Now water. Tap l’eau.', de: 'Jetzt Wasser. Tippe auf l’eau.', fr: 'Maintenant, l’eau. Touche l’eau.' },
      tap: { kind: 'tile', label: 'l’eau' },
      then: [S_MARGAUX, PREND, { k: 'a-del', text: '[de l’]', tight: true }, { k: 'n-eau', text: 'eau', tight: true }, STOP],
      flyInto: 'n-eau',
      say: { en: 'Before a vowel: de l’.', de: 'Vor einem Vokal: de l’.', fr: 'Devant une voyelle : de l’.' },
      hold: 1500,
    },
  ],
  examples: [
    { cast: MARGAUX, fr: 'Je voudrais [du] pain et [de la] confiture.' },
    { cast: GUS, fr: 'Gus fait [du] sport le dimanche.' },
    { cast: LILA, fr: 'Lila boit [de l’]eau.' },
  ],
};

const H_A: MontageToken = { k: 'h-a', text: '[a]' };

const PC_AVOIR: RuleMontageScript = {
  unit: 'FR2_A21_PC_AVOIR',
  subject: GUS,
  start: [S_GUS, { k: 'v-mange', text: 'mange' }, { k: 'o-pizza', text: 'une pizza', tight: true }, STOP],
  beats: [
    {
      ask: { en: 'That was yesterday. Tap avoir.', de: 'Das war gestern. Tippe auf avoir.', fr: 'C’était hier. Touche avoir.' },
      tap: { kind: 'tile', label: 'avoir' },
      then: [HIER, S_GUS, H_A, { k: 'v-mange', text: 'manger', off: true }, { k: 'o-pizza', text: 'une pizza', tight: true }, STOP],
      flyInto: 'h-a',
      wobble: 'v-mange',
      hold: 0,
    },
    {
      ask: { en: 'After avoir, not the infinitive. Tap it.', de: 'Nach avoir kein Infinitiv. Tippe darauf.', fr: 'Après avoir, pas d’infinitif. Touche-le.' },
      tap: { kind: 'token', k: 'v-mange' },
      then: [HIER, S_GUS, H_A, { k: 'v-mange2', text: 'mang[é]' }, { k: 'o-pizza', text: 'une pizza', tight: true }, STOP],
      say: {
        en: 'Avoir + the participle: -er becomes -é. Same sound, other letters.',
        de: 'Avoir + Partizip: -er wird zu -é. Gleicher Klang, andere Buchstaben.',
        fr: 'Avoir + le participe : -er devient -é. Même son, autres lettres.',
      },
      hold: 1900,
    },
    {
      ask: { en: 'Now finir. Tap it.', de: 'Jetzt finir. Tippe darauf.', fr: 'Maintenant, finir. Touche-le.' },
      tap: { kind: 'tile', label: 'finir' },
      then: [HIER, S_GUS, H_A, { k: 'v-fini', text: 'fin[i]' }, { k: 'o-projet', text: 'le projet', tight: true }, STOP],
      say: { en: '-ir becomes -i.', de: '-ir wird zu -i.', fr: '-ir devient -i.' },
      hold: 1300,
    },
    {
      ask: { en: 'Now attendre. Tap it.', de: 'Jetzt attendre. Tippe darauf.', fr: 'Maintenant, attendre. Touche-le.' },
      tap: { kind: 'tile', label: 'attendre' },
      then: [HIER, S_GUS, H_A, { k: 'v-attendu', text: 'attend[u]' }, { k: 'o-romy', text: 'Romy', tight: true }, STOP],
      say: { en: '-re becomes -u.', de: '-re wird zu -u.', fr: '-re devient -u.' },
      hold: 1300,
    },
    {
      ask: { en: 'Now prendre. Tap it.', de: 'Jetzt prendre. Tippe darauf.', fr: 'Maintenant, prendre. Touche-le.' },
      tap: { kind: 'tile', label: 'prendre' },
      then: [HIER, S_GUS, H_A, { k: 'v-pris', text: '[pris]' }, { k: 'o-train', text: 'le train', tight: true }, STOP],
      say: {
        en: 'A few you learn as they are: fait, pris, vu, eu.',
        de: 'Ein paar lernst du so, wie sie sind: fait, pris, vu, eu.',
        fr: 'Quelques-uns s’apprennent tels quels : fait, pris, vu, eu.',
      },
      hold: 1800,
    },
  ],
  examples: [
    { cast: GUS, fr: 'Gus [a] mang[é] au Mistral.' },
    { cast: ROMY, fr: 'Romy [a] attend[u] le bus.' },
    { cast: MARIN, fr: 'Marin [a] [pris] le train de sept heures.' },
  ],
};

const TELEPHONE: MontageToken = { k: 'v-tel', text: 'téléphone', tight: true };

const COI: RuleMontageScript = {
  unit: 'FR2_A21_COI',
  subject: LILA,
  start: [S_LILA, { k: 'v-tel', text: 'téléphone' }, { k: 'o-marin', text: 'à Marin', tight: true }, STOP],
  beats: [
    {
      ask: { en: 'À + a person: tap à Marin.', de: 'À + Person: Tippe auf à Marin.', fr: 'À + une personne : touche à Marin.' },
      tap: { kind: 'token', k: 'o-marin' },
      then: [S_LILA, { k: 'p-lui', text: '[lui]' }, TELEPHONE, STOP],
      say: {
        en: 'It becomes lui, and lui goes before the verb.',
        de: 'Daraus wird lui, und lui steht vor dem Verb.',
        fr: 'Il devient lui, et lui se place devant le verbe.',
      },
      hold: 1700,
    },
    {
      ask: { en: 'Now à Romy. Tap it.', de: 'Jetzt à Romy. Tippe darauf.', fr: 'Maintenant, à Romy. Touche-le.' },
      tap: { kind: 'tile', label: 'à Romy' },
      then: [S_LILA, { k: 'p-lui2', text: '[lui]' }, TELEPHONE, STOP],
      flyInto: 'p-lui2',
      say: { en: 'Lui again: him and her alike.', de: 'Wieder lui: für ihn und für sie.', fr: 'Encore lui : pour lui et pour elle.' },
      hold: 1500,
    },
    {
      ask: { en: 'Now à ses amis. Tap it.', de: 'Jetzt à ses amis. Tippe darauf.', fr: 'Maintenant, à ses amis. Touche-le.' },
      tap: { kind: 'tile', label: 'à ses amis' },
      then: [S_LILA, { k: 'p-leur', text: '[leur]' }, TELEPHONE, STOP],
      flyInto: 'p-leur',
      say: {
        en: 'Several people: leur, never with -s.',
        de: 'Mehrere Personen: leur, nie mit -s.',
        fr: 'Plusieurs personnes : leur, jamais de -s.',
      },
      hold: 1600,
    },
    {
      ask: { en: 'Now écrire. Tap it.', de: 'Jetzt écrire. Tippe darauf.', fr: 'Maintenant, écrire. Touche-le.' },
      tap: { kind: 'tile', label: 'écrire' },
      then: [S_LILA, { k: 'p-leur', text: '[leur]' }, { k: 'v-ecrit', text: 'écrit', tight: true }, STOP],
      say: {
        en: 'Verbs with à take lui and leur: parler à, écrire à, répondre à.',
        de: 'Verben mit à nehmen lui und leur: parler à, écrire à, répondre à.',
        fr: 'Les verbes avec à prennent lui et leur : parler à, écrire à, répondre à.',
      },
      hold: 1900,
    },
  ],
  examples: [
    { cast: LILA, fr: 'Ma mère ? Je [lui] téléphone tous les dimanches.' },
    { cast: MARIN, fr: 'Romy ? Marin [lui] écrit ce soir.' },
    { cast: GUS, fr: 'Ses voisins ? Gus [leur] parle souvent.' },
  ],
};

const VA: MontageToken = { k: 'v-va', text: 'va', tight: true };

const Y_PLACE: RuleMontageScript = {
  unit: 'FR2_A21_Y_PLACE',
  subject: MARGAUX,
  start: [S_MARGAUX, { k: 'v-va', text: 'va' }, { k: 'o-marche', text: 'au marché', tight: true }, STOP],
  beats: [
    {
      ask: { en: 'Au marché is the place. Tap it.', de: 'Au marché ist der Ort. Tippe darauf.', fr: 'Au marché, c’est le lieu. Touche-le.' },
      tap: { kind: 'token', k: 'o-marche' },
      then: [S_MARGAUX, { k: 'p-y', text: '[y]' }, VA, STOP],
      say: {
        en: 'Y replaces the place, before the verb.',
        de: 'Y ersetzt den Ort und steht vor dem Verb.',
        fr: 'Y remplace le lieu, devant le verbe.',
      },
      hold: 1600,
    },
    {
      ask: { en: 'Now chez Lila. Tap it.', de: 'Jetzt chez Lila. Tippe darauf.', fr: 'Maintenant, chez Lila. Touche-le.' },
      tap: { kind: 'tile', label: 'chez Lila' },
      then: [S_MARGAUX, { k: 'p-y2', text: '[y]' }, VA, STOP],
      flyInto: 'p-y2',
      say: {
        en: 'Au marché, à Lyon, chez Lila: any place becomes y.',
        de: 'Au marché, à Lyon, chez Lila: Jeder Ort wird zu y.',
        fr: 'Au marché, à Lyon, chez Lila : tout lieu devient y.',
      },
      hold: 1700,
    },
    {
      ask: { en: 'Make it negative. Tap ne…pas.', de: 'Mach den Satz negativ. Tippe auf ne…pas.', fr: 'Mets la phrase au négatif. Touche ne…pas.' },
      tap: { kind: 'tile', label: 'ne…pas' },
      then: [S_MARGAUX, { k: 'ne', text: '[n’]', tight: true }, { k: 'p-y2', text: '[y]' }, { k: 'v-va', text: 'va' }, { k: 'pas', text: '[pas]', tight: true }, STOP],
      say: { en: 'Y stays right before the verb: n’y va pas.', de: 'Y bleibt direkt vor dem Verb: n’y va pas.', fr: 'Y reste juste devant le verbe : n’y va pas.' },
      hold: 1700,
    },
    {
      ask: { en: 'Two verbs. Tap aller.', de: 'Zwei Verben. Tippe auf aller.', fr: 'Deux verbes. Touche aller.' },
      tap: { kind: 'tile', label: 'aller' },
      then: [S_MARGAUX, { k: 'ne', text: 'ne' }, { k: 'v-va', text: 'va' }, { k: 'pas', text: 'pas' }, { k: 'p-y2', text: '[y]' }, { k: 'v-aller', text: 'aller', tight: true }, STOP],
      say: {
        en: 'With two verbs, y goes before the infinitive.',
        de: 'Bei zwei Verben steht y vor dem Infinitiv.',
        fr: 'Avec deux verbes, y se place devant l’infinitif.',
      },
      hold: 1800,
    },
  ],
  examples: [
    { cast: MARGAUX, fr: 'Le nouveau café ? J’[y] vais tous les matins.' },
    { cast: ROMY, fr: 'Le marché ? Romy [y] va le samedi.' },
    { cast: GUS, fr: 'Lyon ? Gus va [y] aller demain.' },
  ],
};

const EN: MontageToken = { k: 'p-en', text: '[en]' };

const EN_QUANTITY: RuleMontageScript = {
  unit: 'FR2_A21_EN_QUANTITY',
  subject: LILA,
  start: [S_LILA, { k: 'v-prend', text: 'prend' }, { k: 'o-pommes', text: 'des pommes', tight: true }, STOP],
  beats: [
    {
      ask: { en: 'Des pommes: tap it.', de: 'Des pommes: Tippe darauf.', fr: 'Des pommes : touche-le.' },
      tap: { kind: 'token', k: 'o-pommes' },
      then: [S_LILA, EN, { k: 'v-prend', text: 'prend', tight: true }, STOP],
      say: {
        en: 'En replaces des + the thing, before the verb.',
        de: 'En ersetzt des + Sache und steht vor dem Verb.',
        fr: 'En remplace des + la chose, devant le verbe.',
      },
      hold: 1700,
    },
    {
      ask: { en: 'How many? Tap un kilo.', de: 'Wie viele? Tippe auf un kilo.', fr: 'Combien ? Touche un kilo.' },
      tap: { kind: 'tile', label: 'un kilo' },
      then: [S_LILA, EN, { k: 'v-prend', text: 'prend' }, { k: 'q-kilo', text: '[un kilo]', tight: true }, STOP],
      flyInto: 'q-kilo',
      say: { en: 'The amount stays at the end.', de: 'Die Menge bleibt am Ende.', fr: 'La quantité reste à la fin.' },
      hold: 1500,
    },
    {
      ask: { en: 'Just two. Tap deux.', de: 'Nur zwei. Tippe auf deux.', fr: 'Juste deux. Touche deux.' },
      tap: { kind: 'tile', label: 'deux' },
      then: [S_LILA, EN, { k: 'v-prend', text: 'prend' }, { k: 'q-deux', text: '[deux]', tight: true }, STOP],
      flyInto: 'q-deux',
      say: {
        en: 'A number on its own needs en.',
        de: 'Eine Zahl allein braucht en.',
        fr: 'Un nombre seul a besoin de en.',
      },
      hold: 1500,
    },
    {
      ask: { en: 'That was this morning. Tap acheter.', de: 'Das war heute Morgen. Tippe auf acheter.', fr: 'C’était ce matin. Touche acheter.' },
      tap: { kind: 'tile', label: 'acheter' },
      then: [S_LILA, { k: 'p-en', text: '[en]' }, { k: 'h-a', text: 'a' }, { k: 'v-achete', text: 'acheté' }, { k: 'q-deux', text: '[deux]', tight: true }, STOP],
      say: {
        en: 'In the past, en goes before avoir.',
        de: 'In der Vergangenheit steht en vor avoir.',
        fr: 'Au passé, en se place devant avoir.',
      },
      hold: 1800,
    },
  ],
  examples: [
    { cast: LILA, fr: 'Des pommes ? J’[en] voudrais [un kilo].' },
    { cast: MARGAUX, fr: 'Des croissants ? Margaux [en] prend [quatre].' },
    { cast: GUS, fr: 'Des frères ? Gus [en] a [deux].' },
  ],
};

const MONTAGES: Record<string, RuleMontageScript> = {
  [PC_ETRE.unit]: PC_ETRE,
  [PC_PRONOMINAL.unit]: PC_PRONOMINAL,
  [COD.unit]: COD,
  [PC_NEGATION.unit]: PC_NEGATION,
  [ADJ_AGREEMENT.unit]: ADJ_AGREEMENT,
  [NEGATION.unit]: NEGATION,
  [CONTRACTIONS.unit]: CONTRACTIONS,
  [POSSESSIVES.unit]: POSSESSIVES,
  [FUTUR_PROCHE.unit]: FUTUR_PROCHE,
  [PARTITIVE.unit]: PARTITIVE,
  [PC_AVOIR.unit]: PC_AVOIR,
  [COI.unit]: COI,
  [Y_PLACE.unit]: Y_PLACE,
  [EN_QUANTITY.unit]: EN_QUANTITY,
};

export const MONTAGE_COPY: Record<ControlLanguage, { skip: string; replay: string }> = {
  en: { skip: 'Skip', replay: 'Replay' },
  de: { skip: 'Überspringen', replay: 'Noch einmal' },
  fr: { skip: 'Passer', replay: 'Revoir' },
};

export function montageFor(unit: string | null | undefined): RuleMontageScript | null {
  return (unit && MONTAGES[unit]) || null;
}

/** The sentence as a learner reads it, without the marks. */
export function montageSentence(tokens: MontageToken[]): string {
  return tokens
    .map((token, index) => {
      const text = token.gap ? '___' : token.text.replace(/[[\]]/g, '');
      return index < tokens.length - 1 && !token.tight ? `${text} ` : text;
    })
    .join('');
}

const seenKey = (unit: string) => `atelier.montage.${unit}`;

/** Storage that refuses counts as «not seen»: the worst case is playing it once more. */
export function montageSeen(unit: string): boolean {
  if (typeof window === 'undefined') return false;
  try {
    return window.localStorage?.getItem(seenKey(unit)) === '1';
  } catch {
    return false;
  }
}

export function markMontageSeen(unit: string): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage?.setItem(seenKey(unit), '1');
  } catch {
    /* storage refused: it plays again next time */
  }
}
