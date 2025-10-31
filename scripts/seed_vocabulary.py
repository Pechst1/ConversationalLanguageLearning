"""Seed vocabulary database with top 5000 French words."""
from __future__ import annotations

import csv
import sys
from pathlib import Path
from sqlalchemy.orm import Session

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.db.models.vocabulary import VocabularyWord
from app.db.session import SessionLocal


def normalize_word(word: str) -> str:
    """Remove accents and convert to lowercase for matching."""

    import unicodedata

    nfkd = unicodedata.normalize("NFKD", word)
    return "".join([c for c in nfkd if not unicodedata.combining(c)]).lower()


def calculate_difficulty(frequency_rank: int) -> int:
    """Estimate difficulty based on frequency rank."""

    if frequency_rank <= 500:
        return 1
    if frequency_rank <= 1500:
        return 2
    if frequency_rank <= 3000:
        return 3
    if frequency_rank <= 4000:
        return 4
    return 5


def load_vocabulary_from_csv(csv_path: str, language: str = "fr") -> int:
    """Load vocabulary from CSV file into the database."""

    db: Session = SessionLocal()
    loaded = 0

    try:
        with open(csv_path, "r", encoding="utf-8") as file:
            reader = csv.DictReader(file)

            for row in reader:
                existing = (
                    db.query(VocabularyWord)
                    .filter(
                        VocabularyWord.language == language,
                        VocabularyWord.word == row["word"],
                    )
                    .first()
                )

                if existing:
                    continue

                topics = [t.strip() for t in row.get("topics", "").split(",") if t.strip()]

                word = VocabularyWord(
                    language=language,
                    word=row["word"],
                    normalized_word=normalize_word(row["word"]),
                    part_of_speech=row.get("part_of_speech"),
                    gender=row.get("gender") or None,
                    frequency_rank=int(row["rank"]),
                    english_translation=row["translation"],
                    definition=row.get("definition"),
                    example_sentence=row.get("example"),
                    example_translation=row.get("example_translation"),
                    topic_tags=topics if topics else None,
                    difficulty_level=calculate_difficulty(int(row["rank"])),
                )

                db.add(word)
                loaded += 1

                if loaded % 100 == 0:
                    db.commit()
                    print(f"Loaded {loaded} words...")

            db.commit()
            return loaded

    except Exception as exc:  # pragma: no cover - CLI feedback
        db.rollback()
        print(f"Error loading vocabulary: {exc}")
        raise
    finally:
        db.close()


