/**
 * Le Quartier · the market: stalls, what is on them, and what it costs.
 *
 * A Paris street market is trestle tables under striped canvas, crates tipped toward you, a
 * slate in every crate with the price in chalk. The prices are the lesson (a kilo, a bunch, a
 * piece, a hundred grams), so they live here once, for the stalls' slates and for what the
 * stallholders say when you ask (`visit.ts`). They are made up and plausible for an autumn
 * morning in Paris; the forge decides which stall sells what, never the price.
 */
import { Matrix4, Vector3 } from 'three';

import { KERB, boxShape, fitText } from './kit';
import type { Build } from './kit';
import { nextId } from './geo';
import type { Paint } from './geo';
import { INKS, TONES, mix } from './palette';
import type { Hex } from './palette';

export type GoodsKind = 'fruits' | 'legumes' | 'fleurs' | 'olives' | 'fromages' | 'brocante' | 'livres' | 'vaisselle' | 'disques';

type Shape = 'mound' | 'leeks' | 'carrots' | 'big' | 'bunch' | 'bowl' | 'wheel' | 'things' | 'books' | 'plates' | 'records';

export interface Ware {
  /** on the slate */
  label: string;
  /** with its article, in a sentence: «les clémentines» */
  fr: string;
  en: string;
  de: string;
  price: string;
  unit: string;
  /** the price as the stallholder says it */
  say: string;
  color: Hex;
  shape: Shape;
  /** what you ask for at this stall, in the three languages: «un kilo de clémentines» */
  ask: [string, string, string];
  /** what that comes to, on the slate's terms and as it is said: «3,50 €», «trois euros cinquante» */
  total: string;
  pay: string;
  /** the words that name it in what you type, without accents, longest first wins */
  match: string[];
}

interface Order {
  ask: [string, string, string];
  total: string;
  pay: string;
  match: string[];
}

const W = (label: string, fr: string, en: string, de: string, price: string, unit: string, say: string, color: Hex, shape: Shape, o: Order): Ware => ({ label, fr, en, de, price, unit, say, color, shape, ...o });

const orange = mix(INKS.ochre, INKS.vermilion, 0.45);
const apple = mix(INKS.vermilion, INKS.ochre, 0.2);
const pear = mix(INKS.sunflower, INKS.green, 0.35);
const leaf = mix(INKS.green, INKS.sunflower, 0.2);

