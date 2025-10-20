import spacy

from app.core.error_detection import (
    ArticleNounAgreementRule,
    FalseFriendRule,
    VerbConjugationRule,
)


def make_doc(text: str):
    nlp = spacy.blank("fr")
    return nlp(text)


def test_article_noun_agreement_rule_detects_mismatch():
    rule = ArticleNounAgreementRule()
    doc = make_doc("la garçon arrive")

    errors = rule.apply(doc)

    assert any(err.code == "article_noun_agreement" for err in errors)


def test_verb_conjugation_rule_flags_infinitive():
    rule = VerbConjugationRule()
    doc = make_doc("je manger une pomme")

    errors = rule.apply(doc)

    assert any(err.code == "verb_conjugation" for err in errors)


def test_false_friend_rule_detects_common_term():
    rule = FalseFriendRule()
    doc = make_doc("J'étudie actuellement à la librairie")

    errors = rule.apply(doc)

    assert any(err.code == "false_friend" for err in errors)
