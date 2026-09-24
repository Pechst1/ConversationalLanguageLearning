# La Forge — template naturalness review (2026-09-24)

The owner asked for a naturalness review of WP-S2's sentence templates, done together with WP-S5
(story-linked content and coaches). This document covers the method, what the review found, what
was fixed, the risk that remains, and a sheet of 5 items per A1 unit for a human spot-check.

Code: `app/services/item_semantics.py` (the constraints and the checker), `app/services/item_bank.py`
(binding under constraints), `app/data/grammar_templates/` (the lexicon's annotations and the fixed
frames). Tests: `tests/test_forge_naturalness.py`.

## 1. Method

1. **Sample.** 30 items per A1–A2 unit (68 units, 2 040 items), seed `review`, all frames and
   rung sources. Each sentence was read with its English cue.
2. **Classify.** Every sentence that is grammatical but odd, uses the wrong register or collocation,
   has a wrong form, or has an English cue that doesn't match was noted and given a kind (below).
3. **Fix at the source.** Each kind got a constraint in the lexicon or in the slot specs, so that the
   bad combination can't be bound. The constraint is one function, used both when binding a slot
   and by the checker.
4. **Checker.** `item_semantics.violations(item)` reads a finished item — its bindings, its declared
   links, the frame's literal time words, the French sentence and the English cue — and names every
   broken constraint. The bank rejects such an item as a last line of defence and counts it
   (`ItemBank.stats`).
5. **Re-sample and re-read.** Repeated until the sample read clean. Then the test locks it in:
   a seeded sample of 40 items per unit is clean, and the checker rejects under 5 % of rendered
   items in every unit. That second number proves the source constraints do the work, not the
   rejection.

## 2. Findings

**Automated re-count.** The final checker, run over the original 2 040-item sample, flags
**219 items (10.7 %)**:

| Kind | Items | Example (before) |
| --- | ---: | --- |
| English cue in the wrong tense (present with a future time) | 84 | «Vous allez au magasin cet été» → *You go to the shop this summer* |
| Thing in a place that doesn't have it | 50 | «Il y a une pomme à la brocante», «… de beurre à la banque» |
| Two times that clash in one sentence | 27 | «Hier, vous avez nagé le dimanche», «Je vais partir à huit heures après le travail» |
| Price that doesn't fit the thing | 23 | «Le croissant coûte neuf cent quarante euros», «La voiture coûte trente-quatre euros» |
| Verb that can't be wanted, planned or ongoing | 9 | «Je voudrais préférer le métro», «On doit perdre les clés» |
| Odd collocation | 7 | «Elles vont au quartier demain», «Tu vas à l'immeuble ce soir» |
| Same person twice | 5 | «Romy est moins sympa que Romy», «Romy est rentrée avec Romy» |
| Adverb in the wrong place | 4 | «Il a dormi bien», «Tu veux dormir bien ?» |
| Pair of names with a singular verb (FR and EN) | 3 + 3 | «Romy et Margaux part en vacances» / *Romy and Margaux goes* |
| Head count bigger than the place | 3 | «590 personnes au Mistral» |
| Missing elision | 3 | «à côté de elle», «quelque chose de original» |
| Part of the day clashes with the verb | 2 | «On s'est couché tard ce matin» |
| English quantity | 1 | *I buy too much carrots* |

**Manual tally**, for the kinds the re-count can't see because the old lexicon had no annotations
(approximate, from reading):

| Kind | ≈ Items | Example (before) |
| --- | ---: | --- |
| Adjective that doesn't suit the noun | 25 | «Les verres sont anglais», «La lettre est propre», «La pomme est froide», «une photo bleue» |
| Cause, contrast or advice that doesn't follow | 25 | «Il reste au lit parce qu'il est prêt», «J'aime le café mais je suis heureux», «Tu es heureux ? Tu devrais te coucher tôt» |
| Verb and object or place that don't go together | 20 | «C'est le restaurant où Romy étudie», «Il n'achète rien à l'hôpital», «Tu travailles à l'hôpital ? Oui, j'y travaille après le travail» |
| Cast facts against the world bible | 15 | «Voici Romy. C'est une infirmière» (she is a journalist), «Marin a soixante-six ans» |
| Habitual frame with a one-off or stative verb | 12 | «Tu as un vélo rouge tous les jours», «Le lundi, je trouve un bon café», «Elles habitent au sixième étage tous les soirs» |
| Duration that doesn't fit the verb | 6 | «On attend le bus depuis trois semaines», «Tu habites à Munich ? … depuis dix minutes» |
| Comparing unlike things / wrong container / wrong area | 8 | «La table est aussi jolie que le stylo», «une tasse de vin», «l'aéroport le plus moderne du canal» |
| Doubled English words | 4 | *drop by by*, *wait for for* |

About **one sentence in six** was odd before the review. The most common problem was an English cue
in the wrong tense. The most visible was a thing in a place that doesn't have it.

## 3. Fixes

### 3.1 Semantic annotations (lexicon `forge-lexicon-2`)

