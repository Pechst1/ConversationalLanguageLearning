"""«Au comptoir»: the takes desk (WP-119, owner 2026-10-19).

Every morning the regulars of Le Mistral argue about one news story. Romy is writing a
vox pop («micro-trottoir») for her paper and she is one voice short: the learner's. The
learner reads what happened, hears three opinions, catches the one claim that is false,
and says what they think (the loop is ``comptoir_loop.py``; the spec is
``docs/implementation/atelier-v2/WP-119-AU-COMPTOIR.md``).

This module writes what every learner shares: :class:`~app.services.revue.dossier.ComptoirTakes`,
one JSON call per story (:func:`write_comptoir`), modelled on the lead desk (``leads.py``).

- Who sits at the counter is decided here, not by the model (:func:`comptoir_guests`):
  Romy (off duty, so she has opinions), the topic's guest, Gus (who lies by reflex).
- :func:`repair_comptoir` checks what the desk wrote. A failing check drops the smallest
  thing it can (a reason tile, a counter-line, the intox, a band of the intox); the whole
  comptoir is refused only when the question, the three sides or a band's take cannot be
  kept, or when a take still carries a false detail the intox step would not correct.
  One retry with the problems, like the close, before refusing (also when only the intox
  was lost: it is a whole step of the loop).
- :func:`ensure_comptoir` runs each morning after the leads (``app/tasks/revue.py``), once
  per kiosk row: a refusal or a skip is recorded on ``checks["comptoir"]`` so the row is not
  asked again. An evergreen reads the takes shipped with it (``evergreen/comptoir/``).
- :func:`takes_at_start`: a session that starts on a story without takes and without a
  recorded refusal gets one synchronous desk call; when it fails the session is a chat.

The desk's model is ``REVUE_COMPTOIR_MODEL`` (the comparison of 2026-10-19 chose it; see the
spec). Nothing here runs while ``REVUE_COMPTOIR_ENABLED`` is off.
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from loguru import logger

from app.services.revue import policy, voice
from app.services.revue.dossier import (
    COMPTOIR_STANCES,
    ComptoirGuest,
    ComptoirIntox,
    ComptoirPhrase,
    ComptoirReply,
    ComptoirTake,
    ComptoirTakes,
    ComptoirText,
    EditorialDossier,
    fold,
)

COMPTOIR_PROMPT_VERSION = "comptoir-takes-v2"

ROMY_ID = "romy_tremblay"
GUS_ID = "augustin_de_roncourt"
MARGAUX_ID = "margaux_barman"
#: The topic guests who can sit at the counter: the ones with a portrait (never Camille).
COUNTER_GUESTS: tuple[str, ...] = ("lila_bonnet", "marin_leveque", MARGAUX_ID, "landlord_marchand")

#: How each regular signs «La page» (authored here, never by the model).
ROLE_FR: dict[str, str] = {
    ROMY_ID: "journaliste",
    GUS_ID: "consultant",
    MARGAUX_ID: "Le Mistral",
    "lila_bonnet": "prof",
    "marin_leveque": "ONG",
    "landlord_marchand": "propriétaire",
}
NAME_FR: dict[str, str] = {
    ROMY_ID: "Romy",
    GUS_ID: "Gus",
    MARGAUX_ID: "Margaux",
    "lila_bonnet": "Lila",
    "marin_leveque": "Marin",
    "landlord_marchand": "M. Marchand",
}

TAKE_MAX_WORDS: dict[str, int] = {"a1": 16, "a2": 28, "b1": 45}
QUESTION_MAX_WORDS = 9
QUOTE_MAX_WORDS = 8
REPLY_MAX_WORDS = 22
COMEBACK_MAX_WORDS = 10
REASON_MAX_WORDS = 5
FRAME_MAX_WORDS = 14
BANK_MAX_WORDS = 3
PHRASE_MAX_WORDS = 10
ASK_MAX_WORDS = 10
CAUGHT_MAX_WORDS = 22
INTOX_MAX_WORDS = 6
VALUE_MAX_WORDS = 8
TRANSLATION_MAX_CHARS = 600

#: Never in a line a learner reads at the counter («putain» is in Lila's sheet; not here).
RUDE_WORDS: tuple[str, ...] = (
    "putain", "merde", "con", "conne", "connard", "connasse", "bordel", "chier", "foutre", "salope", "enfoire",
    "ta gueule", "nique",
)

# ---------------------------------------------------------------------------
# Authored fallbacks (spec §6): a dropped piece never leaves the screen empty
# ---------------------------------------------------------------------------


def _t(fr: str, en: str, de: str) -> ComptoirText:
    return ComptoirText(fr=fr, en=en, de=de)


AUTHORED_REASONS: dict[str, list[ComptoirText]] = {
    "pour": [_t("c'est une bonne idée", "it's a good idea", "es ist eine gute Idee"),
             _t("c'est bien pour les gens", "it's good for people", "es ist gut für die Leute")],
    "contre": [_t("ce n'est pas utile", "it isn't useful", "es ist nicht nützlich"),
               _t("c'est trop", "it's too much", "es ist zu viel")],
    "nuance": [_t("il y a du bon et du mauvais", "there's good and bad", "es gibt Gutes und Schlechtes"),
               _t("je ne sais pas encore", "I don't know yet", "ich weiß es noch nicht")],
}
AUTHORED_FRAMES: dict[str, ComptoirText] = {
    "pour": _t("À mon avis, c'est une bonne idée, parce que", "In my opinion, it's a good idea, because",
               "Meiner Meinung nach ist es eine gute Idee, weil"),
    "contre": _t("À mon avis, ce n'est pas une bonne idée, parce que", "In my opinion, it's not a good idea, because",
                 "Meiner Meinung nach ist es keine gute Idee, weil"),
    "nuance": _t("À mon avis, ça dépend, parce que", "In my opinion, it depends, because",
                 "Meiner Meinung nach kommt es darauf an, weil"),
}
AUTHORED_PHRASE = ComptoirPhrase(
    a1=_t("Je suis pour… / Je suis contre…", "I'm for… / I'm against…", "Ich bin dafür… / Ich bin dagegen…"),
    a2=_t("À mon avis…, parce que…", "In my opinion…, because…", "Meiner Meinung nach…, weil…"),
    b1=_t("Je ne suis pas d'accord avec…, parce que…", "I don't agree with…, because…",
          "Ich bin nicht einverstanden mit…, weil…"),
    b2=_t("Certes…, mais…", "Admittedly…, but…", "Zwar…, aber…"),
)
#: A side whose counter-line the check dropped reads the cast member's own line.
AUTHORED_REPLIES: dict[str, ComptoirText] = {
    ROMY_ID: _t("Voyons donc ! Pour vrai ? Explique-moi ça.", "Come on! Really? Explain that to me.",
                "Ach komm! Wirklich? Erklär mir das."),
    GUS_ID: _t("Laisse-moi t'expliquer la vie : tu as tort. Avec style, mais tort.",
               "Let me explain life to you: you're wrong. With style, but wrong.",
               "Lass mich dir das Leben erklären: Du liegst falsch. Mit Stil, aber falsch."),
    MARGAUX_ID: _t("Chacun son avis. La même chose ?", "Each to their own. Same again?",
                   "Jedem seine Meinung. Nochmal dasselbe?"),
    "lila_bonnet": _t("Mais arrête ! Tu le penses vraiment ?", "Oh, stop it! Do you really think so?",
                      "Hör doch auf! Meinst du das wirklich?"),
    "marin_leveque": _t("Ah… tu crois ? Ma grand-mère ne serait pas d'accord.", "Ah… you think so? My grandmother wouldn't agree.",
                        "Ach… meinst du? Meine Großmutter wäre nicht einverstanden."),
    "landlord_marchand": _t("Voyez-vous, je ne suis pas d'accord. Mais je vous écoute.",
                            "You see, I don't agree. But I'm listening.",
                            "Sehen Sie, ich bin nicht einverstanden. Aber ich höre Ihnen zu."),
}
AUTHORED_COMEBACK = _t("Et toi, tu as toujours raison ?", "And you, are you always right?", "Und du, hast du immer recht?")
AUTHORED_ASK = _t("Et en vrai, c'est quoi ?", "And what is it really?", "Und was stimmt wirklich?")
AUTHORED_CAUGHT = _t("Bon… J'ai arrondi. C'est un art.", "Well… I rounded it. It's an art.", "Na ja… Ich habe gerundet. Das ist eine Kunst.")

# ---------------------------------------------------------------------------
# Who sits at the counter
# ---------------------------------------------------------------------------

_BIBLE = Path(__file__).resolve().parents[2] / "prompts" / "serial" / "world_bible_paris_v2.json"
_SHEET_FIELDS = ("name", "role", "personality", "speech_pattern", "signature_phrases", "flaw")
#: What the bible does not say about the counter (or says for the season, not for a learner).
_SHEET_NOTES: dict[str, dict[str, Any]] = {
    ROMY_ID: {"at_the_counter": "Off duty, among friends, so she has her own opinions; Québécoise, dry, precise, "
                                "proud of Québec."},
    "lila_bonnet": {"speech_pattern": "Rapid-fire, teasing, southern warmth. Slides from the baby-talk she uses on "
                                      "her pupils into devastating one-liners. Exaggerated endearments («mon chou», "
                                      "«ma belle»)."},
    MARGAUX_ID: {"at_the_counter": "She owns Le Mistral and stands behind the counter."},
}
_MARCHAND = {
    "name": "M. Marchand",
    "role": "The landlord of the building; manages flats in the 10e.",
    "personality": "Grumpy, counts everything, suspicious of change, secretly sentimental.",
    "speech_pattern": "Formal «vous», sighs, numbers and rules.",
    "signature_phrases": ["Voyez-vous…", "Tout cela a un coût."],
    "flaw": "Thinks every change will cost him money.",
}


@lru_cache(maxsize=1)
def character_sheets() -> dict[str, dict[str, Any]]:
    """The regulars' sheets for the desk: the world bible's, M. Marchand's, and the notes above."""

    bible = json.loads(_BIBLE.read_text(encoding="utf-8"))
    sheets = {row["id"]: {key: row.get(key) for key in _SHEET_FIELDS} for row in bible.get("cast") or []}
    sheets["landlord_marchand"] = dict(_MARCHAND)
    for cast_id, notes in _SHEET_NOTES.items():
        sheets.setdefault(cast_id, {}).update(notes)
    return sheets


