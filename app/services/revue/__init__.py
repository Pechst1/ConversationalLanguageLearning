"""La Revue de Romy — real-world French inside the learner's fictional life (WP-119).

Three parts, not one object (§3): the editorial dossier (what is true, with
provenance, shared by every learner), the session plan (this learner, this time) and
the conversation state (what happened, replayed on resume). ``policy`` holds the
editorial data; ``checks`` the checks on meaning (§4.2).

See ``docs/implementation/atelier-v2/WP-119-LA-REVUE-DE-ROMY.md``.
"""

from __future__ import annotations

from app.services.revue.checks import CheckResult, run_dossier_checks
from app.services.revue.dossier import (
    Angle,
    Claim,
    EditorialDossier,
    Entity,
    Place,
    Source,
    TimeScope,
    fold,
    quote_word_count,
)
from app.services.revue.session import (
    Activities,
    Budget,
    Guest,
    LearnerContext,
    SessionPlan,
    StageCast,
    StagePlan,
    Support,
    VocabItem,
    next_support_level,
    plan_for,
)
from app.services.revue.state import ConversationState, StateEvent

__all__ = [
    "Activities",
    "Angle",
    "Budget",
    "CheckResult",
    "Claim",
    "ConversationState",
    "EditorialDossier",
    "Entity",
    "Guest",
    "LearnerContext",
    "Place",
    "SessionPlan",
    "Source",
    "StageCast",
    "StagePlan",
    "StateEvent",
    "Support",
    "TimeScope",
    "VocabItem",
    "fold",
    "next_support_level",
    "plan_for",
    "quote_word_count",
    "run_dossier_checks",
]
