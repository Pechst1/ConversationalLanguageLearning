"""Seed sample stories for the story learning system."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models.story import Story, StoryChapter


def seed_stories(db: Session) -> None:
    """Seed sample stories into the database.

    Creates the "Le Mystère du Café Parisien" story with all chapters.
    """
    # Check if story already exists
    existing = db.query(Story).filter(Story.story_key == "mystery_cafe_parisien").first()
    if existing:
        print("Story 'mystery_cafe_parisien' already exists, skipping seed")
        return

    # Create the story
    story = Story(
        story_key="mystery_cafe_parisien",
        title="Le Mystère du Café Parisien",
        description="Votre café préféré cache un mystère. Le propriétaire a disparu et c'est à vous de découvrir ce qui s'est passé. Une enquête à travers Paris vous attend.",
        difficulty_level="B1",
        estimated_duration_minutes=90,
        theme_tags=["mystery", "detective", "paris", "cafe"],
        vocabulary_theme="daily_life,food,places,emotions",
        cover_image_url="/stories/mystery_cafe.jpg",
        author="Claude Assistant",
        total_chapters=7,
        is_published=True,
        created_at=datetime.now(timezone.utc),
    )

    db.add(story)
    db.flush()  # Get the story ID

    # Create all chapters
    chapters_data = [
        {
            "chapter_key": "ch1_discovery",
            "sequence_order": 1,
            "title": "La Découverte",
            "synopsis": "Vous découvrez que le Café Parisien est fermé et Monsieur Dubois a disparu.",
            "opening_narrative": """Vous poussez la porte du Café Parisien comme chaque matin. Mais quelque chose ne va pas. Les chaises sont renversées, le comptoir est vide, et Monsieur Dubois, le sympathique propriétaire, n'est nulle part. Un jeune serveur vous regarde avec inquiétude.