export const GOODS: Record<GoodsKind, Ware[]> = {
  fruits: [
    W('Clémentines', 'les clémentines', 'clementines', 'Clementinen', '3,50 €', 'le kilo', 'trois euros cinquante le kilo', orange, 'mound', { ask: ['un kilo de clémentines', 'a kilo of clementines', 'ein Kilo Clementinen'], total: '3,50 €', pay: 'trois euros cinquante', match: ['clementine'] }),
    W('Pommes', 'les pommes', 'apples', 'Äpfel', '2,80 €', 'le kilo', 'deux euros quatre-vingts le kilo', apple, 'mound', { ask: ['un kilo de pommes', 'a kilo of apples', 'ein Kilo Äpfel'], total: '2,80 €', pay: 'deux euros quatre-vingts', match: ['pomme'] }),
    W('Poires', 'les poires', 'pears', 'Birnen', '3,20 €', 'le kilo', 'trois euros vingt le kilo', pear, 'mound', { ask: ['un kilo de poires', 'a kilo of pears', 'ein Kilo Birnen'], total: '3,20 €', pay: 'trois euros vingt', match: ['poire'] }),
    W('Raisin', 'le raisin', 'grapes', 'Trauben', '4,50 €', 'le kilo', 'quatre euros cinquante le kilo', mix(INKS.cobalt, INKS.vermilion, 0.35), 'mound', { ask: ['un kilo de raisin', 'a kilo of grapes', 'ein Kilo Trauben'], total: '4,50 €', pay: 'quatre euros cinquante', match: ['raisin'] }),
    W('Kakis', 'les kakis', 'persimmons', 'Kakis', '1 €', 'pièce', 'un euro pièce', mix(INKS.vermilion, INKS.ochre, 0.55), 'mound', { ask: ['deux kakis', 'two persimmons', 'zwei Kakis'], total: '2 €', pay: 'deux euros', match: ['kaki'] }),
    W('Bananes', 'les bananes', 'bananas', 'Bananen', '2,20 €', 'le kilo', 'deux euros vingt le kilo', INKS.sunflower, 'mound', { ask: ['un kilo de bananes', 'a kilo of bananas', 'ein Kilo Bananen'], total: '2,20 €', pay: 'deux euros vingt', match: ['banane'] }),
  ],
  legumes: [
    W('Poireaux', 'les poireaux', 'leeks', 'Lauch', '2 €', 'la botte', 'deux euros la botte', leaf, 'leeks', { ask: ['une botte de poireaux', 'a bunch of leeks', 'ein Bund Lauch'], total: '2 €', pay: 'deux euros', match: ['poireau'] }),
    W('Carottes', 'les carottes', 'carrots', 'Karotten', '1,80 €', 'le kilo', 'un euro quatre-vingts le kilo', orange, 'carrots', { ask: ['un kilo de carottes', 'a kilo of carrots', 'ein Kilo Karotten'], total: '1,80 €', pay: 'un euro quatre-vingts', match: ['carotte'] }),
    W('Pommes de terre', 'les pommes de terre', 'potatoes', 'Kartoffeln', '1,50 €', 'le kilo', 'un euro cinquante le kilo', mix(INKS.ochre, INKS.paper, 0.35), 'mound', { ask: ['deux kilos de pommes de terre', 'two kilos of potatoes', 'zwei Kilo Kartoffeln'], total: '3 €', pay: 'trois euros', match: ['pommes de terre', 'pomme de terre', 'patate'] }),
    W('Potiron', 'le potiron', 'pumpkin', 'Kürbis', '2,50 €', 'le kilo', 'deux euros cinquante le kilo', mix(INKS.vermilion, INKS.ochre, 0.6), 'big', { ask: ['un kilo de potiron', 'a kilo of pumpkin', 'ein Kilo Kürbis'], total: '2,50 €', pay: 'deux euros cinquante', match: ['potiron', 'citrouille'] }),
    W('Choux-fleurs', 'les choux-fleurs', 'cauliflowers', 'Blumenkohl', '2 €', 'pièce', 'deux euros pièce', mix(INKS.card, INKS.sunflower, 0.15), 'big', { ask: ['un chou-fleur', 'a cauliflower', 'einen Blumenkohl'], total: '2 €', pay: 'deux euros', match: ['chou-fleur', 'choux-fleurs', 'chou fleur', 'choux fleurs'] }),
    W('Champignons', 'les champignons', 'mushrooms', 'Pilze', '6 €', 'le kilo', 'six euros le kilo', mix(INKS.paper, INKS.ochre, 0.45), 'mound', { ask: ['trois cents grammes de champignons', 'three hundred grams of mushrooms', 'dreihundert Gramm Pilze'], total: '1,80 €', pay: 'un euro quatre-vingts', match: ['champignon'] }),
    W('Salades', 'les salades', 'lettuces', 'Salat', '1 €', 'pièce', 'un euro pièce', mix(INKS.green, INKS.sunflower, 0.45), 'big', { ask: ['une salade', 'a lettuce', 'einen Salat'], total: '1 €', pay: 'un euro', match: ['salade'] }),
  ],
  fleurs: [
    W('Bouquets', 'les bouquets', 'bunches of flowers', 'Sträuße', '5 €', 'le bouquet', 'cinq euros le bouquet', INKS.vermilion, 'bunch', { ask: ['un bouquet', 'a bunch of flowers', 'einen Strauß'], total: '5 €', pay: 'cinq euros', match: ['bouquet', 'fleur'] }),
    W('Chrysanthèmes', 'les chrysanthèmes', 'chrysanthemums', 'Chrysanthemen', '8 €', 'le pot', 'huit euros le pot', INKS.sunflower, 'bunch', { ask: ['un pot de chrysanthèmes', 'a pot of chrysanthemums', 'einen Topf Chrysanthemen'], total: '8 €', pay: 'huit euros', match: ['chrysantheme'] }),
    W('Roses', 'les roses', 'roses', 'Rosen', '1,50 €', 'pièce', 'un euro cinquante pièce', mix(INKS.vermilion, INKS.card, 0.2), 'bunch', { ask: ['trois roses', 'three roses', 'drei Rosen'], total: '4,50 €', pay: 'quatre euros cinquante', match: ['rose'] }),
  ],
  olives: [
    W('Olives vertes', 'les olives vertes', 'green olives', 'grüne Oliven', '3 €', 'les 100 g', 'trois euros les cent grammes', mix(INKS.green, INKS.sunflower, 0.4), 'bowl', { ask: ['deux cents grammes d’olives vertes', 'two hundred grams of green olives', 'zweihundert Gramm grüne Oliven'], total: '6 €', pay: 'six euros', match: ['olives vertes', 'olive verte'] }),
    W('Olives noires', 'les olives noires', 'black olives', 'schwarze Oliven', '3 €', 'les 100 g', 'trois euros les cent grammes', mix(INKS.ink, INKS.cobalt, 0.25), 'bowl', { ask: ['cent grammes d’olives noires', 'a hundred grams of black olives', 'hundert Gramm schwarze Oliven'], total: '3 €', pay: 'trois euros', match: ['olives noires', 'olive noire', 'olive'] }),
    W('Tapenade', 'la tapenade', 'tapenade', 'Tapenade', '4,50 €', 'le pot', 'quatre euros cinquante le pot', mix(INKS.ink, INKS.green, 0.3), 'bowl', { ask: ['un pot de tapenade', 'a jar of tapenade', 'ein Glas Tapenade'], total: '4,50 €', pay: 'quatre euros cinquante', match: ['tapenade'] }),
  ],
  fromages: [
    W('Comté', 'le comté', 'Comté cheese', 'Comté', '26 €', 'le kilo', 'vingt-six euros le kilo', mix(INKS.sunflower, INKS.card, 0.45), 'wheel', { ask: ['deux cents grammes de comté', 'two hundred grams of Comté', 'zweihundert Gramm Comté'], total: '5,20 €', pay: 'cinq euros vingt', match: ['comte'] }),
    W('Brie', 'le brie', 'Brie', 'Brie', '3 €', 'la part', 'trois euros la part', mix(INKS.card, INKS.ochre, 0.12), 'wheel', { ask: ['une part de brie', 'a slice of Brie', 'ein Stück Brie'], total: '3 €', pay: 'trois euros', match: ['brie'] }),
    W('Chèvre', 'le chèvre', 'goat cheese', 'Ziegenkäse', '3,50 €', 'pièce', 'trois euros cinquante pièce', INKS.card, 'wheel', { ask: ['un chèvre', 'a goat cheese', 'einen Ziegenkäse'], total: '3,50 €', pay: 'trois euros cinquante', match: ['chevre'] }),
  ],
  brocante: [
    W('Tout à 2 €', 'les petits objets', 'bric-a-brac', 'Trödel', '2 €', 'pièce', 'deux euros pièce', INKS.cobalt, 'things', { ask: ['ce petit vase', 'this little vase', 'diese kleine Vase'], total: '2 €', pay: 'deux euros', match: ['vase', 'objet', 'truc'] }),
    W('Lampes', 'les lampes', 'lamps', 'Lampen', '15 €', 'pièce', 'quinze euros pièce', INKS.ochre, 'things', { ask: ['cette lampe', 'this lamp', 'diese Lampe'], total: '15 €', pay: 'quinze euros', match: ['lampe'] }),
  ],
  livres: [
    W('Livres', 'les livres', 'books', 'Bücher', '1 €', 'pièce', 'un euro pièce', TONES.oxblood, 'books', { ask: ['ce livre', 'this book', 'dieses Buch'], total: '1 €', pay: 'un euro', match: ['livre', 'bouquin', 'roman'] }),
    W('Poches', 'les livres de poche', 'paperbacks', 'Taschenbücher', '3 €', 'les quatre', 'trois euros les quatre', INKS.cobalt, 'books', { ask: ['quatre livres de poche', 'four paperbacks', 'vier Taschenbücher'], total: '3 €', pay: 'trois euros', match: ['livres de poche', 'livre de poche', 'poche'] }),
  ],
  vaisselle: [
    W('Assiettes', 'les assiettes', 'plates', 'Teller', '1 €', 'pièce', 'un euro pièce', INKS.card, 'plates', { ask: ['six assiettes', 'six plates', 'sechs Teller'], total: '6 €', pay: 'six euros', match: ['assiette'] }),
    W('Verres', 'les verres', 'glasses', 'Gläser', '5 €', 'les six', 'cinq euros les six', mix(INKS.cobalt, INKS.card, 0.6), 'plates', { ask: ['six verres', 'six glasses', 'sechs Gläser'], total: '5 €', pay: 'cinq euros', match: ['verre'] }),
  ],
  disques: [W('Vinyles', 'les vinyles', 'records', 'Schallplatten', '3 €', 'pièce', 'trois euros pièce', INKS.ink, 'records', { ask: ['ce vinyle', 'this record', 'diese Platte'], total: '3 €', pay: 'trois euros', match: ['vinyle', 'disque'] })],
};

