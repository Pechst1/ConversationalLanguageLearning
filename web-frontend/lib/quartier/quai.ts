/**
 * Le Quartier · the quai de Valmy, the canal and the corner of the rue de Lancry.
 *
 * The prototype's exterior: about 400 m of the Canal Saint-Martin with both quays, a green iron
 * footbridge, plane trees in their November ochre, the lamps, the Morris column, a barge, and
 * the corner where Le Mistral keeps its red neon. The layout follows the real quarter in spirit
 * (the canal runs north–south here, the quai de Valmy on its west bank) and is hand-placed, not
 * surveyed: the plan calls for IGN and OpenStreetMap footprints once the prototype has passed.
 */
import { Vector3 } from 'three';

import {
  KERB,
  WALLS,
  awning,
  bench,
  bollard,
  boxShape,
  building,
  circle,
  frameOf,
  morrisColumn,
  planeTree,
  quayLamp,
  rect,
  terraceSet,
  wallLamp,
  worldOf,
} from './kit';
import type { Build, BuildingInfo, BuildingSpec, Shop } from './kit';
import { LACE, PATTERN, nextId } from './geo';
import type { Paint, Rand } from './geo';
import { INKS, TONES, mix, rgb } from './palette';
import { plaqueArt, posterArt, letteringArt } from './signs';

export const PLAN = {
  water: -2.05,
  zMin: -205,
  zMax: 205,
  canal: { x0: -10, x1: 10 },
  valmy: { face: -27, walk: [-27, -24], road: [-24, -17], strip: [-17, -10] },
  jemmapes: { face: 27, walk: [24, 27], road: [17, 24], strip: [10, 17] },
  lancry: { faceN: -6, faceS: 6, road: [-4.2, 4.2], xEnd: -178 },
  bridge: { z0: -48, z1: -44, deckEnd: 3.9, deckTop: 4.55, westFoot: -30, eastFoot: -62 },
  /** Le Mistral's corner: the chamfer runs from (-30, -6) to (-27, -9) */
  mistral: { chamferA: [-30, -6] as [number, number], chamferB: [-27, -9] as [number, number] },
  start: { pos: new Vector3(-15.6, 0, 17), look: new Vector3(-29, 4.2, -8) },
} as const;

export interface Quai {
  mistral: BuildingInfo;
  /** the lamp heads for the light map and the glints */
  easel: { center: Vector3; normal: Vector3 } | null;
}

const SHOPS: Array<Omit<Shop, 'from' | 'to'>> = [
  { kind: 'shutter', name: 'Serrurerie Lambert', trade: 'clés minute', color: mix(INKS.sunflower, INKS.ink, 0.35) },
  { kind: 'shop', name: 'Fromagerie Belin', color: mix(INKS.green, INKS.paper, 0.15), lit: false },
  { kind: 'shutter', name: 'Quincaillerie Morel', color: mix(INKS.cobalt, INKS.ink, 0.15) },
  { kind: 'shop', name: 'Coiffure Mado', color: mix(INKS.vermilion, INKS.paper, 0.25), lit: true },
  { kind: 'shutter', name: 'Caviste du Canal', color: mix(INKS.vermilion, INKS.ink, 0.55) },
  { kind: 'shutter', name: 'Mercerie', trade: 'boutons · fils · rubans', color: mix(INKS.ochre, INKS.paper, 0.2) },
  { kind: 'shutter', name: 'Disquaire', color: INKS.ink },
  { kind: 'shop', name: 'Boulangerie Diallo', trade: 'pain · viennoiseries', color: mix(INKS.ochre, INKS.ink, 0.25), lit: true, awning: INKS.sunflower },
  { kind: 'shutter', name: 'Cycles du Canal', trade: 'vente · réparation', color: INKS.cobalt },
  { kind: 'shop', name: 'Laverie du Quai', trade: 'ouvert 7 h – 22 h', color: INKS.green, lit: true },
  { kind: 'shutter', name: 'Fleurs Capucine', color: mix(INKS.green, INKS.ink, 0.2) },
  { kind: 'shop', name: 'Librairie La Lanterne', trade: 'livres · cartes', color: mix(INKS.vermilion, INKS.ink, 0.45), lit: true, awning: mix(INKS.vermilion, INKS.ink, 0.35) },
  { kind: 'shutter', name: 'Épicerie du Quai', color: mix(INKS.cobalt, INKS.ink, 0.3) },
  { kind: 'shop', name: 'Pharmacie', trade: 'de garde ce soir', color: INKS.green, lit: true },
  { kind: 'shutter', name: 'Atelier de reliure', color: mix(INKS.ochre, INKS.ink, 0.5) },
  { kind: 'shutter', name: 'Pressing du Canal', color: mix(INKS.cobalt, INKS.paper, 0.2) },
  { kind: 'shop', name: 'Galerie Récollets', color: INKS.ink, lit: true },
];

