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


__all__ = [
    "LEARNER_COPY",
    "SUPPORTED_COPY_LANGUAGES",
    "copy_language",
    "learner_text",
]