const AWNINGS: Array<[Hex, Hex]> = [
  [INKS.vermilion, INKS.card],
  [INKS.green, INKS.card],
  [INKS.cobalt, INKS.card],
  [mix(INKS.ochre, INKS.vermilion, 0.3), INKS.card],
  [mix(INKS.green, INKS.ink, 0.25), mix(INKS.card, INKS.sunflower, 0.2)],
];

/** What one stall shows: its wares by crate, so the stallholder can name them. */
export interface StallInfo {
  goods: GoodsKind;
  wares: Ware[];
  /** where its front is, in the world, and which way it faces */
  front: Vector3;
  facing: Vector3;
}

/** A local point of a stall turned by `rot` about y, in the world. */
function local(x: number, y: number, z: number, rot: number, lx: number, ly: number, lz: number) {
  const c = Math.cos(rot);
  const s = Math.sin(rot);
  return new Vector3(x + lx * c + lz * s, y + ly, z - lx * s + lz * c);
}

/** A price slate: chalk on black, the name and the price. */
export function priceArt(label: string, price: string, unit: string) {
  return (ctx: CanvasRenderingContext2D, w: number, h: number) => {
    ctx.fillStyle = '#5b4a33';
    ctx.fillRect(0, 0, w, h);
    ctx.fillStyle = '#1d2420';
    ctx.fillRect(w * 0.05, h * 0.06, w * 0.9, h * 0.88);
    ctx.fillStyle = '#f8f3e8';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    const serif = "italic 500 {s}px AtelierSerif, 'EB Garamond', Georgia, serif";
    const sans = "700 {s}px AtelierSans, 'Instrument Sans', system-ui, sans-serif";
    let s = fitText(ctx, label, w * 0.84, Math.round(h * 0.3), serif);
    ctx.font = serif.replace('{s}', String(s));
    ctx.fillText(label, w / 2, h * 0.26);
    s = fitText(ctx, price, w * 0.84, Math.round(h * 0.34), sans);
    ctx.font = sans.replace('{s}', String(s));
    ctx.fillStyle = '#f3c318';
    ctx.fillText(price, w / 2, h * 0.58);
    s = fitText(ctx, unit, w * 0.84, Math.round(h * 0.18), sans);
    ctx.font = sans.replace('{s}', String(Math.min(s, Math.round(h * 0.18))));
    ctx.fillStyle = '#f8f3e8';
    ctx.fillText(unit, w / 2, h * 0.84);
  };
}