- **Nouns** get domains (`dom`): produce, bakery, deli, grocery, dish, drink, clothing,
  accessory, books, press, stationery, mail, tech, furniture, seat, fixture, tableware, art,
  music_obj, vehicle, luggage, ticket, plant, tree, animal, and the person roles friend,
  neighbour, family, colleague, student, teacher, staff, child, landlord.
  - Things people own carry `possess`, things bought in a bunch carry `bulk`, weighed foods carry
    `weigh`, and priced things carry a price range in euros.
  - The vague noun «objet» is gone.
- **Places** list what they hold (`holds`), what happens there (`use`: `at_shop`, `at_eat`,
  `at_work`, `at_study`, `at_live`, …) and their capacity (`cap`).
  - Areas (quartier, ville, rue, canal) contain places, never things.
- **Adjectives** list the domains they can describe (`kinds`). Colours go with things you paint;
  nationalities with food, people and a few objects; «chaud/froid» with dishes and drinks; «joli»
  no longer describes a person.
- **Verbs** carry aspect (`stative`, `mishap`, `oneoff`, `habit`, `leisure`), where they happen
  (`at`), how long (`dur`: short / mid / long) and their part of the day (`daypart`).
  - Complements carry `adv_pre` («bien», «beaucoup»: never after a participle), `rest`,
    `routine` and `late`.
- **Pools:**
  - durations have a scale;
  - containers list what they hold («une tasse» holds coffee, tea or milk);
  - numbers for «en» have a size;
  - the reasons behind «car» are either `urgent` or `unwell`;
  - adverbs in -ment list the verbs they modify.
- **The cast** keep their world-bible jobs:
  - Romy is a journalist;
  - Lila is a teacher and a painter;
  - Marin is an environmentalist;
  - Gus is a consultant;
  - Margaux owns a café.
  They also keep plausible ages.

### 3.2 Constraints at binding (`item_semantics.pair_clash` / `link_clash`)

A candidate for a slot is dropped when it clashes with anything already bound. The checks are:

- **Location:** the thing must be of a kind the place holds.
- **Price and capacity:** the price must fit the thing; the head count must fit the place.
- **Verb:** the place must suit the verb (`at`), and so must the duration and the part of the day.
  A verb can't meet a time that excludes it («travailler après le travail»).
- **Identity:** one cast member never appears twice. This includes names inside complements
  («rentrer avec Romy»).
- **Time:** time categories (day, part of day, clock, frequency, span, habit, relative, now) never
  clash. «Now» frames (*en train de*, *venir de*, an interrupted background) take no other time.
- **Declared dependencies (`X@HEAD`):**
  - the adjective fits its noun;
  - the comparison is between like things;
  - the container is an area;
  - the adverb fits its verb;
  - the age fits the person;
  - a vocative agrees with a «tu» subject («Tu es contente, Marin» can't be generated).
- **Frames:** each frame's literal time words («ce soir», «le samedi», «Aujourd'hui») are classified
  once and constrain its slots.

### 3.3 Template fixes (units_a1 / units_a2)

- **Wrong forms:**
  - «Romy et Margaux part» → the verb now agrees with the pair;
  - «à côté de elle» → «à côté d'elle» (`de_tonic`);
  - «quelque chose de original» → «d'original».
- **English cues:**
  - future times take the progressive or *will* (*You are going to the shop this summer*,
    *Yes, I will phone him tomorrow*);
  - quantities agree (*too many carrots*);
  - *drop by by* and *wait for for* are gone;
  - «sortir» is *go out*;
  - *all the project* → *the whole project*.
- **Slot specs:** about 90 slots were narrowed.
  - Question frames about the speaker no longer ask «Où est-ce qu'on habite ?».
  - «Il faut», modals, «je voudrais» and «en train de» exclude stative verbs and mishaps.
  - The object pronoun frames drop «oublier», «perdre» and «connaître», and definite family nouns.
  - Superlatives and «meilleur» use areas.
  - «acheter» places are shops.
  - «répondre à» only takes a message, a question or a letter.
  - Advice and cause frames pair tiredness with rest and gladness with going out.
  - «Vous … ce week-end ? Oui, nous le connaissons demain» is gone.
- **New frames:**
  - partitive with «prendre» (*have*);
  - weighed quantities;
  - «car … mal à la tête»;
  - «tu devrais» when glad.

### 3.4 Story (WP-S5)

- Entries that bring the story in carry a 4× weight:
  - a cast member;
  - a bible place: Le Mistral, the canal market, the newsroom, the flea market, the NGO office;
  - a recurring object: Marin's ring, Gus's notebook, the radiator, Romy's microphone and boxes,
    Lila's paintings.

  Entries the learner's own chronicle has lately been about count 2× more (`forge_story`, read
  only).
- About 60 story complements, such as «prendre un café au Mistral», «chercher la bague de Marin» and
  «lire le carnet de Gus».
- Cast-subject twins for frames with pronoun subjects, where the catalogue's detector allows them.
- Frames whose pronoun is the point get a **vocative twin**: the same sentence said *to* a cast
  member («J'ai faim ce soir, Marin.», «Tu veux des poires, Lila ? Oui, j'en veux deux.»). The
  pronoun the rule is about stays the subject. With a «tu» subject, the vocative agrees in gender.

