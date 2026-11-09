"""#145: the reply is written from the scene's record, and checked against it narrowly.

Two earlier guards (#600, #631) judged meaning with clause patterns and refused natural
French in every scene, at the cost of the learner's turn. So:

* every sentence those reviews said must pass is run against every check here, with the
  ledger that would be most likely to catch it; one firing fails the test;
* every check is a ``SoftRejection``: it can only cost one retry;
* each firing reaches the pilot ledger as a code and an outcome, never as text.

The walk text is exact. No model call.
"""

from __future__ import annotations

import pytest

from app.services import lane_guards, scene_ledger
from app.services import living_story as engine
from app.services import story_lanes as lanes

CAMILLE_OPENING = "L'appartement paie d'abord mon grand-père. Vous êtes d'accord, non ?"
CAMILLE_REFUSED = "Non, je ne suis pas daccord. Pourquoi le appartement paie grand-pere dabord ?"
CAMILLE_WALK_REPLY = "Je ne suis pas d'accord non plus. Mais pourquoi cette question ?"
BERLIN_OPENING = "Vous venez de Berlin ?"
BERLIN_ASKS = "Oui. Et vous, vous venez d'où ?"


def _payload(opening: str, learner: str, history: list[dict] | None = None, level: str = "B1") -> dict:
    rows = history or []
    return {
        "story": {"level": level, "learner": {"address": "neutral"}, "control_language": "en", "commitments": []},
        "scene": {"character_id": "camille", "opening_line_fr": opening, "objective_native": "", "panels": []},
        "learner_text": learner,
        "history": rows,
        "targets": [],
        "turn_plan": {},
        "ledger": scene_ledger.build(opening_line_fr=opening, history=rows, learner_text=learner),
    }


CAMILLE = _payload(CAMILLE_OPENING, CAMILLE_REFUSED)
BERLIN = _payload(BERLIN_OPENING, BERLIN_ASKS)
CAT = _payload("Tu as un animal ?", "Comment s'appelle ton chat ?")


def _codes(reply: str, payload: dict) -> list[str]:
    return [finding.code for finding in lane_guards.scene_findings(reply, payload)]


# ---------------------------------------------------------------------------
# What must pass: the reviewers' lines of #600 and #631, and replies the walks praised
# ---------------------------------------------------------------------------

REVIEWERS_LINES = [
    ("Moi, je suis de Lyon, et vous ?", BERLIN),
    ("Je viens de Lyon, vous connaissez ?", BERLIN),
    ("Je suis de Lyon et vous ?", BERLIN),
    ("Moi je viens de Lyon et toi ?", BERLIN),
    ("Parce qu'il m'a élevé, vous comprenez ?", CAMILLE),
    ("Oui, bien sûr, et vous ?", CAMILLE),
    ("C'est lui qui m'a élevée, vous comprenez ?", CAMILLE),
    ("Parce que c'est lui qui a payé, non ?", CAMILLE),
    ("Moi aussi, je n'aime pas les dettes. Il m'a élevée.", CAMILLE),
    ("Il fait beau, n'est-ce pas ?", CAMILLE),
    ("Ni moi ni mon frère ne céderons. Sa dette passe d'abord, parce qu'il m'a élevée.", CAMILLE),
    ("Mon frère non plus ne cédera pas. Il m'a élevée, voilà pourquoi.", CAMILLE),
    ("Mon chat s'appelle Napoléon, tu veux le voir ?", CAT),
]

#: What the walks saw and liked, against the ledger of the turn it answered.
PRAISED_REPLIES = [
    # 4 Nov, #518: «reply 2: answered on the point».
    ("Non, pas faim. Merci de ne pas lire la lettre.", _payload("Tu lis la lettre ?", "Non, je ne vois pas la lettre. Je veux pas lire. Tu as faim ?")),
    # 2 Nov, #467: Marin answered «tu as faim ?».
    ("Napoléon est un bon nom pour le menu ! Oui, j'ai faim. Tu cuisines ?", _payload("On garde quel canapé ?", "Oui, je garde Napoléon. Il est dans le canapé. Marin, tu as faim?")),
    # 3 Nov, #500.
    ("Ah, Napoléon au milieu ! Pourquoi cette photo ?", _payload("Quelle photo va au milieu ? Et pourquoi celle-là ?", "non, je préfère la photo de mon chat Napoléon")),
    # 6 Nov, #558: Margaux and Gus answered.
    ("Peut-être. Mais ce sont ses mots. Pas mes mots.", _payload("Tu m'en veux ?", "Oui, un peu. Tu as menti pendant trois ans a ma grand-mere. Mais je veux comprendre pourquoi tu as fait ca.")),
    # 6 Nov, #556: Gus's paraphrase was correct.
    ("Tu savais pour le Mistral, mais tu hésites à le garder.", _payload("Tu mets les photos au mur. Tu sais ça ?", "Oui, je savais. Ma grand-mère elle a laissé le Mistral à moi, mais je suis pas sûr de le garder.")),
    # #518's expected reaction to the dinosaur.
    ("Un dinosaure ? Sérieusement ?", _payload("Tu as lu la lettre ?", "Mon voisin a un dinosaure dans le jardin. Il mange la lettre !")),
    # A character giving way in so many words is the character's right.
    ("Vous avez raison, il peut attendre.", CAMILLE),
    ("Parce qu'il m'a élevée. Sa dette passe avant la nôtre.", CAMILLE),
    # Topicalised, not an answer in the learner's place.
    ("Mon grand-père ? Oui, c'est lui.", CAMILLE),
    # A quotation of what the learner really wrote.
    ("Tu as dit « je ne suis pas daccord », et pourtant tu restes.", CAMILLE),
    # A question after a yes; nothing was refused.
    ("Tu es d'accord, alors. Tu signes ?", _payload(CAMILLE_OPENING, "Oui, d'accord.")),
    # Agreeing with someone else is not agreeing with the proposal.
    ("Tu es d'accord avec Gus, alors.", CAMILLE),
]