def comptoir_guests(dossier: EditorialDossier) -> list[str]:
    """Who argues about ``dossier``, in seat order: Romy, the topic's guest
    (``policy.GUEST_AFFINITY``, the first with a portrait; Margaux when it is Gus or none),
    then Gus."""

    topic = next((row["id"] for row in policy.GUEST_AFFINITY.get(dossier.topic, []) if row["id"] in COUNTER_GUESTS),
                 None)
    return [ROMY_ID, topic or MARGAUX_ID, GUS_ID]


def name_fr(cast_id: str) -> str:
    return NAME_FR.get(cast_id, cast_id)


def role_fr(cast_id: str) -> str:
    return ROLE_FR.get(cast_id, "")


# ---------------------------------------------------------------------------
# The prompt
# ---------------------------------------------------------------------------

COMPTOIR_SPEC = """{"fit": "debate" | "skip",
 "question": T,
 "guests": [{"id": str, "stance": "pour" | "contre" | "nuance", "a1": T, "a2": T, "b1": T, "quote": T}],
 "intox": {"by": str, "wrong_fr": str, "right_fr": str, "claim_id": str, "distractor_fr": str, "ask": T,
           "caught": T} | null,
 "reasons": {"pour": [T, T, T], "contre": [T, T, T], "nuance": [T, T, T]},
 "frames": {"pour": T, "contre": T, "nuance": T},
 "bank": [T, T, T, T, T, T],
 "phrase": {"a1": T, "a2": T, "b1": T, "b2": T},
 "replies": {"pour": R, "contre": R, "nuance": R}}
where T = {"fr": str, "en": str, "de": str} (en and de translate the French faithfully, every time)
and R = {"by": str, "line": T, "comeback": T}"""

