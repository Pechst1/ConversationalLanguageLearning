"""WP-164: the repetition report's metrics, on small fixtures (no walk, no model)."""

from __future__ import annotations

from scripts import variety_report as vr


def _day(
    day,
    place,
    *,
    kind="generated",
    character="lila_bonnet",
    opening="",
    premise="",
    premise_id=None,
    complication="",
    text=(),
):
    return {
        "day": day,
        "kind": kind,
        "key": f"g1.{day}",
        "place": place,
        "character": character,
        "opening": opening,
        "premise": premise,
        "premise_id": premise_id,
        "complication": complication,
        "text": list(text),
    }


def test_normalise_folds_quotes_case_and_punctuation_but_keeps_accents():
    assert vr.normalise("«Il pleut sur le canal…»") == "il pleut sur le canal"
    assert vr.normalise("C’est l’été !") == "c'est l'été"
    assert vr.sentences("Il pleut. Tu as une valise ! Et toi ?") == [
        "il pleut",
        "tu as une valise",
        "et toi",
    ]
    assert vr.first_sentence("Le zinc brille. Margaux attend.") == "le zinc brille"


def test_place_shares_runs_and_pairs():
    days = [
        _day(1, "le_mistral", kind="tentpole", character="gus"),
        _day(2, "le_mistral", kind="tentpole", character="gus"),
        _day(3, "le_mistral"),
        _day(4, "boulangerie"),
        _day(5, None, kind="lost"),
        _day(6, "le_mistral"),
    ]
    assert vr.place_shares(days) == {"le_mistral": 0.8, "boulangerie": 0.2}
    assert vr.longest_room_run(days) == ("le_mistral", 3)
    assert vr.repeated_pairs(days) == {"gus@le_mistral": 2, "lila_bonnet@le_mistral": 2}
    assert vr.mistral_windows(days) == {"windows": 1, "over_cap": 1}
    assert vr.borrowed_plate_scenes(days, {"le_mistral": True, "boulangerie": False}) == 1


def test_repeated_openings_premises_complications_and_text_seen_twice():
    days = [
        _day(
            1,
            "le_mistral",
            opening="il pleut sur le canal",
            premise_id="romy",
            complication="Le radiateur est mort.",
            text=["Il pleut sur le canal. Tu as une minute ?"],
        ),
        _day(
            2,
            "toit",
            opening="Il pleut sur le canal.",
            premise_id="romy",
            complication="le radiateur est mort",
            text=["Il pleut sur le canal. Non."],
        ),
        _day(
            3,
            "ecole",
            opening="Les enfants dessinent.",
            premise_id="billet",
            text=["Non. Les enfants dessinent des trains."],
        ),
    ]
    report = vr.learner_report(days)
    assert report["repeated_openings"] == {"il pleut sur le canal": 2}
    assert report["repeated_premises"] == {"romy": 2}
    assert report["repeated_complications"] == {"le radiateur est mort": 2}
    # «Non.» is too short to count; the canal sentence was read on two days.
    assert vr.text_seen_twice(days) == {"il pleut sur le canal": [1, 2]}
    assert report["generated_openings_distinct"] == 2


def test_cross_learner_overlap_keeps_tentpole_and_generated_days_apart():
    same = "Margaux essuie le zinc sans un mot."
    one = [
        _day(1, "le_mistral", kind="tentpole", text=[same]),
        _day(2, "toit", text=["Lila ouvre la lucarne du toit."]),
    ]
    two = [
        _day(1, "le_mistral", kind="tentpole", text=[same]),
        _day(2, "ecole", text=["Les enfants peignent un grand canal."]),
    ]
    across = vr.cross_learner_overlap({"a": one, "b": two})
    assert across["tentpole"] == {"pairs": 1, "mean": 1.0}
    assert across["generated"] == {"pairs": 1, "mean": 0.0}
    assert vr.identical_openings_across({"a": one, "b": two}, kind="generated") is None
    # A third learner at another band never shares a tentpole's wording: same-band pairs only.
    for day in (*one, *two):
        day["band"] = "A1"
    three = [
        {
            **_day(1, "le_mistral", kind="tentpole", text=["Paris, il tombe des cordes ce soir."]),
            "band": "C1",
        }
    ]
    lives = {"a": one, "b": two, "c": three}
    assert vr.cross_learner_overlap(lives)["tentpole"] == {"pairs": 3, "mean": 0.333}
    assert vr.cross_learner_overlap(lives, same_band=True)["tentpole"] == {"pairs": 1, "mean": 1.0}


def test_a_walk_life_and_an_evidence_transcript_read_as_days():
    record = {
        "days": [
            {
                "day": 1,
                "season": {"last": "t1.a"},
                "scene": {
                    "kind": "tentpole",
                    "location_id": "le_mistral",
                    "character_id": "gus",
                    "opening_fr": "Il pleut. Tu as une valise.",
                    "text_fr": ["Il pleut."],
                },
                "journey": {"events": []},
            },
            {"day": 2, "season": {"last": "t1.b"}, "scene": {}, "journey": {"events": []}},
        ]
    }
    days = vr.days_from_life(record)
    assert [day["kind"] for day in days] == ["tentpole", "lost"]
    assert days[0]["opening"] == "il pleut"
    markdown = "\n".join(
        [
            "## Jour 3 — g1.1 (jour généré) · Romy et la rumeur",
            "",
            "> *Romy interroge Margaux au zinc. Elle veut savoir.*",
            "",
            "**P1** — *Medium shot: Margaux behind the zinc drying a glass.*",
            "> *Le zinc est plein d'odeur de café.*",
            "**Margaux** — «J'ai rien entendu, moi, rien du tout.»",
            "",
            "**Romy Tremblay** (se tourne vers toi) — «C'est vous, l'héritage ?»",
            "*Checklist du réalisateur : romy_enquete · avant → après · petit moment : —*",
            "",
            "## Jour 4 — jour perdu : relecture de «t1.b» (la saison n'avance pas)",
        ]
    )
    read = vr.days_from_evidence_md(markdown)
    assert read[0]["kind"] == "generated"
    assert read[0]["place"] == "le_mistral"
    assert read[0]["opening"] == "le zinc est plein d'odeur de café"
    assert read[0]["premise_id"] == "romy_enquete"
    assert read[0]["character"] == "Romy Tremblay"
    assert "J'ai rien entendu, moi, rien du tout." in read[0]["text"]
    assert read[1]["kind"] == "tentpole" and read[1]["key"] == "t1.b"


def test_place_inference_takes_the_earliest_place_word():
    assert vr.infer_place("Night on the roof; below, the café's neon.") == "toit"
    assert vr.infer_place("Wide shot of the café interior; the canal outside.") == "le_mistral"
    assert vr.infer_place("Mme Diallo's bakery at dawn.") == "boulangerie"
    assert vr.infer_place("") is None
