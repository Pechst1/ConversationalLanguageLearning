"""WP-155 «Reply-lane hygiene from the WP-149 read».

The paid WP-149 confirmation (``docs/implementation/atelier-v2/evidence/wp149-confirmation/``)
lost no grade, but the story-lane critic still flagged three released lines and one
day was lost to a spoiler. What these tests pin, with the fake providers and the stored
records only (never a paid call):

1. **Gender scrub in the reply lanes.** «tu t'es engagé·e», «Le apprenant» (what the
   old dot scrub made of «Le·la apprenant·e»), «prêt(e)»: refused with a hint in every
   field the learner reads (the voice's reply, the story lane's ending, summary,
   callback, commitments), rewritten deterministically in the private
   ``understood_intent``, dropped from a correction.
2. **``invented_learner_choice``.** An ending never credits the learner with a plan,
   a proposal or a pledge their own words do not hold (B1 g4.5: «Tu offres ton aide et
   proposes un rendez-vous court demain après-midi» — the rendez-vous was Marin's).
3. **Tentpole reveals.** T5 owns «Berlin»: the reveal lives on the tentpole and every
   gap before it inherits it — in the director's brief, the page guard, and now the
   reply and the ending of a generated day.
4. «La nuit du 14 mars» stays a negative example of the director (WP-149).
5. **Offline replay** of the stored WP-149 records through the new checks.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.services import lane_guards
from app.services import living_story as engine
from app.services import story_lanes as lanes
from app.services.season.director import (
    forbidden_hits,
    gap_brief,
    must_not_rows,
    pattern_hits,
    upcoming_reveals,
)
from app.services.season.format import load_season
from tests import test_journey_end_to_end as support
from tests import test_living_story
from tests.test_wp87_lanes import (  # noqa: F401 - fixtures
    ANSWER,
    LaneProvider,
    _resolution,
    _respond,
    _to_respond,
    inline,
    jobs,
    one_exchange,
    provider,
)

assembled_client = support.assembled_client
clock = support.clock
journey_enabled = support.journey_enabled
driver = test_living_story.driver

EVIDENCE = Path(__file__).resolve().parents[1] / "docs/implementation/atelier-v2/evidence/wp149-confirmation"


def _payload(learner_text: str, *, history=(), opening: str = "", address: str = "neutral",
             season_turn: dict | None = None, control_language: str = "en") -> dict:
    story = {"level": "B1", "learner": {"address": address}, "control_language": control_language,
             "commitments": []}
    if season_turn is not None:
        story["season_turn"] = season_turn
    return {
        "story": story,
        "scene": {"opening_line_fr": opening, "objective_native": "", "panels": []},
        "learner_text": learner_text,
        "history": [{"learner": learner, "character": character} for learner, character in history],
        "targets": [],
        "turn_plan": {},
    }


def _voice(reply: str, intent: str = "The learner agrees.") -> lanes.VoiceReply:
    return lanes.VoiceReply(reply_fr=reply, understood_intent=intent, needs_clarification=False)


def _reason(callable_, *args, **kwargs) -> str | None:
    try:
        callable_(*args, **kwargs)
    except engine.StoryUnavailable as exc:
        return str(exc)
    return None


# ---------------------------------------------------------------------------
# 1. The gender scrub on every lane field
# ---------------------------------------------------------------------------


def test_inclusive_and_gendered_learner_forms_are_found_and_prose_is_not():
    assert lane_guards.gender_form_hits("Merci, tu t'es engagé·e.") == ["engagé·e"]
    assert lane_guards.gender_form_hits("Le apprenant veut rester.") == ["Le apprenant"]
    assert lane_guards.gender_form_hits("Le·la apprenant·e veut rester.")[0] == "Le·la apprenant·e"
    assert lane_guards.gender_form_hits("Tu es prêt(e) ?") == ["prêt(e)"]
    assert lane_guards.gender_form_hits("Tu es engagé.e, bravo.") == ["engagé.e"]
    assert lane_guards.gender_form_hits("la apprenante") == ["la apprenante"]
    for prose in ("L'apprenant veut rester.", "L’apprenant veut rester.", "Les apprenants arrivent.",
                  "M. Marchand arrive.", "C'est fini. Elle part.", "Il est 9.30."):
        assert lane_guards.gender_form_hits(prose) == [], prose


def test_the_private_paraphrase_is_rewritten_never_to_le_apprenant():
    # The old scrub kept the masculine half: this is where «Le apprenant» came from.
    assert engine._scrub_inclusive_dot("Le·la apprenant·e veut rester.") == "Le apprenant veut rester."
    assert lane_guards.scrub_learner_gender("Le·la apprenant·e veut rester.") == "L'apprenant veut rester."
    assert lane_guards.scrub_learner_gender("le apprenant hésite") == "l'apprenant hésite"
    payload = _payload("Je reste.")
    voice = _voice("D'accord, on y va.", intent="Le·la apprenant·e dit qu'il·elle reste.")
    lanes.validate_voice(voice, payload)
    assert voice.understood_intent == "L'apprenant dit qu'il reste."
    # A paraphrase that still agrees with the learner becomes their words, quoted.
    agreeing = _voice("D'accord, on y va.", intent="Tu t'es engagé·e à rester.")
    lanes.validate_voice(agreeing, payload)
    assert agreeing.understood_intent == "Learner said: «Je reste.»"


def test_the_voice_reply_with_an_inclusive_form_is_refused_with_a_hint():
    payload = _payload("Oui, je viens.")
    for reply in ("Merci ! Tu t'es engagé·e, c'est beau.", "Tu es prêt(e) ? On y va.",
                  "Le apprenant est là, enfin."):
        with pytest.raises(engine.StoryUnavailable) as caught:
            lanes.validate_voice(_voice(reply), payload)
        assert str(caught.value) == "learner_gender_form"
        assert "inclusive or gendered form" in caught.value.feedback
    # Endearments are still cut, not refused; a clean reply passes untouched.
    voice = _voice("Merci, mon grand. On prépare la salle ensemble.")
    lanes.validate_voice(voice, payload)
    assert voice.reply_fr == "Merci. On prépare la salle ensemble."
    # A learner who gave the feminine may be called «l'apprenante».
    lane_guards.check_lane_gender(["L'apprenante arrive."], "feminine")
    assert _reason(lane_guards.check_lane_gender, ["L'apprenante arrive."], "neutral") == "learner_gender_form"


def test_a_correction_carrying_an_inclusive_form_is_dropped():
    verdict = lanes.TutorVerdict(
        outcome="partially_met", correction_span_fr="je suis engager",
        correction_fr="je me suis engagé·e", correction_note_native="Use the participle.",
    )
    lanes.validate_tutor(verdict, _payload("Oui, je suis engager."))
    assert verdict.correction_fr is None and verdict.correction_span_fr is None


def _turn(**story) -> engine.SemanticTurn:
    tutor = lanes.TutorVerdict(outcome="met", evidence_quotes=["Oui, je viens."])
    voice = _voice("Super, à demain.")
    defaults = {"resolution_fr": "Lila sourit. La soirée continue.", "summary_native": "Lila smiles."}
    return lanes.merged_turn(tutor, voice, lanes.StoryTurn(**{**defaults, **story}))


def test_every_field_of_the_ending_is_held_to_the_rule():
    payload = _payload("Oui, je viens.")
    assert _reason(lanes.validate_story, _turn(), payload) is None
    for story in (
        {"resolution_fr": "Tu t'es engagé·e. Lila sourit."},
        {"summary_native": "Le apprenant comes along."},
        {"callback_fr": "L'apprenant·e viendra."},
        {"commitments": [{"text_fr": "Venir, prêt(e), demain.", "source_quote": "Oui, je viens."}]},
    ):
        assert _reason(lanes.validate_story, _turn(**story), payload) == "learner_gender_form", story


def _scripted_stories(fake: LaneProvider, stories: list[dict]) -> None:
    """The story lane answers ``stories`` (overrides) in order, then its default."""

    original = fake.generate_chat_completion
    queue = list(stories)

    def scripted(messages, **kwargs):
        if json.loads(messages[0]["content"])["output_schema"]["title"] == "StoryTurn":
            fake.story = queue.pop(0) if queue else {}
        return original(messages, **kwargs)

    fake.generate_chat_completion = scripted


def test_a_gendered_ending_is_retried_with_the_hint_and_never_served(
    assembled_client, db_session, journey_enabled, clock, provider, inline  # noqa: F811
):
    _scripted_stories(provider, [{"resolution_fr": "Tu t'es engagé·e : Margaux sourit."}])
    d = driver(assembled_client, db_session)
    step = _to_respond(d)
    _respond(assembled_client, d, step)
    assert inline == ["done"]
    stories = [data for schema, data in provider.calls if schema == "StoryTurn"]
    assert len(stories) == 2
    assert any("engagé·e" in hint for hint in stories[1]["previous_rejections"])
    d.advance()
    assert "·" not in _resolution(d.journey)["prompt"]["character_line_fr"]


# ---------------------------------------------------------------------------
# 2. invented_learner_choice
# ---------------------------------------------------------------------------

#: B1 g4.5 of the WP-149 read, verbatim from ``b1/B1.1.md`` (day 32).
G45_OPENING = "Alors ? Tu décides pour nous : on la protège, ou on lui demande de parler ?"
G45_HISTORY = [
    ("Merci pour la soupe. Oui, j'ai froid, mais ça va mieux.",
     "Ah, bon. Ça me fait plaisir que tu aies mangé — et un peu de chaleur, ça change tout. "
     "Pardon ? Tu peux le redire autrement ?"),
    ("Je ne sais pas encore. Mais je ne pars pas demain.",
     "C'est déjà quelque chose : tu restes. Ça m'apaise un peu, vraiment. Tu veux qu'on fixe tout "
     "de suite qui garde le silence, et jusqu'à quand ?"),
]
G45_LAST = "D'accord, je t'aide. On commence quand ?"
G45_ENDING = ("Tu offres ton aide et proposes un rendez‑vous court demain après‑midi, mais la décision "
              "publique n'est pas complètement bouclée : le groupe est apaisé, mais attend un accord "
              "clair. La situation reste ouverte pour 48 heures.")


def test_an_ending_that_credits_the_learner_with_the_characters_plan_is_caught():
    payload = _payload(G45_LAST, history=G45_HISTORY, opening=G45_OPENING)
    claim = lane_guards.invented_choice([G45_ENDING], payload)
    assert claim is not None and claim.startswith("proposes un rendez")
    # What the learner did say stands: «je t'aide» → «tu offres ton aide».
    assert lane_guards.invented_choice(["Tu offres ton aide. Marin propose demain après-midi."], payload) is None


def test_what_the_learner_said_or_accepted_is_not_an_invention():
    said = _payload("Je propose un dîner chez Odile samedi.")
    assert lane_guards.invented_choice(["Tu proposes un dîner chez Odile samedi soir."], said) is None
    assert lane_guards.invented_choice(["Tu décides de rester."], _payload("Je reste ici.")) is None
    # Taken up after a character offered it: «oui» to Lila's «demain, dix minutes chez moi ?».
    accepted = _payload("Oui, d'accord.", opening="On se parle demain, dix minutes chez moi ?")
    assert lane_guards.invented_choice(["Tu acceptes de parler demain chez elle."], accepted) is None
    # A question, a negation and a third person claim nothing for the learner.
    nothing = _payload("Euh… je ne sais pas.")
    for ending in ("Tu proposes quoi, alors ?", "Tu ne proposes rien, et Marin attend.",
                   "Tu n'as pas promis de venir.", "Marin propose un rendez-vous demain."):
        assert lane_guards.invented_choice([ending], nothing) is None, ending
    # «Tu acceptes» with nothing accepted is invented.
    assert lane_guards.invented_choice(["Alors tu acceptes."], nothing) == "acceptes"


def test_an_invented_choice_is_retried_then_falls_to_the_authored_ending(
    assembled_client, db_session, journey_enabled, clock, provider, inline  # noqa: F811
):
    invented = {"resolution_fr": "Tu promets un dîner chez Margaux dimanche soir. Lila rit."}
    _scripted_stories(provider, [invented] * 6)
    d = driver(assembled_client, db_session)
    step = _to_respond(d)
    _respond(assembled_client, d, step)
    assert inline == ["fallback"], "never served"
    stories = [data for schema, data in provider.calls if schema == "StoryTurn"]
    assert len(stories) >= 2
    assert any("never said or accepted" in hint for hint in stories[1]["previous_rejections"])
    d.advance()
    assert "dîner" not in _resolution(d.journey)["prompt"]["character_line_fr"]


def test_an_invented_choice_rewritten_on_the_retry_is_served(
    assembled_client, db_session, journey_enabled, clock, provider, inline  # noqa: F811
):
    _scripted_stories(provider, [{"resolution_fr": "Tu promets un dîner chez Margaux dimanche soir."}])
    d = driver(assembled_client, db_session)
    step = _to_respond(d)
    _respond(assembled_client, d, step)
    assert inline == ["done"]
    stories = [data for schema, data in provider.calls if schema == "StoryTurn"]
    assert len(stories) == 2 and stories[1]["learner_text"] == ANSWER
    assert any("never said or accepted" in hint for hint in stories[1]["previous_rejections"])
    d.advance()
    assert "dîner" not in _resolution(d.journey)["prompt"]["character_line_fr"]


# ---------------------------------------------------------------------------
# 3. Tentpole reveals: before T5, Berlin is never named — page, brief, reply, ending
# ---------------------------------------------------------------------------


def test_t5_owns_berlin_and_every_gap_before_it_inherits_the_reveal():
    season = load_season("s1")
    assert [row.id for row in season.tentpoles["t5"].reveals] == ["t5_berlin"]
    before = [gap for gap in ("g1", "g2", "g3", "g4") if "t5_berlin" in [r.id for r in upcoming_reveals(season, gap)]]
    assert before == ["g1", "g2", "g3", "g4"]
    assert upcoming_reveals(season, "g5") == []
    assert forbidden_hits(season, "g5", ["Lila part pour Berlin."], flags={}) == []
    # One word, one hit, even though the gap's own row and T5's reveal both match it.
    assert forbidden_hits(season, "g4", ["Lila dit-elle la vérité sur Berlin ?"], flags={}) == [
        ("berlin_revealed", "Berlin")
    ]
    # T5's reveal alone would have caught it (a gap without its own Berlin row).
    assert pattern_hits(season.tentpoles["t5"].reveals, ["un mail du Künstlerhaus"]) == [("t5_berlin", "Künstlerhaus")]


def test_the_directors_brief_names_the_reveal_and_the_invented_date():
    from app.services.season.clock import Position

    season = load_season("s1")
    index = next(i for i, segment in enumerate(season.segments) if segment.id == "g4")
    pos = Position(season_id="s1", segment=season.segments[index], segment_index=index,
                   day_in_segment=1, season_day=28)
    brief = gap_brief(season, pos, flags={}, state={}, seed="wp155", band="B1")
    must_not = brief["gap"]["must_not"]
    assert any("T5 reveals Berlin" in text for text in must_not)
    assert any("la nuit du 14 mars" in text for text in must_not), "WP-149's negative example stays"
    assert "invented_dates" in [row.id for row in must_not_rows(season, "g4", {})]


def _season_turn(gap: str) -> dict:
    return engine._season_turn_must_not({"id": "s1", "kind": "gap", "position": {"segment": gap}}, None)


def test_the_turn_carries_todays_reveals_and_the_voice_reads_them():
    turn = _season_turn("g4")
    assert turn["season"] == "s1" and turn["gap"] == "g4"
    assert {"berlin_revealed", "t5_berlin", "invented_dates"} <= {row["id"] for row in turn["must_not"]}
    assert all(set(row) == {"id", "text"} for row in turn["must_not"]), "texts and ids, never the patterns"
    voice_in = lanes.voice_payload(_payload("Oui.", season_turn=turn))
    assert any("T5 reveals Berlin" in text for text in voice_in["never_reveal"])
    assert "never_reveal" not in lanes.voice_payload(_payload("Oui."))
    assert engine._season_turn_must_not({"id": "s1", "kind": "gap", "position": {}}, None) == {}


def test_a_reply_or_an_ending_that_names_berlin_before_t5_is_refused():
    g4 = _payload("Je ne sais pas encore.", season_turn=_season_turn("g4"))
    with pytest.raises(engine.StoryUnavailable) as caught:
        lanes.validate_voice(_voice("Tu sais, Lila part pour Berlin."), g4)
    assert str(caught.value) == "season_spoiler" and "T5 owns it" in caught.value.feedback
    g4 = _payload("Oui, je viens.", season_turn=_season_turn("g4"))
    assert _reason(lanes.validate_story, _turn(resolution_fr="Lila regarde un mail du Künstlerhaus."), g4) == "season_spoiler"
    assert _reason(lanes.validate_story, _turn(summary_native="Lila hides the Berlin letter."), g4) == "season_spoiler"
    # After T5, Berlin is the story; on a day outside a season, nothing is forbidden.
    g5 = _payload("Je ne sais pas encore.", season_turn=_season_turn("g5"))
    lanes.validate_voice(_voice("Tu sais, Lila part pour Berlin."), g5)
    lanes.validate_voice(_voice("Tu sais, Lila part pour Berlin."), _payload("Je ne sais pas encore."))
    # The invented date is refused in a reply too.
    assert _reason(lanes.validate_voice, _voice("Depuis la nuit du 14 mars, rien."), g4) == "season_spoiler"


# ---------------------------------------------------------------------------
# 5. Offline replay of the stored WP-149 confirmation
# ---------------------------------------------------------------------------


def _generated_days(path: Path) -> list[dict]:
    """Every generated day of a transcript: its opening line, the learner's lines, the
    character's replies and the ending, as the read printed them."""

    days = []
    text = path.read_text(encoding="utf-8")
    for match in re.finditer(r"^## Jour \d+ — (g\d\.\d) [^\n]*\n(.*?)(?=^## |^---|\Z)", text, re.S | re.M):
        position, body = match.group(1), match.group(2)
        opening = re.search(r"\(se tourne vers toi\) — «(.+?)»$", body, re.M)
        lines = body.split("\n")
        learner, replies, endings, seen_learner = [], [], [], False
        for index, line in enumerate(lines):
            said = re.match(r"^\*\*Toi\*\* — «(.+)»$", line)
            if said:
                seen_learner = True
                learner.append(said.group(1))
                reply = re.match(r"^\*\*[^*]+\*\* — «(.+)»$", lines[index + 1]) if index + 1 < len(lines) else None
                replies.append(reply.group(1) if reply else "")
            elif seen_learner and line.startswith("> *"):
                endings.append(line[3:].rstrip("*"))
        days.append({"position": position, "opening": opening.group(1) if opening else "",
                     "learner": learner, "replies": replies, "endings": endings})
    return days


