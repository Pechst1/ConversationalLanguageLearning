# La Forge: new units (G-FORGE, 2026-10-03)

This package belongs to the [content program](CONTENT-PROGRAM-2026-10-03.md). Only data files changed: the `units_a1/a2/b1.json` templates, additive lexicon pools, and `forge_coaches.json`.

## A1/A2 units that were missing (the catalogue review added them)

| Unit | Coach | Frames | Traps (from `main_traps`) |
|---|---|---|---|
| FR2_A11_NOUN_PLURALS | Margaux | buying, owning, «les … de X sont», «ses …», gifts, boats on the canal, buses | des journals, des gâteaus, des buss, a missing -s, festivaux (overgeneralised), le/la + plural |
| FR2_A11_ON_NOUS | Marin | «On va … demain ?», «Lila et moi, on …», «Nous, on …», «on est prêts» | on allons, on mangent, on sommes / on sont |
| FR2_A12_QUEL_EXCLAMATIF | Romy | event, then the exclamation that fits it (linked by tag); «Tu as … ? Quelle chance !»; plurals; «Que c'est beau !» (accepts «Comme c'est…») | Quel belle vue, Quelle une surprise, Quel beau !, Comment c'est beau |
| FR2_A12_ER_SPELLING | Marin | nous -geons; je/il/ils forms of acheter, appeler, jeter, envoyer, nettoyer, s'ennuyer, essuyer | nous mangons, j'appele, je jete, j'envoye, j'achette |
| FR2_A21_SAVOIR_CONNAITRE | Romy | connaître + person/place, savoir + clause (statement, question, negation), savoir + skill, «je ne sais pas nager : je n'ai jamais appris» | je sais Margaux, je connais où…, je ne peux pas nager |
| FR2_A22_SI_ON_SUGGESTION | Gus | «Et si on allait… ?», «Si on … ce soir ?», «Lila est libre ce soir : si on … avec elle ?», «Et si tu…» | si on irait, si on va, si on faisons |
| FR2_A12_IMPERATIVE (extended) | Lila | sois / soyez, n'aie pas peur, ayez, sache que, «Note de M. Marchand : veuillez …» | Es patient, N'as pas peur, Avez, sais, voulez |

The new lexicon pools are `pl_noun`, `pl_q`, `excl_event`, `excl_noun`, `excl_adj_event`, `excl_adj`, `er_spell`, `conn_obj`, `know_clause`, `skill`, `peur_of`, `imp_soyez`, `imp_ayez`, `imp_sache`, `notice` and `imp_veuillez`. They are additive: no existing entry changed. Every unit passes the acceptance bar: at least 200 distinct valid items per rung, its detector, the naturalness checker (less than 1 % rejected) and at least 87 % story-linked.

## B1 (`units_b1.json`)

`unit_templates()` loads every `grammar_templates/units_*.json`, so this file is **live without a code change**. B1 concepts mapped to these units now get bank items instead of the fallback:

- `FR2_B11_PLUS_QUE_PARFAIT` (v1 FR_B2_TENSE_001): «Hier soir, quand Lila est arrivée…, j'avais déjà…» (avoir and être), and «J'ai vu que j'avais oublié…». Traps: the passé composé, the imparfait, «avions arrivé».
- `FR2_B11_CONDITIONAL` (FR_B1_COND_003): unreal contexts («Dans un monde idéal, …»), «J'aimerais / nous aimerions + inf», «… mais je préférerais …». Traps: the futur («j'aimerai») and the imparfait.
- `FR2_B11_SI_TYPE2` (FR_B1_COND_002): conditions grouped with the verbs they make plausible (more time, money, a car, on holiday, free tonight), in both clause orders, with a pronoun or a cast subject. Traps: «si j'aurais», «si j'ai».
- `FR2_B11_TEMPORAL_FUTURE` (no v1 mapping): «Quand j'arriverai…, j'appellerai Lila», «Dès que…», «Appelle-moi quand tu arriveras…». Traps: the present and the conditionnel.

Coaches: Gus (the first three) and Marin (temporal future).

`FR2_B11_SI_TYPE1` is deliberately left out. `tests/test_wp_s2_item_bank.py::test_concepts_without_templates_keep_the_old_path` uses its v1 concept FR_B1_COND_001 as the example of a concept without templates. Adding it means pointing that test at another concept.

## Engine gaps (need `app/services` changes)

1. **Accents and cedillas cannot be traps.** `normalize()` folds diacritics, so «j'achete», «nous commencons», «nous achètons» and «il préfére» fold onto the answer and are dropped. ER_SPELLING therefore cannot drill the -cer verbs or the è/é accent, and uses «j'achette» as its only acheter trap. The fix is an accent-sensitive comparison for trap distinctness in `ItemBank.render`, kept separate from the grader's fold.
2. **No subjonctif.** `Morph.form` knows present, imparfait, futur and conditionnel. The six B12 subjunctive units need `Morph.subjonctif`, built from the 3p present stem + e/es/e/ions/iez/ent, with a `subj` table on irregular verbs, and `"subjonctif"` in `Morph.form`. With that change, «Il faut que {S} [[{S|v:V:subjonctif} // {S|v:V}]]» works.
3. **No plus-que-parfait or English pluperfect tense.** Both are composed in the templates (`{S|sv:avoir:imparfait} {V|pp}`, «had {..:past_participle}»). A `pqp` tense in `Filters.conj`/`neg` would let negation frames work («je n'avais jamais vu»).
4. **Verbs cannot be linked to a condition.** `verb@X` does not filter, because verbs have no `kinds`. SI_TYPE2 uses one frame per condition group instead.
5. **Double pronouns, dont, ce qui/ce que** are expressible only through hand-listed pools; no filter builds them. They were left for a later pass.
6. The naturalness checker reads «en train demain» as «en train de» (a "now" mark), so it rejects «On voyage en train demain ?». The rejection is rare.
