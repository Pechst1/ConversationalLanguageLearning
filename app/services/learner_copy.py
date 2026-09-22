"""Deterministic learner-facing sentences, in the three languages we ship.

The design contract splits the app's words in two (docs/design-overhaul-2026-08-31.md
§Principles): the *fiction* and the publication chrome are French — "Le Courrier",
"La séance du jour", "Reprenez cette faute de grammaire" — while everything that
*explains* something to the learner follows their `native_language`. A German
beginner must be able to read why a form was wrong without first learning the
French for "agreement".

Until WP-21 the deterministic corrector broke the second half of that rule. The
rule-based detector, the error-memory labels, the brief-exercise fallbacks and the
authored erratum prose in the Courrier were English-only literals (with two
stragglers that were hardcoded *German*, which is worse: an English-speaking
learner got a German verdict). None of them go through a provider, so no prompt
change can fix them — they need a table.

This module is that table. It is deliberately dumb:

* keys are stable identifiers, never English sentences, so a grep for English in
  learner-facing code stays meaningful;
* every key carries all three languages — a missing entry is a test failure, not
  a silent English fallback;
* `{placeholders}` are filled by `str.format`, and a bad placeholder returns the
  unformatted sentence rather than raising inside a correction path.

Nothing here invents French content. The French column is the *chrome* voice the
design already uses; the English and German columns say the same thing in the
learner's own language.
"""
from __future__ import annotations

from typing import Any

from app.services.glosses import DEFAULT_GLOSS_LANGUAGE, normalize_language

#: The languages the copy table is complete in. Anything else falls back to `en`.
SUPPORTED_COPY_LANGUAGES: tuple[str, ...] = ("en", "de", "fr")

# ---------------------------------------------------------------------------
# The table. Grouped by the surface that authors the string, because that is how
# a reviewer checks it: open the surface, read the row.
# ---------------------------------------------------------------------------

