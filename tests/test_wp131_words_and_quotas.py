"""WP-131 — contextual words and reachable quotas.

1. **Throttle smoothing.** Review accuracy scales new intake continuously (full
   at 85 %, half at 70 %), so an average learner near the old 80 % cliff no longer
   flips between ~8 and ~3 new words a day on noise. A struggling learner is
   still halved; the backlog's halving keeps its hysteresis.
2. **Reachable quotas.** The drill reports what the day's allowance still holds
   after its deck (``new_words_left_today``); Soutenu and Intensif reach their 18
   and 30 words through bounded continuations, never past the server's room,
   never twice the same word, whatever the order of journey and drill, reloads or
   tabs. «Encore 5 minutes» stays review-only.
3. **Contextual words.** B1/B2/C1 tentpole days get anchors read off the lines of
   their own level (``app/data/season/s1/lexicon.json``), with the review's floor;
   a foundational word only when it is due. New-word order keeps the list but
   adds scene relevance and diversity (no numeral blocks, no corpus blocks).
"""
from __future__ import annotations

import json
import random
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.models.daily_journey import DailyJourney
from app.db.models.progress import ReviewLog, UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services import intake_throttle, season_lexicon, vocabulary_pace
from app.services.intake_throttle import ThrottleSignals, accuracy_factor, decide, intake_factor
from app.services.journey_contracts import rhythm_caps
from app.services.journey_rhythm import RHYTHM_BUDGET_SECONDS
from app.services.streak import local_today
from app.services.word_order import NewWord, longest_numeral_run, order_new_words
from tests import walk_checks_wp131
from tests.test_journey_events import make_user

NOW = datetime(2026, 10, 5, 8, 0, tzinfo=UTC)
RHYTHM_MINUTES = {"leger": 5, "regulier": 10, "soutenu": 20, "intensif": 30}


# ---------------------------------------------------------------------------
# 1. Throttle smoothing
# ---------------------------------------------------------------------------


def _signals(accuracy: float | None, backlog_days: float = 0.2) -> ThrottleSignals:
    return ThrottleSignals(
        backlog_seconds=int(backlog_days * 1000),
        capacity_seconds=1000,
        backlog_days=backlog_days,
        due_counts={},
        accuracy=accuracy,
        reviews=60 if accuracy is not None else 0,
    )


def test_accuracy_scales_intake_continuously() -> None:
    assert accuracy_factor(None) == 1.0
    assert accuracy_factor(0.92) == accuracy_factor(0.85) == 1.0
    assert accuracy_factor(0.82) == 0.9
    assert accuracy_factor(0.80) == 0.83
    assert accuracy_factor(0.78) == 0.77
    # The struggling learner keeps the protection: half at 70 % and below.
    assert accuracy_factor(0.70) == accuracy_factor(0.62) == 0.5
    # Monotone: more accuracy never means fewer words.
    values = [accuracy_factor(a / 100) for a in range(60, 95)]
    assert values == sorted(values)


def _daily_quotas(accuracies: list[float], *, graded: bool, quota: int = 10) -> list[int]:
    """Replays the throttle over a month of 7-day accuracies, old rule or new."""

    active, since, out = False, None, []
    for day, accuracy in enumerate(accuracies):
        now = NOW + timedelta(days=day)
        signals = _signals(accuracy)
        was = active
        active, reasons = decide(signals, was_active=was, since=since, now=now)
        if active != was:
            since = now if active else None
        if graded:
            factor = intake_factor(signals, active=active, backlog_episode="backlog" in reasons)
        else:  # the pre-WP-131 rule: a flat half while engaged
            factor = 0.5 if active else 1.0
        out.append(int(quota * factor))
    return out


def _average_learner(seed: int, days: int = 30) -> list[float]:
    """7-day review accuracy of an average learner: about 80 % a day, ~20 reviews
    a day (a day's share is noisy, ±9 points), read over the trailing week."""

    rng = random.Random(seed)
    daily = [min(1.0, max(0.4, rng.gauss(0.80, 0.09))) for _ in range(days + 6)]
    return [sum(daily[day : day + 7]) / 7 for day in range(days)]