const shopNamed = (name: string) => SHOPS.find((s) => s.name === name) ?? SHOPS[0];

function shopsFor(R: Rand, bays: number, used: { i: number }): Shop[] {
  const out: Shop[] = [];
  let b = 0;
  while (b < bays) {
    const roll = R.next();
    if (roll < 0.22 && b < bays - 1) {
      out.push({ from: b, to: b, kind: 'door', color: R.pick([INKS.green, mix(INKS.green, INKS.ink, 0.3), INKS.cobalt, mix(INKS.vermilion, INKS.ink, 0.4)]) });
      b += 1;
    } else if (roll < 0.75) {
      const span = Math.min(bays - b, R.int(1, 2));
      const s = SHOPS[used.i++ % SHOPS.length];
      out.push({ ...s, from: b, to: b + span - 1 });
      b += span;
    } else {
      out.push({ from: b, to: b, kind: 'wall' });
      b += 1;
    }
  }
  return out;
}

/** A row of buildings along one façade line, from `from` to `to` (street on the right). */
function row(B: Build, from: [number, number], to: [number, number], opts: { style: BuildingSpec['style'] | 'mixed'; widths: [number, number]; depth: [number, number]; used: { i: number }; seed: number; litShare: number }) {
  const R = B.rand;
  const dx = to[0] - from[0];
  const dz = to[1] - from[1];
  const len = Math.hypot(dx, dz);
  const tx = dx / len;
  const tz = dz / len;
  let u = 0;
  let n = 0;
  while (u < len - 4) {
    const w = Math.min(len - u, R.range(opts.widths[0], opts.widths[1]));
    const a: [number, number] = [from[0] + tx * u, from[1] + tz * u];
    const b: [number, number] = [from[0] + tx * (u + w), from[1] + tz * (u + w)];
    const style = opts.style === 'mixed' ? (R.chance(0.6) ? 'haussmann' : 'faubourg') : opts.style;
    const bays = Math.max(2, Math.round(w / (style === 'haussmann' ? 3.0 : 2.7)));
    building(B, {
      runs: [{ a, b, bays, shops: shopsFor(R, bays, opts.used) }],
      depth: R.range(opts.depth[0], opts.depth[1]),
      style,
      storeys: style === 'haussmann' ? R.int(5, 6) : R.int(4, 5),
      wall: R.pick(WALLS),
      balconies: style === 'haussmann' ? [2, 5] : R.chance(0.4) ? [1] : [],
      lit: opts.litShare,
      seed: opts.seed + n,
    });
    u += w;
    n++;
  }
}