/**
 * A market stall at (x, z), its front toward `rot` (radians about y), `w` metres wide: trestles,
 * crates tipped toward you, the slates, a striped canvas overhead. Brocante tables have no
 * canvas and lay things flat.
 */
export function stall(B: Build, x: number, z: number, rot: number, w: number, goods: GoodsKind, seed: number, y = KERB, canvas = true, crateRows = 2): StallInfo {
  const D = B.dry;
  // what is heaped in the crates is small: drawn only near (`B.fine`), the crates themselves always
  const F = B.fine;
  const R = B.rand;
  const wares = GOODS[goods];
  const isFood = goods === 'fruits' || goods === 'legumes' || goods === 'fleurs' || goods === 'olives' || goods === 'fromages';
  const iron: Paint = { color: mix(TONES.iron, INKS.ink, 0.2), id: nextId() };
  const wood: Paint = { color: TONES.woodLight, id: nextId() };
  const crateWood: Paint = { color: mix(TONES.woodLight, INKS.paper, 0.25), id: nextId(), pattern: 0 };
  const cloth = R.pick(AWNINGS);
  const top = 0.82;
  const depth = 1.1;
  const shown: Ware[] = [];
  F.push(new Matrix4().makeRotationY(rot).setPosition(x, y, z));
  D.at(x, y, z, rot, () => {
    // the trestles and the board
    for (const sx of [-w / 2 + 0.15, w / 2 - 0.15]) {
      D.bar(new Vector3(sx, 0, -depth / 2 + 0.1), new Vector3(sx, top, 0.1), 0.035, iron);
      D.bar(new Vector3(sx, 0, depth / 2 - 0.1), new Vector3(sx, top, -0.1), 0.035, iron);
    }
    D.box(0, top, 0, w, 0.04, depth, wood);
    // a cloth hanging to the ground in front
    D.box(0, top / 2 + 0.02, depth / 2 + 0.01, w, top - 0.08, 0.02, { color: cloth[0], id: nextId() }, { nz: false });
    if (isFood) {
      // the crates, two rows, tipped toward the customer
      const n = Math.max(2, Math.floor(w / 0.55));
      const cw = w / n;
      for (let row = 0; row < crateRows; row++) {
        const cz = crateRows === 1 ? 0.1 : row === 0 ? 0.24 : -0.24;
        const cy = top + 0.02 + (row === 0 ? 0 : 0.14);
        for (let i = 0; i < n; i++) {
          // the back row goes on where the front row stopped, so a stall shows all it has
          const ware = wares[(seed + i + row * n) % wares.length];
          shown.push(ware);
          const cx = -w / 2 + cw * (i + 0.5);
          const tip = new Matrix4().makeRotationX(0.32).setPosition(cx, cy, cz);
          D.push(tip);
          F.push(tip);
          crate(B, cw - 0.06, ware, crateWood);
          D.pop();
          F.pop();
        }
      }
      // the scales at one end, a cash tin at the other
      D.box(w / 2 - 0.25, top + 0.12, -0.42, 0.26, 0.16, 0.2, { color: INKS.card, id: nextId() });
      D.cylinder(w / 2 - 0.25, top + 0.2, -0.42, 0.11, 0.11, 0.02, 10, { color: TONES.pewter, id: nextId(), wet: 0.4 });
      // crates stacked behind, for the morning's second load
      for (let k = 0; k < 3; k++) D.box(-w / 2 + 0.4 + k * 0.05, 0.18 + k * 0.32, -depth / 2 - 0.45, 0.55, 0.3, 0.4, crateWood);
    } else {
      // brocante: things laid out flat on a cloth
      D.box(0, top + 0.025, 0, w - 0.05, 0.01, depth - 0.05, { color: mix(cloth[0], INKS.paper, 0.35), id: nextId() });
      const ware = wares[seed % wares.length];
      shown.push(...wares);
      things(B, w, depth, top, ware.shape, R.next());
    }
    if (isFood && canvas) {
      // the canvas: four poles, a striped roof sloping to the front, a valance
      const poleId = nextId();
      const pole: Paint = { color: mix(TONES.iron, INKS.paper, 0.2), id: poleId };
      const hf = 2.15;
      const hb = 2.45;
      for (const sx of [-w / 2, w / 2]) {
        D.cylinder(sx, 0, depth / 2 + 0.25, 0.025, 0.025, hf, 5, pole, { flat: true });
        D.cylinder(sx, 0, -depth / 2 - 0.15, 0.025, 0.025, hb, 5, pole, { flat: true });
      }
      const stripes = Math.max(4, Math.round(w / 0.35));
      const capId = nextId();
      for (let k = 0; k < stripes; k++) {
        const a = -w / 2 - 0.1 + ((w + 0.2) * k) / stripes;
        const b = -w / 2 - 0.1 + ((w + 0.2) * (k + 1)) / stripes;
        const p: Paint = { color: k % 2 ? cloth[1] : cloth[0], id: capId, shade: 0.1 };
        D.quadXYZ([a, hf + 0.02, depth / 2 + 0.45, b, hf + 0.02, depth / 2 + 0.45, b, hb + 0.02, -depth / 2 - 0.25, a, hb + 0.02, -depth / 2 - 0.25], p, capId);
        D.quadXYZ([b, hf + 0.02, depth / 2 + 0.45, a, hf + 0.02, depth / 2 + 0.45, a, hb + 0.02, -depth / 2 - 0.25, b, hb + 0.02, -depth / 2 - 0.25], { ...p, shade: 0.4 }, capId);
        D.quadXYZ([a, hf - 0.2, depth / 2 + 0.45, b, hf - 0.2, depth / 2 + 0.45, b, hf + 0.02, depth / 2 + 0.45, a, hf + 0.02, depth / 2 + 0.45], p, capId);
      }
    }
  });
  F.pop();
  // the slates, in the world, one per crate along the front row, leaning back a little
  if (isFood) {
    const n = Math.max(2, Math.floor(w / 0.55));
    const cw = w / n;
    for (let i = 0; i < n; i++) {
      const ware = shown[i];
      if (!ware || (i % 2 === 1 && n > 3)) continue;
      const c = local(x, y, z, rot, -w / 2 + cw * (i + 0.5), top + 0.3, 0.46);
      B.signs.push({ key: `prix:${ware.label}`, center: c, normal: new Vector3(Math.sin(rot), 0.35, Math.cos(rot)).normalize(), width: 0.3, height: 0.21, density: 230, draw: priceArt(ware.label, ware.price, ware.unit) });
    }
  } else {
    const ware = shown[0];
    const c = local(x, y, z, rot, w / 2 - 0.35, top + 0.16, 0.36);
    B.signs.push({ key: `prix:${ware.label}`, center: c, normal: new Vector3(Math.sin(rot), 0.5, Math.cos(rot)).normalize(), width: 0.34, height: 0.24, density: 210, draw: priceArt(ware.label, ware.price, ware.unit) });
  }
  B.blocks.push(boxShape(x, z, w + 0.1, depth + 0.3, rot));
  const front = local(x, y, z, rot, 0, 0, depth / 2 + 0.6);
  return { goods, wares: shown.filter((v, i, a) => a.indexOf(v) === i), front, facing: new Vector3(Math.sin(rot), 0, Math.cos(rot)) };
}

