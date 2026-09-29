# Lieux et images: season 1 art direction

*For the image pipeline (WP-110) and the panel-art prompts (`app/services/panel_art.py`). The house style is unchanged: flat screen-printed illustration in the spirit of vintage French travel posters and three-colour risograph prints. That means large flat colour shapes, faces modelled in three or four flat planes, no outlines, slight misregistration and paper grain. The palette is the brand inks only: paper #F1ECE1, ink #14110D, cobalt #1D3A8A, vermilion #D8321A, sunflower #F3C318, deep green #2C6A5D, ochre #C2890F, and natural skin tones (world bible `visual_design`). This file adds the season's places, states and motifs.*

## Standing rules for every panel

1. **At least two characters in frame on most panels, doing something.** Every panel has a verb: carrying, pouring, measuring, peeling, painting, climbing. Tableaux of people sitting and talking are the exception, not the rule.
2. **Toi is never shown face-on.** Show Toi from behind, over the shoulder, cropped at the jaw, reflected in a dark window, or as a hand. They wear the slightly-too-heavy newcomer's coat, and their phone is close. The learner's line is drawn **as a balloon inside the panel** (F-2). Every other character speaks in captions under the art.
3. **Silent panels are compositions, not gaps.** Give them the strongest image on the page: one object, one pair of hands, one face.
4. **Flashbacks (2023) use faded inks.** Paper plus cobalt at about half strength, with a single warm accent (the orange of the fire, or the red of the neon). No vermilion anywhere else in a flashback panel.
5. **Diegetic text must be legible.** This covers Polaroid captions, the calendar, the notebook, letters, SMS, stencils and the neon, and it is written into the prompt verbatim. When it is too long for the art, the reader overlays it as a crisp text layer on the drawn object, never as a caption.
6. **Camille** (`s1.camille_gender`) has two canonical descriptors (below). Other characters never describe Camille's appearance in dialogue.

---

## Places

### Odile's flat · first floor, above Le Mistral · *the time capsule*

- **Canonical descriptor.** A small two-room Paris flat on the first floor above a corner café, stopped in April 2023: the shutters closed, dust suspended in thin bars of light, a woman's green coat on a hook by the door, felt slippers side by side under a chair, an old Polaroid camera on the table beside a cup with a dried ring of café crème, and a kitchen wall calendar showing April 2023. In the kitchen, above the gas stove, one patch of wall is painted a whiter white than the rest. A narrow balcony looks over the canal, and a shoebox sits under the made bed.
- **Palette.** Paper and dust-cobalt in the sealed state. When the shutters open, sunflower light off the canal floods one wall.
- **States across the season.**
  - **T1.** The door is opened and closed: darkness, street light through the slats, a stopped kitchen clock. We see only the room and your hand.
  - **T2.** The shutters open: morning light, dust, the calendar, the Polaroid box spilling on the floorboards.
  - **Gaps 2–5 (if `lila_has_key`).** Lila's easel by the window, a canvas, ochre smears on a rag. Odile's things are moved *carefully* to one side, never removed.
  - **T5 B.** A wooden crate stencilled FRAGILE · BERLIN · KÜNSTLERHAUS AM KANAL, bubble wrap, two washed mugs on the drainer.
  - **T6 A.** Night, one lamp, the black notebook open on the table, a phone propped against the Polaroid box.
  - **T7 B.** Two calendars side by side: April 2023, and January 2027 with «8» circled.
  - **T8, ending 1.** Lived in: your coat now on the hook next to hers, and the radiator.
  - **T8, ending 2.** Builders, dust sheets, the kitchen tiles coming off the wall.
  - **T8, ending 3.** Empty except for Odile's kitchen table, turned over.
- **Never.** Never mess, decay or horror. It is a room that waited, not a room that rotted.

### Le Mistral · the corner of the quai de Valmy

