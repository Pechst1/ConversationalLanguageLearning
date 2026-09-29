/**
 * WP-94 «Numéro spécial» — inside the day, the scene and the reader carry the
 * same kicker the Home card did. The session shell provides it; the reader
 * (deep in the step tree) reads it, so no step signature has to change.
 * `null` on every ordinary day.
 */

import React from 'react';

export const SpecialKickerContext = React.createContext<string | null>(null);

export function useSpecialKicker(): string | null {
  return React.useContext(SpecialKickerContext);
}