/** Lay the whole exterior into the build. */
export function buildQuai(B: Build): Quai {
  const R = B.rand;
  const P = PLAN;
  const { zMin, zMax } = P;
  const used = { i: 3 };

  /* ---- the ground --------------------------------------------------------------------- */
  const W = B.wet;
  const road: Paint = { color: TONES.asphalt, pattern: PATTERN.grit, id: 1 };
  const walk: Paint = { color: TONES.pavement, pattern: PATTERN.grit, id: 2 };
  const setts: Paint = { color: mix(TONES.stoneGround, INKS.cobalt, 0.08), pattern: PATTERN.cobbles, id: 3 };
  const flags: Paint = { color: TONES.quayStone, pattern: PATTERN.flags, id: 4 };
  const kerb: Paint = { color: TONES.curb, id: 5 };
  const top = (x0: number, z0: number, x1: number, z1: number, y: number, p: Paint) => W.quadXYZ([x0, y, z1, x1, y, z1, x1, y, z0, x0, y, z0], p, p.id);
  const kerbX = (x: number, z0: number, z1: number, face: 1 | -1) => B.dry.box(x - face * 0.08, KERB / 2 - 0.02, (z0 + z1) / 2, 0.16, KERB + 0.04, z1 - z0, kerb, { ny: false });
  const kerbZ = (z: number, x0: number, x1: number, face: 1 | -1) => B.dry.box((x0 + x1) / 2, KERB / 2 - 0.02, z - face * 0.08, x1 - x0, KERB + 0.04, 0.16, kerb, { ny: false });

  // the quai de Valmy: canal strip, road, pavement
  top(P.valmy.strip[0], zMin, P.valmy.strip[1] - 0.45, zMax, KERB, setts);
  top(P.valmy.road[0], zMin, P.valmy.road[1], zMax, 0, road);
  kerbX(P.valmy.strip[0], zMin, zMax, -1);
  top(P.valmy.walk[0], zMin, P.valmy.walk[1], P.lancry.road[0], KERB, walk);
  top(P.valmy.walk[0], P.lancry.road[1], P.valmy.walk[1], zMax, KERB, walk);
  kerbX(P.valmy.walk[1], zMin, P.lancry.road[0], 1);
  kerbX(P.valmy.walk[1], P.lancry.road[1], zMax, 1);
  // the quai de Jemmapes
  top(P.jemmapes.strip[0] + 0.45, zMin, P.jemmapes.strip[1], zMax, KERB, setts);
  top(P.jemmapes.road[0], zMin, P.jemmapes.road[1], zMax, 0, road);
  kerbX(P.jemmapes.strip[1], zMin, zMax, 1);
  top(P.jemmapes.walk[0], zMin, P.jemmapes.walk[1], zMax, KERB, walk);
  kerbX(P.jemmapes.walk[0], zMin, zMax, -1);
  // the rue de Lancry: road and two narrow pavements
  const L = P.lancry;
  top(L.xEnd, L.road[0], P.valmy.road[0], L.road[1], 0, road);
  top(L.xEnd, L.faceN, P.valmy.walk[0], L.road[0], KERB, walk);
  top(L.xEnd, L.road[1], P.valmy.walk[0], L.faceS, KERB, walk);
  kerbZ(L.road[0], L.xEnd, P.valmy.walk[1], 1);
  kerbZ(L.road[1], L.xEnd, P.valmy.walk[1], -1);
  // gutters: a darker band where the rain runs
  const gutter: Paint = { color: mix(TONES.asphalt, INKS.ink, 0.25), id: 1 };
  top(P.valmy.road[0], zMin, P.valmy.road[0] + 0.35, P.lancry.road[0], 0.003, gutter);
  top(P.valmy.road[1] - 0.35, zMin, P.valmy.road[1], zMax, 0.003, gutter);
  // zebra crossings: over the rue de Lancry, and over the quai to the café's corner
  const zebra: Paint = { color: mix(INKS.card, INKS.ink, 0.08), id: 6 };
  for (let z = L.road[0] + 0.25; z < L.road[1] - 0.4; z += 1.0) top(-32.5, z, -29.8, z + 0.5, 0.006, zebra);
  for (let x = P.valmy.road[0] + 0.25; x < P.valmy.road[1] - 0.4; x += 1.0) top(x, -11.6, x + 0.5, -9.0, 0.006, zebra);

  // the canal: quay walls of dressed stone, coping, and its iron rings
  const quayWall: Paint = { color: TONES.quayWall, pattern: PATTERN.courses, id: 7 };
  const coping: Paint = { color: mix(TONES.quayStone, INKS.paper, 0.25), id: 8 };
  for (const side of [-1, 1] as const) {
    const xEdge = side * 10;
    B.dry.quadXYZ(
      side < 0
        ? [xEdge, P.water - 0.8, zMax, xEdge, P.water - 0.8, zMin, xEdge, KERB, zMin, xEdge, KERB, zMax]
        : [xEdge, P.water - 0.8, zMin, xEdge, P.water - 0.8, zMax, xEdge, KERB, zMax, xEdge, KERB, zMin],
      quayWall,
    );
    B.dry.box(xEdge + side * 0.22, KERB + 0.06, 0, 0.5, 0.12, zMax - zMin, coping, { ny: false });
    // the water's tide line, a dark band on the stone
    B.dry.box(xEdge - side * 0.006, P.water + 0.25, 0, 0.01, 0.5, zMax - zMin, { color: mix(TONES.quayWall, INKS.green, 0.45), id: 7 }, { ny: false, py: false });
    for (let z = zMin + 7; z < zMax; z += 14) {
      B.dry.cylinder(xEdge + side * 0.7, KERB, z, 0.13, 0.11, 0.42, 7, { color: TONES.iron, id: nextId() });
      B.blocks.push(circle(xEdge + side * 0.7, z, 0.25));
    }
  }
  B.walk.push({ shape: rect(P.valmy.strip[0], zMin, P.valmy.strip[1] - 0.3, zMax), y: KERB });
  B.walk.push({ shape: rect(P.valmy.road[0], zMin, P.valmy.road[1], zMax), y: 0 });
  B.walk.push({ shape: rect(P.valmy.walk[0], zMin, P.valmy.walk[1], zMax), y: KERB });
  B.walk.push({ shape: rect(L.xEnd, L.faceN, P.valmy.walk[0], L.faceS), y: KERB });
  B.walk.push({ shape: rect(L.xEnd, L.road[0], P.valmy.road[0], L.road[1]), y: 0 });
  B.walk.push({ shape: rect(P.jemmapes.strip[0] + 0.3, zMin, P.jemmapes.strip[1], zMax), y: KERB });
  B.walk.push({ shape: rect(P.jemmapes.road[0], zMin, P.jemmapes.road[1], zMax), y: 0 });
  B.walk.push({ shape: rect(P.jemmapes.walk[0], zMin, P.jemmapes.walk[1], zMax), y: KERB });

  /* ---- Le Mistral's building: the corner, with its chamfer ------------------------------- */
  const mistral = building(B, {
    runs: [
      {
        a: [-27, -9],
        b: [-27, -28.5],
        bays: 6,
        shops: [
          { from: 0, to: 2, kind: 'none' },
          { from: 3, to: 3, kind: 'door', color: mix(INKS.green, INKS.ink, 0.12) },
          { from: 4, to: 5, kind: 'shutter', name: 'Gérance Marchand', trade: 'administration de biens · 2e étage', color: mix(INKS.ink, INKS.cobalt, 0.3) },
        ],
      },
      { a: [-30, -6], b: [-27, -9], bays: 1, shops: [{ from: 0, to: 0, kind: 'none' }] },
      {
        a: [-53, -6],
        b: [-30, -6],
        bays: 7,
        shops: [
          { from: 0, to: 1, kind: 'shop', name: 'Atelier de reliure', trade: 'L. Barthe, relieur', color: mix(INKS.ochre, INKS.ink, 0.5) },
          { from: 2, to: 4, kind: 'wall' },
          { from: 5, to: 6, kind: 'none' },
        ],
      },
    ],
    footprint: [
      [-27, -9],
      [-27, -28.5],
      [-53, -28.5],
      [-53, -6],
      [-30, -6],
    ],
    street: [true, false, false, true, true],
    style: 'haussmann',
    storeys: 5,
    wall: TONES.stone,
    balconies: [2, 5],
    lit: 0.36,
    // Odile's flat on the first floor: shutters closed since April 2023
    shut: ['0:1:0', '0:1:1', '0:1:2', '1:1:0', '2:1:5', '2:1:6'],
    hollowGround: true,
    seed: 1,
  });
  // the street plaques at the corner
  B.signs.push({ key: 'plaque:valmy', center: new Vector3(-26.98, 4.0, -10.6), normal: new Vector3(1, 0, 0), width: 0.95, height: 0.42, density: 260, draw: plaqueArt('Quai de Valmy') });
  B.signs.push({ key: 'plaque:lancry', center: new Vector3(-31.6, 4.0, -5.98), normal: new Vector3(0, 0, 1), width: 0.95, height: 0.42, density: 260, draw: plaqueArt('Rue de Lancry') });
  B.signs.push({ key: 'plaque:jemmapes', center: new Vector3(26.98, 4.0, -8), normal: new Vector3(-1, 0, 0), width: 1.1, height: 0.42, density: 260, draw: plaqueArt('Quai de Jemmapes') });
  // the corner's other side of the rue de Lancry
  building(B, {
    runs: [
      { a: [-27, 25], b: [-27, 6], bays: 6, shops: [{ from: 0, to: 1, ...shopNamed('Boulangerie Diallo') }, { from: 2, to: 2, kind: 'door', color: INKS.cobalt }, { from: 3, to: 5, ...shopNamed('Laverie du Quai') }] },
      { a: [-27, 6], b: [-47, 6], bays: 6, shops: [{ from: 0, to: 1, ...shopNamed('Pharmacie') }, { from: 2, to: 5, kind: 'wall' }] },
    ],
    footprint: [
      [-27, 6],
      [-27, 25],
      [-47, 25],
      [-47, 6],
    ],
    street: [true, false, false, true],
    style: 'haussmann',
    storeys: 6,
    wall: TONES.stoneLight,
    balconies: [2, 5],
    lit: 0.42,
    seed: 2,
  });

  /* ---- the rows of buildings ------------------------------------------------------------- */
  // quai de Valmy, north of Le Mistral and south of the corner
  row(B, [-27, -28.5], [-27, zMin], { style: 'mixed', widths: [12, 20], depth: [13, 18], used, seed: 10, litShare: 0.34 });
  row(B, [-27, zMax], [-27, 25], { style: 'mixed', widths: [12, 20], depth: [13, 18], used, seed: 40, litShare: 0.34 });
  // the rue de Lancry: older, narrower houses
  // (the north side faces south, so its façades run east, from the far end back to Le Mistral)
  row(B, [L.xEnd, -6], [-53, -6], { style: 'faubourg', widths: [8, 13], depth: [11, 15], used, seed: 90, litShare: 0.3 });
  let easel: Quai['easel'] = null;
  {
    // the south side, and in it the third-floor window with the easel
    const spec: BuildingSpec = {
      runs: [{ a: [-47, 6], b: [-60, 6], bays: 4, shops: [{ from: 0, to: 1, kind: 'shutter', name: 'Brocante Lancry', color: mix(INKS.green, INKS.ink, 0.4) }, { from: 2, to: 2, kind: 'door', color: INKS.cobalt }, { from: 3, to: 3, kind: 'wall' }] }],
      depth: 13,
      style: 'faubourg',
      storeys: 5,
      wall: mix(INKS.paper, INKS.ochre, 0.22),
      lit: 0.25,
      seed: 120,
    };
    building(B, spec);
    const lspec: BuildingSpec = {
      runs: [{ a: [-60, 6], b: [-71, 6], bays: 4, shops: [{ from: 0, to: 0, kind: 'door', color: INKS.green }, { from: 1, to: 3, kind: 'shutter', name: 'Encadrements', color: mix(INKS.ochre, INKS.ink, 0.3) }] }],
      depth: 13,
      style: 'faubourg',
      storeys: 5,
      wall: mix(INKS.paper, INKS.cobalt, 0.06),
      lit: 0.2,
      forceLit: ['0:3:2'],
      seed: 121,
    };
    const info = building(B, lspec);
    const w = info.windows.get('0:3:2');
    if (w) easel = { center: w.center.clone(), normal: w.normal.clone() };
    row(B, [-71, 6], [L.xEnd, 6], { style: 'faubourg', widths: [8, 13], depth: [11, 15], used, seed: 130, litShare: 0.3 });
  }
  // quai de Jemmapes, across the water
  row(B, [27, zMin], [27, zMax], { style: 'mixed', widths: [12, 22], depth: [13, 18], used, seed: 200, litShare: 0.38 });
  // the far ends: road bridges and houses across the canal close the view
  for (const zEnd of [zMin - 2, zMax + 2]) {
    const s = Math.sign(zEnd);
    const zFar = zEnd + s * 40;
    top(-90, Math.min(zEnd, zFar), 90, Math.max(zEnd, zFar), 0, road);
    stoneBridge(B, zEnd - s * 3, P);
    for (const [x0, x1] of [[-60, -20], [-20, 20], [20, 60]] as Array<[number, number]>) {
      const a: [number, number] = s < 0 ? [x0, zEnd - 18] : [x1, zEnd + 18];
      const b: [number, number] = s < 0 ? [x1, zEnd - 18] : [x0, zEnd + 18];
      row(B, a, b, { style: 'haussmann', widths: [12, 18], depth: [12, 14], used, seed: 300 + x0 + s * 7, litShare: 0.35 });
    }
  }

  /* ---- the street's furniture ------------------------------------------------------------ */
  // plane trees along both canal strips, gaps where the footbridge comes down
  for (let z = zMin + 4; z < zMax - 2; z += 8.5) {
    if (!(z > P.bridge.z0 - 4 && z < P.bridge.westFoot + 3) && !(z > -12.5 && z < -7)) planeTree(B, -14.3, z, KERB, R.range(0.92, 1.12));
    if (!(z > P.bridge.eastFoot - 3 && z < P.bridge.z1 + 4)) planeTree(B, 14.3, z + 4, KERB, R.range(0.92, 1.12));
  }
  // lamps on the canal's edge, staggered across the water
  for (let z = zMin + 10; z < zMax; z += 23) {
    quayLamp(B, -11.2, z);
    quayLamp(B, 11.2, z + 11.5);
  }
  // one by the café's corner, as every corner has
  quayLamp(B, -24.6, -12.4);
  // benches facing the water
  for (const z of [-80, -66, 26, 44, 61, 96]) bench(B, -12.4, z, Math.PI / 2);
  for (const z of [-90, -20, 10, 55]) bench(B, 12.4, z, -Math.PI / 2);
  // the Morris column at the corner of the rue de Lancry
  morrisColumn(B, -15.4, 8.6, [
    { key: 'poster:cle', draw: posterArt('La Clé', ['comédie en un acte', 'Théâtre du Canal', 'jusqu’au 30 novembre'], INKS.vermilion, INKS.card) },
    { key: 'poster:brocante', draw: posterArt('Brocante', ['dimanche 15 novembre', 'quai de Jemmapes', 'de 8 h à 18 h'], INKS.green, INKS.card) },
    { key: 'poster:bal', draw: posterArt('Grand-mère', ['un film de Lina Morel', 'au Louxor', 'dès le 18 novembre'], INKS.cobalt, mix(INKS.card, INKS.sunflower, 0.12)) },
    { key: 'poster:appart', draw: posterArt('À louer', ['appartement', 'premier étage', 'vue sur le canal'], INKS.ink, INKS.card) },
  ]);
  // bollards along the corner's pavement edge
  for (let z = -27; z < -12; z += 1.6) bollard(B, -24.35, z);
  for (let x = -52; x < -33; x += 1.6) bollard(B, x, -4.55);
  // the café's terrace, chairs tipped against the tables for the night
  terraceSet(B, -25.4, -14.8, 0.2);
  terraceSet(B, -25.4, -17.6, -0.15);
  // rue de Lancry: wall lanterns, every sixteen metres
  {
    const fN = frameOf([L.xEnd, -6], [-53, -6]);
    for (let u = 8; u < fN.len; u += 16) wallLamp(B, fN, u, 4.6);
    const fS = frameOf([-27, 6], [L.xEnd, 6]);
    for (let u = 12; u < fS.len; u += 18) wallLamp(B, fS, u, 4.6);
  }

  footbridge(B);
  barge(B, 6.6, 18, 46);

  // leaves fallen on the setts, more under the trees
  const leafTones = [TONES.leafSun, TONES.leafOchre, TONES.leafRust];
  for (let i = 0; i < 900; i++) {
    const side = R.chance(0.5) ? -1 : 1;
    const x = side * R.range(10.6, 16.8);
    const z = R.range(zMin + 2, zMax - 2);
    const s = R.range(0.07, 0.13);
    const a = R.range(0, Math.PI);
    const c = Math.cos(a) * s;
    const d = Math.sin(a) * s;
    W.tri(new Vector3(x - c, KERB + 0.004, z - d), new Vector3(x + d * 0.6, KERB + 0.004, z - c * 0.6), new Vector3(x + c, KERB + 0.004, z + d), { color: R.pick(leafTones), id: 9 }, 9);
  }

  return { mistral, easel };
}

