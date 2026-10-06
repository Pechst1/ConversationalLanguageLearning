# Grammar due diligence — 2026-09-23

Owner question: are the right grammar concepts taught at the right stage, is the collection good
enough, and are they explained well, in a way that looks great?

Short answer: **the sequence is roughly sensible but too thin and partly misplaced, and the
explanations are not good yet.** They are English-only, jargon-heavy, and shown as a block of
text with a typed formula.

This review feeds WP-L2 (syllabus) and a new WP-L10 (the rule card) in
`WORK-PACKAGES-2026-09-23-learning.md`.

References for level placement:
- the Council of Europe's reference level descriptions for French: Beacco et al., *Niveau A1 pour
  le français* and *Niveau A2 pour le français*, and the B1/B2 volumes;
- the DELF A1–B2 syllabi;
- the progression of common course books (Alter Ego+, Édito, Cosmopolite).

Placement varies by ±1 sub-band between these sources. The findings below only flag moves that
all of them agree on.

## 1. What is live

- `templates/french_core_grammar_v1.tsv`, seeded by `FrenchCoreGrammarCatalog.ensure_catalog`,
  has 54 active concepts: A1 12, A2 12, B1 12, B2 12, C1 6.
- 314 older rows (German names, finer-grained) are archived as inactive.
- Each concept has:
  - `core_rule`, `when_to_use`, `pattern`, `contrast_rules`, `main_traps`, `anchor_examples`,
    all **in English only**;
  - an x-ray sentence and marks, which are never shown to the learner;
  - one authored challenge in `app/data/seance_challenges.txt`.
- `grammar_concept_localizations` has `de` and `fr` titles, but their `short_description` is the
  same English sentence.

## 2. Is the collection right?

### 2.1 Granularity: too coarse at A1–A2

Twelve concepts per level is about a third of what a learner needs to be taught one by one. Some
single rows are several lessons each:

