/**
 * Le Quartier · the skeleton every figure stands on.
 *
 * Twenty bones, the same for everyone: a person differs by where the joints sit (Marin's
 * shoulders, Lila's short stride, Gus's height) and by what is built round them. The bind pose
 * stands at the origin facing +z, arms hanging a little away from the body, and every bone starts
 * unrotated, so a pose is a set of plain turns in the figure's own axes: +x turns a limb back
 * (a knee bending), -x swings it forward (a step), +z lifts the left arm sideways, +x on the
 * spine is a bow. Left and right are the figure's own: L is on +x.
 */
import { Bone, Euler, Matrix4, Quaternion, Skeleton, Vector3 } from 'three';

export const BONES = [
  'root',
  'hips',
  'spine',
  'chest',
  'neck',
  'head',
  'clavL',
  'armL',
  'foreL',
  'handL',
  'clavR',
  'armR',
  'foreR',
  'handR',
  'thighL',
  'shinL',
  'footL',
  'thighR',
  'shinR',
  'footR',
] as const;

export type BoneName = (typeof BONES)[number];

/** Bone indices by name. */
export const B = BONES.reduce((acc, name, i) => {
  acc[name] = i;
  return acc;
}, {} as Record<BoneName, number>);

const PARENT: Record<BoneName, BoneName | null> = {
  root: null,
  hips: 'root',
  spine: 'hips',
  chest: 'spine',
  neck: 'chest',
  head: 'neck',
  clavL: 'chest',
  armL: 'clavL',
  foreL: 'armL',
  handL: 'foreL',
  clavR: 'chest',
  armR: 'clavR',
  foreR: 'armR',
  handR: 'foreR',
  thighL: 'hips',
  shinL: 'thighL',
  footL: 'shinL',
  thighR: 'hips',
  shinR: 'thighR',
  footR: 'shinR',
};

export type Side = 'L' | 'R';
export const SIDES: Side[] = ['L', 'R'];
/** +1 for the figure's left (+x), -1 for its right */
export const sx = (s: Side) => (s === 'L' ? 1 : -1);

/** How a body is proportioned. Lengths in metres unless said otherwise. */
export interface BodySpec {
  /** crown to sole */
  height: number;
  /** chin to crown */
  head: number;
  /** chin to the line of the shoulders */
  neck: number;
  /** half the distance between the shoulder joints */
  shoulders: number;
  /** half the distance between the hip joints */
  hips: number;
  /** hip joints' height, as a share of the height */
  legs: number;
  /** shoulder joint to wrist, as a share of the height */
  arm: number;
  /** wrist to fingertips */
  hand: number;
  /** heel to toe */
  foot: number;
  /** how far the arms hang out from the body in the bind pose, radians */
  spread?: number;
  /** a forward stoop of the upper back (Marchand), or a chest held high if negative (Gus), radians */
  stoop?: number;
}

export interface Pair {
  L: Vector3;
  R: Vector3;
}

/** Where the joints are in the bind pose. */
export interface Joints {
  spec: BodySpec;
  crown: number;
  chin: number;
  /** the middle of the head's ball */
  headC: Vector3;
  /** the head bone's pivot, at the top of the neck */
  skull: Vector3;
  neck: Vector3;
  /** height of the shoulder line */
  shoulderY: number;
  chest: Vector3;
  spine: Vector3;
  hips: Vector3;
  clav: Pair;
  shoulder: Pair;
  elbow: Pair;
  wrist: Pair;
  /** the middle of the hand */
  palm: Pair;
  hip: Pair;
  knee: Pair;
  ankle: Pair;
  toe: Pair;
}

const pair = (f: (s: Side) => Vector3): Pair => ({ L: f('L'), R: f('R') });

