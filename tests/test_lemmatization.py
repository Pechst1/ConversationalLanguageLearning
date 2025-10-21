import re

from app.db.models.vocabulary import VocabularyWord
from app.services.session_service import SessionService


class FakeToken:
    def __init__(self, text: str, lemma: str | None = None, *, is_stop: bool = False) -> None:
        self.text = text
        self.lemma_ = lemma or text
        self.is_stop = is_stop
        self.is_punct = False
        self.is_space = False


class FakeDoc(list):
    pass


class FakeNLP:
    def __init__(self, mapping: dict[str, str]) -> None:
        self.mapping = mapping

    def __call__(self, text: str) -> FakeDoc:
        tokens = []
        for match in re.findall(r"[\w'’]+", text, flags=re.UNICODE):
            if "'" in match or "’" in match:
                for part in re.split(r"[’']", match):
                    if not part:
                        continue
                    lemma = self.mapping.get(part.lower(), part.lower())
                    tokens.append(FakeToken(part, lemma))
                continue
            lemma = self.mapping.get(match.lower(), match.lower())
            tokens.append(FakeToken(match, lemma))
        return FakeDoc(tokens)


def make_service(mapping: dict[str, str]) -> SessionService:
    service = SessionService.__new__(SessionService)
    service.nlp = FakeNLP(mapping)
    return service


def test_word_usage_detection_with_conjugation():
    service = make_service({"allé": "aller", "aller": "aller"})
    word = VocabularyWord(
        word="aller",
        normalized_word="aller",
        language="fr",
        english_translation="to go",
        frequency_rank=10,
    )
    learner_text = "Je suis allé au marché."
    lemmas = service._lemmatize_with_context(learner_text)
    was_used, matched = service._check_word_usage(word, learner_text, lemmas)

    assert was_used is True
    assert matched.lower() == "allé"


def test_lemmatization_respects_context():
    mapping = {"étais": "être", "passais": "passer", "passé": "passer"}
    service = make_service(mapping)
    learner_text = "Quand j'étais petit, je passais du temps à étudier."
    lemmas = service._lemmatize_with_context(learner_text)

    assert "être" in lemmas
    assert "passer" in lemmas
    assert "j" in lemmas  # original tokens are preserved