**Story-link rate:** 85.6 % of a seeded sample of 40 items per unit (2 720 items) name a cast
member, a bible place or a story object. Every unit is at least 50 %; the lowest are EN_QUANTITY,
AVOIR and JE_VOUDRAIS, at about 62–68 %. Before the review the rate was 50 %.

## 4. The checker and its test

`tests/test_forge_naturalness.py`:

- Each finding kind has a positive case, and natural look-alikes are negative cases. These include
  «Tu vas au marché ce week-end ? Oui, j'y vais ce week-end.», «Ils viennent d'Angleterre.» and
  «Nous nous sommes beaucoup amusés.».
- A seeded sample of 40 items per A1–A2 unit has **no violation**.
- The checker rejects **< 5 %** of rendered items in every unit. The measured rate is 0 % in almost
  every unit.
- At least **80 %** of the sample is story-linked, and every unit is at least 50 %.
- The WP-S2 acceptance still holds: ≥ 200 distinct valid items per rung type per unit, no
  spoilers, and the séance validator passes (`tests/test_wp_s2_item_bank.py`).

## 5. Remaining risk

- **The world is small and hand-annotated.** A new noun, place or verb without annotations falls
  back to permissive defaults: no domain means no location check. Anyone adding to the lexicon
  must annotate. The location check skips nouns without a `dom`.
- **Pragmatics the rules don't model:**
  - plausibility of frequency («Ils voyagent en Italie toutes les semaines»);
  - mild oddities of taste («Tu prends souvent une douche»);
  - which of two definite nouns is known to the listener («Tu invites le voisin ?»).

  These read as slightly bookish but are correct French.
- **Vocatives are frequent (60 % of eligible frames).** They are natural in speech, but a learner
  may notice the pattern. `VOCATIVE_SHARE` in `item_bank.py` tunes it.
- **The English cues are generated.** They are checked for tense, agreement and quantity, not for
  idiom. S6 moves cues to the learner's language.
- **The catalogue detectors are pronoun-based for ÊTRE, AVOIR and PRONOMINAL.** Cast-subject frames
  for these units are filtered out. The story reaches these units through complements and
  vocatives.
- **The free-use scene uses generic coach openers** when the item has no question or `ask` of its
  own. Openers are per coach, three each. About 12 % of candidate items can't be a scene with their
  coach (the reply would name the coach). The bank then takes the next item.

## 6. Spot-check sheet — 5 items per A1 unit

Seed `spot-check-2026-09-24:<unit>`, the séance's own detector. Tick a box when the sentence is
natural, and write the item's `frame` next to any that isn't.

**FR2_A11_ETRE** — I am, you are: subject pronouns and être · coach: Lila

| # | French | English cue | frame | ok? |
|---|---|---|---|---|
| 1 | Ils sont au marché du canal, Lila. | They are at the canal market, Lila. | `etre-place~voc` | ☐ |
| 2 | Vous êtes calmes, Marin. | You are calm, Marin. | `etre-adj~voc` | ☐ |
| 3 | Je suis anglais. | I am English. | `etre-adj` | ☐ |
| 4 | Nous sommes sérieux, Margaux. | We are serious, Margaux. | `etre-adj~voc` | ☐ |
| 5 | Vous êtes à la rédaction avec Marin. | You are at the newsroom with Marin. | `etre-place-with` | ☐ |

**FR2_A11_AVOIR** — Avoir: I have, I am 20 · coach: Lila

| # | French | English cue | frame | ok? |
|---|---|---|---|---|
| 1 | On a rendez-vous au Mistral. | We have an appointment at Le Mistral. | `avoir-thing` | ☐ |
| 2 | Elles ont dix-huit ans. | They are 18 years old. | `avoir-age` | ☐ |
| 3 | J'ai faim ce soir, Marin. | I am hungry tonight, Marin. | `avoir-state~voc` | ☐ |
| 4 | J'ai une question, Romy. | I have a question, Romy. | `avoir-thing~voc` | ☐ |
| 5 | Lila demande ton âge. J'ai vingt-trois ans. | Lila asks how old you are. I am 23 years old. | `avoir-age-ask` | ☐ |

**FR2_A11_IL_Y_A** — Il y a: there is, there are · coach: M. Marchand

| # | French | English cue | frame | ok? |
|---|---|---|---|---|
| 1 | Il y a une lampe à la brocante, Gus. | There is a lamp at the flea market, Gus. | `ilya-place~voc` | ☐ |
| 2 | Il y a des sandwichs au Mistral, Margaux. | There are sandwiches at Le Mistral, Margaux. | `ilya-plural~voc` | ☐ |
| 3 | Il y a des stylos à l'école, Margaux. | There are pens at the school, Margaux. | `ilya-plural~voc` | ☐ |
| 4 | Il n'y a pas de confiture au marché du canal, Romy. | There is no jam at the canal market, Romy. | `ilya-neg~voc` | ☐ |
| 5 | Il y a des gâteaux au marché du canal. | There are cakes at the canal market. | `ilya-plural` | ☐ |