def test_the_offline_replay_of_the_wp149_confirmation():
    """No paid call: the stored records of the paid read through the new checks. Each of
    the four known cases is caught; nothing else the read served is."""

    readme = (EVIDENCE / "README.md").read_text(encoding="utf-8")
    # --- 1. The two gendered lines the critic flagged after release (README, verbatim) ---
    flagged = re.findall(r"`gendered_address`: [^«]*«([^»]+)»", readme)
    assert flagged == ["Le apprenant", "tu t'es engagé·e"]
    for line in flagged:
        assert lane_guards.gender_form_hits(line), line
        assert _reason(lane_guards.check_lane_gender, [line], "neutral") == "learner_gender_form"
    assert lane_guards.scrub_learner_gender("Le·la apprenant·e") == "L'apprenant"

    # --- 2. The invented choice (B1 g4.5, day 32) ---
    b1 = {day["position"]: day for day in _generated_days(EVIDENCE / "b1/B1.1.md")}
    a1 = {day["position"]: day for day in _generated_days(EVIDENCE / "a1/A1.1.md")}
    assert sorted(b1) == ["g4.1", "g4.2", "g4.3", "g4.4", "g4.5"]
    assert sorted(a1) == ["g1.1", "g1.2", "g1.3", "g1.4", "g1.5", "g2.1"]
    invented = {}
    for band, days in (("b1", b1), ("a1", a1)):
        for position, day in days.items():
            if not day["learner"] or not day["endings"]:
                continue
            history = list(zip(day["learner"][:-1], day["replies"][:-1], strict=True))
            payload = _payload(day["learner"][-1], history=history, opening=day["opening"])
            claim = lane_guards.invented_choice(day["endings"][-1:], payload)
            if claim:
                invented[(band, position)] = claim
    assert list(invented) == [("b1", "g4.5")], invented
    assert invented[("b1", "g4.5")].startswith("proposes un rendez")
    assert b1["g4.5"]["endings"][-1] == G45_ENDING

    # Nothing the read served on a generated day trips the gender scrub.
    served = [text for days in (a1, b1) for day in days.values()
              for text in (*day["replies"], *day["endings"])]
    assert served and [text for text in served if lane_guards.gender_form_hits(text)] == []

    # --- 3. The Berlin spoiler of B1 g4.1 (``refusals[]``, the drafts' own words) ---
    season = load_season("s1")
    record = json.loads((EVIDENCE / "b1/B1.1.json").read_text(encoding="utf-8"))
    spoilers = [row for row in record["refusals"] if row["reason"] == "season_spoiler"]
    assert [row["position"] for row in spoilers] == ["g4.1", "g4.1"]
    for row in spoilers:
        texts = [row["draft"]["dramatic_question"], row["draft"]["objective_native"]]
        assert [word for _, word in forbidden_hits(season, "g4", texts, flags={})] == ["Berlin"]
        assert pattern_hits(season.tentpoles["t5"].reveals, texts), "T5's own reveal catches it"
        g4 = _payload("Je ne sais pas encore.", season_turn=_season_turn("g4"))
        assert _reason(lane_guards.check_season_spoiler, texts, g4) == "season_spoiler"
    # Every other stored draft of the read names no reveal.
    others = [row for path in (EVIDENCE / "a1/A1.1.json", EVIDENCE / "b1/B1.1.json")
              for row in json.loads(path.read_text(encoding="utf-8"))["refusals"]
              if row["reason"] != "season_spoiler"]
    for row in others:
        gap = row["position"].split(".")[0]
        texts = [row["draft"]["dramatic_question"], row["draft"]["objective_native"], row["draft"]["open_question"]]
        if any("berlin" in text.casefold() for text in texts):
            assert forbidden_hits(season, gap, texts, flags={}), row["position"]

    # --- 4. The invented date is a negative example the guard enforces ---
    assert forbidden_hits(season, "g4", ["C'était la nuit du 14 mars."], flags={}) == [
        ("invented_dates", "la nuit du 14 mars")
    ]