| Concept today | What it really is |
| --- | --- |
| «Present tense core verbs» (A1) | -er verbs · être · avoir · aller/faire/prendre/venir · pouvoir/vouloir/devoir + infinitive · -ir/-re verbs |
| «Basic questions» (A1) | intonation · est-ce que · question words (où, quand, combien, comment, qu'est-ce que) · inversion with vous |
| «Direct and indirect object pronouns» (A2) | le/la/les · lui/leur · position with an infinitive and in the passé composé |
| «Y and en basics» (A2) | y for places · en for quantities |

### 2.2 Missing concepts every A1/A2 syllabus has

**A1 (none of these are active; most exist among the 314 archived rows):**
- être and avoir as their own units (j'ai 20 ans, il y a);
- **c'est vs il/elle est**;
- **prepositions with places**: à Paris, en France, au Japon, and the contractions au/du;
- **question words**;
- **numbers, prices, time, dates**: a café story needs «deux euros cinquante» on day 2;
- **modal verbs + infinitive** (je peux, je veux, je dois);
- **pronominal verbs in the present** (je m'appelle, je me lève);
- **the imperative**, plus il faut + infinitive;
- **stressed pronouns** (moi, toi, chez moi, avec lui);
- **je voudrais / tu/vous** as a polite formula: the app's first scene asks for it, but it is
  catalogued as a B1 concept («Conditional present»);
- quantities: un peu de, beaucoup de, un kilo de.

**A2:**
- negative words: ne…plus, ne…jamais, ne…rien, ne…personne;
- passé récent (venir de) and être en train de;
- the futur simple, which is catalogued at B1 (see below);
- adverbs in -ment;
- tout / tous / toute;
- cause and consequence: parce que, car, donc, alors;
- demonstrative pronouns (celui, celle).

**B1:**
- the plus-que-parfait (catalogued at B2);
- the passive, as an introduction (catalogued at B2);
- ne…que;
- indirect questions: the only row is «Reported speech intro»;
- possessive pronouns (le mien);
- lequel / auquel;
- expressing opinion: je pense que + indicative vs je ne pense pas que + subjunctive.

### 2.3 Misplaced concepts

| Concept | Now | Should be | Why |
| --- | --- | --- | --- |
| De/d' after negation («pas de café») | A2 | **A1** | It comes with basic negation and the partitive; the café scene needs it on day 1. |
| Conditional present | B1 | **A1 (formula) → A2 (politeness, wishes)**; B1 keeps the hypothesis (si type 2) | «Je voudrais un café» is A1 in every syllabus; its own challenge line is exactly that. |
| Future simple | B1 | **A2** | Beacco A2, DELF A2 and most course books. |
| Plus-que-parfait | B2 | **B1** | B1 narration, together with the imparfait/passé composé contrast. |
| Passive voice | B2 | **B1 (intro)**, B2 (nuance) | |
| Partitive (order 40) | before present-tense verbs (80) | after être/avoir and -er verbs | You cannot use «du pain» until you can say «je prends / je voudrais». |
| Imparfait vs passé composé | twice (A2 «intro» + B1) | **one concept, two stages** | A duplicate row double-counts it toward promotion. |
| Past participle agreement «basics» | B1 | agreement with être at **A2** (part of PC + être); B1 keeps preceding direct objects with avoir | |

### 2.4 Teaching order inside A1 is not how a learner needs it

Today's A1 order: gender → le/la → un/une → partitive → possessives → demonstratives → subject
pronouns → present verbs → negation → questions → adjectives → futur proche. That is **seven
noun-phrase concepts before the learner has a verb.**

The story needs sentences from day 1. A communicative order (proposed for WP-L2):

**A1.1, «survive at the café» (≈ 15 units)**
1. je / tu / vous + être
2. avoir, il y a
3. un / une, le / la / l' / les (gender as shape, WP-D6)
4. plural
5. -er verbs
6. ne…pas and pas de
7. questions and question words
8. je voudrais / vous voulez (chunk)
9. numbers, prices, time
10. adjectives: agreement and position
11. à / en / au with places, and au / du
12. mon / ma / mes
13. aller and venir (with places)
14. du / de la / de l' and quantities
15. faire and prendre

**A1.2 (≈ 12–15 units)**
- futur proche
- pouvoir / vouloir / devoir + infinitive
- pronominal verbs
- imperative and il faut + infinitive
- ce / cet / cette / ces
- stressed pronouns
- c'est vs il est
- dates and days
- frequency adverbs
- -ir / -re verbs
- place prepositions
- passé composé with avoir, as chunks of frequent verbs (course books introduce it at the end
  of A1)

A2 and B1 follow §2.2–2.3.

### 2.5 Foundation flags and prerequisites

- `is_foundation` is simply "A1 or A2", so it does no work. It should mark units that others
  depend on.
- There are no prerequisites, so the picker can serve «Object pronoun order» before «Direct
  and indirect object pronouns» whenever the band lets it.
- WP-L2 adds `prerequisites` and `contrast_partners` per unit.

## 3. Are they explained well?

What the learner sees (verified on screen, «Plus de pratique» → «La règle», A1 learner, English
native language):

> *French nouns carry gender and number; determiners and many adjectives must match the noun
> they belong to.* (Garamond italic headline)
> **Quand :** Use this whenever a noun phrase contains an article, adjective, or pronoun that
> must agree with the noun.
> **Le schéma :** masculine/feminine + singular/plural noun -> matching determiner/adjective
> **Le contrôle :** Avoid: guessing gender from English
> *Une petite table blanche est dans la cuisine. / un livre blanc / une table blanche*

### Problems

1. **Language.**
   - French labels («Quand», «Le schéma», «Le contrôle») with English content, plus an
     «Avoid:» prefix inside a French label.
   - The German and French «translations» are English.
   - An A1 learner with German as their native language gets English.
2. **Jargon at A1**: «determiners», «noun phrase», «mass noun», «past participle», «bounded
   event». The rule is written for teachers.
3. **The rule is the headline.**
   - The biggest text on the card is the abstract sentence. The French example, which is what
     a learner remembers, is the small blue line.
   - There are two Garamond headlines on one screen (rule and prompt), which breaks the design
     rule.
4. **The pattern is typed, not shown.**
   - `masculine/feminine + singular/plural noun -> matching determiner/adjective` is an ASCII
     formula.
   - The design language already has the right tools, none of them used here:
     - gender by shape (WP-D6);
     - the x-ray marks (authored but never rendered);
     - highlighted endings.
5. **No forms.**
   - «Present tense core verbs» has no conjugation table.
   - «Passé composé with avoir» doesn't list avoir's forms.
   - «Future simple» doesn't list its irregular stems.
6. **Examples have no gloss and no audio, and they are not from the learner's story.**
   - The anchor examples are generic («Elle a vendu sa voiture»), not from today's scene with
     Margaux.
7. **Only one trap is shown, and not as a contrast.**
   - A trap works best as a pair: ✗ «je suis 20 ans» → ✓ «j'ai 20 ans».
   - `main_traps` holds only descriptions («forgetting plural marks»), not the wrong and right
     sentences.
8. **Some content is off.** For example, «Conditional present» (B1) is explained with
   «Je voudrais un café», and the A1 learner meets it on day 1 of the story without a rule.

### What good looks like: WP-L10, the rule card v2

The card follows the design language: av2 tokens, one Garamond line, shapes do the work.
- **The headline is a French example**, taken from today's scene when there is one, with the
  key part marked through the x-ray marks and the WP-D6 gender shapes. Tapping it plays audio
  and shows the translation.
- **The rule is one sentence of at most 20 words in the learner's language**, with no jargon at
  A1 and A2. A French term is introduced once, with a gloss («le participe — the -é form»).
  B1 and above may use terms.
- **The pattern is drawn, not typed.** It is built from tokens: noun and agreeing words linked
  by the same shape; a verb with its ending in red; or a mini conjugation table (6 rows, the
  changing part highlighted) for any verb or tense concept.
- **One contrast pair**: ✗ wrong sentence → ✓ right sentence, with a single highlighted
  difference.
- **«Pourquoi ?»** discloses the longer explanation (when to use it, contrasts), then «Cahier ↗».
- Labels in the learner's language, sentence case; no «Avoid:».
- **Content model change** (with WP-L2): per unit and locale (`en`, `de`, `fr`):
  - `rule_short`;
  - `rule_more`;
  - `glossary[]`;
  - `contrast_pair{wrong_fr, right_fr, mark}`;
  - `forms` (a table spec, or none);
  - `pattern_tokens[]`.
  
  The TSV grows these columns; the LLM drafts, a human reviews.
- **Done when:**
  - every A1–A2 unit has a v2 card in en and de;
  - screenshots in both themes at 320 px show one Garamond line, no text wall, and a card
    readable in under 30 seconds;
  - the card is used by the journey's Règle moment (WP-L4) and «Plus de pratique».
