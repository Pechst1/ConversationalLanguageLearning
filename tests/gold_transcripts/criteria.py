"""The fixed written criteria every gold answer is scored against.

Each criterion is a yes/no question about what the learner was shown. ``by`` says who
answers it: ``check`` is decided in code from the item's ground truth (no model), ``judge``
is answered by the judge model, which sees only these words, the learner's input, the
item's ground-truth notes and the output. A criterion that does not apply to an item
(no refusal to honour, no off-script remark) is ``na`` and leaves the item's score alone.

Changing a criterion's text changes :data:`CRITERIA_VERSION`; the nightly report prints
the version beside every score, and the trend only compares nights of one version.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Criterion:
    id: str
    by: str  # "check" | "judge"
    text: str


SURFACE_TITLES = {
    "scene": "Scene answer",
    "forge": "La Forge free text",
    "courrier": "Courrier reply",
    "correction": "Correction",
}

CRITERIA: dict[str, tuple[Criterion, ...]] = {
    # The scene's reply lanes: the character's reply (VoiceReply) and the grade with its
    # one correction (TutorVerdict), as the learner sees them after one free answer.
    "scene": (
        Criterion("served", "check", "The lanes served a reply: no failure, no authored fallback."),
        Criterion("quotes_real", "check", "Every evidence quote of the grade is words the learner actually wrote."),
        Criterion(
            "takes_up",
            "judge",
            "The character's reply responds to something specific the learner wrote (a reason, a detail, a "
            "date, a name, a question), not with a generic acknowledgement that would fit any answer.",
        ),
        Criterion(
            "honours_no",
            "judge",
            "If the learner refuses or says no, the reply accepts that answer and does not carry on as if "
            "they had agreed. Not applicable when the learner does not refuse.",
        ),
        Criterion(
            "off_script",
            "judge",
            "If the learner asks the character a question or brings up something outside the scene's task, "
            "the reply acknowledges it briefly, in character. Not applicable when there is nothing off-script.",
        ),
        Criterion(
            "no_reask",
            "judge",
            "The reply does not ask again for what the learner has just said (no re-asking an answered "
            "question, no «Pardon ?» to a clear answer).",
        ),
        Criterion(
            "no_invention",
            "judge",
            "The reply does not put words in the learner's mouth, quote a line nobody said, or contradict "
            "what the learner said (their date, their reason, their choice).",
        ),
        Criterion(
            "level_french",
            "judge",
            "The reply is correct, natural French, short and simple enough for the learner's level.",
        ),
        Criterion(
            "outcome_right",
            "judge",
            "The grade's outcome fits the scene's objective: «met» when the learner's answer does what the "
            "objective asks (a refusal or «I don't know» counts when the objective allows it), otherwise not.",
        ),
        Criterion(
            "correction_right",
            "judge",
            "Any correction shown names a real error that is in the learner's own words and fixes it "
            "correctly; a correct form (such as «je suis») is never marked wrong. No correction at all is "
            "fine only when the answer has no clear error.",
        ),
    ),
    # La Forge free text: a production item graded by the Atelier corrector, merged as
    # the second check merges it (the shown verdict, errors, corrected line).
    "forge": (
        Criterion("checked", "check", "The model's check completed: no «second check stopped» fallback."),
        Criterion(
            "verdict_right",
            "check",
            "The verdict matches the ground truth: a right answer (an accepted variant, missing capitals, "
            "punctuation or accents included) passes; an answer with a real error does not.",
        ),
        Criterion(
            "errors_named",
            "judge",
            "Each real error listed in the ground truth is named, with the right fix. Not applicable when "
            "the ground truth lists no error.",
        ),
        Criterion(
            "no_false_errors",
            "judge",
            "No error is reported on something that is correct French for this task (a valid variant such "
            "as «nous préférons» for «on préfère» is not an error).",
        ),
        Criterion(
            "explained",
            "judge",
            "The explanations are in English, short, and name the rule or the right form.",
        ),
        Criterion(
            "corrected_line",
            "judge",
            "The corrected sentence is the learner's own sentence made right, keeping their meaning, not "
            "the stored example answer swapped in.",
        ),
    ),
    # The Courrier: the correspondent's in-character answer to the learner's letter.
    "courrier": (
        Criterion("served", "check", "The correspondent answered: no stock «je l'ai bien lu» acknowledgement or local fallback."),
        Criterion(
            "takes_up",
            "judge",
            "The reply responds to what the learner actually wrote (its content, its details), not with a "
            "line that would fit any letter.",
        ),
        Criterion(
            "honours_no",
            "judge",
            "If the learner refuses or says no, the reply accepts it and does not act as if they agreed. "
            "Not applicable when the learner does not refuse.",
        ),
        Criterion(
            "off_script",
            "judge",
            "If the learner asks a question or mentions something off-topic, the reply answers or "
            "acknowledges it in character. Not applicable when there is nothing off-script.",
        ),
        Criterion(
            "in_character",
            "judge",
            "The reply stays a person in the story: it never corrects, grades or praises the learner's French.",
        ),
        Criterion(
            "register",
            "judge",
            "The reply uses the register the thread declares (tu or vous) for the learner, consistently.",
        ),
        Criterion(
            "consistent",
            "judge",
            "The reply does not contradict the learner or the thread (whose grandmother, which size, which "
            "day) and does not invent people outside the story.",
        ),
        Criterion(
            "level_french",
            "judge",
            "The reply is correct, natural French, short and simple enough for the learner's level.",
        ),
    ),
    # The correction shown under a free sentence (the Courrier and Journal corrector).
    "correction": (
        Criterion("checked", "check", "The model's correction completed: no deterministic-only fallback."),
        Criterion(
            "verdict_right",
            "check",
            "A sentence the ground truth calls correct gets no correction; a sentence with real errors gets at least one.",
        ),
        Criterion(
            "spans_real",
            "check",
            "Every corrected fragment is copied from the learner's own sentence.",
        ),
        Criterion(
            "errors_caught",
            "judge",
            "Each error listed in the ground truth is corrected, with the right fix. Not applicable when "
            "the ground truth lists no error.",
        ),
        Criterion(
            "no_false_errors",
            "judge",
            "Nothing correct is marked wrong (for example «je suis», an intonation question, a «tu» the "
            "learner chose), and no style preference is presented as an error.",
        ),
        Criterion(
            "explained",
            "judge",
            "Every explanation is in English, short, and names the rule or the fixed form.",
        ),
        Criterion(
            "corrected_answer",
            "judge",
            "The corrected sentence is the learner's sentence with the errors fixed and the meaning kept.",
        ),
    ),
}


def criteria_version() -> str:
    blob = json.dumps({s: [asdict(c) for c in cs] for s, cs in CRITERIA.items()}, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


CRITERIA_VERSION = criteria_version()


def judged(surface: str) -> tuple[Criterion, ...]:
    return tuple(c for c in CRITERIA[surface] if c.by == "judge")