**FR2_A11_UN_UNE** — Un, une, des: a, an, some (and gender) · coach: Margaux

| # | French | English cue | frame | ok? |
|---|---|---|---|---|
| 1 | Gus a une plante dans le salon. | Gus has a plant in the living room. | `unune-has` | ☐ |
| 2 | Vous cherchez un carton à l'hôtel. | You look for a box at the hotel. | `unune-look` | ☐ |
| 3 | Nous cherchons une plante au bureau de l'ONG, Romy. | We look for a plant at the NGO office, Romy. | `unune-look~voc` | ☐ |
| 4 | Vous cherchez un stylo à l'école, Romy. | You look for a pen at the school, Romy. | `unune-look~voc` | ☐ |
| 5 | Lila a un tableau dans le salon. | Lila has a painting in the living room. | `unune-has` | ☐ |

**FR2_A11_LE_LA** — Le, la, l', les: the · coach: Margaux

| # | French | English cue | frame | ok? |
|---|---|---|---|---|
| 1 | La rue est vieille. | The street is old. | `lela-is` | ☐ |
| 2 | Lila cherche la bague. | Lila is looking for the ring. | `lela-cast-look` | ☐ |
| 3 | On cherche la bague, Romy. | We look for the ring, Romy. | `lela-look~voc` | ☐ |
| 4 | Vous cherchez la bague, Lila. | You look for the ring, Lila. | `lela-look~voc` | ☐ |
| 5 | Marin cherche la clé. | Marin is looking for the key. | `lela-cast-look` | ☐ |

**FR2_A11_ER_VERBS** — Present tense of -er verbs · coach: Marin

| # | French | English cue | frame | ok? |
|---|---|---|---|---|
| 1 | Nous travaillons à la rédaction. | We work at the newsroom. | `er-comp` | ☐ |
| 2 | Je joue au foot. | I play football. | `er-comp` | ☐ |
| 3 | Tu envoies des photos. | You send photos. | `er-comp` | ☐ |
| 4 | Vous chantez très fort, Lila. | You sing very loudly, Lila. | `er-comp~voc` | ☐ |
| 5 | Tu préfères le métro, Margaux. | You prefer the metro, Margaux. | `er-comp~voc` | ☐ |

**FR2_A11_NEGATION** — Ne…pas, and pas de · coach: Margaux

| # | French | English cue | frame | ok? |
|---|---|---|---|---|
| 1 | On ne danse pas avec Lila. | We do not dance with Lila. | `neg-verb` | ☐ |
| 2 | Vous n'achetez pas de café, Romy. | You do not buy coffee, Romy. | `neg-pas-de-mass~voc` | ☐ |
| 3 | Lila et Romy ne mangent pas à midi. | Lila and Romy do not eat at noon. | `neg-cast` | ☐ |
| 4 | Je ne marche pas le long du canal. | I do not walk along the canal. | `neg-verb` | ☐ |
| 5 | Gus et Marin n'étudient pas avec Lila. | Gus and Marin do not study with Lila. | `neg-cast` | ☐ |

**FR2_A11_QUESTIONS** — Yes/no questions: intonation and est-ce que · coach: Romy

| # | French | English cue | frame | ok? |
|---|---|---|---|---|
| 1 | Est-ce qu'ils commandent deux thés ? | Do they order two teas? | `estceque` | ☐ |
| 2 | Est-ce que Lila dit merci ? | Does Lila say thank you? | `estceque-cast` | ☐ |
| 3 | Est-ce que tu attends le train ? | Do you wait for the train? | `estceque` | ☐ |
| 4 | Est-ce qu'elle danse le samedi soir ? | Does she dance on Saturday nights? | `estceque` | ☐ |
| 5 | Est-ce que Lila appelle Marin ? | Does Lila call Marin? | `estceque-cast` | ☐ |

**FR2_A11_QUESTION_WORDS** — Question words: où, quand, comment, combien, quel · coach: Romy

| # | French | English cue | frame | ok? |
|---|---|---|---|---|
| 1 | Quand est-ce que tu sors, Gus ? | When do you go out, Gus? | `qw-when-do~voc` | ☐ |
| 2 | Quand est-ce que Gus arrive ? | When does Gus arrive? | `qw-when-cast` | ☐ |
| 3 | Quand est-ce que Romy sort ? | When does Romy go out? | `qw-when-cast` | ☐ |
| 4 | Où est-ce que Marin habite ? | Where does Marin live? | `qw-where-cast` | ☐ |
| 5 | Où est le manteau ? | Where is the coat? | `qw-where-is` | ☐ |

**FR2_A11_JE_VOUDRAIS** — Je voudrais…, vous voulez… ? (polite asking) · coach: Margaux

