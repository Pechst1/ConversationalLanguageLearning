"""Brief exercise prompts for daily practice quick exercises.

Simpler prompts for generating:
- 3 brief grammar exercises (vs full 9-exercise structure)
- Error correction exercises based on user mistakes
"""

BRIEF_GRAMMAR_EXERCISES_PROMPT = """Du bist ein Französischlehrer. Erstelle 3 kurze Übungen für: **{concept_name}** (Niveau {level})

# Regeln:
- Jede Übung dauert ~20 Sekunden
- Mische die Typen: Lückentext, Übersetzung, oder kurze Antwort
- Schwierigkeit: a=leicht, b=mittel, c=schwer
- ALLE Texte auf Französisch (außer Übersetzungsaufgaben)

# Antwortformat (strikt JSON):
{{
  "exercises": [
    {{
      "id": "1",
      "type": "fill_blank | translation | short_answer",
      "difficulty": "a",
      "instruction": "Kurze Anweisung auf Deutsch",
      "prompt": "Der Übungstext mit ___ für Lücken",
      "correct_answer": "Die erwartete Antwort",
      "hint": "Ein kleiner Hinweis (optional)"
    }},
    {{
      "id": "2",
      "type": "...",
      "difficulty": "b",
      "instruction": "...",
      "prompt": "...",
      "correct_answer": "...",
      "hint": "..."
    }},
    {{
      "id": "3",
      "type": "...",
      "difficulty": "c",
      "instruction": "...",
      "prompt": "...",
      "correct_answer": "...",
      "hint": "..."
    }}
  ]
}}

Erstelle jetzt 3 kurze Übungen als JSON:"""


ERROR_CORRECTION_EXERCISE_PROMPT = """Du bist ein Französischlehrer. Der Schüler hat folgenden Fehler gemacht:

# Fehler-Details:
- **Falscher Text**: {original_text}
- **Korrektur**: {correction}
- **Kategorie**: {error_category}
- **Kontext**: {context}

# Aufgabe:
Erstelle eine Übung, bei der der Schüler den Fehler selbst korrigieren muss.

# Antwortformat (strikt JSON):
{{
  "exercise_type": "correction | similar_sentence | fill_blank",
  "instruction": "Anweisung auf Deutsch",
  "prompt": "Der Satz mit dem Fehler oder eine ähnliche Konstruktion",
  "correct_answer": "Die korrekte Version",
  "explanation": "Kurze Erklärung der Grammatikregel",
  "memory_tip": "Ein Merksatz für den Schüler"
}}

Erstelle die Übung als JSON:"""


BRIEF_ANSWER_CHECK_PROMPT = """Du bist ein Französischlehrer. Prüfe die Antwort des Schülers.

# Übung:
- Typ: {exercise_type}
- Aufgabe: {prompt}
- Erwartete Antwort: {correct_answer}
- Schüler-Antwort: {user_answer}

# Bewertung:
- Akzeptiere kleine Variationen (groß/klein, Akzente bei Tippfehlern)
- Erkläre WARUM richtig oder falsch
- Gib einen Verbesserungstipp bei Fehlern

# Antwortformat (strikt JSON):
{{
  "is_correct": true | false,
  "feedback": "Kurzes Feedback auf Deutsch",
  "explanation": "Falls falsch: Erklärung der Regel",
  "score": 0-10,
  "detected_error_category": "Grammar | Vocabulary | Spelling | ...",
  "detected_subcategory": "Specific concept (e.g. Subjonctif, Artikel, Accord)"
}}

Prüfe jetzt die Antwort als JSON:"""


def get_brief_grammar_prompt(concept_name: str, level: str) -> str:
    """Build prompt for 3 brief grammar exercises."""
    return BRIEF_GRAMMAR_EXERCISES_PROMPT.format(
        concept_name=concept_name,
        level=level
    )


def get_error_exercise_prompt(
    original_text: str,
    correction: str,
    error_category: str,
    context: str | None
) -> str:
    """Build prompt for error correction exercise."""
    return ERROR_CORRECTION_EXERCISE_PROMPT.format(
        original_text=original_text or "(nicht verfügbar)",
        correction=correction or "(nicht verfügbar)",
        error_category=error_category or "Grammatik",
        context=context or "(kein Kontext)"
    )


def get_answer_check_prompt(
    exercise_type: str,
    prompt: str,
    correct_answer: str,
    user_answer: str
) -> str:
    """Build prompt for checking user answer."""
    return BRIEF_ANSWER_CHECK_PROMPT.format(
        exercise_type=exercise_type,
        prompt=prompt,
        correct_answer=correct_answer,
        user_answer=user_answer
    )
