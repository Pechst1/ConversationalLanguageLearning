"""#134: the compact lemma tables answer exactly what spaCy's own tables answer."""
from __future__ import annotations

from pathlib import Path

import pytest

spacy = pytest.importorskip("spacy")
MODEL = "fr_core_news_sm"
pytest.importorskip(MODEL)

from app.services import compact_lemmas  # noqa: E402

SENTENCES = [
    "Ils sont allés au marché hier soir, puis nous avons mangé des pommes.",
    "Je me suis levée tôt ; les enfants jouaient dans les rues pavées de Lyon.",
    "Qu'est-ce que vous auriez fait à ma place ? Elle n'en savait rien.",
    "Odile a rendu la clé au concierge, qui l'attendait sur les escaliers.",
    "Les 1ers jours, on s'est perdus : c'était beau, étrange et très fatigant.",
    "Aurions-nous dû partir plus tôt ? Peut-être, mais il pleuvait des cordes.",
]


@pytest.fixture(scope="module")
def pipelines(tmp_path_factory: pytest.TempPathFactory):
    out = compact_lemmas.build(MODEL, tmp_path_factory.mktemp("compact") / "tables")
    return spacy.load(MODEL), compact_lemmas.load(MODEL, out), out


def test_same_lemmas_on_sentences(pipelines) -> None:
    full, compact, _ = pipelines
    for text in SENTENCES:
        assert [t.lemma_ for t in compact(text)] == [t.lemma_ for t in full(text)], text


def test_every_table_answers_like_the_original(pipelines) -> None:
    full, compact, _ = pipelines
    original = full.get_pipe("lemmatizer").lookups
    packed = compact.get_pipe("lemmatizer").lookups

    lookup = original.get_table("lemma_lookup")
    for n, (key, value) in enumerate(lookup.items()):
        if n % 97 == 0:  # ~2,200 of the 217k rows; the full sweep takes minutes
            assert packed.get_table("lemma_lookup").get(key) == list(value)
    assert packed.get_table("lemma_lookup").get("pas-un-mot-du-tout") is None

    for pos in ("noun", "verb", "adj", "adv"):
        words = original.get_table("lemma_index").get(pos, [])
        compact_words = packed.get_table("lemma_index").get(pos, {})
        assert all(w in compact_words for w in list(words)[::50])
        assert "pas-un-mot-du-tout" not in compact_words
        exceptions = original.get_table("lemma_exc").get(pos, {})
        compact_exc = packed.get_table("lemma_exc").get(pos, {})
        for word, lemmas in list(exceptions.items())[::50]:
            assert compact_exc.get(word, []) == list(lemmas)
        assert packed.get_table("lemma_rules").get(pos, []) == original.get_table("lemma_rules").get(pos, [])


def test_tables_are_small(pipelines) -> None:
    _, _, out = pipelines
    size = sum(f.stat().st_size for f in Path(out).rglob("*") if f.is_file())
    assert size < 20 * 1024 * 1024


def test_missing_tables_are_reported_for_the_fallback(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        compact_lemmas.load(MODEL, tmp_path / "nowhere")
