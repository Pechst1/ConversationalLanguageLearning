/**
 * Le Quartier · poses: a turn per bone, in the bone's own axes from the bind pose.
 */
import { Euler } from 'three';

import type { Model } from './model';
import type { BoneName } from './rig';
import { BONES } from './rig';

export type Turn = [number, number, number];
export type Pose = Partial<Record<BoneName, Turn>>;

const e = new Euler();

/** Set every bone to the bind pose turned by `pose`. */
export function applyPose(model: Model, pose: Pose) {
  BONES.forEach((name, i) => {
    const bone = model.bones[i];
    bone.position.copy(model.rest[i]);
    const r = pose[name];
    if (r) bone.quaternion.setFromEuler(e.set(r[0], r[1], r[2], 'XYZ'));
    else bone.quaternion.identity();
  });
}