| # | French | English cue | frame | ok? |
|---|---|---|---|---|
| 1 | Margaux, je voudrais une tarte, s'il te plaît. | Margaux, I would like a tart, please. | `voudrais-mistral` | ☐ |
| 2 | Je voudrais un citron, s'il vous plaît. | I would like a lemon, please. | `voudrais-thing` | ☐ |
| 3 | Margaux, je voudrais un sandwich, s'il te plaît. | Margaux, I would like a sandwich, please. | `voudrais-mistral` | ☐ |
| 4 | Je voudrais un croissant, s'il vous plaît. | I would like a croissant, please. | `voudrais-thing` | ☐ |
| 5 | Tu veux aider les voisins ? | Do you want to help the neighbours? | `tu-veux` | ☐ |

**FR2_A11_NUMBERS** — Numbers 0–69 and prices · coach: Margaux

| # | French | English cue | frame | ok? |
|---|---|---|---|---|
| 1 | Romy a payé soixante-huit euros pour l'horloge. | Romy paid 68 euros for the clock. | `num-paid` | ☐ |
| 2 | Ça fait soixante-trois euros, s'il vous plaît. | That's 63 euros, please. | `num-total` | ☐ |
| 3 | Le billet pour Paris coûte quarante-deux euros, Gus. | The ticket to Paris costs 42 euros, Gus. | `num-ticket~voc` | ☐ |
| 4 | Le billet pour Toulouse coûte soixante-sept euros, Gus. | The ticket to Toulouse costs 67 euros, Gus. | `num-ticket~voc` | ☐ |
| 5 | Romy a payé cinquante-sept euros pour le sac. | Romy paid 57 euros for the bag. | `num-paid` | ☐ |

**FR2_A11_ADJ_AGREEMENT** — Adjectives: agreement and position · coach: Lila

| # | French | English cue | frame | ok? |
|---|---|---|---|---|
| 1 | Gus cherche un beau parc. | Gus is looking for a beautiful park. | `adj-pre` | ☐ |
| 2 | Tu achètes une valise chère. | You buy an expensive suitcase. | `adj-position-post` | ☐ |
| 3 | Les lampes sont noires. | The lamps are black. | `adj-plural` | ☐ |
| 4 | Romy a un carnet vert. | Romy has a green notebook. | `adj-post` | ☐ |
| 5 | Marin a un chien noir. | Marin has a black dog. | `adj-post` | ☐ |

**FR2_A11_PLACES** — À Paris, en France, au Japon · coach: Romy

| # | French | English cue | frame | ok? |
|---|---|---|---|---|
| 1 | Nous travaillons aux États-Unis, Gus. | We work in the United States, Gus. | `places-work~voc` | ☐ |
| 2 | Margaux est en Angleterre pour le travail. | Margaux is in England for work. | `places-be` | ☐ |
| 3 | Vous habitez au Portugal. | You live in Portugal. | `places-live` | ☐ |
| 4 | Elles travaillent à Vienne, Marin. | They work in Vienna, Marin. | `places-work~voc` | ☐ |
| 5 | Margaux est à Nice pour le travail. | Margaux is in Nice for work. | `places-be` | ☐ |

**FR2_A11_CONTRACTIONS** — Au, aux, du, des: à and de with le/les · coach: Marin

| # | French | English cue | frame | ok? |
|---|---|---|---|---|
| 1 | Gus va au bureau de l'ONG lundi prochain. | Gus is going to the NGO office next Monday. | `contr-cast-go` | ☐ |
| 2 | C'est le chapeau du voisin. | It's the neighbour's hat. | `contr-of` | ☐ |
| 3 | Margaux va au bureau de l'ONG après le travail. | Margaux is going to the NGO office after work. | `contr-cast-go` | ☐ |
| 4 | C'est l'ordinateur du voisin. | It's the neighbour's computer. | `contr-of` | ☐ |
| 5 | Gus va au marché du canal samedi. | Gus is going to the canal market on Saturday. | `contr-cast-go` | ☐ |

**FR2_A11_POSSESSIVES** — Mon, ma, mes: possessives · coach: Lila

| # | French | English cue | frame | ok? |
|---|---|---|---|---|
| 1 | Marin aime beaucoup sa bague. | Marin likes his ring a lot. | `poss-loves` | ☐ |
| 2 | Lila aime beaucoup son téléphone. | Lila likes her phone a lot. | `poss-loves` | ☐ |
| 3 | Vous cherchez votre clé, Margaux. | You look for your key, Margaux. | `poss-look~voc` | ☐ |
| 4 | Elles cherchent leur stylo, Romy. | They look for their pen, Romy. | `poss-look~voc` | ☐ |
| 5 | Je cherche mes billets, Lila. | I look for my tickets, Lila. | `poss-plural~voc` | ☐ |

**FR2_A11_ALLER_VENIR** — Aller and venir: going and coming · coach: Marin

| # | French | English cue | frame | ok? |
|---|---|---|---|---|
| 1 | Nous venons d'Iran. | We come from Iran. | `venir-origin` | ☐ |
| 2 | Nous venons de Chine, Marin. | We come from China, Marin. | `venir-origin~voc` | ☐ |
| 3 | Il vient de Grèce. | He comes from Greece. | `venir-origin` | ☐ |
| 4 | On va au bureau de l'ONG avec Margaux. | We go to the NGO office with Margaux. | `aller-with` | ☐ |
| 5 | Elles viennent du restaurant. | They come from the restaurant. | `venir-place` | ☐ |