- **Canonical descriptor** (extends `le_mistral`). A narrow corner café-bar by the Canal Saint-Martin. It has a worn zinc counter with a **hinged flap** at one end, and a **small round-topped stool at the far end of the zinc** (Odile's). The **booth** at the back has old ox-blood leather, and its **corner seat** is Gus's. Behind the zinc hangs a long mirror. The **till** has an old photograph tucked behind it. Above the zinc is a **small oil painting**: the café's corner in a strong wind, blue and ochre, signed «L.» lower right. Outside, a vertical **red neon sign «MISTRAL»**. Warm amber light.
- **The back room.** It was rebuilt after the 2023 fire: new plaster that is a slightly different white, the café's electrical board, stacked crates, and an easel under a sheet (Lila's portrait, from gap 4).
- **Variants.**
  - **T4 party.** Lila's hand-painted banner «LE MISTRAL · 25 ANS · ON RESTE» across the mirror. The Polaroid wall above the booth: rows of white-bordered squares, each with a small handwritten card beneath. The camera on its tripod with its red light.
  - **T7 Réveillon.** One long table, paper stars, and Gus's candelabra.
  - **T8, ending 2 (co-op).** Communal long tables at the front, a serving pass, and the booth moved to the back and reupholstered in loud orange («couleur sarrasin»). The Polaroid wall is framed and permanent.
  - **T8, ending 3.** Being emptied: chairs going out to a white van, bare nails, the neon going out letter by letter.
- **Mood.** Home base, but never the default location in the generated days (the canon rotation rule applies).

### The stairwell

- **Canonical descriptor.** A narrow old Paris stairwell with worn wooden steps, a stair window onto the courtyard, and a push-button timed light (*minuterie*) that clicks off mid-scene. On the first-floor door there is a brass numeral «1».
- **Use.** The stairwell is the season's threshold, so sitting on the steps is how people say what they cannot say at a table (T1 R4, T4 R4–R5). The light going out is a punctuation mark.

### M. Marchand's office · second floor, «Gérance Marchand»

- **Canonical descriptor.** A small property-management office in an old building. Walls of **key boards** hold hundreds of labelled keys on hooks. There are grey filing cabinets, a desk lamp, and a framed photo of his late wife. In the middle of it all stands a **camp bed made with hospital corners**. On the desk is a small framed Polaroid of an old man and an old woman laughing on a bench by a lake.
- **Mood.** Order holding back loneliness. Keep it cold ink and grey, with one warm lamp.
- **The Polaroid on the desk.** Caption «Dimanche. M. rit. Enfin.»

### Rue de Lancry · *season-2 seed*

- **Canonical descriptor.** A narrow street running off the quai de Valmy, with tall pale façades and wrought-iron balconies. There is **one third-floor window with an easel visible inside**, and sometimes the tiny silhouette of an old man at it.
- **Rule.** In season 1 he is **background only**, and never larger than a thumbnail in the frame: T1 A P1, T5 A R1, and T8 (the lit window at dusk). Never face-on, never named, never lit brighter than the street.

### The canal · quai de Valmy

- **Canonical descriptor.** The Canal Saint-Martin: green iron footbridges, locks with black water, plane trees, moored barges, and night reflections of red neon.
- **Use.** The walks where things are said sideways: T5 A R1, T7 B R1, and the gaps. New Year's morning is empty: one jogger, one pigeon.

### The roof *(gap 3)*

Zinc roofs, chimney pots, an open skylight, the canal below, and a torch beam finding two figures.

### Your rented studio *(canon `user_apartment`)*

A sixth-floor walk-up studio with the cold radiator (canon) and a phone lit on the bed. The return ticket is on its screen.

### Other places

- **Marin and Lila's flat** (canon). The co-op folder on the fridge, held by a sardine-shaped magnet.
- **Marin's NGO office** (canon). The fern, the spreadsheet projected on the wall, the leek pointer.
- **Mairie du 10e.** Stone steps, and two counters on two floors with no lift.
- **The notary's office** (Maître Vasseur). A polished table, a fountain pen, tall windows on a boulevard, the quartier visible on the pavement below (T6 B, public variant).
- **Mme Diallo's boulangerie.** Baguettes in a wicker rack, floured counter, and a paper bag of two croissants.
- **Gare de l'Est.** A glass-roofed platform, a long white high-speed train, and a banner painted by Gus.
- **Gus's loft** (canon). In ending 2, the painting leans against the wall face-first, with the inscriptions facing the viewer.

---

