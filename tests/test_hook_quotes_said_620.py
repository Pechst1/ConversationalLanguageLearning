"""#620 (root cause #145, same family as #378 and #445): the closing hook puts words in
the learner's mouth.

Live walk 9 Nov 2026, Nº 27 «Lila revient avec une pizza»: the learner answered Lila
three times (the pizza, the cat Napoléon, the letter) and never said a word about
selling anything. The closing panel read «Toi, tu me caches quelque chose… Tu as
promis, hein : « Je pense que je vais vendre la bouillotte de Odile, mais non, je ne
vends pas le café. »» and Done and Home repeated it under «Tomorrow».

Why the code allowed it: the hook is picked from every promise the story still holds
open, and a promise from an earlier day keeps its ``source_quote``. Nothing asked
whether the words inside the guillemets were said in THIS scene, so a stale line from
a day the learner no longer remembers (and not even a promise) came back in the
character's mouth as «Tu as promis». The rule is now one check on the finished line:
guillemets hold only words the learner wrote in the scene being closed.
"""

from __future__ import annotations

from app.services import living_story as engine

STALE = "Je pense que je vais vendre la bouillotte de Odile, mais non, je ne vends pas le café."
REPLIES = [
    "Non, je ne partage pas la pizza… tu a menti à Margaux",
    "Napoleon est mon chat. Il aime le poisson. Et toi, tu as un chat ?",
    "Oui Napoleon aime le poisson. Bon, je lis la lettre avec toi, mais dis moi la verité d abord.",
]


def _live(*, quote: str = STALE) -> dict:
    return {
        "commitments": [
            {
                "id": "e9:commitment:0",
                "status": "open",
                "witnesses": ["lila_bonnet"],
                "text_fr": "Vendre la bouillotte d'Odile.",
                "source_quote": quote,
            }
        ],
    }


def _hook(live: dict, **kwargs) -> dict | None:
    return engine.next_teaser(
        live, {}, character_id="lila_bonnet", register="tu", date="2026-11-09", seed="walk", **kwargs
    )


def test_a_promise_from_an_earlier_day_is_not_quoted_in_this_scenes_hook():
    """The walk: the learner's three replies never mention selling."""

    teaser = _hook(_live())
    text = teaser["text_fr"] if teaser else ""
    assert "bouillotte" not in text and "vendre" not in text, (
        f"the closing hook quotes words the learner never said in this scene: {text!r}"
    )


def test_a_promise_the_learner_just_made_is_still_quoted():
    quote = "Oui, je viens chercher la lettre demain."
    teaser = _hook(_live(quote=quote), said=[REPLIES[0], quote])
    assert teaser is not None and f"« {quote} »" in teaser["text_fr"]


def test_every_quotation_in_a_finished_hook_is_checked_against_the_replies():
    said = ["Je serai chez moi après deux heures."]
    assert engine.teaser_quotes_only_said("Tu n'as pas oublié ? « Je serai chez moi après deux heures. »", said)
    assert not engine.teaser_quotes_only_said(f"Tu as promis, hein : « {STALE} »", said)
    # A hook with no quotation says nothing the learner could deny.
    assert engine.teaser_quotes_only_said("Il faudra qu'on en parle. La clé bleue.", [])
    # A clipped quote (the hook cuts long lines at 110 characters) is still the learner's.
    clipped = "Tu as promis, hein : « Je serai chez moi après deux… »"
    assert engine.teaser_quotes_only_said(clipped, said)