**FR2_A11_PARTITIVE** — Du, de la, de l': some (food and drink) · coach: Margaux

| # | French | English cue | frame | ok? |
|---|---|---|---|---|
| 1 | Au marché du canal, Marin achète de l'huile d'olive. | At the canal market, Marin buys olive oil. | `part-market` | ☐ |
| 2 | Au marché du canal, Margaux achète du fromage. | At the canal market, Margaux buys cheese. | `part-market` | ☐ |
| 3 | Au marché du canal, Marin achète du sucre. | At the canal market, Marin buys sugar. | `part-market` | ☐ |
| 4 | Je voudrais du fromage, s'il vous plaît. | I would like some cheese, please. | `part-want` | ☐ |
| 5 | Je mange de la salade, Gus. | I eat salad, Gus. | `part-verb~voc` | ☐ |

**FR2_A11_FAIRE_PRENDRE** — Faire and prendre · coach: Marin

| # | French | English cue | frame | ok? |
|---|---|---|---|---|
| 1 | Il fait une promenade le long du canal après le travail, Gus. | He is going for a walk along the canal after work, Gus. | `faire~voc` | ☐ |
| 2 | Elles font les courses au marché du canal après le travail. | They are doing the shopping at the canal market after work. | `faire` | ☐ |
| 3 | Vous prenez le train. | You take the train. | `prendre` | ☐ |
| 4 | Elles font les courses samedi, Romy. | They are doing the shopping on Saturday, Romy. | `faire~voc` | ☐ |
| 5 | Je prends mon vélo samedi, Gus. | I am taking my bike on Saturday, Gus. | `prendre-time~voc` | ☐ |

**FR2_A12_FUTUR_PROCHE** — Futur proche: aller + infinitive · coach: Marin

| # | French | English cue | frame | ok? |
|---|---|---|---|---|
| 1 | Ils vont travailler avec Gus la semaine prochaine, Romy. | They are going to work with Gus next week, Romy. | `near~voc` | ☐ |
| 2 | Elles vont déjeuner vers midi lundi prochain, Marin. | They are going to have lunch around noon next Monday, Marin. | `near~voc` | ☐ |
| 3 | Nous allons nous lever tôt ce week-end, Romy. | We are going to get up early this weekend, Romy. | `near~voc` | ☐ |
| 4 | Vous allez étudier à la bibliothèque ce soir. | You are going to study at the library tonight. | `near` | ☐ |
| 5 | Elles ne vont pas oublier les clés, Margaux. | They are not going to forget the keys, Margaux. | `near-neg~voc` | ☐ |

**FR2_A12_MODALS** — Pouvoir, vouloir, devoir + infinitive · coach: Gus

| # | French | English cue | frame | ok? |
|---|---|---|---|---|
| 1 | Nous pouvons appeler un taxi, Gus. | We can call a taxi, Gus. | `modal-person~voc` | ☐ |
| 2 | Nous voulons déjeuner avec Romy. | We want to have lunch with Romy. | `modal` | ☐ |
| 3 | Je dois chercher le carnet de Gus. | I have to look for Gus's notebook. | `modal` | ☐ |
| 4 | Elle peut goûter le gâteau, Romy. | She can taste the cake, Romy. | `modal-person~voc` | ☐ |
| 5 | Il veut visiter la ville, Lila. | He wants to visit the town, Lila. | `modal~voc` | ☐ |

**FR2_A12_PRONOMINAL** — Je m'appelle, je me lève: pronominal verbs · coach: Marin

| # | French | English cue | frame | ok? |
|---|---|---|---|---|
| 1 | Nous nous habillons vite, Marin. | We get dressed quickly, Marin. | `pron~voc` | ☐ |
| 2 | Vous vous habillez en noir. | You get dressed in black. | `pron` | ☐ |
| 3 | On se prépare pour l'examen, Romy. | We get ready for the exam, Romy. | `pron~voc` | ☐ |
| 4 | Ils se lèvent tard. | They get up late. | `pron` | ☐ |
| 5 | Elles se reposent chez Lila. | They rest at Lila's place. | `pron` | ☐ |

**FR2_A12_IMPERATIVE** — Imperative, and il faut + infinitive · coach: Lila

| # | French | English cue | frame | ok? |
|---|---|---|---|---|
| 1 | Il faut voyager avec Gus. | You have to travel with Gus. | `il-faut` | ☐ |
| 2 | Il faut choisir la table près de la fenêtre, Lila. | You have to choose the table by the window, Lila. | `il-faut~voc` | ☐ |
| 3 | Il faut étudier avec Lila, Margaux. | You have to study with Lila, Margaux. | `il-faut~voc` | ☐ |
| 4 | Viens à la brocante, Romy ! | Come to the flea market, Romy! | `imp-tu` | ☐ |
| 5 | Regardez les tableaux de Lila, s'il vous plaît. | Look at Lila's paintings, please. | `imp-vous` | ☐ |

