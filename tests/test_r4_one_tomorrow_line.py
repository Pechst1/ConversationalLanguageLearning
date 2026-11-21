"""Round 4 · the «tomorrow» line is the same in every place.

Third real-model walk (19 Nov), B1 day 3, from the walk database (read-only): the
learner wrote «… je voudrais quand même parler à Gus demain, parce qu'il connaissait bien
Odile.»; the scene's last panel (``resolution_fr``) said it back: «Oui, tu comprends mieux
pourquoi Odile gardait cette clé. Parle à Gus demain : il connaissait une autre facette
d'elle, et je veux savoir ce qu'il en dira.» The filed hook (``next_teaser``, ``source:
beat``) was «Demain, Marin est là : la soupe de Marin.», so recap and Home promised Marin
while the scene promised Gus — and the next night's brief was told Marin's soup while the
critic, reading the learner's agreement, asked for Gus on all three drafts.

The sentence that said the plan back runs 18 words, over the 14 a hook may have, and its
only break is a colon: no clause was found, so the learner's plan was never filed and the
beat won. The order already puts the learner's plan said back first (P8, fourth commit);
the colon is now a clause break, so «Parle à Gus demain.» is the one line every place
reads, and tomorrow's brief carries the plan.
"""

from __future__ import annotations

from app.services.story_teaser import ending_hook, one_hook, plan_step

#: B1 day 3, stored ``recap_payload.resolution_fr``.
ENDING = (
    "Oui, tu comprends mieux pourquoi Odile gardait cette clé. Parle à Gus demain : il connaissait "
    "une autre facette d’elle, et je veux savoir ce qu’il en dira."
)
#: B1 day 3, the learner's fourth reply (play log, «Day 3 reply 4»).
SAID = ["Oui, je comprends mieux, mais je voudrais quand même parler à Gus demain, parce qu'il connaissait bien Odile."]


def test_the_learner_s_plan_said_back_after_a_colon_is_the_day_s_hook():
    assert plan_step(SAID, [ENDING]) == "Parle à Gus demain."
    hook = one_hook(ending_hook(ENDING, {}, character_id="lila_bonnet", date="2026-11-21", name="Lila", said=SAID))
    assert hook is not None and hook["source"] == "plan", hook
    assert hook["text_fr"] == hook["open_fr"] == "Parle à Gus demain."


def test_a_clock_s_colon_is_not_a_clause_break():
    ending = "Gus sera au Mistral demain à 19:00 avec les papiers de la succession et la clé de la cave d'Odile."
    assert plan_step(["Demain, je veux parler à Gus."], [ending]) is None, "no clause of it stands alone"