@pytest.mark.parametrize(("reply", "payload"), [*REVIEWERS_LINES, *PRAISED_REPLIES])
def test_natural_french_is_not_refused(reply, payload):
    assert _codes(reply, payload) == []


# ---------------------------------------------------------------------------
# What fires
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "reply",
    [
        CAMILLE_WALK_REPLY,
        "Moi non plus. Pourquoi cette question ?",
        "Ni moi. Parce que c'est injuste.",
        "Moi aussi, je ne suis pas d'accord. Parce que c'est la loi.",
        "Nous sommes d'accord, alors. Parce que c'est injuste.",
    ],
)
def test_a_character_does_not_join_the_refusal_of_their_own_proposal(reply):
    assert "reply_contradicts_position" in _codes(reply, CAMILLE)


def test_joining_a_refusal_is_fine_when_nothing_was_proposed():
    payload = _payload("Tu aimes les dettes ?", "Non, je n'aime pas les dettes.")
    assert _codes("Moi non plus. Elles me fatiguent.", payload) == []


def test_a_proposal_refused_earlier_does_not_bind_a_later_reply():
    history = [{"learner": CAMILLE_REFUSED, "character": "Parce qu'il m'a élevée. Et vous, votre famille ?"}]
    payload = _payload(CAMILLE_OPENING, "Ma famille est à Berlin.", history)
    assert "reply_contradicts_position" not in _codes("Moi non plus, je ne connais pas Berlin.", payload)


@pytest.mark.parametrize(
    "reply",
    ["Mais pourquoi cette question ?", "Pourquoi ?", "Pourquoi cette question, Camille ?", "Et vous ?"],
)
def test_a_question_is_not_answered_with_only_a_question(reply):
    assert "reply_skips_learner_question" in _codes(reply, CAMILLE)


def test_a_question_back_is_fine_when_the_learner_asked_nothing():
    payload = _payload("Tu viens ?", "Non, je reste ici.")
    assert _codes("Pourquoi ?", payload) == []


def test_a_clarifying_question_is_left_alone():
    voice = lanes.VoiceReply(reply_fr="Pourquoi ?", understood_intent="?", needs_clarification=True)
    engine.reply_soft_check(voice, "B1", None, CAMILLE_REFUSED, payload=CAMILLE)


def test_words_the_learner_never_wrote_are_not_quoted_at_them():
    """#620: «Tu as promis, hein : « Je pense que je vais vendre la bouillotte… »». The
    learner's three replies never mentioned selling."""

    payload = _payload(
        "Tu partages la pizza ?",
        "Oui Napoleon aime le poisson. Bon, je lis la lettre avec toi, mais dis moi la verité d abord.",
        [{"learner": "Non, je ne partage pas la pizza… tu a menti à Margaux", "character": "Tu as raison."}],
    )
    reply = "D'accord. Tu as promis, hein : « Je pense que je vais vendre la bouillotte de Odile. »"
    findings = lane_guards.scene_findings(reply, payload)
    assert [finding.code for finding in findings] == ["reply_quotes_unsaid"]
    assert findings[0].served == "D'accord."
    assert _codes("Tu as dit : « je ne partage pas la pizza ».", payload) == []


def test_a_character_does_not_answer_in_the_learners_place():
    payload = _payload("Tu viens ?", "Je ne sais pas.")
    findings = lane_guards.scene_findings("Tu viens samedi ? Oui, tu viens.", payload)
    assert [finding.code for finding in findings] == ["reply_answers_for_learner"]
    assert "Oui, tu viens" not in findings[0].served