LEARNER_COPY: dict[str, dict[str, str]] = {
    # -- app/core/error_detection/rules.py: the rule-based detector -----------
    "detect.article_feminine_with_masculine": {
        "en": "A feminine article looks wrong in front of this masculine noun.",
        "de": "Vor diesem maskulinen Substantiv wirkt der feminine Artikel falsch.",
        "fr": "L’article féminin semble incorrect devant ce nom masculin.",
    },
    "detect.article_masculine_with_feminine": {
        "en": "A masculine article looks wrong in front of this feminine noun.",
        "de": "Vor diesem femininen Substantiv wirkt der maskuline Artikel falsch.",
        "fr": "L’article masculin semble incorrect devant ce nom féminin.",
    },
    "detect.verb_infinitive_after_pronoun": {
        "en": "After a subject pronoun the verb is conjugated, not left in the infinitive.",
        "de": "Nach einem Subjektpronomen wird das Verb konjugiert, nicht im Infinitiv gelassen.",
        "fr": "Après un pronom sujet, le verbe se conjugue ; il ne reste pas à l’infinitif.",
    },
    "detect.verb_ending_mismatch": {
        "en": "This verb ending does not match the subject pronoun.",
        "de": "Diese Verbendung passt nicht zum Subjektpronomen.",
        "fr": "Cette terminaison de verbe ne correspond pas au pronom sujet.",
    },
    "detect.false_friend_actuellement": {
        "en": "“Actuellement” means “currently”, not “actually”.",
        "de": "„Actuellement“ heißt „zurzeit“, nicht „eigentlich“.",
        "fr": "« Actuellement » veut dire « en ce moment », pas « en fait ».",
    },
    "detect.false_friend_librairie": {
        "en": "“Librairie” is a bookshop; a library is “bibliothèque”.",
        "de": "„Librairie“ ist eine Buchhandlung; eine Bibliothek heißt „bibliothèque“.",
        "fr": "« Librairie » désigne le commerce ; la bibliothèque se dit « bibliothèque ».",
    },
    "detect.false_friend_sensible": {
        "en": "“Sensible” means “sensitive”; for “sensible” use “raisonnable”.",
        "de": "„Sensible“ heißt „empfindsam“; für „vernünftig“ nimm „raisonnable“.",
        "fr": "« Sensible » veut dire « émotif » ; pour « raisonnable », dites « raisonnable ».",
    },
    "detect.false_friend_deception": {
        "en": "“Déception” means “disappointment”; deception is “tromperie”.",
        "de": "„Déception“ heißt „Enttäuschung“; Täuschung ist „tromperie“.",
        "fr": "« Déception » veut dire « désillusion » ; la tromperie se dit « tromperie ».",
    },
    "detect.false_friend_suggestion": {
        "en": "Check what this word actually means before using it again.",
        "de": "Prüfe die tatsächliche Bedeutung dieses Wortes, bevor du es wieder benutzt.",
        "fr": "Révisez l’usage correct de ce mot avant de le réutiliser.",
    },
    "detect.summary_heuristic_only": {
        "en": "Automated check only — no teacher review on this answer.",
        "de": "Nur automatische Prüfung — keine Lehrer-Durchsicht für diese Antwort.",
        "fr": "Relecture automatique seulement — pas de correction détaillée ici.",
    },
    "detect.summary_default": {
        "en": "Nothing else to repair in this answer.",
        "de": "In dieser Antwort gibt es nichts weiter zu korrigieren.",
        "fr": "Rien d’autre à reprendre dans cette réponse.",
    },
    # -- app/services/error_memory.py: the durable erratum ledger -------------
    "erratum.form_needs_review": {
        "en": "This form needs another look.",
        "de": "Diese Form musst du dir noch einmal ansehen.",
        "fr": "Cette forme est à revoir.",
    },
    "erratum.label_pronoun_choice": {
        "en": "Pronoun choice",
        "de": "Pronomenwahl",
        "fr": "Choix du pronom",
    },
    "erratum.label_vocabulary_choice": {
        "en": "Vocabulary choice",
        "de": "Wortwahl",
        "fr": "Choix du mot",
    },
    "erratum.label_spelling": {
        "en": "Spelling",
        "de": "Rechtschreibung",
        "fr": "Orthographe",
    },
    "erratum.label_language_repair": {
        "en": "Language repair",
        "de": "Sprachliche Korrektur",
        "fr": "Reprise de langue",
    },
    # -- app/services/atelier.py: the recognize round's immediate feedback (WP-56).
    # The background relecture rewrites these in the learner's language a moment
    # later; until it lands, the deterministic line must already be readable.
    "atelier.recognize.chose_requires": {
        "en": "You chose “{learner}”; this item needs “{target}”.",
        "de": "Du hast „{learner}“ gewählt; hier ist „{target}“ nötig.",
        "fr": "Vous avez choisi « {learner} » ; il faut « {target} » ici.",
    },
    "atelier.recognize.blank_needs": {
        "en": "You chose “{learner}”, but this blank needs “{target}”.",
        "de": "Du hast „{learner}“ gewählt, aber in diese Lücke gehört „{target}“.",
        "fr": "Vous avez choisi « {learner} », mais ce blanc demande « {target} ».",
    },
    "atelier.recognize.classified_as": {
        "en": "You classified “{prompt}” as “{learner}”, but the target label is “{target}”.",
        "de": "Du hast „{prompt}“ als „{learner}“ eingeordnet; richtig wäre „{target}“.",
        "fr": "Vous avez classé « {prompt} » comme « {learner} » ; l’étiquette attendue est « {target} ».",
    },
    "atelier.recognize.word_bank_mismatch": {
        "en": "The sentence you built does not match the target sentence.",
        "de": "Der Satz, den du gebaut hast, stimmt nicht mit dem Zielsatz überein.",
        "fr": "La phrase construite ne correspond pas à la phrase attendue.",
    },
    "atelier.recognize.word_bank_rebuild": {
        "en": "Rebuild the sentence as: {target}",
        "de": "Baue den Satz so: {target}",
        "fr": "Reconstruisez la phrase ainsi : {target}",
    },
    "atelier.recognize.rule_reference": {
        "en": "Rule: {title}.",
        "de": "Regel: {title}.",
        "fr": "Règle : {title}.",
    },
    "atelier.recognize.missing_label": {
        "en": "Missing answer",
        "de": "Fehlende Antwort",
        "fr": "Réponse manquante",
    },
    "atelier.recognize.missing_why": {
        "en": "You left this item blank, so there is no grammar choice to review.",
        "de": "Du hast dieses Element leer gelassen, also gibt es keine Grammatikwahl zu prüfen.",
        "fr": "Vous avez laissé cet élément vide : il n’y a aucun choix grammatical à revoir.",
    },
    "atelier.recognize.missing_repair": {
        "en": "Answer the item first; a blank item is not filed as an erratum.",
        "de": "Beantworte das Element zuerst; ein leeres Element wird nicht als Erratum abgelegt.",
        "fr": "Répondez d’abord ; un élément vide n’est pas consigné comme erratum.",
    },
    "atelier.recognize.label_classification": {
        "en": "Classification",
        "de": "Einordnung",
        "fr": "Classement",
    },
    "atelier.recognize.label_word_bank": {
        "en": "Word bank",
        "de": "Wortbank",
        "fr": "Banque de mots",
    },
    # -- app/services/atelier.py: the profile-specific erratum prose (WP-67) ---
    # WP-56 put the *generic* recognize feedback in the learner's language and
    # left the three hand-written grammar families — si type 1, the article
    # after negation, imparfait vs passé composé — as English literals, which is
    # the worst of both: the learner who most needs an explanation (they just
    # got the item wrong) is the one who cannot read it. Same rule as above: the
    # French column is the publication's own voice, `{placeholders}` are the
    # learner's own words and the expected form, and every backtick span is a
    # French form quoted verbatim in all three columns.
    "atelier.si.label_target_form": {
        "en": "Target form needed",
        "de": "Verlangte Form",
        "fr": "Forme attendue",
    },
    "atelier.si.label_imperative_result": {
        "en": "Imperative result",
        "de": "Imperativ als Folge",
        "fr": "Résultat à l’impératif",
    },
    "atelier.si.label_form_classification": {
        "en": "Form classification",
        "de": "Formbestimmung",
        "fr": "Identification de la forme",
    },
    "atelier.si.label_conditional_vs_future": {
        "en": "Conditional vs future",
        "de": "Conditionnel statt Futur",
        "fr": "Conditionnel ou futur",
    },
    "atelier.si.label_future_after_si": {
        "en": "Future placed after si",
        "de": "Futur nach « si »",
        "fr": "Futur placé après « si »",
    },
    "atelier.si.label_future_result": {
        "en": "Future result",
        "de": "Futur als Folge",
        "fr": "Résultat au futur",
    },
    "atelier.si.fill_present_in_result": {
        "en": "You used present `appelle` in the result clause. In si type 1, the si-clause stays present and the consequence takes future simple, so the blank needs `appellerai`.",
        "de": "Du hast im Folgesatz das Präsens `appelle` benutzt. Beim si-Typ 1 bleibt der si-Satz im Präsens und die Folge steht im Futur simple: hier gehört `appellerai` in die Lücke.",
        "fr": "Vous avez mis le présent `appelle` dans la principale. Au si de type 1, la subordonnée reste au présent et la conséquence passe au futur simple : ce blanc demande `appellerai`.",
    },
    "atelier.si.fill_conditional_in_result": {
        "en": "You used conditional `appellerais`, which belongs to a hypothetical si frame. This sentence is a real future condition, so the result needs future simple `appellerai`.",
        "de": "Du hast das Conditionnel `appellerais` benutzt, das zum hypothetischen si-Satz gehört. Hier steht eine reale Bedingung in der Zukunft, also braucht die Folge das Futur simple `appellerai`.",
        "fr": "Vous avez employé le conditionnel `appellerais`, qui appartient à l’hypothèse. Ici la condition est réelle et future : la conséquence demande le futur simple `appellerai`.",
    },
    "atelier.si.fill_past_in_result": {
        "en": "You used past tense `ai appelé`, but the sentence says what will happen if the condition is met. The result needs future simple `appellerai`.",
        "de": "Du hast die Vergangenheit `ai appelé` benutzt, aber der Satz sagt, was geschehen *wird*, wenn die Bedingung eintritt. Die Folge braucht das Futur simple `appellerai`.",
        "fr": "Vous avez employé le passé `ai appelé`, alors que la phrase dit ce qui arrivera si la condition se réalise. La conséquence demande le futur simple `appellerai`.",
    },
    "atelier.si.fill_result_needs_future": {
        "en": "This si-clause is in the present, so the result clause needs future simple here.",
        "de": "Dieser si-Satz steht im Präsens, also braucht der Folgesatz hier das Futur simple.",
        "fr": "Cette subordonnée en « si » est au présent : la principale demande donc le futur simple.",
    },
    "atelier.si.repair_present_then_future": {
        "en": "Keep the verb after si in the present, then put the consequence in future simple.",
        "de": "Lass das Verb nach « si » im Präsens und setze die Folge ins Futur simple.",
        "fr": "Gardez le verbe après « si » au présent, puis mettez la conséquence au futur simple.",
    },
    "atelier.si.fill_imperative_expected": {
        "en": "Future `prendras` can be grammatical in si type 1, but this blank is a direct instruction: `take your coat`. The expected result is imperative `prends`.",
        "de": "Das Futur `prendras` ist beim si-Typ 1 grammatisch möglich, aber diese Lücke ist eine direkte Aufforderung: „nimm deinen Mantel“. Erwartet wird der Imperativ `prends`.",
        "fr": "Le futur `prendras` est possible au si de type 1, mais ce blanc est une consigne directe : « prends ton manteau ». La forme attendue est l’impératif `prends`.",
    },
    "atelier.si.fill_imperative_generic": {
        "en": "You chose `{learner}`, but the result clause is a command, so it needs the imperative `prends`.",
        "de": "Du hast `{learner}` gewählt, aber der Folgesatz ist eine Aufforderung und braucht den Imperativ `prends`.",
        "fr": "Vous avez choisi `{learner}`, mais la principale est un ordre : il faut l’impératif `prends`.",
    },
    "atelier.si.repair_imperative_result": {
        "en": "When the result tells someone what to do, use the imperative after the si-clause.",
        "de": "Wenn die Folge jemandem sagt, was zu tun ist, steht nach dem si-Satz der Imperativ.",
        "fr": "Quand la conséquence dit quoi faire, employez l’impératif après la subordonnée en « si ».",
    },
    "atelier.si.fill_irons_present": {
        "en": "You used present `allons` in the result clause. With a present si-clause, the consequence should be future simple: `irons`.",
        "de": "Du hast im Folgesatz das Präsens `allons` benutzt. Mit einem si-Satz im Präsens gehört die Folge ins Futur simple: `irons`.",
        "fr": "Vous avez mis le présent `allons` dans la principale. Avec un « si » au présent, la conséquence passe au futur simple : `irons`.",
    },
    "atelier.si.fill_irons_conditional": {
        "en": "You used conditional `irions`, but this is a real future condition, not a hypothetical one. Use future simple `irons`.",
        "de": "Du hast das Conditionnel `irions` benutzt, aber das ist eine reale, keine hypothetische Bedingung. Nimm das Futur simple `irons`.",
        "fr": "Vous avez employé le conditionnel `irions`, mais la condition est réelle, pas hypothétique. Employez le futur simple `irons`.",
    },
    "atelier.si.fill_irons_generic": {
        "en": "The condition is present, so the consequence needs future simple `irons`.",
        "de": "Die Bedingung steht im Präsens, also braucht die Folge das Futur simple `irons`.",
        "fr": "La condition est au présent : la conséquence demande le futur simple `irons`.",
    },
    "atelier.si.repair_present_then_future_short": {
        "en": "Use present after si, then future simple for the consequence.",
        "de": "Nach « si » das Präsens, für die Folge das Futur simple.",
        "fr": "Présent après « si », puis futur simple pour la conséquence.",
    },
    "atelier.si.classify_present": {
        "en": "You classified `{prompt}` as `{learner}`, but `{prompt}` is present tense in the si-clause.",
        "de": "Du hast `{prompt}` als `{learner}` eingeordnet, aber `{prompt}` steht im Präsens im si-Satz.",
        "fr": "Vous avez classé `{prompt}` comme `{learner}`, mais `{prompt}` est au présent dans la subordonnée en « si ».",
    },
    "atelier.si.classify_imperative": {
        "en": "You classified `{prompt}` as `{learner}`, but here `{prompt}` is an imperative command form, which can serve as the result in si type 1.",
        "de": "Du hast `{prompt}` als `{learner}` eingeordnet, aber `{prompt}` ist hier ein Imperativ, der beim si-Typ 1 als Folge stehen kann.",
        "fr": "Vous avez classé `{prompt}` comme `{learner}`, mais `{prompt}` est ici un impératif, qui peut servir de résultat au si de type 1.",
    },
    "atelier.si.classify_future": {
        "en": "You classified `{prompt}` as `{learner}`, but `{prompt}` is future simple; the `-rai` ending marks the future result.",
        "de": "Du hast `{prompt}` als `{learner}` eingeordnet, aber `{prompt}` steht im Futur simple; die Endung `-rai` markiert die Folge in der Zukunft.",
        "fr": "Vous avez classé `{prompt}` comme `{learner}`, mais `{prompt}` est au futur simple ; la terminaison `-rai` marque le résultat futur.",
    },
    "atelier.si.repair_name_the_form": {
        "en": "Name the verb form before reading the whole sentence frame.",
        "de": "Bestimme zuerst die Verbform, dann lies den ganzen Satzrahmen.",
        "fr": "Nommez la forme du verbe avant de lire tout le cadre de la phrase.",
    },
    "atelier.si.word_bank_conditional_why": {
        "en": "You built the right si-frame, but the result verb is `répondrais`, which is conditional. In a real condition with si + present, the consequence uses future simple: `répondrai`.",
        "de": "Der si-Rahmen stimmt, aber das Verb der Folge ist `répondrais`, also Conditionnel. Bei einer realen Bedingung mit si + Präsens steht die Folge im Futur simple: `répondrai`.",
        "fr": "Le cadre en « si » est juste, mais le verbe de la principale est `répondrais`, au conditionnel. Dans une condition réelle avec si + présent, la conséquence prend le futur simple : `répondrai`.",
    },
    "atelier.si.word_bank_conditional_repair": {
        "en": "Keep `Si elle appelle` in the present, then change only the result verb to future simple: `je répondrai`.",
        "de": "Lass `Si elle appelle` im Präsens und setze nur das Verb der Folge ins Futur simple: `je répondrai`.",
        "fr": "Gardez `Si elle appelle` au présent, puis changez seulement le verbe de la principale : `je répondrai`.",
    },
    "atelier.si.word_bank_future_after_si_why": {
        "en": "You put future `arriverons` inside the si-clause and present `partons` in the result. In si type 1, the condition stays present: `Si nous partons maintenant`; the consequence carries the future: `nous arriverons tôt`.",
        "de": "Du hast das Futur `arriverons` in den si-Satz gesetzt und das Präsens `partons` in die Folge. Beim si-Typ 1 bleibt die Bedingung im Präsens: `Si nous partons maintenant`; die Folge trägt das Futur: `nous arriverons tôt`.",
        "fr": "Vous avez mis le futur `arriverons` dans la subordonnée et le présent `partons` dans la principale. Au si de type 1, la condition reste au présent : `Si nous partons maintenant` ; la conséquence porte le futur : `nous arriverons tôt`.",
    },
    "atelier.si.word_bank_future_after_si_repair": {
        "en": "Put the present action after `si`, then put the future action after the comma: `Si nous partons maintenant, nous arriverons tôt`.",
        "de": "Setze die Handlung im Präsens hinter `si` und die Handlung im Futur hinter das Komma: `Si nous partons maintenant, nous arriverons tôt`.",
        "fr": "Mettez l’action au présent après `si`, puis l’action au futur après la virgule : `Si nous partons maintenant, nous arriverons tôt`.",
    },
    "atelier.si.word_bank_future_result_why": {
        "en": "The result clause uses `{learner_form}`, but si type 1 needs future simple `{target_form}` here.",
        "de": "Die Folge benutzt `{learner_form}`, aber der si-Typ 1 braucht hier das Futur simple `{target_form}`.",
        "fr": "La principale emploie `{learner_form}`, alors que le si de type 1 demande ici le futur simple `{target_form}`.",
    },
    "atelier.si.word_bank_result_missing_why": {
        "en": "The si-clause is present, but the result clause does not carry the future or imperative form that this pattern needs.",
        "de": "Der si-Satz steht im Präsens, aber die Folge trägt weder das Futur noch den Imperativ, den dieses Muster verlangt.",
        "fr": "La subordonnée en « si » est au présent, mais la principale ne porte ni le futur ni l’impératif que ce schéma demande.",
    },
    "atelier.si.word_bank_result_missing_repair": {
        "en": "Use present after `si`, then put the consequence in future simple or imperative.",
        "de": "Nach `si` das Präsens, dann die Folge im Futur simple oder im Imperativ.",
        "fr": "Présent après `si`, puis la conséquence au futur simple ou à l’impératif.",
    },
    "atelier.negation.label_article": {
        "en": "Article after negation",
        "de": "Artikel nach der Verneinung",
        "fr": "Article après la négation",
    },
    "atelier.negation.label_pattern": {
        "en": "Negation pattern",
        "de": "Verneinungsmuster",
        "fr": "Schéma de négation",
    },
    "atelier.negation.fill_kept_article": {
        "en": "You kept `{learner}` after `pas`. For a negated quantity, du/de la/des/un/une become `de` or `d'` after `pas`, so this blank needs `{target}`.",
        "de": "Du hast `{learner}` nach `pas` stehen lassen. Bei einer verneinten Menge werden du/de la/des/un/une nach `pas` zu `de` oder `d'`: hier gehört `{target}` in die Lücke.",
        "fr": "Vous avez gardé `{learner}` après `pas`. Devant une quantité niée, du/de la/des/un/une deviennent `de` ou `d'` après `pas` : ce blanc demande `{target}`.",
    },
    "atelier.negation.fill_generic": {
        "en": "After `pas`, a negated quantity uses `de` or `d'` before the noun.",
        "de": "Nach `pas` steht bei einer verneinten Menge `de` oder `d'` vor dem Substantiv.",
        "fr": "Après `pas`, une quantité niée prend `de` ou `d'` devant le nom.",
    },
    "atelier.negation.repair_check_quantity": {
        "en": "Check whether the original article expresses quantity; after ne...pas, change it to de/d' unless the verb is être.",
        "de": "Prüfe, ob der ursprüngliche Artikel eine Menge ausdrückt; nach ne…pas wird er zu de/d', außer das Verb ist être.",
        "fr": "Vérifiez si l’article de départ exprime une quantité ; après ne…pas, il devient de/d', sauf avec le verbe être.",
    },
    "atelier.negation.classify_etre_exception": {
        "en": "You classified this as `{learner}`, but with `être`, the original article stays: `ce n'est pas du café`.",
        "de": "Du hast das als `{learner}` eingeordnet, aber mit `être` bleibt der ursprüngliche Artikel stehen: `ce n'est pas du café`.",
        "fr": "Vous avez classé cela comme `{learner}`, mais avec `être` l’article d’origine reste : `ce n'est pas du café`.",
    },
    "atelier.negation.classify_normal": {
        "en": "You classified this as `{learner}`, but this is a normal negated quantity where the article changes to de/d'.",
        "de": "Du hast das als `{learner}` eingeordnet, aber hier steht eine gewöhnliche verneinte Menge, bei der der Artikel zu de/d' wird.",
        "fr": "Vous avez classé cela comme `{learner}`, mais c’est une quantité niée ordinaire, où l’article devient de/d'.",
    },
    "atelier.negation.repair_check_etre": {
        "en": "First check whether the verb is être; if it is not, a negated quantity changes to de/d'.",
        "de": "Prüfe zuerst, ob das Verb être ist; wenn nicht, wird die verneinte Menge zu de/d'.",
        "fr": "Vérifiez d’abord si le verbe est être ; sinon, la quantité niée devient de/d'.",
    },
    "atelier.negation.word_bank_why": {
        "en": "After pas, a negated quantity changes du/de la/des/un/une to de or d'.",
        "de": "Nach pas wird bei einer verneinten Menge du/de la/des/un/une zu de oder d'.",
        "fr": "Après pas, une quantité niée change du/de la/des/un/une en de ou d'.",
    },
    "atelier.negation.word_bank_repair": {
        "en": "Keep ne...pas around the verb, then use de or d' before the noun unless the verb is être.",
        "de": "Lass ne…pas um das Verb stehen und setze dann de oder d' vor das Substantiv, außer das Verb ist être.",
        "fr": "Gardez ne…pas autour du verbe, puis mettez de ou d' devant le nom, sauf si le verbe est être.",
    },
    "atelier.tense.label_background_vs_event": {
        "en": "Background vs event",
        "de": "Hintergrund oder Ereignis",
        "fr": "Arrière-plan ou événement",
    },
    "atelier.tense.fill_needs_imparfait": {
        "en": "You chose `{learner}`, but this verb describes the ongoing background of the sentence, so it needs imparfait: `{target}`.",
        "de": "Du hast `{learner}` gewählt, aber dieses Verb beschreibt den laufenden Hintergrund des Satzes und braucht das Imparfait: `{target}`.",
        "fr": "Vous avez choisi `{learner}`, mais ce verbe décrit l’arrière-plan en cours : il demande l’imparfait `{target}`.",
    },
    "atelier.tense.fill_needs_passe_compose": {
        "en": "You chose `{learner}`, but this verb is the bounded completed event, so it needs passé composé: `{target}`.",
        "de": "Du hast `{learner}` gewählt, aber dieses Verb ist das abgeschlossene, begrenzte Ereignis und braucht das Passé composé: `{target}`.",
        "fr": "Vous avez choisi `{learner}`, mais ce verbe est l’événement borné et achevé : il demande le passé composé `{target}`.",
    },
    "atelier.tense.repair_ask_ongoing": {
        "en": "Ask whether the verb is ongoing background or a completed event, then choose imparfait or passé composé.",
        "de": "Frag dich, ob das Verb laufender Hintergrund oder abgeschlossenes Ereignis ist, und wähle dann Imparfait oder Passé composé.",
        "fr": "Demandez-vous si le verbe est un arrière-plan qui dure ou un événement achevé, puis choisissez l’imparfait ou le passé composé.",
    },
    "atelier.tense.classify_background": {
        "en": "You classified `{prompt}` as `{learner}`, but it describes an ongoing scene or state, so it belongs to the background/imparfait side.",
        "de": "Du hast `{prompt}` als `{learner}` eingeordnet, aber es beschreibt eine laufende Szene oder einen Zustand und gehört auf die Seite Hintergrund/Imparfait.",
        "fr": "Vous avez classé `{prompt}` comme `{learner}`, mais cela décrit une scène ou un état qui dure : c’est le côté arrière-plan/imparfait.",
    },
    "atelier.tense.classify_event": {
        "en": "You classified `{prompt}` as `{learner}`, but it is a bounded completed event, so it belongs to the passé composé side.",
        "de": "Du hast `{prompt}` als `{learner}` eingeordnet, aber es ist ein abgeschlossenes, begrenztes Ereignis und gehört auf die Seite Passé composé.",
        "fr": "Vous avez classé `{prompt}` comme `{learner}`, mais c’est un événement borné et achevé : c’est le côté passé composé.",
    },
    "atelier.tense.repair_background_or_event": {
        "en": "Use background for ongoing scene-setting; use bounded event for a completed interruption or action.",
        "de": "Hintergrund für die laufende Szene; begrenztes Ereignis für eine abgeschlossene Unterbrechung oder Handlung.",
        "fr": "Arrière-plan pour la scène qui dure ; événement borné pour une interruption ou une action achevée.",
    },
    "atelier.tense.word_bank_why": {
        "en": "The sentence needs the same background/event contrast as the target.",
        "de": "Der Satz braucht denselben Kontrast zwischen Hintergrund und Ereignis wie die Zielfassung.",
        "fr": "La phrase demande le même contraste arrière-plan / événement que la phrase attendue.",
    },
    "atelier.tense.word_bank_repair": {
        "en": "Use imparfait for the ongoing scene and passé composé for the bounded event.",
        "de": "Imparfait für die laufende Szene, Passé composé für das begrenzte Ereignis.",
        "fr": "Imparfait pour la scène qui dure, passé composé pour l’événement borné.",
    },
    "atelier.word_bank.label_word_order": {
        "en": "Word order",
        "de": "Wortstellung",
        "fr": "Ordre des mots",
    },
    "atelier.word_bank.label_target_sentence": {
        "en": "Target sentence",
        "de": "Zielsatz",
        "fr": "Phrase attendue",
    },
    "atelier.word_bank.order_why": {
        "en": "The right words are present, but they are not assembled in the target order.",
        "de": "Die richtigen Wörter sind da, aber sie stehen nicht in der verlangten Reihenfolge.",
        "fr": "Les bons mots sont là, mais ils ne sont pas assemblés dans l’ordre attendu.",
    },
    "atelier.word_bank.order_repair": {
        "en": "Move the chips into this order: {target}",
        "de": "Bring die Bausteine in diese Reihenfolge: {target}",
        "fr": "Remettez les étiquettes dans cet ordre : {target}",
    },
    "atelier.word_bank.label_spelling_slip": {
        "en": "Spelling slip",
        "de": "Schreibfehler",
        "fr": "Faute d’orthographe",
    },
    "atelier.word_bank.spelling_why": {
        "en": "You wrote `{learner}`, but the target word here is `{target}`.",
        "de": "Du hast `{learner}` geschrieben, aber das Zielwort ist hier `{target}`.",
        "fr": "Vous avez écrit `{learner}`, alors que le mot attendu ici est `{target}`.",
    },
    "atelier.word_bank.spelling_repair": {
        "en": "Keep the sentence frame, then fix the spelling of `{target}`.",
        "de": "Behalte den Satzrahmen und korrigiere nur die Schreibung von `{target}`.",
        "fr": "Gardez la structure de la phrase, puis corrigez l’orthographe de `{target}`.",
    },
    # -- the rewrite and output ladders' deterministic errata -----------------
    "atelier.transform.missing_label": {
        "en": "Missing rewrite",
        "de": "Fehlende Umformung",
        "fr": "Réécriture manquante",
    },
    "atelier.transform.missing_why": {
        "en": "This rewrite was not attempted.",
        "de": "Diese Umformung wurde nicht versucht.",
        "fr": "Cette réécriture n’a pas été tentée.",
    },
    "atelier.transform.missing_repair": {
        "en": "Submit the rewrite when you want it reviewed; missed transform rows are not scheduled as grammar errata.",
        "de": "Schick die Umformung ab, wenn du sie geprüft haben willst; ausgelassene Zeilen werden nicht als Grammatik-Erratum eingeplant.",
        "fr": "Envoyez la réécriture quand vous voulez qu’elle soit relue ; une ligne laissée de côté n’est pas consignée comme erratum de grammaire.",
    },
    "atelier.output.missing_label": {
        "en": "Missing output",
        "de": "Fehlende Ausgabe",
        "fr": "Production manquante",
    },
    "atelier.output.missing_why": {
        "en": "This output step was left blank, so it cannot strengthen active use yet.",
        "de": "Dieser Schritt blieb leer und kann den aktiven Gebrauch deshalb noch nicht festigen.",
        "fr": "Cette étape est restée vide : elle ne peut pas encore renforcer l’usage actif.",
    },
    "atelier.output.missing_repair": {
        "en": "Produce one sentence or turn before submitting; blank output is not scheduled as grammar errata.",
        "de": "Schreib einen Satz oder eine Replik, bevor du abschickst; eine leere Ausgabe wird nicht als Grammatik-Erratum eingeplant.",
        "fr": "Produisez une phrase ou une réplique avant d’envoyer ; une production vide n’est pas consignée comme erratum de grammaire.",
    },
    "atelier.output.target_count_why": {
        "en": "This step is stronger when you use {label} at least {target_count} time(s); this answer used it {detected_count}.",
        "de": "Dieser Schritt wird stärker, wenn du {label} mindestens {target_count}-mal benutzt; diese Antwort benutzt es {detected_count}-mal.",
        "fr": "Cette étape porte mieux quand vous employez {label} au moins {target_count} fois ; cette réponse l’emploie {detected_count} fois.",
    },
    "atelier.si.output_pattern_hint": {
        "en": "Use si + present, then a future simple or imperative result.",
        "de": "Nimm si + Präsens und als Folge das Futur simple oder den Imperativ.",
        "fr": "Employez si + présent, puis une conséquence au futur simple ou à l’impératif.",
    },
    "atelier.si.output_future_result_why": {
        "en": "You wrote `{learner_form}` in the result clause. With si + present for a real condition, the result uses future simple, so this should be `{target_form}`.",
        "de": "Du hast `{learner_form}` in die Folge geschrieben. Bei si + Präsens für eine reale Bedingung steht die Folge im Futur simple: hier also `{target_form}`.",
        "fr": "Vous avez écrit `{learner_form}` dans la principale. Avec si + présent pour une condition réelle, la conséquence prend le futur simple : ce serait donc `{target_form}`.",
    },
    "atelier.si.output_future_result_repair": {
        "en": "Keep your si-clause, then change only the result verb from conditional to future simple.",
        "de": "Behalte deinen si-Satz und ändere nur das Verb der Folge vom Conditionnel ins Futur simple.",
        "fr": "Gardez votre subordonnée en « si », puis passez seulement le verbe de la principale du conditionnel au futur simple.",
    },
    "atelier.si.label_result_form_needed": {
        "en": "Result form needed",
        "de": "Form der Folge fehlt",
        "fr": "Forme du résultat attendue",
    },
    "atelier.si.output_result_missing_why": {
        "en": "Your si-clause is in the present, but the consequence does not show a future simple or imperative result.",
        "de": "Dein si-Satz steht im Präsens, aber die Folge zeigt weder ein Futur simple noch einen Imperativ.",
        "fr": "Votre subordonnée en « si » est au présent, mais la conséquence ne montre ni futur simple ni impératif.",
    },
    "atelier.si.output_result_missing_repair": {
        "en": "After the comma, make the consequence future simple or a direct command.",
        "de": "Setze die Folge nach dem Komma ins Futur simple oder in den Imperativ.",
        "fr": "Après la virgule, mettez la conséquence au futur simple ou à l’impératif.",
    },
    "atelier.si.label_clause_tense": {
        "en": "Si-clause tense",
        "de": "Zeitform im si-Satz",
        "fr": "Temps de la subordonnée en « si »",
    },
    "atelier.si.output_clause_tense_why": {
        "en": "You put `{learner_form}` inside the si-clause. In si type 1, the verb right after si stays in the present.",
        "de": "Du hast `{learner_form}` in den si-Satz gesetzt. Beim si-Typ 1 bleibt das Verb direkt nach si im Präsens.",
        "fr": "Vous avez mis `{learner_form}` dans la subordonnée. Au si de type 1, le verbe qui suit « si » reste au présent.",
    },
    "atelier.si.output_clause_tense_repair": {
        "en": "Move the future idea to the result clause; keep the condition after si in the present.",
        "de": "Verschieb die Zukunft in die Folge; die Bedingung nach si bleibt im Präsens.",
        "fr": "Déplacez l’idée de futur dans la principale ; la condition après « si » reste au présent.",
    },
    "atelier.si.the_verb_after_si": {
        "en": "the verb after si",
        "de": "das Verb nach si",
        "fr": "le verbe après « si »",
    },
    # The two errata that had the *opposite* defect: French prose shown to a
    # learner who may not read French yet. Same rule, other direction.
    "atelier.writing.too_short_label": {
        "en": "Paragraph too short",
        "de": "Absatz zu kurz",
        "fr": "Paragraphe trop court",
    },
    "atelier.writing.too_short_why": {
        "en": "{written} word(s) written, {required} required for this assignment.",
        "de": "{written} Wort/Wörter geschrieben, {required} für diese Aufgabe verlangt.",
        "fr": "{written} mot(s) écrits, {required} requis pour cette consigne.",
    },
    "atelier.writing.too_short_repair": {
        "en": "Add {missing} more word(s) to complete the paragraph.",
        "de": "Ergänze {missing} Wort/Wörter, um den Absatz zu vervollständigen.",
        "fr": "Ajoutez {missing} mot(s) pour compléter le paragraphe.",
    },
    "atelier.lexical_gap.label": {
        "en": "French word needed",
        "de": "Französisches Wort nötig",
        "fr": "Mot en français",
    },
    "atelier.lexical_gap.in_german": {
        "en": "in German",
        "de": "auf Deutsch",
        "fr": "en allemand",
    },
    "atelier.lexical_gap.in_english": {
        "en": "in English",
        "de": "auf Englisch",
        "fr": "en anglais",
    },
    "atelier.lexical_gap.in_your_language": {
        "en": "in your own language",
        "de": "in deiner eigenen Sprache",
        "fr": "dans votre langue",
    },
    "atelier.lexical_gap.why": {
        "en": "You wrote « {fragment} » {language}. In French this is « {french} »{gloss}.",
        "de": "Du hast « {fragment} » {language} geschrieben. Auf Französisch heißt das « {french} »{gloss}.",
        "fr": "Vous avez écrit « {fragment} » {language}. En français, cela donne « {french} »{gloss}.",
    },
    "atelier.lexical_gap.repair": {
        "en": "Replace « {fragment} » with « {french} ».",
        "de": "Ersetze « {fragment} » durch « {french} ».",
        "fr": "Remplacez « {fragment} » par « {french} ».",
    },
    "atelier.writing.missing_target_label": {
        "en": "Missing writing target",
        "de": "Fehlendes Schreibziel",
        "fr": "Objectif d’écriture manquant",
    },
    "atelier.writing.missing_target_why": {
        "en": "The writing submitted successfully, but it used this target {detected_count} time(s) instead of {target_count}.",
        "de": "Der Text wurde abgeschickt, benutzt dieses Ziel aber {detected_count}-mal statt {target_count}-mal.",
        "fr": "Le texte est bien parti, mais il emploie cet objectif {detected_count} fois au lieu de {target_count}.",
    },
    "atelier.writing.missing_target_repair": {
        "en": "Add the target naturally in revision; do not block submission for this.",
        "de": "Ergänze das Ziel beim Überarbeiten ganz natürlich; das Abschicken soll daran nicht scheitern.",
        "fr": "Ajoutez l’objectif naturellement à la relecture ; cela ne doit pas empêcher d’envoyer.",
    },
    # The three no-concept floors of the correction service: an erratum filed
    # against no catalogue concept still has to say something readable.
    "atelier.generic.label": {
        "en": "Grammar target",
        "de": "Grammatikziel",
        "fr": "Objectif de grammaire",
    },
    "atelier.generic.this_form": {
        "en": "this form",
        "de": "diese Form",
        "fr": "cette forme",
    },
    "atelier.generic.no_label": {
        "en": "no label",
        "de": "keine Einordnung",
        "fr": "aucune étiquette",
    },
    "atelier.generic.why": {
        "en": "The answer does not match the requested grammar target.",
        "de": "Die Antwort trifft das verlangte Grammatikziel nicht.",
        "fr": "La réponse ne correspond pas à l’objectif de grammaire demandé.",
    },
    "atelier.generic.repair": {
        "en": "Name the trigger, then apply the target form.",
        "de": "Benenne den Auslöser und wende dann die Zielform an.",
        "fr": "Nommez le déclencheur, puis appliquez la forme visée.",
    },
    "erratum.repair_use_suggestion": {
        "en": "Use “{suggestion}” here, then try the same contrast in a fresh sentence.",
        "de": "Nimm hier „{suggestion}“ und übe denselben Kontrast dann in einem neuen Satz.",
        "fr": "Employez « {suggestion} » ici, puis reprenez le même contraste dans une autre phrase.",
    },
    "erratum.source_practice": {
        "en": "Practice",
        "de": "Übung",
        "fr": "Pratique",
    },
    # -- app/services/brief_exercise_service.py: the short drill --------------
    "brief.repair_review_requested_form": {
        "en": "Review the requested form, then answer a fresh version of this exercise.",
        "de": "Sieh dir die verlangte Form noch einmal an und beantworte dann eine neue Fassung dieser Übung.",
        "fr": "Revoyez la forme demandée, puis refaites une nouvelle version de cet exercice.",
    },
    "brief.feedback_correct": {
        "en": "That matches the grammar task.",
        "de": "Das passt zur Grammatikaufgabe.",
        "fr": "Cela correspond à la consigne de grammaire.",
    },
    "brief.feedback_incorrect": {
        "en": "Not this time. The expected answer is: {answer}",
        "de": "Leider falsch. Richtig wäre: {answer}",
        "fr": "Pas cette fois. La réponse attendue est : {answer}",
    },
    "brief.feedback_exact_correct": {
        "en": "Correct.",
        "de": "Richtig.",
        "fr": "Correct.",
    },
    "brief.feedback_near": {
        "en": "Close. The expected answer is: {answer}",
        "de": "Fast. Die erwartete Antwort ist: {answer}",
        "fr": "Presque. La réponse attendue est : {answer}",
    },
    "brief.label_review": {
        "en": "Review",
        "de": "Wiederholung",
        "fr": "Révision",
    },
    "brief.label_brief_exercise": {
        "en": "Brief exercise",
        "de": "Kurzübung",
        "fr": "Exercice court",
    },
    # -- app/services/missions.py: the authored Courrier fallback -------------
    "mission.objective_submitted": {
        "en": "Submitted",
        "de": "Abgeschickt",
        "fr": "Envoyé",
    },
    "mission.objective_unassessed": {
        "en": "Not corrected yet",
        "de": "Noch nicht korrigiert",
        "fr": "Pas encore corrigé",
    },
    "mission.objective_no_answer": {
        "en": "No answer yet",
        "de": "Noch keine Antwort",
        "fr": "Pas encore de réponse",
    },
    "mission.target_generic_label": {
        "en": "Target",
        "de": "Ziel",
        "fr": "Objectif",
    },
    "mission.empty_label": {
        "en": "Missing mission response",
        "de": "Fehlende Antwort auf den Auftrag",
        "fr": "Réponse manquante",
    },
    "mission.empty_target": {
        "en": "Write a short French response before submitting.",
        "de": "Schreibe eine kurze französische Antwort, bevor du abschickst.",
        "fr": "Écrivez une courte réponse en français avant d’envoyer.",
    },
    "mission.empty_why": {
        "en": "You submitted an empty response, so there is no French to review.",
        "de": "Du hast eine leere Antwort abgeschickt, es gibt also kein Französisch zu prüfen.",
        "fr": "Vous avez envoyé une réponse vide : il n’y a pas de français à relire.",
    },
    "mission.empty_hint": {
        "en": "Write two or three sentences that answer the brief.",
        "de": "Schreibe zwei oder drei Sätze, die den Auftrag beantworten.",
        "fr": "Écrivez deux ou trois phrases qui répondent à la consigne.",
    },
    "mission.short_label": {
        "en": "Too little context",
        "de": "Zu wenig Kontext",
        "fr": "Trop peu de contexte",
    },
    "mission.short_why": {
        "en": "Your answer is understandable, but it is too short to show the mission targets.",
        "de": "Deine Antwort ist verständlich, aber zu kurz, um die Ziele des Auftrags zu zeigen.",
        "fr": "Votre réponse se comprend, mais elle est trop courte pour montrer les objectifs.",
    },
    "mission.short_hint": {
        "en": "Add one reason, one concrete detail, and one target grammar form.",
        "de": "Ergänze einen Grund, ein konkretes Detail und eine Zielform der Grammatik.",
        "fr": "Ajoutez une raison, un détail concret et une forme de grammaire visée.",
    },
    "mission.rule_avoir_vous_label": {
        "en": "Conjugation: vous avez",
        "de": "Konjugation: vous avez",
        "fr": "Conjugaison : vous avez",
    },
    "mission.rule_avoir_vous_why": {
        "en": "With “vous”, the verb avoir is “avez”, not “avet”.",
        "de": "Mit „vous“ heißt avoir „avez“, nicht „avet“.",
        "fr": "Avec « vous », le verbe avoir donne « avez », pas « avet ».",
    },
    "mission.rule_avoir_vous_hint": {
        "en": "Write “vous avez” before a noun or a past participle.",
        "de": "Schreibe „vous avez“ vor einem Substantiv oder Partizip.",
        "fr": "Écrivez « vous avez » devant un nom ou un participe passé.",
    },
    "mission.rule_probleme_label": {
        "en": "Spelling: problème",
        "de": "Rechtschreibung: problème",
        "fr": "Orthographe : problème",
    },
    "mission.rule_probleme_why": {
        "en": "The French word is “problème”, with an accent grave.",
        "de": "Das französische Wort ist „problème“, mit Accent grave.",
        "fr": "Le mot français est « problème », avec un accent grave.",
    },
    "mission.rule_probleme_hint": {
        "en": "Write “problème”, or “problèmes” in the plural.",
        "de": "Schreibe „problème“, im Plural „problèmes“.",
        "fr": "Écrivez « problème », ou « problèmes » au pluriel.",
    },
    # -- app/services/atelier.py: the authored fallback exercises (WP-67) -----
    # These instructions are written once, cached in `atelier_exercise_sets` and
    # shared across learners, so they cannot be generated in one learner's
    # language: they carry a `instruction_key` and are resolved on the way out
    # (`_with_learner_instructions`, the same discipline `_with_fr_titles`
    # already uses for the French concept titles). The French sentence the
    # learner must rewrite is data and stays identical in all three columns;
    # only the instruction around it moves.
    "atelier.transform.negation.1": {
        "en": "Make this negative and change the partitive 'du' to its form after 'pas'.",
        "de": "Verneine den Satz und setze das Teilungswort 'du' in die Form nach 'pas'.",
        "fr": "Mettez la phrase à la négative et changez le partitif « du » en sa forme après « pas ».",
    },
    "atelier.transform.negation.2": {
        "en": "Negate 'C'est du café' with ne…pas, watching the être exception.",
        "de": "Verneine 'C'est du café' mit ne…pas und achte auf die être-Ausnahme.",
        "fr": "Niez « C'est du café » avec ne…pas, en surveillant l’exception d’être.",
    },
    "atelier.transform.negation.3": {
        "en": "Repair the article 'une' after 'pas' to its negated quantity form.",
        "de": "Korrigiere den Artikel 'une' nach 'pas' zur Form der verneinten Menge.",
        "fr": "Corrigez l’article « une » après « pas » en sa forme de quantité niée.",
    },
    "atelier.transform.tense.1": {
        "en": "Change 'pleut' to the imparfait and 'sors' to the passé composé.",
        "de": "Setze 'pleut' ins Imparfait und 'sors' ins Passé composé.",
        "fr": "Mettez « pleut » à l’imparfait et « sors » au passé composé.",
    },
    "atelier.transform.tense.2": {
        "en": "Turn the habit 'lisais' into a single completed event in the passé composé.",
        "de": "Mach aus der Gewohnheit 'lisais' ein einzelnes abgeschlossenes Ereignis im Passé composé.",
        "fr": "Transformez l’habitude « lisais » en un seul événement achevé au passé composé.",
    },
    "atelier.transform.tense.3": {
        "en": "Repair the contrast: put 'suis' in the imparfait and 'sonnait' in the passé composé.",
        "de": "Korrigiere den Kontrast: 'suis' ins Imparfait, 'sonnait' ins Passé composé.",
        "fr": "Corrigez le contraste : « suis » à l’imparfait et « sonnait » au passé composé.",
    },
    "atelier.transform.si.1": {
        "en": "Rewrite 'Quand il arrivera, on commencera' to start with a si-clause whose condition is in the present.",
        "de": "Schreibe 'Quand il arrivera, on commencera' so um, dass der Satz mit einem si-Satz im Präsens beginnt.",
        "fr": "Réécrivez « Quand il arrivera, on commencera » pour commencer par une subordonnée en « si » dont la condition est au présent.",
    },
    "atelier.transform.si.2": {
        "en": "Make this a si type 1: put 'avais' in the present and 'viendrais' in the future.",
        "de": "Mach daraus einen si-Typ 1: 'avais' ins Präsens, 'viendrais' ins Futur.",
        "fr": "Faites-en un si de type 1 : « avais » au présent et « viendrais » au futur.",
    },
    "atelier.transform.si.3": {
        "en": "Repair the verb 'viendras' after 'si': the condition must be in the present.",
        "de": "Korrigiere das Verb 'viendras' nach 'si': die Bedingung muss im Präsens stehen.",
        "fr": "Corrigez le verbe « viendras » après « si » : la condition doit être au présent.",
    },
    "atelier.transform.conditional_mood.1": {
        "en": "Rewrite 'veux' as 'voudrais' so the request sounds polite.",
        "de": "Schreibe 'veux' als 'voudrais', damit die Bitte höflich klingt.",
        "fr": "Réécrivez « veux » en « voudrais » pour que la demande soit polie.",
    },
    "atelier.transform.conditional_mood.2": {
        "en": "Rewrite as a polite possibility instead of a plain fact: put the verb in the conditional.",
        "de": "Schreibe es als höfliche Möglichkeit statt als schlichte Tatsache: setze das Verb ins Conditionnel.",
        "fr": "Réécrivez en possibilité polie plutôt qu’en fait brut : mettez le verbe au conditionnel.",
    },
    "atelier.transform.conditional_mood.3": {
        "en": "Repair the verb: a polite wish needs the conditional, not the present.",
        "de": "Korrigiere das Verb: ein höflicher Wunsch braucht das Conditionnel, nicht das Präsens.",
        "fr": "Corrigez le verbe : un souhait poli demande le conditionnel, pas le présent.",
    },
    "atelier.transform.mood.1": {
        "en": "Rewrite 'es' as 'sois' after adding 'il faut que'.",
        "de": "Füge 'il faut que' hinzu und schreibe 'es' als 'sois'.",
        "fr": "Ajoutez « il faut que » et réécrivez « es » en « sois ».",
    },
    "atelier.transform.mood.2": {
        "en": "Rewrite as a wish instead of a certainty: keep 'demain' and put the verb in the subjunctive.",
        "de": "Schreibe es als Wunsch statt als Gewissheit: behalte 'demain' und setze das Verb in den Subjonctif.",
        "fr": "Réécrivez en souhait plutôt qu’en certitude : gardez « demain » et mettez le verbe au subjonctif.",
    },
    "atelier.transform.mood.3": {
        "en": "Repair the verb after 'bien que': this trigger requires the subjunctive.",
        "de": "Korrigiere das Verb nach 'bien que': dieser Auslöser verlangt den Subjonctif.",
        "fr": "Corrigez le verbe après « bien que » : ce déclencheur exige le subjonctif.",
    },
    "atelier.transform.relative_pronoun.1": {
        "en": "Repair 'qui' to 'que': this relative pronoun replaces a direct object.",
        "de": "Korrigiere 'qui' zu 'que': dieses Relativpronomen vertritt ein direktes Objekt.",
        "fr": "Corrigez « qui » en « que » : ce pronom relatif remplace un complément d’objet direct.",
    },
    "atelier.transform.relative_pronoun.2": {
        "en": "Repair the relative pronoun: 'arrive' needs its subject relative pronoun.",
        "de": "Korrigiere das Relativpronomen: 'arrive' braucht das Relativpronomen des Subjekts.",
        "fr": "Corrigez le pronom relatif : « arrive » demande son pronom relatif sujet.",
    },
    "atelier.transform.relative_pronoun.3": {
        "en": "Repair the relative pronoun: this clause names a place, so it needs the locative relative pronoun.",
        "de": "Korrigiere das Relativpronomen: dieser Nebensatz nennt einen Ort und braucht das Relativpronomen des Ortes.",
        "fr": "Corrigez le pronom relatif : cette proposition nomme un lieu, il lui faut le relatif de lieu.",
    },
    "atelier.transform.pronoun_choice.1": {
        "en": "Replace 'Marc' with 'le', the direct object pronoun.",
        "de": "Ersetze 'Marc' durch 'le', das direkte Objektpronomen.",
        "fr": "Remplacez « Marc » par « le », le pronom complément d’objet direct.",
    },
    "atelier.transform.pronoun_choice.2": {
        "en": "Replace 'à Paul' with the indirect object pronoun, keeping 'parlons'.",
        "de": "Ersetze 'à Paul' durch das indirekte Objektpronomen und behalte 'parlons'.",
        "fr": "Remplacez « à Paul » par le pronom complément d’objet indirect, en gardant « parlons ».",
    },
    "atelier.transform.pronoun_choice.3": {
        "en": "Repair the pronoun: a quantity taken from a group needs 'en', not a direct object pronoun.",
        "de": "Korrigiere das Pronomen: eine Menge aus einer Gruppe braucht 'en', kein direktes Objektpronomen.",
        "fr": "Corrigez le pronom : une quantité prise dans un ensemble demande « en », pas un pronom d’objet direct.",
    },
    "atelier.transform.determiner.1": {
        "en": "Rewrite 'une' as 'la': this gare is a specific, already-known one.",
        "de": "Schreibe 'une' als 'la': diese gare ist eine bestimmte, bereits bekannte.",
        "fr": "Réécrivez « une » en « la » : cette gare est précise et déjà connue.",
    },
    "atelier.transform.determiner.2": {
        "en": "Rewrite for several tickets: change the article and noun to plural.",
        "de": "Schreibe es für mehrere Fahrkarten um: Artikel und Substantiv in den Plural.",
        "fr": "Réécrivez pour plusieurs billets : mettez l’article et le nom au pluriel.",
    },
    "atelier.transform.determiner.3": {
        "en": "Repair the article: ordering one coffee needs the indefinite article, not the definite one.",
        "de": "Korrigiere den Artikel: wer einen Kaffee bestellt, braucht den unbestimmten Artikel, nicht den bestimmten.",
        "fr": "Corrigez l’article : commander un café demande l’article indéfini, pas le défini.",
    },
    "atelier.transform.agreement.1": {
        "en": "Rewrite 'maison' as the plural 'maisons', agreeing the rest of the sentence.",
        "de": "Schreibe 'maison' im Plural 'maisons' und passe den Rest des Satzes an.",
        "fr": "Réécrivez « maison » au pluriel « maisons » et accordez le reste de la phrase.",
    },
    "atelier.transform.agreement.2": {
        "en": "Rewrite in the feminine, agreeing the determiner and the adjective with the new noun.",
        "de": "Schreibe es im Femininum und passe Begleiter und Adjektiv an das neue Substantiv an.",
        "fr": "Réécrivez au féminin, en accordant le déterminant et l’adjectif avec le nouveau nom.",
    },
    "atelier.transform.agreement.3": {
        "en": "Repair the past participle: with être, it must agree with the plural subject.",
        "de": "Korrigiere das Partizip: mit être richtet es sich nach dem Subjekt im Plural.",
        "fr": "Corrigez le participe passé : avec être, il s’accorde avec le sujet pluriel.",
    },
    "atelier.transform.preposition.1": {
        "en": "Rewrite 'au bureau de' as 'chez' to say 'at Marie's place'.",
        "de": "Schreibe 'au bureau de' als 'chez', um „bei Marie“ zu sagen.",
        "fr": "Réécrivez « au bureau de » en « chez » pour dire « chez Marie ».",
    },
    "atelier.transform.preposition.2": {
        "en": "Add the preposition 'parler' needs before its topic.",
        "de": "Ergänze die Präposition, die 'parler' vor seinem Thema verlangt.",
        "fr": "Ajoutez la préposition que « parler » demande devant son sujet de conversation.",
    },
    "atelier.transform.preposition.3": {
        "en": "Repair the preposition: living on a street uses 'dans', not 'à'.",
        "de": "Korrigiere die Präposition: in einer Straße wohnen heißt 'dans', nicht 'à'.",
        "fr": "Corrigez la préposition : habiter une rue se dit avec « dans », pas « à ».",
    },
    "atelier.transform.comparison.1": {
        "en": "Rewrite 'aussi' as 'plus': she is faster, not equally fast.",
        "de": "Schreibe 'aussi' als 'plus': sie ist schneller, nicht gleich schnell.",
        "fr": "Réécrivez « aussi » en « plus » : elle est plus rapide, pas aussi rapide.",
    },
    "atelier.transform.comparison.2": {
        "en": "Rewrite to say this coffee costs less, not more.",
        "de": "Schreibe es so um, dass dieser Kaffee weniger kostet, nicht mehr.",
        "fr": "Réécrivez pour dire que ce café coûte moins cher, pas plus cher.",
    },
    "atelier.transform.comparison.3": {
        "en": "Repair the comparison: equality between two people needs 'aussi… que', not 'si… que'.",
        "de": "Korrigiere den Vergleich: Gleichheit zwischen zwei Personen braucht 'aussi… que', nicht 'si… que'.",
        "fr": "Corrigez la comparaison : l’égalité entre deux personnes demande « aussi… que », pas « si… que ».",
    },
    "atelier.transform.generic.1": {
        "en": "Rewrite 'Je pratique' as 'Nous pratiquons' for the subject 'we'.",
        "de": "Schreibe 'Je pratique' als 'Nous pratiquons' für das Subjekt „wir“.",
        "fr": "Réécrivez « Je pratique » en « Nous pratiquons » pour le sujet « nous ».",
    },
    "atelier.transform.generic.2": {
        "en": "Rewrite in the passé composé, as something already done.",
        "de": "Schreibe es im Passé composé, als etwas bereits Getanes.",
        "fr": "Réécrivez au passé composé, comme quelque chose de déjà fait.",
    },
    "atelier.transform.generic.3": {
        "en": "Repair the verb: it must agree with the singular subject 'elle'.",
        "de": "Korrigiere das Verb: es richtet sich nach dem Subjekt 'elle' im Singular.",
        "fr": "Corrigez le verbe : il s’accorde avec le sujet singulier « elle ».",
    },
    "atelier.fallback.output_instruction": {
        "en": "Use the target grammar visibly in your answer.",
        "de": "Benutze die Zielgrammatik sichtbar in deiner Antwort.",
        "fr": "Employez visiblement la grammaire visée dans votre réponse.",
    },
    # -- app/services/pragmatics.py: WP-33 register and pragmatics ------------
    # Explicit meta-pragmatic instruction: the line names the rule *and* the
    # reason, because "instruction beats exposure" only holds when the learner
    # is told why (Taguchi 2015). `{counterpart}` is the character's own name;
    # `{reason}` is the scene's own declared reason and may be empty, so every
    # sentence must still read correctly without it.
    "pragmatics.register_use_vous": {
        "en": "Here it is “vous”: {counterpart} addresses you with vous. {reason}",
        "de": "Hier gilt „vous“: {counterpart} siezt dich. {reason}",
        "fr": "Ici, c’est « vous » : {counterpart} vous vouvoie. {reason}",
    },
    "pragmatics.register_use_tu": {
        "en": "Here it is “tu”: {counterpart} uses tu with you, and the verb follows it. {reason}",
        "de": "Hier gilt „tu“: {counterpart} duzt dich, und das Verb geht mit. {reason}",
        "fr": "Ici, c’est « tu » : {counterpart} vous tutoie, et le verbe suit. {reason}",
    },
    "pragmatics.register_mixed": {
        "en": "One register per conversation: this answer uses both tu and vous.",
        "de": "Eine Anrede pro Gespräch: diese Antwort benutzt tu und vous zugleich.",
        "fr": "Une seule adresse par conversation : cette réponse mêle « tu » et « vous ».",
    },
    "pragmatics.bare_imperative": {
        "en": "That is an order. Ask instead: “je voudrais…”, or “est-ce que vous pouvez…”.",
        "de": "Das ist ein Befehl. Frag lieber: „je voudrais…“ oder „est-ce que vous pouvez…“.",
        "fr": "C’est un ordre. Demandez plutôt : « je voudrais… » ou « est-ce que vous pouvez… ».",
    },
    "pragmatics.blunt_want": {
        "en": "“Je veux” is blunt in a shop or an office. “Je voudrais” is the request.",
        "de": "„Je veux“ klingt im Laden oder Amt schroff. „Je voudrais“ ist die Bitte.",
        "fr": "« Je veux » est brutal dans un commerce. La demande, c’est « je voudrais ».",
    },
    "pragmatics.missing_greeting": {
        "en": "In France you greet first: “bonjour” opens the exchange before the request.",
        "de": "In Frankreich grüßt man zuerst: „bonjour“ eröffnet das Gespräch vor der Bitte.",
        "fr": "En France, on salue d’abord : « bonjour » ouvre l’échange avant la demande.",
    },
    "pragmatics.missing_politeness": {
        "en": "Nothing softens this request — “s’il vous plaît” or “je voudrais” does it.",
        "de": "Nichts mildert diese Bitte — „s’il vous plaît“ oder „je voudrais“ tut es.",
        "fr": "Rien n’adoucit cette demande — « s’il vous plaît » ou « je voudrais » suffit.",
    },
    "pragmatics.missing_closing": {
        "en": "The exchange ends on a word: “merci”, “au revoir”, “bonne journée”.",
        "de": "Der Austausch endet mit einem Wort: „merci“, „au revoir“, „bonne journée“.",
        "fr": "L’échange se ferme sur un mot : « merci », « au revoir », « bonne journée ».",
    },
    "pragmatics.register_not_evaluated": {
        "en": "Register was not assessed here — nothing in these answers addressed anyone.",
        "de": "Die Anrede wurde hier nicht bewertet — keine Antwort sprach jemanden an.",
        "fr": "L’adresse n’a pas été évaluée ici — aucune réponse ne s’adresse à quelqu’un.",
    },
    "capability.register_title": {
        "en": "Speak to the right person the right way",
        "de": "Die passende Anrede treffen",
        "fr": "S’adresser comme il faut",
    },
    "capability.register_context_with": {
        "en": "Kept {register} with {character}.",
        "de": "{register} bei {character} durchgehalten.",
        "fr": "« {register} » tenu avec {character}.",
    },
    "capability.register_context_bare": {
        "en": "Kept the scene’s register.",
        "de": "Die Anrede der Szene gehalten.",
        "fr": "L’adresse de la scène tenue.",
    },
    "capability.register_context_slip_with": {
        "en": "Slipped out of {register} with {character}.",
        "de": "Aus {register} bei {character} herausgefallen.",
        "fr": "Sortie de « {register} » avec {character}.",
    },
    "capability.register_context_slip_bare": {
        "en": "Slipped out of the scene’s register.",
        "de": "Aus der Anrede der Szene herausgefallen.",
        "fr": "Sortie de l’adresse de la scène.",
    },
    # -- app/services/journey_conversation.py: WP-36 self-repair --------------
    # The character asks first, in French, and that question is not copy: it is
    # the fiction. What *is* copy is the explicit correction that follows a
    # repair the learner did not manage — explicit meaning the right form is
    # named outright, in their own language (Lyster & Ranta 1997: 50 % uptake
    # against 31 % for a recast). `{why}` is the erratum's stored explanation
    # and is appended by the caller, so each sentence must end cleanly without it.
    "self_repair.explicit_note": {
        "en": "That was the one you were just asked about: it is “{correct}”, not “{wrong}”.",
        "de": "Danach wurde eben gefragt: Es heißt „{correct}“, nicht „{wrong}“.",
        "fr": "C’est ce qu’on venait de vous demander : on dit « {correct} », pas « {wrong} ».",
    },
}