COMPTOIR_RULES = """RULES
- fit: "skip" when the story is a death, a war, a crime with victims, an election or a party's politics, or
  anything where taking sides would be cruel or partisan. Otherwise "debate".
- question: the question of the day, nine words or fewer, plain A2 French, ending with «?», a yes/no question
  about the story's everyday consequences that ordinary people answer differently. «Oui» is the "pour" side.
- guests: one per INPUT guest, in INPUT order, exactly one "pour", one "contre", one "nuance". Each take answers
  the question in that person's own voice (speech pattern, life, job) with a reason from their own life (money,
  noise, pride, fun, the planet, the neighbourhood, work, taste). Make them fun to answer: each take has an
  attitude (a joke, an exaggeration, a confession, a dig at another guest by name) so the learner wants to reply.
  Gus is theatrical and snobbish, Romy dry and proud of Québec, Lila teasing and fast, Marin sentimental («c'est
  un signe»), Margaux one dry line, M. Marchand grumpy with «vous».
  a1: two short present-tense sentences, 14 words at most, the most common words. a2: 26 words at most.
  b1: 42 words at most, with one connector («parce que», «même si», «d'un côté… de l'autre…»).
  quote: the heart of the take in six words at most, printed in Romy's paper; never the false detail.
- The stance must match the words: "pour" says yes, "contre" says no, "nuance" weighs both («ça dépend», «d'un
  côté…», «je ne sais pas») and never says «je suis pour» or «je suis contre».
- Facts: only what the claims say. Numbers in digits, copied exactly from the claims; no other number, except the
  intox. Never a relative date (demain, hier, aujourd'hui, ce soir, cette semaine) nor a weekday the claims do not
  name. No insults, no swearing (never «putain», «merde», «con»), nothing about a real person's private life or
  body. People talk about the story, never about the app: never «dossier», «session», «application»,
  «événement», «sur la table».
- intox: ONE deliberately false detail, so a careful reader can catch it in the facts: a number, a date, a place
  or a name from one claim, changed. by: the guest whose character lies or exaggerates (prefer
  augustin_de_roncourt). wrong_fr: a SHORT phrase (2 to 6 words, «un million de personnes»), not a sentence; it
  sits word for word inside that guest's a1, a2 AND b1, naturally, as if he believed it, and in nobody else's
  take. right_fr: the true value, copied from the French of claim claim_id (2 to 6 words, the same kind:
  «plus de 500 000 personnes»). distractor_fr: another TRUE value of the same kind copied from another claim
  (a number for a number, a place for a place), for the learner to choose between it and right_fr. ask: the
  question that sends the learner back to the facts («Combien de spectateurs, en vrai ?»). caught: what the liar
  says when he is caught, in character, 14 words at most. null when no claim has a number, a date, a place or a
  name to change.
- reasons: three short reasons per side, five words at most, the most common words, each one completing «Je
  suis pour, parce que …» (no «parce que» in it); the "nuance" ones weigh both sides («c'est beau mais cher»).
- frames: the A2 opening for each side, ending with «parce que» (the learner writes the reason after it).
- bank: six words or short phrases (with their article) a learner needs to give a reason on this story.
- phrase: the opinion pattern of each band, as the takes use it (a1 «Je suis pour… / Je suis contre…», a2 «À mon
  avis…, parce que…», b1 «Je ne suis pas d'accord avec…, parce que…», b2 «Certes…, mais…»).
- replies: for each side the learner may take, what a guest of ANOTHER side says back (by: prefer the opposite
  side; for "nuance", the guest with the strongest opinion), in character, 20 words at most, to «tu», ending on a
  question or a jab. The reply speaks to the LEARNER, whom nobody at the counter knows: never another regular's
  name as the one spoken to («Voyons donc, Gus !» is wrong here), and nothing that guesses the learner's gender:
  no «mon cher», «ma chère», «ma belle», «mon grand», no adjective or participle about them («tu es sérieux»,
  «tu es sûre»); ask what they think or do instead («Pour vrai ?», «Tu te lèves à quelle heure ?»).
  comeback: one fun A2 comeback the learner can tap back at that guest, eight words at most: the learner's own
  words, consistent with the learner's side, never another regular's catchphrase (not Gus's champagne or
  silence, not Romy's «voyons donc»).
- French typography: a space before ? ! : ;
EXAMPLE (story: Céline Dion ends her first series of concerts in Paris, more than 500 000 spectators, she comes
back in May 2027; guests romy_tremblay, margaux_barman, augustin_de_roncourt):
{"fit": "debate",
 "question": {"fr": "Céline revient en 2027. Bonne nouvelle ?", "en": "Céline is coming back in 2027. Good news?",
  "de": "Céline kommt 2027 zurück. Eine gute Nachricht?"},
 "guests": [
  {"id": "romy_tremblay", "stance": "pour",
   "a1": {"fr": "Je suis pour ! Céline, c'est le Québec. J'ai pleuré au concert.",
    "en": "I'm for it! Céline is Québec. I cried at the concert.",
    "de": "Ich bin dafür! Céline ist Québec. Ich habe beim Konzert geweint."},
   "a2": {"fr": "Céline, c'est le Québec ! Moi, j'ai pleuré au concert. Ne le dis à personne.",
    "en": "Céline is Québec! I cried at the concert. Don't tell anyone.",
    "de": "Céline ist Québec! Ich habe beim Konzert geweint. Sag es niemandem."},
   "b1": {"fr": "Je suis pour, parce que Céline, c'est un peu ma maison loin de la maison. J'ai pleuré au concert, voyons donc. Si Gus le raconte, je nie tout.",
    "en": "I'm for it, because Céline is a bit of home away from home. I cried at the concert, come on. If Gus tells anyone, I'll deny everything.",
    "de": "Ich bin dafür, weil Céline für mich ein Stück Zuhause in der Ferne ist. Ich habe beim Konzert geweint, na und. Wenn Gus das erzählt, streite ich alles ab."},
   "quote": {"fr": "Céline, c'est le Québec !", "en": "Céline is Québec!", "de": "Céline ist Québec!"}},
  {"id": "margaux_barman", "stance": "nuance",
   "a1": {"fr": "Ça dépend. Les fans, c'est bon pour la caisse. Pas pour mes oreilles.",
    "en": "It depends. Fans are good for the till. Not for my ears.",
    "de": "Kommt drauf an. Fans sind gut für die Kasse. Nicht für meine Ohren."},
   "a2": {"fr": "Des fans au comptoir tous les soirs ? Bon pour la caisse. Mauvais pour mes oreilles.",
    "en": "Fans at the counter every night? Good for the till. Bad for my ears.",
    "de": "Jeden Abend Fans an der Theke? Gut für die Kasse. Schlecht für meine Ohren."},
   "b1": {"fr": "D'un côté, des fans au comptoir tous les soirs, c'est bon pour la caisse. De l'autre, ils chantent jusqu'à la fermeture. Et faux. La même chose ?",
    "en": "On the one hand, fans at the counter every night are good for the till. On the other, they sing until closing time. Out of tune. Same again?",
    "de": "Einerseits sind Fans jeden Abend an der Theke gut für die Kasse. Andererseits singen sie bis zur Sperrstunde. Und falsch. Nochmal dasselbe?"},
   "quote": {"fr": "Bon pour la caisse. Mauvais pour mes oreilles.", "en": "Good for the till. Bad for my ears.",
    "de": "Gut für die Kasse. Schlecht für meine Ohren."}},
  {"id": "augustin_de_roncourt", "stance": "contre",
   "a1": {"fr": "Je suis contre. Un million de personnes ? Moi, j'aime le silence.",
    "en": "I'm against it. A million people? I like silence.",
    "de": "Ich bin dagegen. Eine Million Menschen? Ich mag die Stille."},
   "a2": {"fr": "Un million de personnes pour les mêmes chansons ? Moi, je préfère le silence. Et le champagne.",
    "en": "A million people for the same songs? I prefer silence. And champagne.",
    "de": "Eine Million Menschen für dieselben Lieder? Ich ziehe die Stille vor. Und Champagner."},
   "b1": {"fr": "Mon cher, un million de personnes pour les mêmes chansons, c'est une foule, pas un public. Règle numéro un de La Méthode : on ne se cache pas dans une foule. Je préfère le silence.",
    "en": "My dear, a million people for the same songs is a crowd, not an audience. Rule number one of The Method: you don't hide in a crowd. I prefer silence.",
    "de": "Mein Lieber, eine Million Menschen für dieselben Lieder, das ist eine Menge, kein Publikum. Regel Nummer eins der Methode: Man versteckt sich nicht in der Menge. Ich ziehe die Stille vor."},
   "quote": {"fr": "Je préfère le silence. Et le champagne.", "en": "I prefer silence. And champagne.",
    "de": "Ich ziehe die Stille vor. Und Champagner."}}],
 "intox": {"by": "augustin_de_roncourt", "wrong_fr": "un million de personnes",
  "right_fr": "plus de 500 000 personnes", "claim_id": "c2", "distractor_fr": "seize concerts",
  "ask": {"fr": "Combien de spectateurs, en vrai ?", "en": "How many spectators, really?",
   "de": "Wie viele Zuschauer, wirklich?"},
  "caught": {"fr": "Cinq cent mille, un million… Je suis généreux avec les chiffres.",
   "en": "Five hundred thousand, a million… I'm generous with numbers.",
   "de": "Fünfhunderttausend, eine Million… Ich bin großzügig mit Zahlen."}},
 "reasons": {"pour": [{"fr": "sa voix est belle", "en": "her voice is beautiful", "de": "ihre Stimme ist schön"},
   {"fr": "les fans sont contents", "en": "the fans are happy", "de": "die Fans sind glücklich"},
   {"fr": "c'est bon pour Paris", "en": "it's good for Paris", "de": "es ist gut für Paris"}],
  "contre": [{"fr": "les billets sont chers", "en": "the tickets are expensive", "de": "die Karten sind teuer"},
   {"fr": "la foule me fatigue", "en": "crowds tire me out", "de": "die Menge macht mich müde"},
   {"fr": "je n'aime pas ses chansons", "en": "I don't like her songs", "de": "ich mag ihre Lieder nicht"}],
  "nuance": [{"fr": "c'est beau mais cher", "en": "it's beautiful but expensive", "de": "es ist schön, aber teuer"},
   {"fr": "c'est bien, mais pas trop", "en": "it's good, but not too much", "de": "es ist gut, aber nicht zu oft"},
   {"fr": "une fois, c'est bien", "en": "once is fine", "de": "einmal ist gut"}]},
 "frames": {"pour": {"fr": "À mon avis, c'est une bonne nouvelle, parce que", "en": "In my opinion, it's good news, because",
   "de": "Meiner Meinung nach ist das eine gute Nachricht, weil"},
  "contre": {"fr": "À mon avis, ce n'est pas une bonne nouvelle, parce que", "en": "In my opinion, it's not good news, because",
   "de": "Meiner Meinung nach ist das keine gute Nachricht, weil"},
  "nuance": {"fr": "À mon avis, ça dépend, parce que", "en": "In my opinion, it depends, because",
   "de": "Meiner Meinung nach kommt es darauf an, weil"}},
 "bank": [{"fr": "sa voix", "en": "her voice", "de": "ihre Stimme"}, {"fr": "les fans", "en": "the fans", "de": "die Fans"},
  {"fr": "le concert", "en": "the concert", "de": "das Konzert"}, {"fr": "la foule", "en": "the crowd", "de": "die Menge"},
  {"fr": "trop cher", "en": "too expensive", "de": "zu teuer"}, {"fr": "revenir", "en": "to come back", "de": "zurückkommen"}],
 "phrase": {"a1": {"fr": "Je suis pour… / Je suis contre…", "en": "I'm for… / I'm against…", "de": "Ich bin dafür… / Ich bin dagegen…"},
  "a2": {"fr": "À mon avis…, parce que…", "en": "In my opinion…, because…", "de": "Meiner Meinung nach…, weil…"},
  "b1": {"fr": "Je ne suis pas d'accord avec…, parce que…", "en": "I don't agree with…, because…", "de": "Ich bin nicht einverstanden mit…, weil…"},
  "b2": {"fr": "Certes…, mais…", "en": "Admittedly…, but…", "de": "Zwar…, aber…"}},
 "replies": {"pour": {"by": "augustin_de_roncourt",
   "line": {"fr": "Toi aussi ? Les mêmes chansons, encore et encore ? Tu n'en as pas marre ?",
    "en": "You too? The same songs, again and again? Aren't you fed up?",
    "de": "Du auch? Immer wieder dieselben Lieder? Hast du nicht genug davon?"},
   "comeback": {"fr": "Et toi, tu chantes sous la douche !", "en": "And you sing in the shower!", "de": "Und du singst unter der Dusche!"}},
  "contre": {"by": "romy_tremblay",
   "line": {"fr": "Voyons donc ! Tu es contre Céline ? Tu as déjà écouté sa voix, au moins ?",
    "en": "Come on! You're against Céline? Have you ever even listened to her voice?",
    "de": "Ach komm! Du bist gegen Céline? Hast du ihre Stimme überhaupt schon mal gehört?"},
   "comeback": {"fr": "Oui, et ses chansons me fatiguent !", "en": "Yes, and her songs tire me out!",
    "de": "Ja, und ihre Lieder machen mich müde!"}},
  "nuance": {"by": "augustin_de_roncourt",
   "line": {"fr": "Ni pour ni contre ? C'est la position du canapé. Choisis !",
    "en": "Neither for nor against? That's the sofa position. Choose!",
    "de": "Weder dafür noch dagegen? Das ist die Sofa-Position. Entscheide dich!"},
   "comeback": {"fr": "Le canapé, c'est confortable !", "en": "The sofa is comfortable!", "de": "Das Sofa ist bequem!"}}}}
Do not reuse the example's lines: write for THIS story and THESE guests."""