def test_a_learner_who_said_no_is_not_told_they_agreed():
    payload = _payload(CAMILLE_OPENING, "Non, je ne suis pas d'accord.")
    assert _codes("Bon, vous êtes d'accord. On signe demain.", payload) == ["reply_answers_for_learner"]


def test_the_walks_reply_to_marin_drops_the_question_already_answered():
    """#467, exact: reply 2 said «Non, je veux pas ce nom», and Marin asked it again."""

    history = [
        {
            "learner": "Je garde la canapé rouge. Le menu, il s'appelle Les Mots sur les cartes.",
            "character": "Le canapé rouge, oui ! Tu veux garder ce nom ?",
        }
    ]
    payload = _payload(
        "Pour samedi, on garde quel canapé ?",
        "Non, je veux pas ce nom. Ma grand-mère avait une chat qui s'appelle Napoléon, on peut l'appeler Napoléon?",
        history,
    )
    findings = lane_guards.scene_findings("Oui, bien sûr. Tu me le fais garder ?", payload)
    assert findings[0].code == "reply_reasks_answered_question"
    assert findings[0].served == "Oui, bien sûr."


# ---------------------------------------------------------------------------
# A check can only cost one retry
# ---------------------------------------------------------------------------


def _lane(answers: list[str], payload: dict) -> tuple[lanes.VoiceReply, list[dict]]:
    """``_run_lane`` with the given replies in place of a model."""

    replies = iter(answers)
    firings: list[dict] = []

    def fake_call(system, request, schema, record, **kwargs):
        return schema(reply_fr=next(replies), understood_intent="x", needs_clarification=False), {}

    original = engine._json_call
    engine._json_call = fake_call
    try:
        served = lanes._run_lane(
            "system", {}, lanes.VoiceReply, lambda voice: lanes.validate_voice(voice, payload),
            deadline=lanes.time.monotonic() + 60, collected=[], max_tokens=100, window=10, firings=firings,
        )
    finally:
        engine._json_call = original
    return served, firings


def test_a_finding_the_retry_fixes_is_counted_as_corrected():
    served, firings = _lane([CAMILLE_WALK_REPLY, "Parce qu'il m'a élevée. Sa dette passe avant la nôtre."], CAMILLE)
    assert served.reply_fr.startswith("Parce qu'il m'a élevée")
    assert firings == [{"code": "reply_contradicts_position", "outcome": "corrected"}]


def test_a_finding_that_comes_back_is_served_never_a_lost_turn():
    served, firings = _lane([CAMILLE_WALK_REPLY, CAMILLE_WALK_REPLY, "never reached"], CAMILLE)
    assert served.reply_fr == CAMILLE_WALK_REPLY
    assert firings == [{"code": "reply_contradicts_position", "outcome": "served_anyway"}]


def test_a_firing_carries_no_text():
    """A code and an outcome: nothing the learner wrote reaches the pilot ledger."""

    _, firings = _lane([CAMILLE_WALK_REPLY, "Parce qu'il m'a élevée."], CAMILLE)
    assert set(firings[0]) == {"code", "outcome"}


# ---------------------------------------------------------------------------
# What the voice lane read is kept for the next turn
# ---------------------------------------------------------------------------


def test_the_voice_reading_and_its_facts_are_kept_with_the_exchange():
    said = "Non, je veux pas ce nom. Ma grand-mère avait une chat qui s'appelle Napoléon."
    voice = lanes.VoiceReply(
        reply_fr="Napoléon !",
        understood_intent="L'apprenant refuse le nom.",
        needs_clarification=False,
        learner_intent="no",
        learned=[
            {"key": "chat", "fact_fr": "Sa grand-mère avait un chat.", "quote": "une chat qui s'appelle Napoléon"},
            {"key": "vente", "fact_fr": "L'apprenant vend.", "quote": "je vends la bouillotte"},
        ],
    )
    heard = lanes._heard_of(voice, said)
    assert heard["intent"] == "no"
    assert [fact["key"] for fact in heard["learned"]] == ["chat"]
    ledger = scene_ledger.build(
        opening_line_fr="Tu gardes ce nom ?", history=[{"learner": said, "character": "Napoléon !", "heard": heard}]
    )
    assert ledger["last_turn"]["read_by"] == "voice"
    assert ledger["established"][0]["key"] == "chat"


def test_a_recorded_answer_without_the_new_fields_still_parses():
    voice = lanes.VoiceReply(reply_fr="Oui.", understood_intent="x", needs_clarification=False)
    assert voice.learner_intent is None
    assert lanes._heard_of(voice, "Oui.") == {"meant": "x"}


def test_the_voice_prompt_explains_the_record_it_is_given():
    for field in ("last_turn", "stands", "established", "learner_intent", "learned"):
        assert field in lanes.VOICE, field