def generate_sample_csv(output_path: Path | None = None) -> Path:
    """Generate a sample vocabulary CSV."""

    # A small but useful starter list (content words first; stopwords are filtered later)
    sample_data = [
        [
            "rank",
            "word",
            "part_of_speech",
            "gender",
            "translation",
            "definition",
            "example",
            "example_translation",
            "topics",
        ],
        ["1","bonjour","interjection","","hello","Common greeting","Bonjour ! Comment ça va ?","Hello! How are you?","greetings"],
        ["2","merci","interjection","","thank you","Polite expression of thanks","Merci pour votre aide","Thank you for your help","greetings"],
        ["3","s'il vous plaît","phrase","","please","Polite request","Un café, s'il vous plaît","A coffee, please","greetings"],
        ["4","baguette","noun","feminine","baguette","Type of French bread","Je prends une baguette","I'll take a baguette","food"],
        ["5","croissant","noun","masculine","croissant","Buttery crescent pastry","Un croissant frais","A fresh croissant","food"],
        ["6","café","noun","masculine","coffee; café","Drink or coffee shop","Un café noir","A black coffee","food"],
        ["7","thé","noun","masculine","tea","Infusion drink","Du thé vert","Green tea","food"],
        ["8","fromage","noun","masculine","cheese","Dairy product","Du fromage français","French cheese","food"],
        ["9","pain","noun","masculine","bread","Staple food","Du pain frais","Fresh bread","food"],
        ["10","eau","noun","feminine","water","Drink","De l'eau plate","Still water","food"],
        ["11","vin","noun","masculine","wine","Alcoholic beverage","Un verre de vin rouge","A glass of red wine","food"],
        ["12","boire","verb","","to drink","Consume liquid","Je veux boire de l'eau","I want to drink water","verbs"],
        ["13","manger","verb","","to eat","Consume food","Nous allons manger","We are going to eat","verbs"],
        ["14","parler","verb","","to speak","To converse","Parlez-vous français ?","Do you speak French?","verbs"],
        ["15","aimer","verb","","to like; to love","To enjoy or love","J'aime le chocolat","I like chocolate","verbs"],
        ["16","acheter","verb","","to buy","Purchase","Je vais acheter du pain","I'm going to buy bread","shopping"],
        ["17","payer","verb","","to pay","Pay for goods/services","Je vais payer en carte","I will pay by card","shopping"],
        ["18","commande","noun","feminine","order","Restaurant/shop order","Passer une commande","Place an order","shopping"],
        ["19","menu","noun","masculine","menu","List of dishes","Le menu du jour","The daily menu","restaurant"],
        ["20","addition","noun","feminine","bill","Restaurant bill","L'addition, s'il vous plaît","The bill, please","restaurant"],
        ["21","maison","noun","feminine","house","Dwelling","Une grande maison","A big house","home"],
        ["22","école","noun","feminine","school","Educational institution","L'école est ouverte","The school is open","education"],
        ["23","travail","noun","masculine","work","Employment/work","Je suis au travail","I'm at work","work"],
        ["24","voiture","noun","feminine","car","Automobile","Ma voiture est neuve","My car is new","transport"],
        ["25","train","noun","masculine","train","Rail transport","Prendre le train","Take the train","transport"],
        ["26","bus","noun","masculine","bus","Public transport","Attendre le bus","Wait for the bus","transport"],
        ["27","ville","noun","feminine","city","Urban area","La ville est belle","The city is beautiful","places"],
        ["28","rue","noun","feminine","street","Road in a city","Dans la rue principale","On the main street","places"],
        ["29","ami","noun","masculine","friend","Male friend","Un bon ami","A good friend","people"],
        ["30","amie","noun","feminine","friend","Female friend","Une bonne amie","A good (female) friend","people"],
        ["31","fille","noun","feminine","girl; daughter","Female child/daughter","Sa fille a 8 ans","His daughter is 8","people"],
        ["32","garçon","noun","masculine","boy; waiter","Male child / waiter","Le garçon apporte l'eau","The waiter brings water","people"],
        ["33","homme","noun","masculine","man","Adult male","Un homme gentil","A kind man","people"],
        ["34","femme","noun","feminine","woman; wife","Adult female / wife","Sa femme est ici","His wife is here","people"],
        ["35","aller","verb","","to go","Movement from one place to another","Aller au restaurant","Go to the restaurant","verbs"],
        ["36","venir","verb","","to come","Movement to the speaker","Vous pouvez venir ?","Can you come?","verbs"],
        ["37","prendre","verb","","to take","Seize/consume","Prendre le métro","Take the metro","verbs"],
        ["38","faire","verb","","to do; to make","Perform/Create","Que faire ce soir ?","What to do tonight?","verbs"],
        ["39","voir","verb","","to see","Perceive with eyes","Je veux voir ça","I want to see that","verbs"],
        ["40","bon","adjective","","good","Of high quality","Un bon café","A good coffee","adjectives"],
        ["41","grand","adjective","","big; tall","Large/High","Un grand musée","A big museum","adjectives"],
        ["42","petit","adjective","","small; little","Of small size","Un petit pain","A small bread","adjectives"],
        ["43","chaud","adjective","","hot; warm","High temperature","Du chocolat chaud","Hot chocolate","adjectives"],
        ["44","froid","adjective","","cold","Low temperature","Un plat froid","A cold dish","adjectives"],
        ["45","heure","noun","feminine","hour; time","Unit of time","Dans une heure","In an hour","time"],
        ["46","jour","noun","masculine","day","24-hour period","Bon jour de repos","Nice day off","time"],
        ["47","matin","noun","masculine","morning","Time of day","Le matin, je cours","In the morning, I run","time"],
        ["48","soir","noun","masculine","evening","Time of day","Ce soir, on sort","Tonight, we go out","time"],
        ["49","semaine","noun","feminine","week","Seven days","La semaine prochaine","Next week","time"],
        ["50","mois","noun","masculine","month","Calendar month","Ce mois-ci","This month","time"],
    ]

    output_path = output_path or Path("vocabulary_fr_sample.csv")

    with open(output_path, "w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerows(sample_data)

    print(f"Sample CSV generated: {output_path}")
    return output_path


if __name__ == "__main__":  # pragma: no cover - CLI execution
    import argparse

    parser = argparse.ArgumentParser(description="Seed vocabulary database")
    parser.add_argument("--csv", type=str, help="Path to CSV file")
    parser.add_argument("--language", type=str, default="fr", help="Language code")
    parser.add_argument(
        "--generate-sample",
        action="store_true",
        help="Generate sample CSV",
    )

    args = parser.parse_args()

    if args.generate_sample:
        generate_sample_csv()
    elif args.csv:
        count = load_vocabulary_from_csv(args.csv, args.language)
        print(f"Successfully loaded {count} words")
    else:
        parser.error("Please specify --csv path or --generate-sample")
