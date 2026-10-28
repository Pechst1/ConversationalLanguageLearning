/**
 * Le Quartier · a person, assembled: their file's pieces sculpted into one skinned mesh, on
 * their skeleton, in their ink, with their face printed on.
 */
import { SkinnedMesh, Vector3 } from 'three';
import type { Bone, ShaderMaterial } from 'three';

import type { Pt } from '@/components/cast/vivant/kit';

import type { World } from '../materials';
import type { Hex } from '../palette';

import type { FaceLook, FaceSource } from './face';
import { FacePrint } from './face';
import type { HeadDef } from './head';
import { HeadShape, sculptEars, sculptHead } from './head';
import type { Build } from './kit';
import { PLATE, ink } from './kit';
import { figure3dMaterial } from './material';
import type { BodySpec, BoneName, Joints } from './rig';
import { B, joints, skeleton } from './rig';
import { Sculptor } from './sculpt';

/** How a person moves when nothing else is asked of them. */
export interface Manner {
  /** the arms' resting pose: the props they hold at rest are held up by it */
  rest?: Partial<Record<BoneName, [number, number, number]>>;
  /** how lively the idle is (0.6 still, 1.4 restless) */
  energy?: number;
  /** the walk: stride share of the height, bounce, arm swing */
  stride?: number;
  bounce?: number;
  swing?: number;
}

/** One person of the troupe in the round. */
export interface Person {
  /** the quarter's key for them (`margaux_barman`) */
  key: string;
  name: string;
  body: BodySpec;
  skin: Hex;
  head: HeadDef;
  /** how the face is inked; a variant can change it (Camille's beard) */
  look: FaceLook | ((variant?: string) => FaceLook);
  face: (variant?: string) => FaceSource;
  /** the drawn eyes' centres in the head frame (the print's glassy shine needs them) */
  eyes: [Pt, Pt];
  /** what they wear and carry, round the bind pose */
  build: (b: Build, variant?: string) => void;
  manner?: Manner;
  /** variants of the person (Camille's two), the first the default */
  variants?: string[];
  /** the head's mesh, segments round and rings down: the troupe's 36 × 26, lighter in the street */
  headMesh?: [number, number];
  /** a lighter body for across the square, on the same bones and in the same print (the street's people have one) */
  far?: Pick<Person, 'head' | 'headMesh' | 'build'>;
}

export interface Model {
  person: Person;
  variant: string | undefined;
  J: Joints;
  head: HeadShape;
  mesh: SkinnedMesh;
  /** the lighter body, hidden until it is wanted */
  far: SkinnedMesh | null;
  bones: Bone[];
  /** each bone's bind-pose position relative to its parent */
  rest: Vector3[];
  print: FacePrint;
  material: ShaderMaterial;
  triangles: number;
  dispose(): void;
}

/** The middle of a person's head in the bind pose. */
export function headCentre(J: Joints): Vector3 {
  return new Vector3(0, (J.chin + J.crown) / 2, 0.012);
}

/** A person's body, sculpted and skinned to the bind pose, before any face is printed on it. */
export function sculptPerson(person: Person, variant = person.variants?.[0]) {
  const J = joints(person.body);
  const head = new HeadShape(person.head, person.body.head);
  const S = new Sculptor();
  const hc = headCentre(J);
  const b: Build = { S, J, head, hc };
  const look = typeof person.look === 'function' ? person.look(variant) : person.look;
  sculptHead(S, head, hc, look.frame, ink(person.skin, PLATE.skin), B.head, person.headMesh);
  sculptEars(S, head, hc, ink(person.skin, PLATE.skin2), B.head);
  person.build(b, variant);
  return { J, head, look, geometry: S.geometry(), triangles: S.triangles };
}

/** Sculpt a person and stand them on their skeleton. */
export function buildModel(world: World, person: Person, opts: { variant?: string; cell?: number } = {}): Model {
  const variant = opts.variant ?? person.variants?.[0];
  const { J, head, look, geometry, triangles } = sculptPerson(person, variant);
  const print = new FacePrint(look, person.face(variant), person.eyes, opts.cell ?? 256);
  print.draw('neutre');
  const material = figure3dMaterial(world, print.texture);
  print.offset('own', material.uniforms.uFaceCell.value);
  const mesh = new SkinnedMesh(geometry, material);
  const rig = skeleton(J);
  mesh.add(rig.bones[0]);
  mesh.bind(rig.skeleton);
  mesh.frustumCulled = false;
  let far: SkinnedMesh | null = null;
  if (person.far) {
    far = new SkinnedMesh(sculptPerson({ ...person, ...person.far }, variant).geometry, material);
    far.bind(rig.skeleton, mesh.bindMatrix);
    far.frustumCulled = false;
    far.visible = false;
  }
  const rest = rig.bones.map((bone) => bone.position.clone());
  return {
    person,
    variant,
    J,
    head,
    mesh,
    far,
    bones: rig.bones,
    rest,
    print,
    material,
    triangles,
    dispose() {
      geometry.dispose();
      far?.geometry.dispose();
      material.dispose();
      print.dispose();
      rig.skeleton.dispose();
    },
  };
}