def test_an_average_learners_intake_no_longer_swings_on_noise() -> None:
    import statistics

    old_months, new_months, old_flips = [], [], 0
    for seed in range(40):  # forty runs of the same learner, only the noise differs
        accuracies = _average_learner(seed)
        old, new = _daily_quotas(accuracies, graded=False), _daily_quotas(accuracies, graded=True)
        old_months.append(sum(old))
        new_months.append(sum(new))
        old_flips += sum(1 for a, b in zip(old, old[1:], strict=False) if abs(b - a) >= 5)
        # Within a month: a word or two from one day to the next, never half.
        assert max(abs(b - a) for a, b in zip(new, new[1:], strict=False)) <= 2, (seed, new)
        assert min(new) >= 5  # a bad week (≈ 72 %) costs words, gradually
    # Before: one noisy morning under 80 % halved intake (10 → 5) for days, and
    # most runs of an 80 % learner spent the month halved.
    assert old_flips >= 20 and statistics.median(old_months) <= 190
    # After: the month depends on the learner's accuracy, not on the noise.
    assert min(new_months) > statistics.median(old_months)
    assert statistics.pstdev(new_months) < 0.6 * statistics.pstdev(old_months)


def test_a_struggling_learner_is_still_halved() -> None:
    assert _daily_quotas([0.62] * 10, graded=True) == [5] * 10


def test_a_backlog_still_halves_with_its_hold() -> None:
    signals = _signals(None, backlog_days=1.6)
    active, reasons = decide(signals, was_active=False, since=None, now=NOW)
    assert active and intake_factor(signals, active=True, backlog_episode="backlog" in reasons) == 0.5
    # Pile cleared inside the hold: still halved (the episode is a backlog one).
    cleared = _signals(None, backlog_days=0.1)
    assert intake_factor(cleared, active=True, backlog_episode=True) == 0.5
    # An accuracy episode with no pile is graded, not halved.
    assert intake_factor(_signals(0.79, 0.1), active=True, backlog_episode=False) == 0.8


def _learner(db: Session, *, minutes: int = 10, quota: int | None = None) -> User:
    user = make_user(db, f"wp131-{uuid.uuid4().hex[:8]}@example.com")
    user.daily_goal_minutes = minutes
    user.new_words_per_day = quota
    user.timezone = "Europe/Paris"
    db.flush()
    return user


_CREATED: list[int] = []


@pytest.fixture(scope="module", autouse=True)
def _leave_the_catalogue_as_found(db_engine):
    """A request in this module may sync the core list into the shared database;
    later suites order their words without it, so it leaves with the module."""

    from sqlalchemy.orm import sessionmaker

    from app.services.core_lexicon import CORE_DECK

    db = sessionmaker(bind=db_engine)()
    had_core = db.query(VocabularyWord.id).filter(VocabularyWord.deck_name == CORE_DECK).first() is not None
    db.close()
    yield
    if had_core:
        return
    db = sessionmaker(bind=db_engine)()
    core = db.query(VocabularyWord.id).filter(VocabularyWord.deck_name == CORE_DECK).subquery()
    progress = db.query(UserVocabularyProgress.id).filter(UserVocabularyProgress.word_id.in_(core)).subquery()
    db.query(ReviewLog).filter(ReviewLog.progress_id.in_(progress)).delete(synchronize_session=False)
    db.query(UserVocabularyProgress).filter(UserVocabularyProgress.word_id.in_(core)).delete(synchronize_session=False)
    db.query(VocabularyWord).filter(VocabularyWord.deck_name == CORE_DECK).delete(synchronize_session=False)
    db.commit()
    db.close()


@pytest.fixture(autouse=True)
def _forget_test_words(db_session: Session):
    """The suite shares one database: the cards this module makes (rank 1, Anki
    cards) would otherwise be every later learner's first new words."""

    yield
    db_session.rollback()
    if not _CREATED:
        return
    progress_ids = [
        row.id for row in db_session.query(UserVocabularyProgress).filter(UserVocabularyProgress.word_id.in_(_CREATED))
    ]
    if progress_ids:
        db_session.query(ReviewLog).filter(ReviewLog.progress_id.in_(progress_ids)).delete(synchronize_session=False)
        db_session.query(UserVocabularyProgress).filter(UserVocabularyProgress.id.in_(progress_ids)).delete(
            synchronize_session=False
        )
    db_session.query(VocabularyWord).filter(VocabularyWord.id.in_(_CREATED)).delete(synchronize_session=False)
    db_session.commit()
    _CREATED.clear()


def _word(db: Session, text: str, *, rank: int = 100) -> VocabularyWord:
    word = VocabularyWord(
        word=text,
        normalized_word=text,
        language="fr",
        english_translation=f"{text} (en)",
        is_anki_card=True,
        frequency_rank=rank,
    )
    db.add(word)
    db.flush()
    _CREATED.append(int(word.id))
    return word


