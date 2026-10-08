"""WP-39 — regressions found on the 2026-09-11 browser walk of the new surfaces.

Two defects, both of the "the product quietly does the opposite of what it
claims" kind:

* a day-one learner whose declared level equals the measured floor was labelled
  ``estimate_source == "measured"`` (and Le Dossier said «mesuré · vérifié»);
* the journey was created with ``preferred_input_mode == "text"`` by default, so
  the server never offered voice and WP-27's «Parler» never rendered.
"""

from __future__ import annotations

from pathlib import Path

from app.services.cefr_progress import CEFRProgressService
from tests.test_cefr_progress import _user

FRONTEND = Path(__file__).resolve().parents[1] / "web-frontend"


def test_a_prior_equal_to_the_measured_floor_is_still_a_prior(db_session):
    """A1.1 declared, A1.1 measured on zero attempts: nothing was measured."""
    user = _user(db_session, email="cefr-equal-prior@example.com", proficiency_level="A1")

    payload = CEFRProgressService(db_session).recompute(user, source="test")

    assert payload["computed_estimate"] == "A1.1"
    assert payload["estimate"] == "A1.1"
    assert payload["estimate_source"] == "declared"
    assert payload["breakdown"]["status"] == "unverified"


def test_the_journey_is_created_for_voice_unless_the_learner_chose_text():
    hook = (FRONTEND / "components/atelier-v2/journey/useDailyJourney.ts").read_text(encoding="utf-8")
    page = (FRONTEND / "pages/atelier.tsx").read_text(encoding="utf-8")

    assert "preferredInputMode = 'voice'" in hook
    assert "preferredInputMode = 'text'" not in hook
    assert "preferredInputMode: readAnswerMode('voice')" in page
    assert "from '@/components/atelier-v2/journey/voice-answer'" in page