def copy_language(native_language: Any) -> str:
    """The copy column to read for a learner, with `en` as the safe default."""
    code = normalize_language(native_language)
    return code if code in SUPPORTED_COPY_LANGUAGES else DEFAULT_GLOSS_LANGUAGE


def learner_text(key: str, native_language: Any = None, **fields: Any) -> str:
    """One deterministic sentence, in the learner's language.

    An unknown key returns the key itself: a visible defect in a correction card
    beats an exception thrown while grading a learner's answer.
    """
    row = LEARNER_COPY.get(key)
    if not row:
        return key
    template = row.get(copy_language(native_language)) or row.get(DEFAULT_GLOSS_LANGUAGE) or ""
    if not fields:
        return template
    try:
        return template.format(**fields)
    except (KeyError, IndexError, ValueError):
        return template


#: English sentence -> key, for content that was written into shared storage
#: before it carried a key. `atelier_exercise_sets` rows are generated once and
#: reused by every learner, so a payload cached last week holds the English
#: instruction and no `instruction_key`; rather than bump the generator version
#: and regenerate every cached set, the serve-time localizer looks the sentence
#: up here. The keys stay the identifiers — this index is derived from the `en`
#: column, never authored — so a grep for English in learner-facing code still
#: finds only this file.
_ENGLISH_INDEX: dict[str, str] = {}
for _key, _row in LEARNER_COPY.items():
    _english = _row.get("en")
    if _english and _english not in _ENGLISH_INDEX:
        _ENGLISH_INDEX[_english] = _key
del _key, _row, _english


def key_for_english(text: Any) -> str | None:
    """The copy key whose English column is exactly `text`, if there is one."""
    return _ENGLISH_INDEX.get(str(text or "").strip())


def learner_text_for_english(text: Any, native_language: Any = None) -> str:
    """Re-read a stored English sentence in the learner's language.

    Unknown text is returned unchanged: this is a repair for content already in
    the database, never a translation service, and a sentence nobody authored a
    row for must still reach the learner.
    """
    key = key_for_english(text)
    if key is None:
        return str(text or "")
    return learner_text(key, native_language)


__all__ = [
    "LEARNER_COPY",
    "SUPPORTED_COPY_LANGUAGES",
    "copy_language",
    "key_for_english",
    "learner_text",
    "learner_text_for_english",
]
