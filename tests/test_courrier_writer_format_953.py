"""#953: a friend's note in tu is never framed as a formal e-mail or a form.

The walk of 20 Nov read «Un mot de Marin», a chat line in tu, under a composer
that asked for «Ein Betreff, eine Anrede, der Text, ein Gruß» and a button
«E-Mail senden». The letter's shape was drawn by a die that never asked who
writes. These tests hold the die, the variety draw that feeds it, and the
stored letter's way back to the screen.
"""

from __future__ import annotations

from app.services import missions as missions_module
from app.services.missions import MissionGenerator

FORMAL = {"email_formal", "admin_form"}
SEEDS = [("user-953", day, "story_born") for day in range(400)]


def test_a_tu_writer_is_never_dealt_a_formal_email_or_a_form():
    for channel in ("message", "email", "formal_email", "admin_form", "chat", "voice_note"):
        for recent in (set(), {"chat_message"}, {"chat_message", "voicemail_reply"}):
            drawn = {
                MissionGenerator._choose_format(
                    channel=channel,
                    recent_formats=recent,
                    seed=seed,
                    writer_register="tu / registre familier",
                )
                for seed in SEEDS
            }
            assert drawn <= {"chat_message", "voicemail_reply"}, (channel, recent, drawn)


def test_a_vous_writer_can_still_send_an_email():
    drawn = {
        MissionGenerator._choose_format(
            channel="message", recent_formats=set(), seed=seed, writer_register="vous / registre poli"
        )
        for seed in SEEDS
    }
    assert "email_formal" in drawn
    assert MissionGenerator._choose_format(
        channel="email", recent_formats=set(), seed=SEEDS[0], writer_register="vous"
    ) in {"email_formal", "chat_message", "voicemail_reply"}


def test_the_variety_draw_hands_the_story_writers_register_to_the_die():
    generator = MissionGenerator.__new__(MissionGenerator)
    for seed in SEEDS[:200]:
        variety = generator._choose_variety(
            active_category=None,
            recent_variety=[],
            fuel_source="vocab",
            seed=seed,
            writer_register="tu / warm informal",
        )
        assert variety["mission_format"] not in FORMAL, (seed, variety.get("channel"))


def test_a_stored_tu_letter_reaches_the_screen_as_a_message():
    format_for_writer = missions_module.format_for_writer
    letter_writer_register = missions_module.letter_writer_register
    stored = {
        "mission_format": "email_formal",
        "custom_context": {"source": "story_born", "relationship": "marin", "register": "tu / registre familier"},
        "messenger": {"contact_name": "Marin", "target_register": "tu / registre familier"},
    }
    assert letter_writer_register(stored) == "tu"
    assert format_for_writer(stored["mission_format"], letter_writer_register(stored)) == "chat_message"
    agency = {"mission_format": "email_formal", "target_register": "vous / administrative formal"}
    assert format_for_writer(agency["mission_format"], letter_writer_register(agency)) == "email_formal"
    assert format_for_writer("voicemail_reply", "tu") == "voicemail_reply"
    assert missions_module.FORMAL_MISSION_FORMATS == frozenset(FORMAL)