/** One crate and what is heaped in it (the crate's frame: x across, z toward you, y up). */
function crate(B: Build, cw: number, ware: Ware, wood: Paint) {
  const d = 0.4;
  const h = 0.13;
  // the slatted sides, and a bed of the colour so a crate is never empty from across the street
  B.dry.box(0, h / 2, d / 2, cw, h, 0.02, wood, { ny: false });
  B.dry.box(0, h / 2, -d / 2, cw, h, 0.02, wood, { ny: false });
  B.dry.box(-cw / 2, h / 2, 0, 0.02, h, d, wood, { ny: false });
  B.dry.box(cw / 2, h / 2, 0, 0.02, h, d, wood, { ny: false });
  B.dry.quadXYZ([-cw / 2, h - 0.03, d / 2, cw / 2, h - 0.03, d / 2, cw / 2, h - 0.03, -d / 2, -cw / 2, h - 0.03, -d / 2], { color: ware.color, id: nextId(), shade: 0.05 });
  const D = B.fine;
  const id = nextId();
  const p: Paint = { color: ware.color, id, shade: 0.05 };
  const dark: Paint = { color: mix(ware.color, INKS.ink, 0.22), id };
  switch (ware.shape) {
    case 'leeks':
      for (let i = 0; i < 5; i++) {
        const lx = -cw / 2 + 0.07 + (i * (cw - 0.14)) / 4;
        D.bar(new Vector3(lx, h + 0.04, d / 2 + 0.05), new Vector3(lx, h + 0.06, -d / 2 + 0.05), 0.05, { color: mix(INKS.card, INKS.green, 0.1), id });
        D.bar(new Vector3(lx, h + 0.06, -d / 2 + 0.05), new Vector3(lx + 0.03, h + 0.1, -d / 2 - 0.2), 0.07, p);
      }
      break;
    case 'carrots':
      for (let i = 0; i < 7; i++) {
        const lx = -cw / 2 + 0.05 + (i * (cw - 0.1)) / 6;
        D.bar(new Vector3(lx, h + 0.03, d / 2 - 0.02), new Vector3(lx, h + 0.04, -d / 2 + 0.1), 0.035, p);
        D.bar(new Vector3(lx, h + 0.04, -d / 2 + 0.1), new Vector3(lx, h + 0.1, -d / 2 - 0.08), 0.05, { color: leaf, id: nextId() });
      }
      break;
    case 'big':
      for (let i = 0; i < 2; i++) D.ball(-cw / 4 + (i * cw) / 2, h + 0.08, 0, Math.min(0.13, cw / 4), 0.1, 0.13, i ? dark : p, 1);
      break;
    case 'bunch':
      // flowers: buckets with bunches standing up
      for (let i = 0; i < 2; i++) {
        const bx = -cw / 4 + (i * cw) / 2;
        D.cylinder(bx, 0, 0, 0.1, 0.12, 0.22, 7, { color: TONES.zincDark, id: nextId() });
        D.cylinder(bx, 0.22, 0, 0.01, 0.12, 0.26, 6, { color: leaf, id: nextId() }, { flat: true });
        D.ball(bx, 0.52, 0, 0.13, 0.08, 0.13, i ? dark : p, 1);
      }
      break;
    case 'bowl':
      D.lathe(0, h - 0.05, 0, [[0.06, 0], [0.16, 0.05], [0.18, 0.12]], 8, { color: mix(TONES.woodLight, INKS.ochre, 0.3), id: nextId() });
      D.lathe(0, h + 0.05, 0, [[0.17, 0], [0.12, 0.05], [0, 0.07]], 8, p, { flat: true });
      break;
    case 'wheel':
      D.cylinder(-cw / 5, h - 0.04, 0, 0.15, 0.15, 0.09, 10, p);
      D.cylinder(cw / 5, h - 0.04, 0.02, 0.11, 0.11, 0.06, 10, dark);
      break;
    default: {
      // a heap: a low dome, and a few that rolled to the top
      D.lathe(0, h - 0.06, 0, [[Math.min(0.19, cw / 2 - 0.03), 0], [0.15, 0.08], [0.07, 0.12], [0, 0.13]], 7, p, { flat: true });
      for (let i = 0; i < 3; i++) D.ball(-0.08 + i * 0.08, h + 0.07 + (i % 2) * 0.02, -0.04 + (i % 2) * 0.07, 0.045, 0.045, 0.045, i % 2 ? dark : p, 0);
    }
  }
}