COMPTOIR_DESK_INSTRUCTIONS = (
    """You write «Au comptoir» for «Le Papier de Romy», a French-learning app. Every morning the regulars of Le
Mistral, a Paris café, argue about ONE news story over coffee; Romy, a Québécoise journalist, is writing a vox pop
for her paper. The learner reads what happened, hears the three takes, catches the one false detail, then gives
their own opinion. From INPUT (the story's French facts and today's three guests, each with a character sheet)
answer with ONE JSON object:
"""
    + COMPTOIR_SPEC
    + "\n"
    + COMPTOIR_RULES
)
DESK_SYSTEM = "You write lively, in-character, correct French for language learners. Answer with one JSON object only."

# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

_WORD = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*|\d+(?:[\s.,]\d+)*")
#: A number as the French write it: «500 000», «9,9», «2027».
_NUMBER = re.compile(r"\d{1,3}(?:[\s.]\d{3})+(?:,\d+)?|\d+(?:,\d+)?")
_ELLIPSIS = re.compile(r"\s*(?:…|\.\.\.)\s*$")


def word_count(text: str | None) -> int:
    """Words and numbers («500 000» is one), never punctuation («Oui !» is one word)."""

    return len(_WORD.findall(str(text or "")))


def numbers(text: str | None) -> set[str]:
    """The numbers in ``text``, digits only («500 000» → ``"500000"``, «9,9» → ``"9.9"``)."""

    return {re.sub(r"[\s.]", "", match).replace(",", ".") for match in _NUMBER.findall(str(text or ""))}


_NUMBER_WORDS = frozenset("""
    deux trois quatre cinq six sept huit neuf dix onze douze treize quatorze quinze seize vingt trente quarante
    cinquante soixante cent cents mille million millions milliard milliards moitie quart double
    fois heure heures jour jours semaine semaines mois an ans annee annees siecle siecles euro euros
""".split())