/** A green iron footbridge with stairs at both ends: lattice parapets, an arched deck. */
function footbridge(B: Build) {
  const D = B.dry;
  const P = PLAN.bridge;
  const green: Paint = { color: mix(INKS.green, INKS.ink, 0.15), id: nextId() };
  const deckPaint: Paint = { color: mix(TONES.wood, INKS.ink, 0.15), id: nextId(), pattern: PATTERN.planks };
  const z0 = P.z0;
  const z1 = P.z1;
  const yEnd = P.deckEnd;
  const yTop = P.deckTop;
  const arch = (x: number) => yEnd + (yTop - yEnd) * (1 - (x / 10.2) ** 2);
  const laceId = nextId();
  // deck over the water, in segments that follow the arch
  const seg = 10;
  for (let i = 0; i < seg; i++) {
    const xa = -10.2 + (20.4 * i) / seg;
    const xb = -10.2 + (20.4 * (i + 1)) / seg;
    const ya = arch(xa);
    const yb = arch(xb);
    B.wet.quadXYZ([xa, ya, z1, xb, yb, z1, xb, yb, z0, xa, ya, z0], deckPaint, deckPaint.id);
    // the girders under the deck's edges
    for (const z of [z0, z1]) {
      D.quadXYZ([xa, ya - 0.75, z, xb, yb - 0.75, z, xb, yb + 0.05, z, xa, ya + 0.05, z], green, green.id);
      D.quadXYZ([xa, ya - 0.75, z + (z === z0 ? 0.2 : -0.2), xb, yb - 0.75, z + (z === z0 ? 0.2 : -0.2), xb, yb - 0.75, z, xa, ya - 0.75, z], green, green.id);
    }
    B.lace.panel(new Vector3(xa, ya, z0 + 0.05), new Vector3(xb, yb, z0 + 0.05), 1.1, LACE.lattice, laceId, xa + 10.2);
    B.lace.panel(new Vector3(xb, yb, z1 - 0.05), new Vector3(xa, ya, z1 - 0.05), 1.1, LACE.lattice, laceId, xa + 10.2);
    B.walk.push({ shape: rect(xa, z0 + 0.25, xb, z1 - 0.25), y: { from: [xa, (z0 + z1) / 2], to: [xb, (z0 + z1) / 2], y0: ya, y1: yb } });
  }
  // handrail caps
  D.sweep(new Vector3(-10.2, yEnd + 1.1, z0 + 0.05), new Vector3(10.2, yEnd + 1.1, z0 + 0.05), [[-0.04, 0], [0.04, 0], [0.04, 0.06], [-0.04, 0.06]], green, { closed: true });
  // landings over the strips, on cast-iron columns
  for (const side of [-1, 1] as const) {
    const xa = side < 0 ? -15.8 : 10.2;
    const xb = side < 0 ? -10.2 : 15.8;
    B.wet.quadXYZ([xa, yEnd, z1, xb, yEnd, z1, xb, yEnd, z0, xa, yEnd, z0], deckPaint, deckPaint.id);
    D.box((xa + xb) / 2, yEnd - 0.38, (z0 + z1) / 2, xb - xa, 0.7, z1 - z0, green, { py: false });
    for (const cx of [xa + 0.3, xb - 0.3]) for (const cz of [z0 + 0.3, z1 - 0.3]) {
      D.cylinder(cx, KERB, cz, 0.13, 0.11, yEnd - 0.7 - KERB, 8, green);
      B.blocks.push(circle(cx, cz, 0.3));
    }
    const outer = side < 0 ? xa : xb;
    B.lace.panel(new Vector3(outer, yEnd, z0), new Vector3(outer, yEnd, z1), 1.1, LACE.lattice, laceId);
    B.walk.push({ shape: rect(xa, z0 + 0.25, xb, z1 - 0.25), y: yEnd });
  }
  // the stairs: the west flight comes up from the south, the east one goes down to the north
  stairs(B, -15.6, -12.6, P.westFoot, z1, KERB, yEnd, green, deckPaint, laceId);
  stairs(B, 12.6, 15.6, P.eastFoot, z0, KERB, yEnd, green, deckPaint, laceId);
  // nobody walks under the landings
  B.blocks.push(rect(-15.9, z0 - 0.1, -10.2, z1 + 0.1));
  B.blocks.push(rect(10.2, z0 - 0.1, 15.9, z1 + 0.1));
}