/** What a brocante table holds, laid out (the table's frame: x across, z toward you). */
function things(B: Build, w: number, depth: number, top: number, shape: Shape, roll: number) {
  const D = B.dry;
  const y = top + 0.03;
  const n = Math.max(3, Math.round(w / 0.4));
  for (let i = 0; i < n; i++) {
    const tx = -w / 2 + 0.25 + (i * (w - 0.5)) / (n - 1);
    const tz = ((i * 7 + Math.round(roll * 10)) % 3) * 0.28 - 0.28;
    const id = nextId();
    const c = [INKS.cobalt, INKS.vermilion, INKS.ochre, INKS.green, INKS.card, mix(INKS.sunflower, INKS.paper, 0.3)][(i + Math.round(roll * 6)) % 6];
    const p: Paint = { color: c, id };
    switch (shape) {
      case 'books':
        for (let k = 0; k < 4; k++) D.box(tx + (k - 1.5) * 0.06, y + 0.11, tz, 0.045, 0.22, 0.16, { color: [INKS.cobalt, INKS.vermilion, INKS.green, INKS.ochre][(i + k) % 4], id: nextId() });
        break;
      case 'plates':
        for (let k = 0; k < 3; k++) D.cylinder(tx, y + k * 0.018, tz, 0.11, 0.12, 0.015, 10, { color: k % 2 ? INKS.card : mix(INKS.card, INKS.cobalt, 0.2), id });
        break;
      case 'records':
        D.box(tx, y + 0.16, tz, 0.32, 0.32, 0.03, p);
        D.box(tx + 0.02, y + 0.16, tz - 0.04, 0.32, 0.32, 0.03, { color: INKS.ink, id: nextId() });
        break;
      default:
        if (i % 3 === 0) D.lathe(tx, y, tz, [[0.05, 0], [0.09, 0.08], [0.06, 0.2], [0.035, 0.26], [0.05, 0.3]], 8, p);
        else if (i % 3 === 1) D.box(tx, y + 0.12, tz, 0.3, 0.24, 0.03, { color: mix(TONES.wood, INKS.ochre, 0.2), id });
        else D.cylinder(tx, y, tz, 0.1, 0.12, 0.08, 8, p);
    }
  }
  void depth;
}