def numeric(text: str | None) -> bool:
    """A number or a quantity, in digits or in words («seize concerts», «un million», «au
    moins un mois»): the intox's kind (a number for a number, a place for a place)."""

    return bool(numbers(text)) or bool(set(re.findall(r"[a-z]+", ci(text))) & _NUMBER_WORDS)


#: What a value may start with that the story need not repeat («à Montmartre» ← «de Montmartre»).
_VALUE_HEAD = re.compile(r"^(?:sur les|sur la|sur le|sur|aux|au|a|en|dans|des|du|de|les|le|la)\s+|^l'")


def in_story(story: str, value: str) -> bool:
    """``value`` is in ``story``, word for word or without its leading preposition."""

    if contains(story, value):
        return True
    bare = _VALUE_HEAD.sub("", ci(value).strip(" .,!?…"))
    return word_count(bare) >= 1 and bare != ci(value) and contains(story, bare)


def ci(text: str | None) -> str:
    """Case- and accent-folded, quotes folded, spaces collapsed: what the intox check compares."""

    decomposed = unicodedata.normalize("NFKD", fold(text).casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def contains(text: str | None, phrase: str | None) -> bool:
    folded = ci(phrase).strip(" .,!?…")
    return bool(folded) and folded in ci(text)


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


#: A pet name that says who the learner is («mon cher», «ma belle»): nobody at the counter knows.
_GENDERED_ADDRESS = re.compile(
    r"(?<![\w-])(?:mon cher|ma chere|mon cheri|ma cherie|ma belle|mon beau|mon grand|ma grande|ma jolie|"
    r"mon vieux|ma vieille|mon pote|ma pote|mon gars|ma fille|mon garcon|mademoiselle)(?![\w-])"
)
#: «tu es» and an adjective that agrees with the learner («tu es sérieux», «tu es sûre»).
_GENDERED_YOU = re.compile(
    r"(?<![\w-])(?:tu es|t'es|es-tu|tu etais|tu seras)\s+(?:vraiment\s+|si\s+|trop\s+|bien\s+)?"
    r"(?:serieux|serieuse|sure?|fou|folle|prete?|certaine?|contente?|heureux|heureuse|fatiguee?|jaloux|jalouse|"
    r"amoureux|amoureuse|seule?|naif|naive|curieux|curieuse|genereux|genereuse|perdue?|fier|fiere|un tiede|"
    r"une tiede|gentil|gentille|nul|nulle|malin|maligne)(?![\w-])"
)


def address_problem(fr: str | None, speaker: str) -> str | None:
    """Why a line said TO the learner speaks to someone else or guesses who they are: another
    regular's name as the one addressed («Voyons donc, Gus !»), a gendered pet name («mon
    cher»), an adjective agreeing with «tu» («tu es sérieux»). ``None`` when it is fine."""

    folded = ci(fr)
    if _GENDERED_ADDRESS.search(folded) or _GENDERED_YOU.search(folded):
        return "gendered_address"
    for cast_id, name in NAME_FR.items():
        if cast_id == speaker:
            continue
        key = re.escape(ci(name))
        if re.search(rf"(?:^|[,.!?…:;]\s*){key}\s*[,!?.…]|,\s*{key}\s*(?:[,!?.…]|$)", folded):
            return "addresses_other"
    return None


_LOWERED_STARTS = {"plus", "moins", "un", "une", "le", "la", "les", "des", "du", "au", "aux", "a", "en", "dans",
                   "environ", "pres", "seulement", "presque", "sept", "six", "cinq", "quatre", "trois", "deux"}


def _value(value: Any) -> str:
    """An intox value as it sits inside a sentence: «Plus de 500 000 personnes» → «plus de 500 000
    personnes» (a name keeps its capital), no final stop."""

    text = _clean(value).strip(" .;:«»\"")
    head = ci(text.split(" ", 1)[0]) if text else ""
    if head in _LOWERED_STARTS or head.startswith(("l'", "d'")):
        text = text[:1].lower() + text[1:]
    return text


# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------


class _Checker:
    """What a line at the counter may say about ``dossier``."""

    def __init__(self, dossier: EditorialDossier) -> None:
        from app.services.revue.leads import (
            _weekdays_known,  # noqa: PLC0415 - the leads' Temporal rule
        )

        self.dossier = dossier
        story = " ".join([dossier.title_fr, dossier.summary_fr, *(c.fr for c in dossier.claims)])
        self.story = story
        self.known = numbers(story)
        self.weekdays = _weekdays_known(dossier)

    def problem(self, fr: str, limit: int, *, allow: str | None = None) -> str | None:
        """Why ``fr`` cannot be read at the counter, or ``None``. ``allow``: the intox's
        ``wrong_fr``, whose numbers the liar's lines may carry («Le 17, le 18…»)."""

        from app.services.revue.checks import _relative_dates  # noqa: PLC0415
        from app.services.revue.leads import _weekdays  # noqa: PLC0415

        if not fr:
            return "empty"
        if word_count(fr) > limit:
            return "too_long"
        if _relative_dates(fr, weekdays_allowed=True) or _weekdays(fr) - self.weekdays:
            return "relative_date"
        if voice.id_leaks(fr):
            return "id_leak"
        if voice.app_words(fr) or voice.meta_words(fr):
            return "app_words"
        folded = f" {ci(fr)} "
        if any(re.search(rf"(?<![\w-]){re.escape(word)}(?![\w-])", folded) for word in RUDE_WORDS):
            return "rude"
        if numbers(fr) - self.known - numbers(allow):
            return "number_not_in_claims"
        return None

    def text(self, row: Any, limit: int, *, allow: str | None = None) -> tuple[ComptoirText | None, str | None]:
        if isinstance(row, str):
            row = {"fr": row}
        if not isinstance(row, dict):
            return None, "missing"
        fr = _clean(row.get("fr"))
        why = self.problem(fr, limit, allow=allow)
        if why:
            return None, why
        translations = {lang: (_clean(row.get(lang))[:TRANSLATION_MAX_CHARS] or None) for lang in ("en", "de")}
        return ComptoirText(fr=voice.french_typography(fr), **translations), None


def _stance_problem(text: str, stance: str) -> bool:
    """The words take another side than ``stance`` («je suis pour» in a «contre» take)."""

    folded = ci(text)
    says_pour, says_contre = "je suis pour" in folded, "je suis contre" in folded
    if stance == "nuance":
        return says_pour or says_contre
    return says_contre if stance == "pour" else says_pour


#: The words a sentence may start with that are lower case inside one («Les fans…» → «les fans…»).
_COMMON_STARTS = {
    "c", "ce", "ca", "cela", "il", "elle", "ils", "elles", "on", "je", "j", "tu", "nous", "vous", "les", "le", "la",
    "l", "un", "une", "des", "du", "sa", "son", "ses", "mon", "ma", "mes", "ton", "ta", "tes", "leur", "leurs",
    "tout", "tous", "toute", "trop", "pas", "plus", "moins", "n", "y", "en", "personne", "rien", "notre", "votre",
    "quel", "quelle", "beaucoup", "peu", "au", "aux", "a", "pour", "avec", "sans", "j'aime", "c'est",
}


def _lower_start(text: str) -> str:
    head = re.split(r"[\s'’]", ci(text), maxsplit=1)[0] if text else ""
    return text[:1].lower() + text[1:] if head in _COMMON_STARTS else text


def _reason(fr: Any) -> str:
    """A reason tile completes «… parce que …»: no «parce que» of its own, no final stop, lower case."""

    text = re.sub(r"^(?:parce qu['’]|parce que|car)\s*", "", _clean(fr), flags=re.IGNORECASE).strip(" .!…")
    return _lower_start(text)


def _frame(fr: str) -> str:
    """An A2 frame ends on «parce que» (the learner writes the reason after it)."""

    text = _ELLIPSIS.sub("", _clean(fr)).rstrip(" ,.:")
    if not re.search(r"(?:parce que|parce qu['’]|car)$", ci(text)):
        text = f"{text}, parce que"
    return text


def _intox(raw: Any, guests: list[dict[str, Any]], ids: list[str], check: _Checker) -> tuple[ComptoirIntox | None, list[str]]:
    """The intox the desk planted, checked against the claims; ``None`` with the reason when
    it is dropped."""

    if not isinstance(raw, dict) or not raw:
        return None, ["comptoir:intox:missing"]
    dossier = check.dossier
    by = _clean(raw.get("by"))
    wrong, right, distractor = _value(raw.get("wrong_fr")), _value(raw.get("right_fr")), _value(raw.get("distractor_fr"))
    if by not in ids:
        return None, ["comptoir:intox:by"]
    if not 1 <= word_count(wrong) <= INTOX_MAX_WORDS:
        return None, ["comptoir:intox:wrong_length"]
    if contains(check.story, wrong):
        return None, ["comptoir:intox:not_false"]
    claims = dossier.claims_by_id()
    claim_id = _clean(raw.get("claim_id"))
    if not right or word_count(right) > VALUE_MAX_WORDS:
        return None, ["comptoir:intox:right_length"]
    if claim_id not in claims or not contains(claims[claim_id].fr, right):
        found = [c.id for c in dossier.claims if contains(c.fr, right)]
        if not found:
            return None, ["comptoir:intox:right_not_in_claim"]
        claim_id = found[0]
    if ci(right) == ci(wrong) or contains(right, wrong):
        return None, ["comptoir:intox:right_is_wrong"]
    if (not distractor or word_count(distractor) > VALUE_MAX_WORDS or not in_story(check.story, distractor)
            or ci(distractor) in {ci(right), ci(wrong)} or contains(right, distractor) or contains(distractor, right)
            or numeric(right) != numeric(distractor)):
        return None, ["comptoir:intox:distractor"]
    if numbers(right) and not numbers(right) <= check.known:
        return None, ["comptoir:intox:right_number"]
    problems: list[str] = []
    ask, why = check.text(raw.get("ask"), ASK_MAX_WORDS)
    if ask is None:
        problems.append(f"comptoir:intox:ask:{why}")
        ask = AUTHORED_ASK
    caught, why = check.text(raw.get("caught"), CAUGHT_MAX_WORDS, allow=wrong)
    if caught is None:
        problems.append(f"comptoir:intox:caught:{why}")
        caught = AUTHORED_CAUGHT
    liar = next(row for row in guests if row.get("id") == by)
    bands = [band for band in ("a1", "a2", "b1") if contains(_take_fr(liar, band), wrong)]
    if not bands:
        return None, ["comptoir:intox:not_in_takes"]
    return ComptoirIntox(by=by, wrong_fr=wrong, right_fr=right, claim_id=claim_id, distractor_fr=distractor,
                         ask=ask, caught=caught, bands=bands), problems  # type: ignore[arg-type]


def _take_fr(row: dict[str, Any], band: str) -> str:
    value = row.get(band)
    return _clean(value.get("fr") if isinstance(value, dict) else value)


_SENTENCE = re.compile(r"[^.!?…]+[.!?…]*")


def sentences(text: str) -> list[str]:
    return [chunk.strip() for chunk in _SENTENCE.findall(text or "") if chunk.strip(" .!?…")]


def _spare_quote(texts: dict[str, ComptoirText], planted: str) -> str | None:
    """The heart of a take when the desk's quote failed: its first sentence of three to eight
    words that takes no side out loud and carries no false detail."""

    for text in texts.values():
        for sentence in sentences(text.fr):
            folded = ci(sentence)
            if (3 <= word_count(sentence) <= QUOTE_MAX_WORDS and not (planted and contains(sentence, planted))
                    and not folded.startswith(("je suis pour", "je suis contre", "ca depend"))):
                return sentence
    return None


def repair_comptoir(raw: Any, dossier: EditorialDossier) -> tuple[ComptoirTakes | None, list[str]]:
    """What the takes desk wrote, checked against ``dossier`` (spec §2.3), with the repairs
    made. ``(None, ["skip"])`` when the desk judged the story unfit for an argument;
    ``(None, problems)`` when it is refused; else the takes and what was dropped."""

    if not isinstance(raw, dict):
        return None, ["comptoir:missing"]
    if _clean(raw.get("fit")).lower() == "skip":
        return None, ["skip"]
    check = _Checker(dossier)
    ids = comptoir_guests(dossier)
    rows = raw.get("guests") or raw.get("takes")
    seated = [row.get("id") if isinstance(row, dict) else None for row in rows] if isinstance(rows, list) else []
    if sorted(map(str, seated)) != sorted(ids):
        return None, ["comptoir:guests:order"]
    if seated != ids:  # the right three, in another order: seat them (nothing is lost)
        rows = sorted(rows, key=lambda row: ids.index(row["id"]))
    if sorted(str(row.get("stance")) for row in rows) != sorted(COMPTOIR_STANCES):
        return None, ["comptoir:guests:stances"]

    question, why = check.text(raw.get("question"), QUESTION_MAX_WORDS)
    if question is None or not question.fr.rstrip().endswith("?"):
        return None, [f"comptoir:question:{why or 'not_a_question'}"]

    intox, problems = _intox(raw.get("intox"), rows, ids, check)
    planted = _value((raw.get("intox") or {}).get("wrong_fr")) if isinstance(raw.get("intox"), dict) else ""
    refusals: list[str] = []
    guests: list[ComptoirGuest] = []
    for row in rows:
        cast_id, stance = str(row["id"]), str(row["stance"])
        liar = intox is not None and intox.by == cast_id
        texts: dict[str, ComptoirText] = {}
        for band, limit in TAKE_MAX_WORDS.items():
            text, why = check.text(row.get(band), limit, allow=intox.wrong_fr if liar else None)
            if text is not None and _stance_problem(text.fr, stance):
                why = "stance"
            if text is not None and planted and not liar and contains(text.fr, planted):
                why = "uncorrected_intox"  # a false detail the intox step would not correct
            if why:
                refusals.append(f"comptoir:{cast_id}:{band}:{why}")
                continue
            texts[band] = text  # type: ignore[assignment]
        quote, why = check.text(row.get("quote"), QUOTE_MAX_WORDS)
        if quote is not None and planted and contains(quote.fr, planted):
            quote, why = None, "intox_in_quote"
        if quote is None:
            spare = _spare_quote(texts, planted)
            if spare:
                quote = ComptoirText(fr=spare)
                problems.append(f"comptoir:{cast_id}:quote:{why}")
            else:
                refusals.append(f"comptoir:{cast_id}:quote:{why}")
        if len(texts) == 3 and quote is not None:
            guests.append(ComptoirGuest(id=cast_id, stance=stance, quote=quote,  # type: ignore[arg-type]
                                        take=ComptoirTake(**texts)))
    if refusals:
        return None, [*refusals, *problems]

    reasons: dict[str, list[ComptoirText]] = {}
    frames: dict[str, ComptoirText] = {}
    replies: dict[str, ComptoirReply] = {}
    stance_of = {guest.id: guest.stance for guest in guests}
    for stance in COMPTOIR_STANCES:
        kept: list[ComptoirText] = []
        for index, row in enumerate((_section(raw, "reasons").get(stance) or [])[:3]):
            row = {"fr": row} if isinstance(row, str) else row
            fixed = {**row, "fr": _reason(row.get("fr"))} if isinstance(row, dict) else row
            text, why = check.text(fixed, REASON_MAX_WORDS)
            if text is None:
                problems.append(f"comptoir:reason:{stance}:{index}:{why}")
            elif ci(text.fr) not in {ci(k.fr) for k in kept}:
                kept.append(text)
        if not kept:
            problems.append(f"comptoir:reason:{stance}:authored")
        reasons[stance] = kept or list(AUTHORED_REASONS[stance])

        row = _section(raw, "frames").get(stance)
        row = {"fr": row} if isinstance(row, str) else row
        text, why = check.text({**row, "fr": _frame(row.get("fr"))} if isinstance(row, dict) else row, FRAME_MAX_WORDS)
        if text is None:
            problems.append(f"comptoir:frame:{stance}:{why}")
        frames[stance] = text or AUTHORED_FRAMES[stance]

        row = _section(raw, "replies").get(stance)
        reply = _reply(row, stance, stance_of, check, planted)
        if isinstance(reply, str):
            problems.append(f"comptoir:reply:{stance}:{reply}")
        else:
            replies[stance] = reply

    bank: list[ComptoirText] = []
    for index, row in enumerate((raw.get("bank") if isinstance(raw.get("bank"), list) else [])[:8]):
        text, why = check.text(row, BANK_MAX_WORDS)
        if text is None:
            problems.append(f"comptoir:bank:{index}:{why}")
        elif ci(text.fr) not in {ci(b.fr) for b in bank} and len(bank) < 6:
            bank.append(text)

    phrase: dict[str, ComptoirText] = {}
    for band in ("a1", "a2", "b1", "b2"):
        text, why = check.text(_section(raw, "phrase").get(band), PHRASE_MAX_WORDS)
        if text is None:
            problems.append(f"comptoir:phrase:{band}:{why}")
        phrase[band] = text or getattr(AUTHORED_PHRASE, band)

    takes = ComptoirTakes(
        question=question,
        guests=guests,
        intox=intox,
        reasons=reasons,  # type: ignore[arg-type]
        frames=frames,  # type: ignore[arg-type]
        bank=bank,
        phrase=ComptoirPhrase(**phrase),
        replies=replies,  # type: ignore[arg-type]
    )
    return takes, problems


def as_desk_answer(takes: ComptoirTakes) -> dict[str, Any]:
    """``takes`` in the desk's answer shape, so :func:`audit` can run the same checks on
    stored or hand-edited takes (the evergreens' files, the tests)."""

    data = takes.model_dump(mode="json")
    return {
        "fit": "debate",
        "question": data["question"],
        "guests": [{"id": g["id"], "stance": g["stance"], **g["take"], "quote": g["quote"]} for g in data["guests"]],
        "intox": data["intox"],
        "reasons": data["reasons"],
        "frames": data["frames"],
        "bank": data["bank"],
        "phrase": data["phrase"],
        "replies": data["replies"],
    }


def audit(takes: ComptoirTakes, dossier: EditorialDossier) -> list[str]:
    """Every check :func:`repair_comptoir` would make on ``takes`` for ``dossier``: ``[]``
    when nothing would be dropped or refused."""

    repaired, problems = repair_comptoir(as_desk_answer(takes), dossier)
    if repaired is not None and (repaired.intox is None) != (takes.intox is None):
        problems = [*problems, "comptoir:intox:dropped"]
    return problems if repaired is not None else problems or ["comptoir:refused"]


def _section(raw: dict[str, Any], key: str) -> dict[str, Any]:
    value = raw.get(key)
    return value if isinstance(value, dict) else {}


def _reply(row: Any, stance: str, stance_of: dict[str, str], check: _Checker, planted: str) -> ComptoirReply | str:
    """One side's counter-line, or why it was dropped."""

    if not isinstance(row, dict):
        return "missing"
    by = _clean(row.get("by"))
    if by not in stance_of or stance_of[by] == stance:
        return "by"
    line, why = check.text(row.get("line"), REPLY_MAX_WORDS)
    if line is None:
        return f"line:{why}"
    if planted and contains(line.fr, planted):
        return "line:intox"
    address = address_problem(line.fr, by)
    if address:
        return f"line:{address}"
    comeback, why = check.text(row.get("comeback"), COMEBACK_MAX_WORDS)
    return ComptoirReply(by=by, line=line, comeback=comeback or AUTHORED_COMEBACK)


def reply_for(takes: ComptoirTakes, stance: str) -> ComptoirReply:
    """The counter-line for a learner on ``stance``: the desk's, else the authored line of the
    guest on the opposite side (for «nuance», the «contre» guest)."""

    reply = takes.replies.get(stance)  # type: ignore[call-overload]
    if reply is not None:
        return reply
    opposite = {"pour": "contre", "contre": "pour", "nuance": "contre"}[stance]
    guest = takes.by_stance(opposite)
    return ComptoirReply(by=guest.id, line=AUTHORED_REPLIES.get(guest.id, AUTHORED_REPLIES[ROMY_ID]),
                         comeback=AUTHORED_COMEBACK)


# ---------------------------------------------------------------------------
# The desk
# ---------------------------------------------------------------------------


def desk_payload(dossier: EditorialDossier) -> dict[str, Any]:
    """What the takes desk reads: the story's French (never its sources' text) and the guests."""

    sheets = character_sheets()
    return {
        "title_fr": dossier.title_fr,
        "summary_fr": dossier.summary_fr,
        "claims": [{"id": c.id, "kind": c.kind, "fr": c.fr, "attributed_to": c.attributed_to} for c in dossier.claims],
        "topic": dossier.topic,
        "guests": [{"id": cast_id, **sheets.get(cast_id, {"name": name_fr(cast_id)})} for cast_id in comptoir_guests(dossier)],
    }


def desk_model() -> str:
    from app.config import settings

    return str(getattr(settings, "REVUE_COMPTOIR_MODEL", "") or "") or "claude-haiku-5-5"


def desk_provider(model: str | None = None) -> Any:
    from app.services.revue.encounter import (
        OpenAIRevueProvider,  # noqa: PLC0415 - encounter imports this module
    )

    return OpenAIRevueProvider(name="openai-revue-comptoir-desk", max_tokens=7000, model=model or desk_model())


def write_comptoir(dossier: EditorialDossier, provider: Any = None) -> tuple[ComptoirTakes | None, list[str]]:
    """The takes desk: one JSON call (a second with the problems when the first was refused
    or lost its intox), checked by :func:`repair_comptoir`. ``(None, ["skip"])`` for a story
    unfit for an argument; ``(None, problems)`` when nothing passes or the call fails."""

    provider = provider if provider is not None else desk_provider()
    payload = desk_payload(dossier)
    best: ComptoirTakes | None = None
    best_problems: list[str] = []
    problems: list[str] = []
    for attempt in range(2):
        ask = payload if attempt == 0 else {**payload, "retry_feedback": {"problems": problems}}
        try:
            raw = provider.ask_json(COMPTOIR_DESK_INSTRUCTIONS, ask, system=DESK_SYSTEM, temperature=0.8,
                                    label="write_comptoir")
        except Exception as exc:  # noqa: BLE001 - the story stays chat-only
            logger.bind(dossier=dossier.id).warning("revue comptoir desk failed ({})", exc)
            problems = ["comptoir:desk_failed"]
            break
        takes, problems = repair_comptoir(raw, dossier)
        if problems == ["skip"]:
            return None, problems
        if takes is not None and (best is None or (best.intox is None and takes.intox is not None)):
            best, best_problems = takes, problems
        if best is not None and best.intox is not None:
            break
    if best is None:
        return None, problems
    model = getattr(provider, "model", None) or desk_model()
    return best.model_copy(update={"model": str(model), "written_at": datetime.now(UTC),
                                   "prompt_version": COMPTOIR_PROMPT_VERSION}), best_problems


def _kiosk_rows(db: Any, period: str) -> list[Any]:
    from sqlalchemy import select

    from app.db.models.revue_session import RevueDossier
    from app.services.revue.leads import kiosk_periods

    return list(db.scalars(
        select(RevueDossier)
        .where(RevueDossier.period.in_(kiosk_periods(period)))
        .order_by(RevueDossier.period.desc(), RevueDossier.id.asc())  # today's first
    ))


def ensure_comptoir(db: Any, period: str, *, provider: Any = None) -> list[str]:
    """Give every dossier in ``period``'s kiosk without takes a try at the takes desk, once
    (``checks["comptoir"]`` records a refusal, or ``"skip"``, so the row is not asked again);
    an evergreen reads the takes shipped with it. Returns the ids that got takes."""

    from app.services.revue.evergreen import evergreen_takes

    done: list[str] = []
    changed = False
    for row in _kiosk_rows(db, period):
        if (row.payload or {}).get("comptoir") or (row.checks or {}).get("comptoir"):
            continue
        try:
            dossier = EditorialDossier.model_validate(row.payload)
        except Exception as exc:  # noqa: BLE001 - an unreadable row is left to the kiosk's own guard
            logger.bind(row=row.id).debug("revue comptoir: stored dossier unreadable ({})", exc)
            continue
        takes = evergreen_takes(dossier.id) if dossier.evergreen else None
        problems: list[str] = []
        if takes is None:
            takes, problems = write_comptoir(dossier, provider)
        changed = True
        if takes is None:
            row.checks = {**(row.checks or {}), "comptoir": "skip" if problems == ["skip"] else ",".join(problems) or "refused"}
            logger.bind(dossier=dossier.id, problems=problems).info("revue comptoir: no takes; the story stays a chat")
            continue
        row.payload = {**row.payload, "comptoir": takes.model_dump(mode="json")}
        done.append(dossier.id)
    if changed:
        db.commit()
    return done


#: Stories with no stored row (an authored weekly file) asked once per process.
_ROWLESS: dict[str, ComptoirTakes | None] = {}


def forget_cache() -> None:
    _ROWLESS.clear()


def takes_at_start(db: Any, dossier: EditorialDossier, period: str, *, provider: Any = None) -> tuple[ComptoirTakes | None, float]:
    """The takes a session on ``dossier`` plays (spec §2.6), and what a desk call cost: the
    dossier's own, the evergreen's shipped ones, the kiosk row's; else, unless a refusal is
    recorded, one synchronous desk call whose answer is stored on the row (or, without a
    row, kept for the process). ``None``: the session is a chat."""

    from app.services.revue.evergreen import evergreen_takes

    if dossier.comptoir is not None:
        return dossier.comptoir, 0.0
    if dossier.evergreen:
        shipped = evergreen_takes(dossier.id)
        if shipped is not None:
            return shipped, 0.0
    try:
        rows = [row for row in _kiosk_rows(db, period) if (row.payload or {}).get("id") == dossier.id]
    except Exception as exc:  # noqa: BLE001 - no table: a file-built kiosk
        logger.debug("revue comptoir: kiosk rows unreadable ({})", exc)
        rows = []
    for row in rows:
        if (row.checks or {}).get("comptoir"):
            return None, 0.0
        if (row.payload or {}).get("comptoir"):
            try:
                return ComptoirTakes.model_validate(row.payload["comptoir"]), 0.0
            except Exception as exc:  # noqa: BLE001 - an unreadable answer: ask again
                logger.bind(dossier=dossier.id).warning("revue comptoir: stored takes unreadable ({})", exc)
    if not rows and dossier.id in _ROWLESS:
        return _ROWLESS[dossier.id], 0.0
    provider = provider if provider is not None else desk_provider()
    before = float(getattr(provider, "spent_usd", 0.0) or 0.0)
    takes, problems = write_comptoir(dossier, provider)
    cost = round(float(getattr(provider, "spent_usd", 0.0) or 0.0) - before, 6)
    if problems == ["comptoir:desk_failed"]:
        return None, cost  # a failed call is asked again by the next session or the morning
    if not rows:
        _ROWLESS[dossier.id] = takes
        return takes, cost
    for row in rows:
        if takes is None:
            row.checks = {**(row.checks or {}), "comptoir": "skip" if problems == ["skip"] else ",".join(problems) or "refused"}
        else:
            row.payload = {**row.payload, "comptoir": takes.model_dump(mode="json")}
    db.commit()
    return takes, cost


def comptoir_enabled() -> bool:
    from app.config import settings

    return bool(getattr(settings, "REVUE_ENABLED", False) and getattr(settings, "REVUE_COMPTOIR_ENABLED", False))


__all__ = [
    "AUTHORED_REPLIES",
    "COMPTOIR_DESK_INSTRUCTIONS",
    "COMPTOIR_PROMPT_VERSION",
    "NAME_FR",
    "ROLE_FR",
    "address_problem",
    "character_sheets",
    "comptoir_enabled",
    "comptoir_guests",
    "desk_payload",
    "ensure_comptoir",
    "repair_comptoir",
    "reply_for",
    "takes_at_start",
    "write_comptoir",
]