'Vous êtes un habitué ?' vous demande-t-il. 'Monsieur Dubois n'est pas venu aujourd'hui. C'est très étrange...'""",
            "min_turns": 3,
            "max_turns": 8,
            "narrative_goals": [
                {
                    "goal_id": "talk_to_waiter",
                    "description": "Parler au serveur pour comprendre la situation",
                    "hint": "Utilisez des mots comme 'inquiet', 'disparaître', 'chercher'",
                    "required_words": ["inquiet", "disparaître"]
                },
                {
                    "goal_id": "examine_cafe",
                    "description": "Examiner le café pour trouver des indices",
                    "hint": "Regardez autour du comptoir et des tables",
                    "required_words": ["chercher", "trouver"]
                }
            ],
            "completion_criteria": {
                "min_goals_completed": 1,
                "min_vocabulary_used": 4
            },
            "completion_xp": 75,
            "perfect_completion_xp": 150,
        },
        {
            "chapter_key": "ch2_clues",
            "sequence_order": 2,
            "title": "Les Premiers Indices",
            "synopsis": "Vous trouvez un vieux ticket de métro et une note mystérieuse.",
            "opening_narrative": """En fouillant derrière le comptoir, vous trouvez deux objets intéressants : un vieux ticket de métro pour la station 'Châtelet' et une note griffonnée : 'RDV 18h - Cave - Important'.

Le serveur s'approche. 'J'ai vu Monsieur Dubois hier soir. Il semblait nerveux. Il a mentionné quelque chose à propos d'une vieille cave sous le café...'""",
            "min_turns": 4,
            "max_turns": 10,
            "narrative_goals": [
                {
                    "goal_id": "discuss_metro_ticket",
                    "description": "Discuter du ticket de métro avec le serveur",
                    "required_words": ["métro", "station"]
                },
                {
                    "goal_id": "ask_about_cave",
                    "description": "Demander des informations sur la cave",
                    "required_words": ["cave", "descendre"]
                },
                {
                    "goal_id": "make_decision",
                    "description": "Décider de votre prochaine action",
                    "required_words": ["décider", "aller"]
                }
            ],
            "branching_choices": [
                {
                    "choice_id": "explore_cave",
                    "text": "Explorer la cave sous le café",
                    "hint": "Dites : 'Je veux descendre dans la cave pour chercher des indices.'"
                },
                {
                    "choice_id": "follow_metro",
                    "text": "Suivre la piste du métro à Châtelet",
                    "hint": "Dites : 'Je vais prendre le métro pour aller à la station Châtelet.'"
                }
            ],
            "completion_criteria": {
                "min_goals_completed": 2,
                "min_vocabulary_used": 5
            },
            "completion_xp": 100,
            "perfect_completion_xp": 200
        },
        # Branching path 1: Cave exploration
        {
            "chapter_key": "ch3_cave",
            "sequence_order": 3,
            "title": "La Cave Secrète",
            "synopsis": "Vous descendez dans la cave et découvrez un passage secret.",
            "opening_narrative": """Avec l'aide du serveur, vous trouvez l'entrée de la cave. L'escalier est étroit et sombre. En bas, vous découvrez une vieille porte en bois. Derrière, un passage secret mène à... un atelier d'artiste caché ! Des peintures partout, et au centre, un portrait de Monsieur Dubois plus jeune, avec une belle femme.""",
            "min_turns": 5,
            "max_turns": 10,
            "narrative_goals": [
                {
                    "goal_id": "examine_paintings",
                    "description": "Examiner les peintures et l'atelier",
                    "required_words": ["peinture", "tableau", "regarder"]
                },
                {
                    "goal_id": "find_letter",
                    "description": "Trouver une lettre révélant le passé de Monsieur Dubois",
                    "required_words": ["lettre", "lire", "découvrir"]
                }
            ],
            "completion_xp": 125,
            "perfect_completion_xp": 250,
        },
        # Branching path 2: Metro investigation
        {
            "chapter_key": "ch4_metro",
            "sequence_order": 4,
            "title": "L'Enquête au Métro",
            "synopsis": "À la station Châtelet, vous rencontrez un vieil ami de Monsieur Dubois.",
            "opening_narrative": """Vous arrivez à la station Châtelet. C'est bondé. Près de la sortie, un vieil homme vend des journaux. Il vous regarde avec curiosité.

'Vous cherchez quelqu'un ?' demande-t-il. 'Je connais tout le monde ici. Si c'est à propos de Dubois, j'ai peut-être des informations...'""",
            "min_turns": 5,
            "max_turns": 10,
            "narrative_goals": [
                {
                    "goal_id": "talk_to_newspaper_man",
                    "description": "Interroger le vendeur de journaux",
                    "required_words": ["connaître", "raconter", "savoir"]
                },
                {
                    "goal_id": "learn_secret",
                    "description": "Apprendre le secret de Monsieur Dubois",
                    "required_words": ["secret", "passé", "comprendre"]
                }
            ],
            "completion_xp": 125,
            "perfect_completion_xp": 250,
        },
        # Convergence: both paths lead here
        {
            "chapter_key": "ch5_revelation",
            "sequence_order": 5,
            "title": "La Révélation",
            "synopsis": "Les pièces du puzzle s'assemblent. Vous découvrez la vérité.",
            "opening_narrative": """Tous les indices commencent à avoir un sens. Monsieur Dubois était un artiste célèbre dans sa jeunesse ! Il a disparu du monde de l'art il y a 30 ans pour des raisons mystérieuses.

Soudain, votre téléphone sonne. C'est le serveur : 'Venez vite ! Monsieur Dubois est revenu !'""",
            "min_turns": 4,
            "max_turns": 8,
            "narrative_goals": [
                {
                    "goal_id": "return_to_cafe",
                    "description": "Retourner au café rapidement",
                    "required_words": ["retourner", "vite", "courir"]
                },
                {
                    "goal_id": "confront_dubois",
                    "description": "Parler à Monsieur Dubois de ce que vous avez découvert",
                    "required_words": ["expliquer", "découvrir", "vérité"]
                }
            ],
            "completion_xp": 150,
            "perfect_completion_xp": 300,
        },
        # Final chapter
        {
            "chapter_key": "ch6_resolution",
            "sequence_order": 6,
            "title": "La Résolution",
            "synopsis": "Monsieur Dubois vous raconte son histoire et vous remercie.",
            "opening_narrative": """Au café, Monsieur Dubois vous attend avec un sourire triste. 'Merci d'avoir cherché,' dit-il. 'Je suppose que vous avez des questions.'

Il commence à raconter son histoire : son passé d'artiste, son grand amour perdu, et pourquoi il a choisi de disparaître du monde de l'art pour ouvrir un petit café...""",
            "min_turns": 5,
            "max_turns": 12,
            "narrative_goals": [
                {
                    "goal_id": "listen_to_story",
                    "description": "Écouter l'histoire complète de Monsieur Dubois",
                    "required_words": ["comprendre", "histoire", "écouter"]
                },
                {
                    "goal_id": "offer_support",
                    "description": "Offrir votre soutien et amitié",
                    "required_words": ["ami", "aider", "soutenir"]
                },
                {
                    "goal_id": "final_decision",
                    "description": "Aider Dubois à décider de son avenir",
                    "required_words": ["futur", "décision", "choisir"]
                }
            ],
            "completion_xp": 200,
            "perfect_completion_xp": 400,
        },
        # Epilogue
        {
            "chapter_key": "ch7_epilogue",
            "sequence_order": 7,
            "title": "Épilogue",
            "synopsis": "Un nouveau chapitre commence pour le Café Parisien.",
            "opening_narrative": """Trois mois plus tard, vous retournez au Café Parisien. Les murs sont maintenant décorés avec les peintures de Monsieur Dubois. Le café est devenu une petite galerie d'art locale, attirant artistes et amateurs.

Monsieur Dubois vous sourit depuis le comptoir. 'Tout ça grâce à vous,' dit-il en vous offrant un café. 'Vous m'avez aidé à réconcilier mon passé et mon présent.'""",
            "min_turns": 3,
            "max_turns": 6,
            "narrative_goals": [
                {
                    "goal_id": "celebrate",
                    "description": "Célébrer le nouveau départ du café",
                    "required_words": ["célébrer", "heureux", "réussite"]
                }
            ],
            "completion_xp": 250,
            "perfect_completion_xp": 500,
        }
    ]

    # Create chapter objects
    chapters = []
    for data in chapters_data:
        chapter = StoryChapter(
            story_id=story.id,
            **data
        )
        chapters.append(chapter)
        db.add(chapter)

    # Flush to get IDs
    db.flush()

    # Now set up the chapter linking (default_next_chapter_id and branching)
    # Chapter 1 -> Chapter 2
    chapters[0].default_next_chapter_id = chapters[1].id

    # Chapter 2 -> branching to chapters 3 or 4
    chapters[1].branching_choices = [
        {
            "choice_id": "explore_cave",
            "text": "Explorer la cave sous le café",
            "hint": "Dites : 'Je veux descendre dans la cave pour chercher des indices.'",
            "next_chapter_id": chapters[2].id  # Cave (ch3)
        },
        {
            "choice_id": "follow_metro",
            "text": "Suivre la piste du métro à Châtelet",
            "hint": "Dites : 'Je vais prendre le métro pour aller à la station Châtelet.'",
            "next_chapter_id": chapters[3].id  # Metro (ch4)
        }
    ]
    chapters[1].default_next_chapter_id = chapters[2].id  # Default to cave if no choice

    # Chapter 3 (cave) -> Chapter 5 (revelation)
    chapters[2].default_next_chapter_id = chapters[4].id

    # Chapter 4 (metro) -> Chapter 5 (revelation)
    chapters[3].default_next_chapter_id = chapters[4].id

    # Chapter 5 (revelation) -> Chapter 6 (resolution)
    chapters[4].default_next_chapter_id = chapters[5].id

    # Chapter 6 (resolution) -> Chapter 7 (epilogue)
    chapters[5].default_next_chapter_id = chapters[6].id

    # Chapter 7 (epilogue) -> None (story complete)
    chapters[6].default_next_chapter_id = None

    # Commit everything
    db.commit()

    print(f"✅ Successfully seeded story: {story.title}")
    print(f"   - Story ID: {story.id}")
    print(f"   - Total chapters: {len(chapters)}")
    print(f"   - Difficulty: {story.difficulty_level}")
    print(f"   - Branching at chapter 2: Cave or Metro investigation")


if __name__ == "__main__":
    """Run seeder directly."""
    from app.db.session import get_db

    print("Starting story seeder...")

    # Get database session
    db = next(get_db())

    try:
        seed_stories(db)
        print("\n✅ Story seeding complete!")
    except Exception as e:
        print(f"\n❌ Error seeding stories: {e}")
        db.rollback()
        raise
    finally:
        db.close()