## Recurring motifs *(each is written into prompts exactly as described)*

| Motif | How it looks | Where it matters |
|---|---|---|
| **The Polaroids** | Square image, thick white border, flash-lit colours. The caption is in **Odile's hand**: blue ballpoint, slanted and looped. It is firm from 2009 to 2020 and visibly shakier in 2022–23. | T2, T4 (the wall; two stuck together with **browned, curled edges**), T6 (the desk), T7 B (Gus's), throughout the gaps |
| **The key and the cicada** | An old brass key on a ring with a small **enamel cicada**, green and gold. Lila's copy (if made) is new, brighter brass without a charm. | T1 P3 (Margaux's hand stops), T2 P1, T5 B P1, T8 platform |
| **The neon «MISTRAL»** | Vertical red letters (vermilion ink) on the corner. Seen from the first-floor window, from above and behind, they read reversed: **LARTSIM**. | T1 P1, T4 P6 (the proof), T7 midnight, T8 ending 3 (going out: MISTRA… MIST… M.) |
| **The painting «L.»** | A small oil in a gilt frame: the café's corner in the wind, painted from slightly above. The back reads «Pour Odile, qui part. — L., 1970» in ink, and «Toujours rue de Lancry. — L., 2021» in pencil. | Every Mistral interior (always above the zinc until T8), T8 (all endings) |
| **Odile's stool** | A small round-topped stool at the far end of the zinc. Margaux puts a café crème in front of it on certain nights. | T1, T4 P3, T7 P2, T8 ending 1 R2 |
| **The zinc flap** | The hinged barrier at the end of the counter. Nobody crosses it except in T4 (c). | T4 exchange 2 |
| **Empty hands** | Margaux without a glass happens twice in the season. | T4 P8, T7 (lease variant) |
| **The calendar(s)** | April 2023 in Odile's hand, and later January 2027 beside it. | T2 (Enquête), T7 À suivre |
| **The black notebook** | A worn black notebook, opened to «Le Mistral à nous» (a list of forty names) or to the last pages in a breaking hand. | T2 B, T6 A |
| **The camp bed** | Hospital corners among the files. | T3 À suivre, T6 A, gap 6 (stripped) |
| **Lila's ochre** | Paint on her thumb, and later on your hand. The ochre scarf. | T5 (romance: the thumb that stays), T7 midnight, gap 7 |
| **The portrait** | The group at the booth, Odile at the zinc, and in the lower corner **a figure from behind in a heavy coat**. Over the season the figure gains the coat, then hands, and never a face. | T5, T8 |
| **Romy's red light** | The camera's tally light, and the memory card slid into her jacket. | T4, T6 B |
| **Gus's index cards** | A fan of cards in his breast pocket behind the red pocket square. They fall. | T3, T4, gap 3 |
| **Marchand's keys** | A heavy ring of old keys. It is lighter by two in ending 1. | Every Marchand panel |
| **Recorded letters** | The green-and-white *recommandé* slip. | Gaps 4–5 (Margaux's lease) |

---

## Character notes new this season

- **Odile Ferrand** appears in Polaroids and flashbacks only.
  - **Descriptor.** A small, upright woman in her seventies. Short white hair cut straight, large dark eyes with deep laugh lines, fair lined skin. A moss-green cardigan and an old Polaroid camera on a strap. She is usually laughing at something outside the frame.
  - **In the 2023 flashback.** A dressing gown, holding a smoking pan by its handle.
- **Camille Marchand.** Both descriptors share: about thirty, a bike helmet under one arm, rain-damp, a practical dark waxed jacket, a folder of figures, a direct, level gaze, and M. Marchand's long nose, softened. Accent colour: Marchand's ink-grey, lightened.
  - **(m)** A lean man, short dark hair flattened by the helmet, a close-trimmed beard, rolled sleeves.
  - **(f)** A lean woman, dark hair in a low knot flattened by the helmet, small silver earrings, rolled sleeves.
- **Bastien Roux** (Solvel). A good camel coat, a laser measure, and a red dot that crosses people's things.
- **Mme Diallo.** A baker in her fifties with a floured apron and reading glasses on a chain.
- **«L.»** A distant figure only (see rue de Lancry).