def test_a_learner_at_78_percent_takes_seven_words_not_five(db_session: Session) -> None:
    user = _learner(db_session, quota=10)
    rows = []
    for index in range(5):
        word = _word(db_session, f"thrq{index}{uuid.uuid4().hex[:4]}")
        progress = UserVocabularyProgress(
            user_id=user.id, word_id=word.id, reps=3, state="review",
            due_at=NOW + timedelta(days=5), next_review_date=NOW + timedelta(days=5),
            created_at=NOW - timedelta(days=20),
        )
        db_session.add(progress)
        rows.append(progress)
    db_session.flush()
    for index in range(50):  # 39 right, 11 wrong: 78 %
        db_session.add(ReviewLog(progress_id=rows[index % 5].id, rating=2 if index < 39 else 0,
                                 review_date=NOW - timedelta(days=1)))
    db_session.flush()
    status = intake_throttle.throttle_status(db_session, user, now=NOW)
    assert status.active and status.reasons == ("accuracy",)  # the notice still says «on consolide»
    assert status.factor == 0.77
    assert vocabulary_pace.daily_quota(db_session, user, now=NOW) == 7


# ---------------------------------------------------------------------------
# 2. Reachable quotas
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rhythm", ["leger", "regulier", "soutenu", "intensif"])
def test_the_drill_room_is_the_rhythms_quota_less_the_journeys_share(db_session: Session, rhythm: str) -> None:
    user = _learner(db_session, minutes=RHYTHM_MINUTES[rhythm])
    quota = vocabulary_pace.RHYTHM_NEW_WORDS[rhythm]
    share = rhythm_caps(RHYTHM_BUDGET_SECONDS[rhythm]).journey_new_words
    room, _ = vocabulary_pace.drill_new_word_room(db_session, user, now=NOW)
    assert room == quota - share  # Léger 3, Régulier 6, Soutenu 10, Intensif 18
    # The journey planned fewer than its share: the drill gets the difference.
    _plan_journey(db_session, user, [_word(db_session, f"res{rhythm}{i}").id for i in range(2)])
    room, reserved = vocabulary_pace.drill_new_word_room(db_session, user)
    assert room == quota - 2 and len(reserved) == 2


def _plan_journey(db: Session, user: User, word_ids: list[int]) -> DailyJourney:
    journey = DailyJourney(
        id=uuid.uuid4(),
        user_id=user.id,
        local_date=local_today(user),
        timezone="Europe/Paris",
        status="active",
        budget_seconds=600,
        plan_selection={vocabulary_pace.JOURNEY_NEW_WORDS_KEY: list(word_ids)},
        created_at=datetime.now(UTC),
    )
    db.add(journey)
    db.flush()
    return journey


def _login(client: TestClient, db: Session, *, minutes: int) -> tuple[dict, User]:
    email = f"wp131-{uuid.uuid4().hex[:8]}@example.com"
    password = "wp131-secure-pass"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "target_language": "fr", "native_language": "en"},
    )
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    user = db.get(User, UUID(str(decode_token(token)["sub"])))
    user.daily_goal_minutes = minutes
    user.new_words_per_day = None
    user.timezone = "Europe/Paris"
    db.flush()
    return {"Authorization": f"Bearer {token}"}, user


def _supply(db: Session, count: int, tag: str) -> list[VocabularyWord]:
    return [_word(db, f"{tag}{index:03d}", rank=index + 1) for index in range(count)]


SESSION = {"limit": 50, "due_limit": 30, "fragile_limit": 12, "new_limit": 8, "topic_limit": 8, "linked_limit": 8}


def _more(n: int) -> dict:
    """review.tsx's «Encore N mots» continuation."""

    return {"limit": n + 30, "due_limit": 30, "fragile_limit": 0, "new_limit": n, "topic_limit": 0, "linked_limit": 0}


