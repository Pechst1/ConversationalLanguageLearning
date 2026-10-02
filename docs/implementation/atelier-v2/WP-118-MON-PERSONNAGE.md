# WP-118 · Mon personnage: the learner draws themself into the story

*Defined 2026-10-02 at the owner's request. It depends on WP-116 (the rig library), and its story use touches canon: §4 needs the owner's decisions before any panel shows the learner differently.*

## 1. Goal

The learner makes their own character, a rig in the same variant-C style as the cast, so that "Toi" is somebody in the story and not a generic coat. There are two ways in:

1. **The editor.** Pick parts and colours with a live preview: «Mon personnage».
2. **From a photo.** Upload a picture; the app proposes a character built from the same parts. The learner then edits it like any other.

## 2. The character is parts, not a drawing

A character is a small JSON spec. Every value comes from a fixed catalogue, so whatever the learner picks or the photo suggests, the result is always in the house style, and nothing is drawn freehand.

| Part | Choices (first version) |
|---|---|
| Face shape | round, long, heart |
| Skin | 10 tones |
| Hair style | very short, crop, curls, coily, waves, long straight, bun, braids, bald, headscarf |
| Hair colour | 8 (black, dark brown, brown, auburn, red, blond, grey, white) |
| Eyes | 3 shapes, 4 iris colours |
| Brows | 3 weights |
| Nose | 3 |
| Facial hair | none, stubble, beard, moustache |
| Glasses | none, round, square |
| Headwear | none, tuque (the canon one), cap |
| Coat | the heavy coat stays (canon); 6 colours |
| Scarf | none, red (canon), ochre, blue |

- **No gender field.** The parts are combined freely. The rig's moods, mouths and blinks work for every combination, because they are the shared face kit.
- **Storage.** The spec lives on the user (`users.avatar_spec`, JSON, versioned, validated against the catalogue server-side). A missing or invalid spec falls back to today's Toi.
- **Rig.** `components/cast/rigs/toi.tsx` becomes parametric. It has a back view (what the story shows) and a face view (what the editor shows), both built from the spec.

## 3. The two ways in

### 3.1 The editor
- **Where:**
  - one onboarding step, optional and skippable;
  - Settings › «Mon personnage»;
  - the Trombinoscope's «Toi» card.
- **Screen:**
  - a large live preview at the top, which turns around: front and back, since the story mostly sees your back;
  - below it, one row per part with swatches or thumbnails;
  - «Au hasard» (random) and «Annuler».
- **Live preview:** it blinks, and a tap plays the five moods, so the learner sees their character act.
- **Design:** the av2 system; one 3D-press primary, «Enregistrer».

### 3.2 From a photo
- **Flow:** upload or take a photo → a vision model looks at it and returns only a part spec chosen from the catalogue. It returns no description, no likeness drawing and no stored features. The editor then opens on that spec, for the learner to adjust.
- **Privacy, a hard requirement:**
  - the photo is processed in memory and never stored, on our servers or in logs;
  - only the resulting spec is kept;
  - a consent line before upload says what happens to the photo;
  - the feature works without the photo at all;
  - the GDPR export (`gdpr_export.py`) includes the spec.
- **Cost:** one vision call per attempt, about US$0.01. A cap of 3 attempts per learner per day. A paid call, so live use needs the owner's OK.
- **Feasibility:** yes. Mapping a face to a fixed catalogue (skin tone, hair style and colour, glasses, facial hair) is a classification task that current vision models do reliably. A true likeness is not the aim: the house style would not hold, and likeness raises consent issues.
- **Safety:** we refuse photos that show more than one face, or a child. On any failure, the editor opens on a random spec.

## 4. In the story: decisions for the owner

The bible's visual rule is: "Toi: never shown face-on. From behind, cropped, or reflected in a dark window." Lila's portrait is a plot device built on that rule: across the season the figure in it "gains the coat, then hands, and never a face" (T5, T8).

| Option | What the learner's character does | Canon change |
|---|---|---|
| **A** (recommended) | The story keeps showing Toi from behind. Your hair, headwear, coat and scarf are now *yours*, in every panel where Toi stands, and in Lila's portrait as it gains the coat and the hands. Your face appears only in your own spaces: the editor, the Trombinoscope card, your profile and the recap seal. | None |
| **B** | As A, and your face appears once, at the season's end: in ending 1, Lila's portrait gains your face. | Yes, an ending beat. The owner (and the bible) must approve it |
| **C** | Toi is shown face-on in panels like the cast. | Yes, the visual rule. It also changes how every authored panel is framed |

Other open questions:
- Do the speech bubbles of your own lines get your small face (chrome, not the comic), or stay faceless as now?
- Should the generated seasons (WP-116 §12) let characters react to your look (Lila: «Tu as changé de coiffure ?»)? It would be a small, charming use of the spec, director-side.

## 5. Phases

| Phase | What | Done when |
|---|---|---|
| 1 | Parametric Toi rig: front and back, the catalogue, render tests for every part | Every combination renders. The back view replaces today's Toi in panels |
| 2 | `avatar_spec` on the user: schema, validation, API, GDPR export | Backend tests. A bad spec falls back |
| 3 | The editor: Settings, onboarding step, Trombinoscope | Walk screenshots of the editor in 3 languages, light and dark, phone size |
| 4 | From a photo: vision call → spec, no storage, consent, cap | Tests prove the photo is never written. A capped live trial with the owner's OK |
| 5 | Story use per the owner's option (§4) | The walk shows your character's back in the panels |

## 6. Not in scope
- Freehand drawing.
- Uploading a photo as the avatar itself.
- Likeness generation.
- Sharing characters with other learners.