function stairs(B: Build, x0: number, x1: number, zFoot: number, zTop: number, yFoot: number, yTop: number, frame: Paint, tread: Paint, laceId: number) {
  const D = B.dry;
  const dir = Math.sign(zTop - zFoot);
  const run = Math.abs(zTop - zFoot);
  const steps = Math.round((yTop - yFoot) / 0.165);
  const depth = run / steps;
  const riser: Paint = { color: mix(TONES.wood, INKS.ink, 0.35), id: tread.id };
  for (let i = 0; i < steps; i++) {
    const z = zFoot + dir * (i + 0.5) * depth;
    const y = yFoot + (i + 1) * ((yTop - yFoot) / steps);
    B.wet.quadXYZ([x0, y, z + dir * depth * 0.5, x1, y, z + dir * depth * 0.5, x1, y, z - dir * depth * 0.5, x0, y, z - dir * depth * 0.5], tread, tread.id);
    D.quadXYZ(dir > 0 ? [x0, y - (yTop - yFoot) / steps, z - depth * 0.5, x1, y - (yTop - yFoot) / steps, z - depth * 0.5, x1, y, z - depth * 0.5, x0, y, z - depth * 0.5] : [x1, y - (yTop - yFoot) / steps, z + depth * 0.5, x0, y - (yTop - yFoot) / steps, z + depth * 0.5, x0, y, z + depth * 0.5, x1, y, z + depth * 0.5], riser, riser.id);
  }
  // stringers and parapets
  for (const x of [x0, x1]) {
    D.quadXYZ([x, yFoot - 0.4, zFoot, x, yTop - 0.4, zTop, x, yTop + 0.1, zTop, x, yFoot + 0.1, zFoot], frame, frame.id);
    B.lace.panel(new Vector3(x, yFoot + 0.1, zFoot), new Vector3(x, yTop, zTop), 1.05, LACE.lattice, laceId);
  }
  const xs = Math.min(x0, x1);
  const xe = Math.max(x0, x1);
  B.walk.push({ shape: rect(xs + 0.2, Math.min(zFoot, zTop), xe - 0.2, Math.max(zFoot, zTop)), y: { from: [(xs + xe) / 2, zFoot], to: [(xs + xe) / 2, zTop], y0: yFoot, y1: yTop } });
  // walls of the flight: you can't step off the side
  B.blocks.push(rect(xs - 0.25, Math.min(zFoot, zTop) + 1.5, xs + 0.1, Math.max(zFoot, zTop)));
  B.blocks.push(rect(xe - 0.1, Math.min(zFoot, zTop) + 1.5, xe + 0.25, Math.max(zFoot, zTop)));
}

