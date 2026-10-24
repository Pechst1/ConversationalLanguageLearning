/**
 * Le Quartier · the cast in the round, to look at: turn them, change their mood, make them act,
 * under the quarter's morning, its night or the café's lamps, printed by the quarter's own print
 * pass. `build-cast3d-viewer.mjs` bundles this with the page's markup into one HTML file.
 */
import { CylinderGeometry, LatheGeometry, Mesh, PerspectiveCamera, Scene, ShaderMaterial, Vector2, Vector3, WebGLRenderer } from 'three';

import type { Seat } from '../../lib/quartier/cast';
import { ModelFigure } from '../../lib/quartier/cast3d/figure';
import type { Person } from '../../lib/quartier/cast3d/model';
import { PEOPLE } from '../../lib/quartier/cast3d/people';
import { applyAmbiance, makeWorld } from '../../lib/quartier/materials';
import { AMBIANCES, INKS, TONES, mix, rgb } from '../../lib/quartier/palette';
import type { Hex } from '../../lib/quartier/palette';
import { PrintPass } from '../../lib/quartier/print';

type Light = 'matin' | 'nuit' | 'cafe';

/** Who they are, in a line (from the season bible). */
const ROLES: Record<string, string> = {
  margaux_barman: 'Owner of Le Mistral, behind the zinc since 2001',
  augustin_de_roncourt: 'Augustin de Roncourt, showman of the booth',
  lila_bonnet: 'Teaches a CE1 class, paints, wants Berlin',
  marin_leveque: 'Works at an NGO, writes a novel, plans a co-op',
  romy_tremblay: 'Québécoise journalist, her camera always running',
  landlord_marchand: 'Owns the building. 74, widowed, opponent',
  camille_marchand: 'Urban planner, handles the sale for their grandfather',
  odile_ferrand: 'The grandmother whose key starts it all',
};

/** Each person's colour on their chip (the quarter's speaker accents, and costume colours). */
const ACCENTS: Record<string, string> = {
  margaux_barman: '#a85d24',
  augustin_de_roncourt: '#8a2f2a',
  lila_bonnet: '#c2890f',
  marin_leveque: '#2c6a5d',
  romy_tremblay: '#1d3a8a',
  landlord_marchand: '#7d7565',
  camille_marchand: '#5b5346',
  odile_ferrand: '#5d6e35',
};

const MOODS: Array<[string, string]> = [
  ['neutre', 'Calm'],
  ['joie', 'Joy'],
  ['malice', 'Mischief'],
  ['fier', 'Proud'],
  ['surprise', 'Surprise'],
  ['panique', 'Panic'],
  ['fache', 'Cross'],
  ['emu', 'Moved'],
  ['amour', 'Smitten'],
  ['fatigue', 'Tired'],
];
const GESTURES: Array<[string, string]> = [
  ['salut', 'Wave'],
  ['bravo', 'Applaud'],
  ['oups', 'Oops'],
  ['reflechit', 'Think'],
  ['montre', 'Point'],
  ['signature', 'Sign'],
];

/** The stage's paper, floor and print by the light. */
const LOOKS: Record<Light, { sky: Hex; floor: Hex; halftone: number; idLines: number }> = {
  matin: { sky: 0xe9e2d3, floor: mix(INKS.paper, INKS.ink, 0.05), halftone: 0.6, idLines: 0.6 },
  nuit: { sky: 0x1b2552, floor: mix(INKS.cobalt, INKS.ink, 0.62), halftone: 0.42, idLines: 0.45 },
  cafe: { sky: mix(INKS.ochre, INKS.paper, 0.55), floor: 0xefe6cf, halftone: 0.5, idLines: 0.55 },
};

const FLAT_VERT = /* glsl */ `
varying vec3 vN;
void main() { vN = normal; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }
`;
const FLAT_FRAG = /* glsl */ `
uniform vec3 uColor;
uniform float uId;
varying vec3 vN;
void main() {
  float band = vN.y > 0.5 ? 2.0 : 1.0;
  gl_FragColor = vec4(uColor * (band > 1.5 ? 1.0 : 0.82), (uId * 4.0 + band) / 255.0);
}
`;