def _deck(client: TestClient, headers: dict, params: dict) -> dict:
    response = client.get("/api/v1/vocabulary/due-context", headers=headers, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def _review_new(client: TestClient, headers: dict, deck: dict) -> list[int]:
    ids = [item["word_id"] for item in deck["new_words"]]
    for word_id in ids:
        reviewed = client.post(
            "/api/v1/anki/review", headers=headers, json={"word_id": word_id, "rating": 2, "format": "flashcard"}
        )
        assert reviewed.status_code == 200, reviewed.text
    return ids


def test_intensif_reaches_its_30_words_in_bounded_sessions(client: TestClient, db_session: Session) -> None:
    headers, user = _login(client, db_session, minutes=30)
    _supply(db_session, 60, "intens")
    reserved = [_word(db_session, f"scene{index}", rank=1000 + index).id for index in range(12)]
    _plan_journey(db_session, user, reserved)  # the journey took its 12

    first = _deck(client, headers, SESSION)
    assert len(first["new_words"]) == 8 and first["new_words_left_today"] == 10
    introduced = _review_new(client, headers, first)
    second = _deck(client, headers, _more(min(8, first["new_words_left_today"])))
    assert len(second["new_words"]) == 8 and second["new_words_left_today"] == 2
    introduced += _review_new(client, headers, second)
    third = _deck(client, headers, _more(second["new_words_left_today"]))
    assert len(third["new_words"]) == 2 and third["new_words_left_today"] == 0
    introduced += _review_new(client, headers, third)

    assert len(introduced) == len(set(introduced)) == 18
    assert not set(introduced) & set(reserved), "the drill never introduces a reserved word"
    # The day is full: 18 + the journey's 12 = 30, and no request opens more.
    assert _deck(client, headers, _more(8))["new_words"] == []
    assert _deck(client, headers, {**SESSION, "new_limit": 50})["new_words"] == []


def test_soutenu_gets_its_18_with_one_continuation(client: TestClient, db_session: Session) -> None:
    headers, user = _login(client, db_session, minutes=20)
    _supply(db_session, 40, "sout")
    _plan_journey(db_session, user, [_word(db_session, f"ssc{i}", rank=900 + i).id for i in range(8)])
    first = _deck(client, headers, SESSION)
    assert (len(first["new_words"]), first["new_words_left_today"]) == (8, 2)
    _review_new(client, headers, first)
    second = _deck(client, headers, _more(first["new_words_left_today"]))
    assert (len(second["new_words"]), second["new_words_left_today"]) == (2, 0)


def test_the_server_clamps_a_greedy_request_to_the_room(client: TestClient, db_session: Session) -> None:
    headers, _user = _login(client, db_session, minutes=30)
    _supply(db_session, 60, "greedy")
    deck = _deck(client, headers, {**SESSION, "new_limit": 50})
    # Before the journey is planned, the drill leaves it its share (12 of 30).
    assert len(deck["new_words"]) == 18 and deck["new_words_left_today"] == 0


def test_encore_five_minutes_stays_review_only(client: TestClient, db_session: Session) -> None:
    headers, _user = _login(client, db_session, minutes=30)
    _supply(db_session, 20, "encore")
    deck = _deck(client, headers, {"limit": 15, "due_limit": 15, "fragile_limit": 15, "new_limit": 0,
                                   "topic_limit": 0, "linked_limit": 0})
    assert deck["new_words"] == [] and deck["new_words_left_today"] is None


def test_a_short_supply_offers_no_empty_continuation() -> None:
    # The deck served fewer new words than it was allowed: the supply ran out,
    # so «Encore N mots» would open an empty deck.
    assert vocabulary_pace.new_words_left_today(18, 8, 3) == 0
    assert vocabulary_pace.new_words_left_today(18, 8, 8) == 10
    assert vocabulary_pace.new_words_left_today(None, 0, 0) is None


def test_drill_first_and_journey_first_introduce_the_same_total(db_session: Session) -> None:
    totals = []
    for order in ("drill_first", "journey_first"):
        user = _learner(db_session, minutes=20)  # Soutenu: 18 a day, journey share 8
        if order == "drill_first":
            room, _ = vocabulary_pace.drill_new_word_room(db_session, user)
            for index in range(room):
                db_session.add(UserVocabularyProgress(user_id=user.id, word_id=_word(db_session, f"df{index}{uuid.uuid4().hex[:4]}").id, reps=1))
            db_session.flush()
            journey = vocabulary_pace.journey_new_word_room(db_session, user)
            _plan_journey(db_session, user, [_word(db_session, f"dj{i}{uuid.uuid4().hex[:4]}").id for i in range(journey)])
        else:
            journey = vocabulary_pace.journey_new_word_room(db_session, user)
            journey = min(journey, rhythm_caps(RHYTHM_BUDGET_SECONDS["soutenu"]).journey_new_words)
            _plan_journey(db_session, user, [_word(db_session, f"jj{i}{uuid.uuid4().hex[:4]}").id for i in range(journey)])
        room, reserved = vocabulary_pace.drill_new_word_room(db_session, user)
        total = len(vocabulary_pace.introduced_today(db_session, user) | reserved) + room
        totals.append(total)
    assert totals == [18, 18]


def test_two_tabs_and_a_reload_introduce_each_word_once(client: TestClient, db_session: Session, pinned_clock) -> None:
    # Five requests read the learner's Paris «today»; pinned at noon UTC they share one day (WP-153).
    headers, user = _login(client, db_session, minutes=10)  # Régulier: drill room 6
    _supply(db_session, 30, "tabs")
    tab_a = _deck(client, headers, SESSION)
    tab_b = _deck(client, headers, SESSION)
    assert [w["word_id"] for w in tab_a["new_words"]] == [w["word_id"] for w in tab_b["new_words"]]
    # Tab A reviews half its deck; a reload shows the rest of the same words.
    half = tab_a["new_words"][:3]
    _review_new(client, headers, {"new_words": half})
    reload = _deck(client, headers, SESSION)
    assert [w["word_id"] for w in reload["new_words"]] == [w["word_id"] for w in tab_a["new_words"][3:]]
    # Both tabs then finish: every word has one card, and the day holds 6.
    _review_new(client, headers, tab_a)
    _review_new(client, headers, tab_b)
    rows = db_session.query(UserVocabularyProgress).filter(UserVocabularyProgress.user_id == user.id).all()
    assert len(rows) == len({row.word_id for row in rows}) == 6
    assert _deck(client, headers, SESSION)["new_words"] == []


def test_a_reserved_word_is_never_a_linked_card(db_session: Session) -> None:
    from app.services.progress import ProgressService

    user = _learner(db_session, minutes=10)
    reserved = _word(db_session, "reservelink")
    payload = ProgressService(db_session).get_vocabulary_due_context(
        user=user, new_limit=4, linked_limit=4, linked_word_ids=[reserved.id],
        exclude_new_word_ids={reserved.id}, direction=None,
    )
    assert all(item["word_id"] != reserved.id for item in payload["linked_words"] + payload["new_words"])


# ---------------------------------------------------------------------------
# 3. Contextual words
# ---------------------------------------------------------------------------


def test_the_season_lexicon_file_is_current() -> None:
    """``scripts/build_season_lexicon.py`` must be rerun after a bible or level edit."""

    on_disk = json.loads(season_lexicon.lexicon_path("s1").read_text(encoding="utf-8"))
    assert on_disk == season_lexicon.build("s1")


def test_every_advanced_anchor_is_a_word_of_its_own_levels_lines() -> None:
    from app.services.level_coverage import CLOSED_CLASS_WORDS
    from app.services.lexical_coverage import load_lexicon
    from app.services.scene_items import contains_surface
    from app.services.season.format import load_season

    season = load_season("s1")
    data = season_lexicon.load("s1")
    lexicon = load_lexicon()
    counts = dict.fromkeys(season_lexicon.ADVANCED_LEVELS, 0)
    for tentpole in season.tentpoles.values():
        for day in tentpole.days:
            rows = data["days"][season_lexicon.day_key(tentpole.id, day.day, day.variant)]
            for level in season_lexicon.ADVANCED_LEVELS:
                texts = [say.text(level.upper()) for say in season_lexicon._says(day)]
                learner = season_lexicon._band_level(level)
                for row in rows[level]:
                    assert contains_surface(row["sentence_fr"], row["surface_fr"])
                    assert any(row["sentence_fr"] in text for text in texts), (level, row)
                    entry = lexicon.lemmas[row["lemma"]]
                    assert entry.get("pos") in season_lexicon.CONTENT_POS and not entry.get("numeral")
                    assert row["lemma"] not in CLOSED_CLASS_WORDS
                    band = season_lexicon._band_level(row["band"])
                    if row["role"] == "new":
                        counts[level] += 1
                        # The review's floor: the learner's band or one below, never above.
                        assert season_lexicon.floor_level(learner) <= band <= learner
                    else:
                        assert band < season_lexicon.floor_level(learner)
    # Every advanced level has its own words to practise (not the A2 lexicon).
    assert min(counts.values()) >= 100, counts


def test_lemma_resolution_prefers_precision() -> None:
    assert season_lexicon.lemma_of("est") == "être"
    assert season_lexicon.lemma_of("refuse") == "refuser"
    assert season_lexicon.lemma_of("boulangère") == "boulanger"
    assert season_lexicon.lemma_of("regarde") == "regarder"
    assert season_lexicon.lemma_of("paris", capitalised=True) is None
    assert season_lexicon.lemma_of("signe", capitalised=True) == "signer"


def _nameless(sentence: str) -> bool:
    from app.services.lexical_coverage import tokenize

    names = season_lexicon._season_cast_tokens("s1")
    return not any(token.key in names for token in tokenize(sentence))


def _tentpole_scenario(level: str, draft_line: str) -> SimpleNamespace:
    page = {"season_id": "s1", "tentpole": "t1", "day": "a", "variant": None, "band": level.upper()}
    draft = {"premise_fr": "", "panels": [{"narration_fr": "", "dialogue": [{"character_id": "x", "text_fr": draft_line}]}]}
    return SimpleNamespace(story_context={"season": {"kind": "tentpole", "page": page}, "draft": draft}, level_band=level.upper())


def test_b2_scene_words_come_from_the_printed_lines_and_are_glossed(db_session: Session) -> None:
    user = _learner(db_session)
    user.native_language = "de"
    anchors = season_lexicon.page_anchors({"season_id": "s1", "tentpole": "t1", "day": "a", "band": "B2"})
    new = [a for a in anchors if a["role"] == "new" and _nameless(a["sentence_fr"])]
    assert len(new) >= 2, "t1.a holds B2 words in lines that name nobody"
    line = " ".join(a["sentence_fr"] for a in new[:2])
    entries = season_lexicon.scene_entries(db_session, user=user, scenario=_tentpole_scenario("b2", line))
    assert [e["lemma"] for e in entries] == [a["lemma"] for a in new[:2]]
    assert all(e["gloss_native"] and e["line_ref"].startswith("panel:") for e in entries)
    assert entries[0]["gloss_native"] == new[0]["gloss"]["de"]
    # Below B1 the bible's own lexicon serves: nothing derived.
    assert season_lexicon.scene_entries(db_session, user=user, scenario=_tentpole_scenario("a2", line)) == []


def test_a_foundational_word_is_offered_only_when_it_is_due(db_session: Session) -> None:
    user = _learner(db_session)
    anchors = season_lexicon.page_anchors({"season_id": "s1", "tentpole": "t1", "day": "a", "band": "B2"})
    base = next(a for a in anchors if a["role"] == "foundational" and _nameless(a["sentence_fr"]))
    scenario = _tentpole_scenario("b2", base["sentence_fr"])
    assert all(e["lemma"] != base["lemma"] for e in season_lexicon.scene_entries(db_session, user=user, scenario=scenario))
    word = _word(db_session, base["lemma"])
    progress = UserVocabularyProgress(user_id=user.id, word_id=word.id, reps=4, state="review",
                                      due_at=datetime.now(UTC) - timedelta(days=1),
                                      next_review_date=datetime.now(UTC) - timedelta(days=1))
    db_session.add(progress)
    db_session.flush()
    entries = season_lexicon.scene_entries(db_session, user=user, scenario=scenario)
    assert entries[0]["lemma"] == base["lemma"] and entries[0]["anchor_role"] == "foundational"
    # Held but not due: not offered (it is not a weakness today).
    progress.due_at = progress.next_review_date = datetime.now(UTC) + timedelta(days=9)
    db_session.flush()
    assert all(e["lemma"] != base["lemma"] for e in season_lexicon.scene_entries(db_session, user=user, scenario=scenario))


def test_a_scene_word_is_never_practised_in_a_line_that_names_a_character(db_session: Session) -> None:
    # Found by the life walk: day one's cloze «Augustin, vous êtes bien trop … pour
    # ce siècle» named Augustin before the learner had met him.
    user = _learner(db_session)
    anchors = season_lexicon.page_anchors({"season_id": "s1", "tentpole": "t1", "day": "a", "band": "C1"})
    new = next(a for a in anchors if a["role"] == "new")
    named = _tentpole_scenario("c1", f"Augustin, voici le mot {new['surface_fr']}.")
    assert season_lexicon.scene_entries(db_session, user=user, scenario=named) == []
    plain = _tentpole_scenario("c1", f"Voici le mot {new['surface_fr']}.")
    assert [e["lemma"] for e in season_lexicon.scene_entries(db_session, user=user, scenario=plain)] == [new["lemma"]]
    # The planner may cut its item from any line printing the word: one named
    # line anywhere in the scene keeps the word out.
    both = _tentpole_scenario("c1", f"Voici le mot {new['surface_fr']}. Augustin, encore {new['surface_fr']} !")
    both.story_context["draft"]["panels"].append(
        {"narration_fr": f"Voici le mot {new['surface_fr']}.", "dialogue": []}
    )
    both.story_context["draft"]["panels"][0]["dialogue"][0]["text_fr"] = f"Augustin, encore le {new['surface_fr']} !"
    assert season_lexicon.scene_entries(db_session, user=user, scenario=both) == []


def test_season_words_never_reach_above_the_level() -> None:
    from app.services.lexical_coverage import load_lexicon

    lemmas = load_lexicon().lemmas
    for level in ("A1", "A2", "B1", "B2", "C1"):
        bands = {season_lexicon._band_level(lemmas[w].get("band")) for w in season_lexicon.season_words(level)}
        assert max(bands) <= season_lexicon._band_level(level), level


def test_season_words_are_per_level() -> None:
    a1, c1 = season_lexicon.season_words("A1"), season_lexicon.season_words("C1")
    assert "clé" in a1 and len(c1) > len(a1)
    assert season_lexicon.season_words(None) == frozenset()


# ---------------------------------------------------------------------------
# 3b. New-word order
# ---------------------------------------------------------------------------


def _a1_list() -> list[NewWord]:
    adverbs = ["alors", "beaucoup", "comme", "hier", "demain", "maintenant"]
    numbers = ["deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix", "onze", "douze",
               "treize", "quatorze", "quinze", "seize", "vingt", "trente", "quarante", "cinquante"]
    verbs = ["être", "avoir", "faire", "aller", "venir", "dire", "voir", "savoir", "pouvoir", "vouloir",
             "devoir", "prendre", "donner", "parler", "manger", "boire", "habiter", "travailler", "aimer",
             "arriver", "partir", "entrer", "sortir", "demander", "répondre", "attendre", "comprendre",
             "apprendre", "écouter", "regarder"]
    words = [(w, False) for w in adverbs] + [(w, True) for w in numbers] + [(w, False) for w in verbs]
    return [NewWord(word_id=i + 1, lemma=w, numeral=n) for i, (w, n) in enumerate(words)]


def test_numerals_are_spread_not_blocked() -> None:
    pool = _a1_list()
    days: list[list[NewWord]] = []
    for _ in range(5):  # five days of one 8-word session each
        batch = order_new_words(pool, 8)
        days.append(batch)
        pool = [w for w in pool if w not in batch]
    for batch in days:
        flags = [w.numeral for w in batch]
        assert len(batch) == 8
        assert sum(flags) <= 2 and not flags[0] and longest_numeral_run(flags) <= 1
    # Over the week the list still advances: the numbers keep coming, about two a day.
    assert sum(w.numeral for batch in days for w in batch) >= 8
    # Two sessions back to back (a continuation) never make a run of four.
    assert longest_numeral_run([w.numeral for w in days[0] + days[1]]) < 4


def test_corpus_words_are_interleaved_with_curated_and_story_words() -> None:
    corpus = [NewWord(word_id=i, lemma=f"corpus{i}", corpus=True) for i in range(1, 13)]
    curated = [NewWord(word_id=100 + i, lemma=f"theme{i}") for i in range(6)]
    batch = order_new_words(corpus + curated, 8)
    flags = [w.corpus for w in batch]
    assert sum(flags) <= 4
    assert "TTT" not in "".join("T" if f else "F" for f in flags)
    # A corpus word the story uses is contextualised: it is not capped.
    story = [NewWord(word_id=200 + i, lemma=f"story{i}", corpus=True, season=True) for i in range(3)]
    first = order_new_words(corpus + curated + story, 8)
    assert [w.word_id for w in first[:3]] == [200, 201, 202]
    # Only corpus words left: the batch is still full (the list is legitimate).
    assert len(order_new_words(corpus, 8)) == 8


def test_met_words_then_story_words_then_the_list() -> None:
    words = [
        NewWord(word_id=1, lemma="liste1"),
        NewWord(word_id=2, lemma="story", season=True),
        NewWord(word_id=3, lemma="met", met=True),
        NewWord(word_id=4, lemma="liste2"),
    ]
    assert [w.word_id for w in order_new_words(words, 4)] == [3, 2, 1, 4]
    # Story words take at most half a batch: the list keeps advancing.
    many = [NewWord(word_id=10 + i, lemma=f"s{i}", season=True) for i in range(8)] + [
        NewWord(word_id=100 + i, lemma=f"l{i}") for i in range(8)
    ]
    assert sum(w.season for w in order_new_words(many, 8)) == 4
    assert order_new_words(words, 0) == []


def test_the_drill_spreads_the_a1_numbers_over_real_catalogue_rows(db_session: Session) -> None:
    from app.services.core_lexicon import ensure_core_lexicon
    from app.services.progress import ProgressService

    ensure_core_lexicon(db_session)
    user = _learner(db_session)
    service = ProgressService(db_session)
    shown: list[list[str]] = []
    for _day in range(6):
        result = service.get_vocabulary_recommendations(user=user, limit=20, due_limit=0, fragile_limit=0, new_limit=8)
        new = [item for item in result["items"] if item["bucket"] == "new"]
        shown.append([item["word"] for item in new])
        for item in new:
            db_session.add(UserVocabularyProgress(user_id=user.id, word_id=item["word_id"], reps=1,
                                                  due_at=datetime.now(UTC) + timedelta(days=30)))
        db_session.flush()
    for words in shown:
        flags = [walk_checks_wp131.is_numeral(word) for word in words]
        assert len(words) == 8 and longest_numeral_run(flags) <= 1 and sum(flags) <= 2, words
    # Spread, not skipped: the list's numbers still arrive in the first week.
    assert any(walk_checks_wp131.is_numeral(word) for words in shown for word in words), shown


def test_story_words_never_pull_the_next_sub_band_forward(db_session: Session) -> None:
    # Found by the life walk: A1 story words from A1.2 cost a third of the A1.1
    # coverage the level gate counts (known words 189 → 126).
    from app.services.core_lexicon import ensure_core_lexicon
    from app.services.progress import ProgressService

    ensure_core_lexicon(db_session)
    user = _learner(db_session)
    result = ProgressService(db_session).get_vocabulary_recommendations(
        user=user, limit=20, due_limit=0, fragile_limit=0, new_limit=8
    )
    ids = [item["word_id"] for item in result["items"] if item["bucket"] == "new"]
    rows = db_session.query(VocabularyWord).filter(VocabularyWord.id.in_(ids)).all()
    core = [row for row in rows if row.deck_name == "Lexique de base"]
    assert len(rows) == 8 and all("A1.1" in (row.topic_tags or []) for row in core)


def test_a_c1_learner_gets_no_block_of_corpus_words(db_session: Session) -> None:
    from app.services.core_lexicon import CORPUS_TAG, ensure_core_lexicon
    from app.services.progress import ProgressService

    ensure_core_lexicon(db_session)
    user = _learner(db_session)
    user.cefr_estimate = "C1.1"
    db_session.flush()
    result = ProgressService(db_session).get_vocabulary_recommendations(
        user=user, limit=20, due_limit=0, fragile_limit=0, new_limit=8
    )
    new = [item for item in result["items"] if item["bucket"] == "new"]
    rows = {row.id: row for row in db_session.query(VocabularyWord).filter(VocabularyWord.id.in_([i["word_id"] for i in new]))}
    story = season_lexicon.season_words("C1")
    bare = ["T" if CORPUS_TAG in (rows[i["word_id"]].topic_tags or []) and rows[i["word_id"]].normalized_word not in story else "F"
            for i in new]
    assert len(new) == 8 and bare.count("T") <= 4 and "TTT" not in "".join(bare), [i["word"] for i in new]


# ---------------------------------------------------------------------------
# Walk checks
# ---------------------------------------------------------------------------


def _record(quality: str, counts: list[int], words: list[list[str]] | None = None) -> dict:
    days = []
    for index, count in enumerate(counts, start=1):
        names = (words[index - 1] if words else [f"mot{index}{n}" for n in range(count)])
        days.append({"day": index, "drill": {"cards": [{"word": w, "new": True} for w in names]}})
    return {"persona": "a1-de-fresh", "quality": quality, "days": days}


def test_walk_check_swing_fires_on_a_throttle_flip_and_not_on_noise() -> None:
    assert walk_checks_wp131.check_new_word_swing(_record("average", [8, 8, 8, 8, 3, 3, 8]))
    assert walk_checks_wp131.check_new_word_swing(_record("average", [8, 8, 7, 8, 6, 5, 7, 8])) == []
    # Days 1–2 (onboarding, placement) and the other qualities are not judged.
    assert walk_checks_wp131.check_new_word_swing(_record("average", [0, 8, 8, 8])) == []
    assert walk_checks_wp131.check_new_word_swing(_record("struggling", [8, 0, 8, 0])) == []


def test_walk_check_numeral_runs() -> None:
    bad = _record("strong", [8], [["deux", "trois", "quatre", "cinq", "être", "avoir", "faire", "aller"]])
    good = _record("strong", [8], [["être", "deux", "avoir", "trois", "faire", "aller", "dire", "voir"]])
    assert walk_checks_wp131.check_numeral_runs(bad)
    assert walk_checks_wp131.check_numeral_runs(good) == []