/** A stone road bridge across the canal, closing the view at the far ends. */
function stoneBridge(B: Build, z: number, P: typeof PLAN) {
  const D = B.dry;
  const stone: Paint = { color: mix(TONES.quayWall, INKS.paper, 0.2), id: nextId(), pattern: PATTERN.courses };
  const depth = 12;
  const z0 = z - depth / 2;
  const z1 = z + depth / 2;
  // the arch's face: a stack of slabs leaving a segmental opening over the water
  const span = 20;
  const seg = 12;
  for (let i = 0; i < seg; i++) {
    const xa = -span / 2 + (span * i) / seg;
    const xb = -span / 2 + (span * (i + 1)) / seg;
    const ya = P.water + 1.2 + 2.4 * Math.sqrt(Math.max(0, 1 - (xa / (span / 2)) ** 2));
    const yb = P.water + 1.2 + 2.4 * Math.sqrt(Math.max(0, 1 - (xb / (span / 2)) ** 2));
    const yMid = Math.min(ya, yb);
    D.box((xa + xb) / 2, (yMid + 1.0) / 2, z, xb - xa, 1.0 - yMid, depth, stone);
  }
  D.box(0, 1.3, z, 70, 0.6, depth, { color: TONES.asphalt, id: nextId() }, { ny: false });
  for (const zz of [z0, z1]) D.box(0, 2.05, zz, 70, 0.9, 0.5, stone, { ny: false });
}

