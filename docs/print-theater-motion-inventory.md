# Print-theater motion inventory

Pilot baseline: motion behaves like paper, ink, and a small press mechanism. It is
short, functional, and never required to understand or complete an activity.

| Moment | Surface | Treatment | Timing | Haptic |
|---|---|---|---:|---|
| Completion stamp | La Une, Courrier | scale-settle “thud” | 120 ms | success |
| Bon à tirer | Épreuve, Studio | scale-settle “thud” | 120 ms | success |
| Concept assembled | Épreuve | scale down → slight overshoot → settle | 180 ms | none |
| Newly printed content | all journal surfaces | opacity + small translate/scale | 120–180 ms | none |
| Press action | Cahiers, Studio | translate down + ink opacity | 120 ms | existing action haptic only |
| Speaking meter | Studio | alternating vertical scale | 900 ms loop | none |

All new keyframes animate only `transform` and/or `opacity`. The journal components
contain no `box-shadow: Npx Npx 0` treatments; press depth uses an inset ink
impression and an active translation.

`prefers-reduced-motion: reduce` disables these animations and transitions. The
shared haptic helper also suppresses browser/native pulses when reduced motion is
requested, so the completion effect never becomes an unavoidable sensory signal.

Audit commands:

```sh
rg "box-shadow:\s*[0-9-]+px\s+[0-9-]+px\s+0" \
  web-frontend/components/{laune,courrier,feuilleton,epreuve,cahiers} \
  web-frontend/pages/audio-session.tsx
rg "@keyframes|prefers-reduced-motion" \
  web-frontend/components/{laune,courrier,feuilleton,epreuve,cahiers} \
  web-frontend/pages/audio-session.tsx
```