export function joints(spec: BodySpec): Joints {
  const H = spec.height;
  const crown = H;
  const chin = H - spec.head;
  const shoulderY = chin - spec.neck;
  const hipY = spec.legs * H;
  const torso = shoulderY - hipY;
  const headC = new Vector3(0, chin + spec.head * 0.47, 0.005);
  const skull = new Vector3(0, chin + spec.head * 0.12, -0.012);
  const neck = new Vector3(0, shoulderY + 0.015, -0.01);
  const chest = new Vector3(0, hipY + torso * 0.6, 0);
  const spine = new Vector3(0, hipY + torso * 0.24, 0);
  const hips = new Vector3(0, hipY, 0);
  const spread = spec.spread ?? 0.13;
  const upper = spec.arm * H * 0.53;
  const fore = spec.arm * H * 0.47;
  const clav = pair((s) => new Vector3(sx(s) * spec.shoulders * 0.28, shoulderY - 0.012, -0.012));
  const shoulder = pair((s) => new Vector3(sx(s) * spec.shoulders, shoulderY - 0.035, -0.012));
  const elbow = pair((s) => shoulder[s].clone().add(new Vector3(sx(s) * Math.sin(spread) * upper, -Math.cos(spread) * upper, -0.012)));
  // the forearm hangs a little forward of the elbow, as arms at rest do
  const wrist = pair((s) => elbow[s].clone().add(new Vector3(sx(s) * Math.sin(spread * 0.7) * fore, -Math.cos(0.14) * fore, Math.sin(0.14) * fore)));
  const palm = pair((s) => wrist[s].clone().add(new Vector3(sx(s) * 0.006, -spec.hand * 0.45, 0.008)));
  const ankleY = Math.max(0.055, H * 0.042);
  const legLen = hipY - ankleY;
  const hip = pair((s) => new Vector3(sx(s) * spec.hips, hipY - 0.02, 0));
  const knee = pair((s) => new Vector3(sx(s) * spec.hips * 0.92, ankleY + legLen * 0.49, 0.008));
  const ankle = pair((s) => new Vector3(sx(s) * spec.hips * 0.88, ankleY, -0.012));
  const toe = pair((s) => new Vector3(sx(s) * spec.hips * 0.9, 0.02, -0.012 + spec.foot * 0.72));
  return { spec, crown, chin, headC, skull, neck, shoulderY, chest, spine, hips, clav, shoulder, elbow, wrist, palm, hip, knee, ankle, toe };
}

/** Each bone's pivot in the bind pose. */
export function pivots(J: Joints): Record<BoneName, Vector3> {
  return {
    root: new Vector3(0, 0, 0),
    hips: J.hips.clone(),
    spine: J.spine.clone(),
    chest: J.chest.clone(),
    neck: J.neck.clone(),
    head: J.skull.clone(),
    clavL: J.clav.L.clone(),
    armL: J.shoulder.L.clone(),
    foreL: J.elbow.L.clone(),
    handL: J.wrist.L.clone(),
    clavR: J.clav.R.clone(),
    armR: J.shoulder.R.clone(),
    foreR: J.elbow.R.clone(),
    handR: J.wrist.R.clone(),
    thighL: J.hip.L.clone(),
    shinL: J.knee.L.clone(),
    footL: J.ankle.L.clone(),
    thighR: J.hip.R.clone(),
    shinR: J.knee.R.clone(),
    footR: J.ankle.R.clone(),
  };
}

/** The bones, parented and placed in the bind pose, and the skeleton over them. */
export function skeleton(J: Joints): { bones: Bone[]; skeleton: Skeleton; at: Record<BoneName, Vector3> } {
  const at = pivots(J);
  const bones = BONES.map((name) => {
    const b = new Bone();
    b.name = name;
    return b;
  });
  BONES.forEach((name, i) => {
    const parent = PARENT[name];
    const b = bones[i];
    if (parent) {
      const p = bones[B[parent]];
      p.add(b);
      b.position.copy(at[name]).sub(at[parent]);
    } else {
      b.position.copy(at[name]);
    }
  });
  bones[0].updateMatrixWorld(true);
  return { bones, skeleton: new Skeleton(bones), at };
}

export function parentOf(name: BoneName): BoneName | null {
  return PARENT[name];
}

/**
 * Where a pose carries each bone: the matrix taking a bind-pose point bound to it to its posed
 * place. Props use it to be built where a hand holds them at rest (Romy's camera between her hands).
 */
export function posed(J: Joints, pose: Partial<Record<BoneName, [number, number, number]>>): Record<BoneName, Matrix4> {
  const at = pivots(J);
  const world = {} as Record<BoneName, Matrix4>;
  const out = {} as Record<BoneName, Matrix4>;
  const e = new Euler();
  const one = new Vector3(1, 1, 1);
  BONES.forEach((name) => {
    const parent = PARENT[name];
    const t = parent ? at[name].clone().sub(at[parent]) : at[name].clone();
    const turn = pose[name];
    const q = turn ? new Quaternion().setFromEuler(e.set(turn[0], turn[1], turn[2], 'XYZ')) : new Quaternion();
    const local = new Matrix4().compose(t, q, one);
    world[name] = parent ? world[parent].clone().multiply(local) : local;
    out[name] = world[name].clone().multiply(new Matrix4().makeTranslation(-at[name].x, -at[name].y, -at[name].z));
  });
  return out;
}