/** A barge moored by the quai de Jemmapes: someone lives aboard, a lamp lit in the cabin. */
function barge(B: Build, x: number, zFrom: number, zTo: number) {
  const D = B.dry;
  const y0 = PLAN.water - 0.4;
  const len = zTo - zFrom;
  const w = 4.2;
  const hull: Paint = { color: mix(INKS.cobalt, INKS.ink, 0.35), id: nextId() };
  const band: Paint = { color: INKS.vermilion, id: nextId() };
  const shape: Array<[number, number]> = [
    [x - w / 2, zFrom + 2.5],
    [x, zFrom],
    [x + w / 2, zFrom + 2.5],
    [x + w / 2, zTo - 1.2],
    [x + w / 2 - 0.6, zTo],
    [x - w / 2 + 0.6, zTo],
    [x - w / 2, zTo - 1.2],
  ];
  D.prism(shape, y0, y0 + 1.5, hull, {});
  D.prism(shape.map(([px, pz]) => [px + (px - x) * 0.02, pz] as [number, number]), y0 + 1.5, y0 + 1.68, band, { top: false });
  // the cabin
  const cabin: Paint = { color: mix(INKS.ochre, INKS.paper, 0.3), id: nextId() };
  D.block(x, y0 + 1.5, zFrom + len * 0.55, w - 0.9, 2.0, len * 0.5, cabin);
  D.block(x, y0 + 3.5, zFrom + len * 0.55, w - 0.6, 0.12, len * 0.52, { color: TONES.zincDark, id: nextId() });
  const lit: Paint = { color: TONES.paneLit, glow: 1, id: nextId() };
  for (let i = 0; i < 5; i++) {
    const z = zFrom + len * 0.32 + i * (len * 0.46) / 4;
    D.quadXYZ([x - (w - 0.9) / 2 - 0.01, y0 + 2.2, z + 0.4, x - (w - 0.9) / 2 - 0.01, y0 + 2.2, z - 0.4, x - (w - 0.9) / 2 - 0.01, y0 + 2.9, z - 0.4, x - (w - 0.9) / 2 - 0.01, y0 + 2.9, z + 0.4], i % 2 === 0 ? lit : { color: TONES.pane, id: lit.id });
  }
  // pots of geraniums and a chimney pipe
  for (let i = 0; i < 4; i++) D.cylinder(x - 1.2 + i * 0.8, y0 + 1.5, zFrom + 4.2, 0.18, 0.22, 0.3, 6, { color: TONES.pot, id: nextId() }, { flat: true });
  for (let i = 0; i < 4; i++) D.ball(x - 1.2 + i * 0.8, y0 + 1.95, zFrom + 4.2, 0.24, 0.2, 0.24, { color: i % 2 ? INKS.vermilion : mix(INKS.green, INKS.sunflower, 0.2), id: nextId() }, 0);
  D.cylinder(x + 0.8, y0 + 3.6, zFrom + len * 0.7, 0.08, 0.08, 0.9, 6, { color: TONES.iron, id: nextId() });
  B.lamps.push({ pos: new Vector3(x - 2.5, y0 + 2.6, zFrom + len * 0.55), color: rgb(mix(INKS.sunflower, INKS.card, 0.3)), power: 0.6, range: 6, glint: true });
  void boxShape;
  void letteringArt;
  void awning;
  void worldOf;
}