/** A plain inked surface on the print's plate: its colour, its line id, lit on top. */
function flat(color: Hex, id: number) {
  const c = rgb(color);
  return new ShaderMaterial({ uniforms: { uColor: { value: new Vector3(c[0], c[1], c[2]) }, uId: { value: id } }, vertexShader: FLAT_VERT, fragmentShader: FLAT_FRAG });
}

interface Member {
  person: Person;
  fig: ModelFigure;
  seats: Seat[];
  stool: Mesh;
  home: Vector3;
  stoolHeight: number;
}

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;

function start() {
  const stage = $<HTMLElement>('stage');
  const canvas = $<HTMLCanvasElement>('stage-canvas');
  // not premultiplied: the clear's alpha is the sky's line id, and must not darken its colour
  const renderer = new WebGLRenderer({ canvas, antialias: false, alpha: false, premultipliedAlpha: false, powerPreference: 'high-performance' });
  const scene = new Scene();
  const camera = new PerspectiveCamera(34, 1, 0.05, 80);
  const world = makeWorld();
  const print = new PrintPass(2, 2, { line: 1, idLines: 0.6, halftone: 0.6, grain: 1 });
  const floorMat = flat(INKS.paper, 2);
  const floor = new Mesh(new CylinderGeometry(9, 9, 0.04, 64), floorMat);
  floor.position.y = -0.02;
  scene.add(floor);
  // Odile's stool's wood, which reads under dark trousers as the zinc's black stools would not
  const stoolMat = flat(mix(TONES.wood, INKS.ochre, 0.15), 3);

  const dark = typeof matchMedia === 'function' && matchMedia('(prefers-color-scheme: dark)').matches;
  const state = {
    all: false,
    chosen: PEOPLE[0].key,
    variant: 'f',
    light: (dark ? 'nuit' : 'matin') as Light,
    mood: 'neutre',
    seated: false,
  };
  let members: Member[] = [];
  let light: [number, number, number] = [1, 1, 1];
  let indoor = false;
  const view = { yaw: 0, pitch: 0.1, dist: 3.4, target: new Vector3(0, 0.9, 0) };
  /** Whether the stage shows everyone, and in how many rows, as they were last set out. */
  let shown: boolean | null = null;
  let laidOut = 1;
  const SPACING = 0.82;

  function stoolFor(person: Person) {
    const h = person.body.height * 0.2 + 0.02;
    const geo = new LatheGeometry(
      [
        [0.16, 0],
        [0.035, 0.06],
        [0.03, h - 0.05],
        [0.15, h - 0.03],
        [0.15, h],
        [0, h + 0.004],
      ].map(([x, y]) => new Vector2(x, y)),
      12,
    );
    return { mesh: new Mesh(geo, stoolMat), height: h };
  }

  function cast() {
    members.forEach((m) => {
      scene.remove(m.fig.root, m.stool);
      m.fig.dispose();
      m.stool.geometry.dispose();
    });
    const people = state.all ? PEOPLE.slice() : PEOPLE.filter((p) => p.key === state.chosen);
    members = people.map((person) => {
      const home = new Vector3();
      const seats: Seat[] = [];
      const fig = new ModelFigure(world, person, { key: person.key, height: person.body.height }, { variant: person.variants ? state.variant : undefined, seats });
      // a turntable: they hold their heading while you walk round them
      fig.attentive = false;
      fig.place(home);
      fig.express(state.mood, null);
      const { mesh: stool, height: stoolHeight } = stoolFor(person);
      stool.position.copy(home);
      scene.add(fig.root, stool);
      return { person, fig, seats, stool, home, stoolHeight };
    });
    arrange();
    view.target.set(0, state.all ? 0.85 : people[0].body.height * 0.55 - 0.2 * portrait(), 0);
    // a new person keeps the angle you were looking from; everyone together starts from the front
    if (shown !== state.all) frontOn();
    else view.dist = reach();
    shown = state.all;
    describe();
  }

  /** How far the stage is a portrait (0 square or wider, 1 a phone's 4:5): one person stands higher in it, clear of their name card. */
  const portrait = () => Math.max(0, Math.min(1, (1.1 - camera.aspect) / 0.3));

  /** Everyone in two staggered rows, the tallest at the back, unless the stage is wide enough for one. */
  const rows = () => (state.all && camera.aspect < 1.7 ? 2 : 1);

  function arrange() {
    laidOut = rows();
    const two = laidOut === 2;
    const back = two ? members.slice().sort((a, b) => b.person.body.height - a.person.body.height).slice(0, Math.ceil(members.length / 2)) : [];
    [members.filter((m) => !back.includes(m)), back].forEach((line, r) =>
      line.forEach((m, i) => {
        if (state.all) m.home.set((i - (line.length - 1) / 2 + (two ? (r ? 0.25 : -0.25) : 0)) * SPACING, 0, two ? (r ? -0.55 : 0.55) : 0);
        m.fig.place(m.home);
        m.stool.position.copy(m.home);
      }),
    );
    sit(state.seated);
  }

  /** How far back to stand to take in everyone (or the one), whatever the stage's shape. */
  function reach() {
    if (!state.all) return 3.4 * (1 + 0.12 * portrait());
    const tanV = Math.tan((camera.fov * Math.PI) / 360);
    const two = laidOut === 2;
    const across = ((Math.ceil(members.length / laidOut) - 1) / 2 + (two ? 0.25 : 0)) * SPACING + 0.5;
    return Math.max(across / (tanV * camera.aspect), 1.15 / tanV) + (two ? 0.55 : 0);
  }

  /** Back to the front: a little from above for two rows, so the back row's faces show. */
  function frontOn() {
    view.yaw = 0;
    view.pitch = state.all && laidOut === 2 ? 0.22 : 0.1;
    view.dist = reach();
  }

  function sit(on: boolean) {
    state.seated = on;
    members.forEach((m) => {
      m.seats.length = 0;
      if (on) m.seats.push({ at: m.home.clone(), height: m.stoolHeight });
      m.stool.visible = on;
    });
  }

  function setLight(l: Light) {
    state.light = l;
    const look = LOOKS[l];
    applyAmbiance(world, AMBIANCES[l === 'matin' ? 'matin' : 'nuit']);
    const w = world;
    let base: Vector3;
    if (l === 'cafe') base = w.uIndoorLit.value.clone().multiplyScalar(0.92).add(w.uRoomLamp.value.clone().multiplyScalar(0.3));
    else {
      base = w.uShade.value.clone().lerp(w.uSun.value, 0.62).add(w.uAmbient.value);
      // at night, a street lamp near by
      if (l === 'nuit') base.add(new Vector3(0.42, 0.33, 0.2));
    }
    const lum = base.x * 0.3 + base.y * 0.59 + base.z * 0.11;
    if (lum < 0.62) base.multiplyScalar(0.62 / Math.max(lum, 0.01));
    light = [Math.min(base.x, 1.15), Math.min(base.y, 1.15), Math.min(base.z, 1.15)];
    indoor = l === 'cafe';
    const sky = rgb(look.sky);
    renderer.setClearColor((Math.round(sky[0] * 255) << 16) | (Math.round(sky[1] * 255) << 8) | Math.round(sky[2] * 255), 2 / 255);
    const f = rgb(look.floor);
    floorMat.uniforms.uColor.value.set(f[0], f[1], f[2]);
    print.set({ halftone: look.halftone, idLines: look.idLines, fogFar: 400 });
    stage.dataset.light = l;
    press('light', l);
  }

  function describe() {
    const name = $<HTMLElement>('who-name');
    const role = $<HTMLElement>('who-role');
    if (state.all) {
      name.textContent = 'La troupe';
      role.textContent = `${members.length} people, ${members.reduce((s, m) => s + m.fig.model.triangles, 0).toLocaleString('en')} triangles`;
    } else {
      const m = members[0];
      name.textContent = m.person.key === 'landlord_marchand' ? 'M. Marchand' : m.person.name;
      role.textContent = ROLES[m.person.key] ?? '';
    }
    $<HTMLElement>('variant-row').hidden = !(state.all || state.chosen === 'camille_marchand');
    press('people', state.all ? 'all' : state.chosen);
    press('variant', state.variant);
    press('moods', state.mood);
    press('seat', state.seated ? 'on' : 'off');
    for (const id of ['act-walk']) ($<HTMLButtonElement>(id).disabled = state.all);
  }

  /** Mark the pressed chip of a row. */
  function press(row: string, value: string) {
    document.querySelectorAll<HTMLButtonElement>(`[data-row="${row}"]`).forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.value === value)));
  }

  function chip(row: string, value: string, label: string, onClick: () => void, accent?: string) {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'chip';
    b.dataset.row = row;
    b.dataset.value = value;
    b.setAttribute('aria-pressed', 'false');
    if (accent) {
      const dot = document.createElement('span');
      dot.className = 'dot';
      dot.style.background = accent;
      b.appendChild(dot);
    }
    b.appendChild(document.createTextNode(label));
    b.addEventListener('click', onClick);
    return b;
  }

  // the rows of chips
  const peopleRow = $<HTMLElement>('people-row');
  PEOPLE.forEach((p) =>
    peopleRow.appendChild(
      chip('people', p.key, p.key === 'landlord_marchand' ? 'M. Marchand' : p.name, () => {
        state.all = false;
        state.chosen = p.key;
        cast();
      }, ACCENTS[p.key]),
    ),
  );
  peopleRow.appendChild(
    chip('people', 'all', 'Everyone', () => {
      state.all = true;
      cast();
    }),
  );
  const variantRow = $<HTMLElement>('variant-chips');
  [['f', 'Camille, version F'], ['m', 'Camille, version M']].forEach(([v, label]) =>
    variantRow.appendChild(
      chip('variant', v, label, () => {
        state.variant = v;
        cast();
      }),
    ),
  );
  const moodRow = $<HTMLElement>('mood-row');
  MOODS.forEach(([id, label]) =>
    moodRow.appendChild(
      chip('moods', id, label, () => {
        state.mood = id;
        members.forEach((m) => m.fig.express(id, null));
        press('moods', id);
      }),
    ),
  );
  const gestureRow = $<HTMLElement>('gesture-row');
  GESTURES.forEach(([id, label]) =>
    gestureRow.appendChild(
      chip('gesture', id, label, () => {
        members.forEach((m, i) =>
          window.setTimeout(() => {
            m.fig.express(state.mood, null);
            m.fig.express(state.mood, id);
          }, i * 90),
        );
      }),
    ),
  );
  $<HTMLButtonElement>('act-talk').addEventListener('click', () => {
    // one after another, the others turning to whoever speaks
    members.forEach((m, i) => window.setTimeout(() => m.fig.talk(state.all ? 1.4 : 3.2), i * 1500));
  });
  $<HTMLButtonElement>('act-bow').addEventListener('click', () => members.forEach((m, i) => window.setTimeout(() => m.fig.bow(0.62, 1.5), i * 110)));
  $<HTMLButtonElement>('act-hop').addEventListener('click', () => members.forEach((m, i) => window.setTimeout(() => m.fig.hop(), i * 80)));
  $<HTMLButtonElement>('act-walk').addEventListener('click', () => {
    const m = members[0];
    if (!m || state.all) return;
    sit(false);
    describe();
    // a loop away from you and back, the last steps toward you
    const s = Math.sin(view.yaw);
    const c = Math.cos(view.yaw);
    const at = (x: number, z: number) => new Vector3(x * c + z * s, 0, -x * s + z * c);
    m.fig.walk([at(0.9, -0.5), at(0.6, -1.7), at(-0.6, -1.7), at(-0.9, -0.6), at(0, -0.7), at(0, 0)], 1.1);
  });
  document.querySelectorAll<HTMLButtonElement>('[data-row="seat"]').forEach((b) =>
    b.addEventListener('click', () => {
      sit(b.dataset.value === 'on');
      describe();
    }),
  );
  document.querySelectorAll<HTMLButtonElement>('[data-row="light"]').forEach((b) => b.addEventListener('click', () => setLight(b.dataset.value as Light)));

  // turning round them: a drag turns, a pinch or the wheel comes closer
  const pointers = new Map<number, { x: number; y: number }>();
  let pinch = 0;
  stage.addEventListener('pointerdown', (e) => {
    stage.setPointerCapture(e.pointerId);
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    $<HTMLElement>('hint').hidden = true;
  });
  // the hint stays long enough to read, then leaves the tallest heads clear
  window.setTimeout(() => $<HTMLElement>('hint').classList.add('gone'), 8000);
  stage.addEventListener('pointermove', (e) => {
    const p = pointers.get(e.pointerId);
    if (!p) return;
    if (pointers.size === 1) {
      view.yaw -= (e.clientX - p.x) * 0.008;
      view.pitch = Math.max(-0.08, Math.min(0.7, view.pitch + (e.clientY - p.y) * 0.005));
    } else if (pointers.size === 2) {
      const pts = Array.from(pointers.values());
      const d = Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y);
      if (pinch > 0) zoom(pinch / Math.max(d, 1));
      pinch = d;
    }
    p.x = e.clientX;
    p.y = e.clientY;
  });
  const lift = (e: PointerEvent) => {
    pointers.delete(e.pointerId);
    pinch = 0;
  };
  stage.addEventListener('pointerup', lift);
  stage.addEventListener('pointercancel', lift);
  stage.addEventListener('dblclick', frontOn);
  stage.addEventListener(
    'wheel',
    (e) => {
      e.preventDefault();
      zoom(Math.exp(e.deltaY * 0.0012));
    },
    { passive: false },
  );
  stage.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowLeft') view.yaw += 0.2;
    else if (e.key === 'ArrowRight') view.yaw -= 0.2;
    else if (e.key === 'ArrowUp') zoom(0.9);
    else if (e.key === 'ArrowDown') zoom(1.1);
    else return;
    e.preventDefault();
  });
  function zoom(k: number) {
    const [lo, hi] = state.all ? [3.5, reach() * 1.5] : [1.2, 6];
    view.dist = Math.max(lo, Math.min(hi, view.dist * k));
  }

  function resize() {
    const w = Math.max(1, stage.clientWidth);
    const h = Math.max(1, stage.clientHeight);
    const pr = Math.min(2, window.devicePixelRatio || 1);
    renderer.setPixelRatio(pr);
    renderer.setSize(w, h, false);
    print.setSize(Math.round(w * pr), Math.round(h * pr), pr);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    // a turned phone or a resized window: set everyone out again to fit
    if (state.all && rows() !== laidOut) {
      arrange();
      frontOn();
    } else view.dist = reach();
  }
  new ResizeObserver(resize).observe(stage);

  let last = performance.now();
  function frame(t: number) {
    const dt = Math.min(0.1, Math.max(0, (t - last) / 1000));
    last = t;
    const now = t / 1000;
    // the camera follows whoever walks, and comes down with them when they sit
    if (!state.all && members[0]) {
      const m = members[0];
      const y = m.person.body.height * (state.seated ? 0.4 : 0.55) - 0.2 * portrait();
      const k = 1 - Math.exp(-dt * 4);
      view.target.x += (m.fig.pos.x - view.target.x) * k;
      view.target.z += (m.fig.pos.z - view.target.z) * k;
      view.target.y += (y - view.target.y) * k;
    }
    const tg = view.target;
    camera.position.set(tg.x + Math.sin(view.yaw) * Math.cos(view.pitch) * view.dist, tg.y + Math.sin(view.pitch) * view.dist, tg.z + Math.cos(view.yaw) * Math.cos(view.pitch) * view.dist);
    camera.lookAt(tg);
    camera.updateMatrixWorld();
    world.uTime.value = now;
    members.forEach((m) => {
      m.fig.indoor = indoor;
      m.fig.update(dt, now, camera, light);
    });
    print.render(renderer, scene, camera);
    requestAnimationFrame(frame);
  }

  resize();
  setLight(state.light);
  cast();
  requestAnimationFrame(frame);
  stage.dataset.ready = 'true';
}

try {
  start();
} catch (e) {
  const note = document.getElementById('stage-note');
  if (note) {
    note.hidden = false;
    note.textContent = `The 3D stage could not start here (${e instanceof Error ? e.message : String(e)}). It needs WebGL.`;
  }
}