**FR2_A12_DEMONSTRATIVES** — Ce, cet, cette, ces · coach: Lila

| # | French | English cue | frame | ok? |
|---|---|---|---|---|
| 1 | Tu connais cet hôpital, Lila ? | Do you know this hospital, Lila? | `dem-know~voc` | ☐ |
| 2 | Lila prend cette orange. | Lila takes this orange. | `dem-cast` | ☐ |
| 3 | Cette veste est chère, Lila. | This jacket is expensive, Lila. | `dem-is~voc` | ☐ |
| 4 | Ils prennent cet oignon, Marin. | They take this onion, Marin. | `dem-take~voc` | ☐ |
| 5 | Gus prend cette bague. | Gus takes this ring. | `dem-cast` | ☐ |

**FR2_A12_STRESSED_PRONOUNS** — Moi, toi, lui…: chez moi, avec lui · coach: Marin

| # | French | English cue | frame | ok? |
|---|---|---|---|---|
| 1 | Lila dîne chez moi ce soir. | Lila is having dinner at my place tonight. | `tonic-prep` | ☐ |
| 2 | Margaux dîne avec moi ce soir. | Margaux is having dinner with me tonight. | `tonic-prep` | ☐ |
| 3 | Lila est à côté de moi au Mistral. | Lila is next to me at Le Mistral. | `tonic-next` | ☐ |
| 4 | Lila dîne chez elle ce soir. | Lila is having dinner at her place tonight. | `tonic-prep` | ☐ |
| 5 | Cette plante est pour elles. | This plant is for them. | `tonic-for` | ☐ |

**FR2_A12_CEST_IL_EST** — C'est vs il/elle est · coach: Lila

| # | French | English cue | frame | ok? |
|---|---|---|---|---|
| 1 | Voici Margaux. C'est une patronne de café. | This is Margaux. She is a café owner. | `job-cest` | ☐ |
| 2 | C'est une clé, Romy. | It's a key, Romy. | `thing~voc` | ☐ |
| 3 | Lila, elle est tranquille. | Lila? She is quiet. | `adj` | ☐ |
| 4 | Marin, il est écologiste. | Marin? He is an environmentalist. | `job` | ☐ |
| 5 | C'est une clé. | It's a key. | `thing` | ☐ |

**FR2_A12_NUMBERS_BIG** — Numbers from 70: soixante-dix, quatre-vingts, cent, mille · coach: Margaux

| # | French | English cue | frame | ok? |
|---|---|---|---|---|
| 1 | Il y a quatre cent soixante-dix personnes à la brocante. | There are 470 people at the flea market. | `big-people` | ☐ |
| 2 | Marin a payé soixante-dix-sept euros pour le billet. | Marin paid 77 euros for the ticket. | `big-paid` | ☐ |
| 3 | Romy a payé huit cent soixante euros pour la bague. | Romy paid 860 euros for the ring. | `big-paid` | ☐ |
| 4 | Le billet coûte soixante-quinze euros, Romy. | The ticket costs 75 euros, Romy. | `big-costs~voc` | ☐ |
| 5 | Lila a payé cent vingt euros pour la guitare. | Lila paid 120 euros for the guitar. | `big-paid` | ☐ |

**FR2_A12_TIME** — Telling the time: il est trois heures · coach: Romy

| # | French | English cue | frame | ok? |
|---|---|---|---|---|
| 1 | Le spectacle commence à six heures moins dix. | The show starts at 5:50. | `time-starts` | ☐ |
| 2 | L'émission commence à onze heures. | The programme starts at 11:00. | `time-starts` | ☐ |
| 3 | Marin arrive au parc à deux heures moins le quart. | Marin arrives at the park at 1:45. | `time-arrive` | ☐ |
| 4 | Il est une heure moins dix. | It is 12:50. | `time-is` | ☐ |
| 5 | Gus arrive à la piscine à huit heures moins dix. | Gus arrives at the swimming pool at 7:50. | `time-arrive` | ☐ |

**FR2_A12_DAYS_DATES** — Days, months, dates: le lundi, le 3 mai · coach: Romy

| # | French | English cue | frame | ok? |
|---|---|---|---|---|
| 1 | L'anniversaire de Marin est le vingt-quatre mai. | Marin's birthday is on May 24. | `date-birthday` | ☐ |
| 2 | Le mardi, il dîne chez Lila, Romy. | On Tuesdays, he has dinner at Lila's place, Romy. | `weekday~voc` | ☐ |
| 3 | L'anniversaire de Lila est le huit mars. | Lila's birthday is on March 8. | `date-birthday` | ☐ |
| 4 | Marin et Lila partent en novembre. | Marin and Lila leave in November. | `month` | ☐ |
| 5 | L'anniversaire de Margaux est le vingt-cinq novembre. | Margaux's birthday is on November 25. | `date-birthday` | ☐ |

**FR2_A12_IR_RE_VERBS** — Present of -ir and -re verbs (finir, partir, attendre) · coach: Marin

