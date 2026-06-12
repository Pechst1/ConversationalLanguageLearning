from app.services.anki_import import AnkiCardParser


def test_extract_example_pair_from_french_5000_card():
    parser = AnkiCardParser()
    text = (
        "abaisser abaisser Les prix ne sont pas *abaissés* proportionnellement aux coûts. "
        "Die Preise werden nicht proportional zu den Kosten *gesenkt*. "
        "Pourrais-tu *abaisser* la vitre ? Il fait très chaud ici. "
        "Könntest du das Fenster *herunterlassen*? Es ist sehr heiß hier."
    )

    example, translation = parser.extract_example_pair(text, "abaisser", "fr_to_de")

    assert example == "Les prix ne sont pas abaissés proportionnellement aux coûts."
    assert translation == "Die Preise werden nicht proportional zu den Kosten gesenkt."


def test_extract_example_pair_falls_back_to_french_sentence():
    parser = AnkiCardParser()
    text = "bonjour Guten Tag. Je vous appelle demain. Ich rufe Sie morgen an."

    example, translation = parser.extract_example_pair(text, "saluer", "fr_to_de")

    assert example == "Je vous appelle demain."
    assert translation == "Ich rufe Sie morgen an."