| # | French | English cue | frame | ok? |
|---|---|---|---|---|
| 1 | Marin attend Gus au Mistral. | Marin waits for Gus at Le Mistral. | `irre-cast` | ☐ |
| 2 | Nous descendons vers le canal, Romy. | We go down towards the canal, Romy. | `irre~voc` | ☐ |
| 3 | Il vend un vieux vélo, Margaux. | He sells an old bike, Margaux. | `irre~voc` | ☐ |
| 4 | J'attends Romy devant le Mistral. | I wait for Romy outside Le Mistral. | `irre` | ☐ |
| 5 | Romy dort chez Lila. | Romy sleeps at Lila's place. | `irre-cast` | ☐ |

**FR2_A12_FREQUENCY** — Toujours, souvent, parfois: how often · coach: Romy

| # | French | English cue | frame | ok? |
|---|---|---|---|---|
| 1 | Vous restez au Mistral tous les jours. | You stay at Le Mistral every day. | `freq-phrase` | ☐ |
| 2 | Tu prends souvent une douche, Marin. | You often take a shower, Marin. | `freq-adv~voc` | ☐ |
| 3 | Je fais toujours les courses au marché du canal, Margaux. | I always do the shopping at the canal market, Margaux. | `freq-adv~voc` | ☐ |
| 4 | Elles portent souvent des lunettes, Marin. | They often wear glasses, Marin. | `freq-adv~voc` | ☐ |
| 5 | Ils voyagent en Italie toutes les semaines, Gus. | They travel in Italy every week, Gus. | `freq-phrase~voc` | ☐ |

**FR2_A12_PLACE_PREPOSITIONS** — Dans, sur, sous, devant, à côté de · coach: Marin

| # | French | English cue | frame | ok? |
|---|---|---|---|---|
| 1 | La bibliothèque est à côté de la brocante. | The library is next to the flea market. | `loc-is` | ☐ |
| 2 | Marin habite près de la poste. | Marin lives near the post office. | `loc-lives` | ☐ |
| 3 | Le bureau de l'ONG est loin du marché du canal. | The NGO office is far from the canal market. | `loc-is` | ☐ |
| 4 | Romy habite près de la librairie. | Romy lives near the bookshop. | `loc-lives` | ☐ |
| 5 | La brocante est à côté de l'aéroport, Gus. | The flea market is next to the airport, Gus. | `loc-is~voc` | ☐ |

**FR2_A12_QUANTITIES** — Un peu de, beaucoup de, un kilo de · coach: Margaux

| # | French | English cue | frame | ok? |
|---|---|---|---|---|
| 1 | Je voudrais une tasse de lait, s'il vous plaît. | I would like a cup of milk, please. | `qty-drink` | ☐ |
| 2 | Je voudrais un litre d'eau, s'il vous plaît. | I would like a litre of water, please. | `qty-drink` | ☐ |
| 3 | J'achète cinq cents grammes de riz, Margaux. | I buy five hundred grams of rice, Margaux. | `qty-weigh~voc` | ☐ |
| 4 | Il y a beaucoup de lits à la brocante. | There are a lot of beds at the flea market. | `qty-many` | ☐ |
| 5 | Il y a beaucoup de miroirs à l'hôtel. | There are a lot of mirrors at the hotel. | `qty-many` | ☐ |

**FR2_A12_CONNECTORS** — Et, mais, ou, parce que · coach: Romy

| # | French | English cue | frame | ok? |
|---|---|---|---|---|
| 1 | Nous nageons avec Romy parce que nous aimons ça, Margaux. | We swim with Romy because we like it, Margaux. | `because-like~voc` | ☐ |
| 2 | Nous dansons avec Lila parce que nous aimons ça, Romy. | We dance with Lila because we like it, Romy. | `because-like~voc` | ☐ |
| 3 | Je danse le samedi soir mais je suis malade, Gus. | I dance on Saturday nights but I am ill, Gus. | `but-state~voc` | ☐ |
| 4 | Je reste chez Lila parce que je suis malade. | I stay at Lila's place because I am ill. | `because-state` | ☐ |
| 5 | Je reste au lit parce que je suis fatiguée. | I stay in bed because I am tired. | `because-state` | ☐ |

**FR2_A12_PC_CHUNKS** — First past: j'ai mangé, j'ai fait, j'ai pris · coach: Gus

| # | French | English cue | frame | ok? |
|---|---|---|---|---|
| 1 | Avant-hier, elle a écrit un roman, Marin. | The day before yesterday, she wrote a novel, Marin. | `pc-chunk~voc` | ☐ |
| 2 | Samedi dernier, j'ai parlé doucement. | Last Saturday, I spoke softly. | `pc-chunk` | ☐ |
| 3 | Hier soir, tu as écouté un podcast, Lila. | Last night, you listened to a podcast, Lila. | `pc-chunk~voc` | ☐ |
| 4 | Avant-hier, nous avons bu du jus d'orange, Margaux. | The day before yesterday, we drank orange juice, Margaux. | `pc-chunk~voc` | ☐ |
| 5 | Hier soir, elle a mangé chez Lila. | Last night, she ate at Lila's place. | `pc-chunk` | ☐ |
