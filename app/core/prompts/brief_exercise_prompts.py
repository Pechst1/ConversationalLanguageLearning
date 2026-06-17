"""Brief exercise prompts for answer checking.

Learner-facing exercise generation now lives in
`app.services.exercise_generation`; this module keeps only the deterministic
answer-check prompt used by brief exercise correction.
"""


BRIEF_ANSWER_CHECK_PROMPT = """Du bist ein Französischlehrer. Prüfe die Antwort des Schülers.

# Übung:
- Typ: {exercise_type}
- Aufgabe: {prompt}
- Erwartete Antwort: {correct_answer}
- Schüler-Antwort: {user_answer}

# Bewertung:
- Akzeptiere kleine Variationen (groß/klein, Akzente bei Tippfehlern)
- Bei Grammatikaufgaben mit freier Satzbildung ist die Referenzlösung nur ein Beispiel.
- Markiere eine Antwort als RICHTIG, wenn sie die geforderte Struktur korrekt verwendet, auch wenn Wortwahl oder Inhalt anders sind.
- Markiere eine Antwort nur dann als "nicht passend", wenn sie die geforderte Struktur wirklich nicht benutzt.
- Erkläre WARUM richtig oder falsch
- Gib einen Verbesserungstipp bei Fehlern

# Antwortformat (strikt JSON):
{{
  "is_correct": true | false,
  "feedback": "Kurzes Feedback auf Deutsch",
  "explanation": "Falls falsch: Erklärung der Regel",
  "sample_solution": "Kurze Beispiel- oder Referenzlösung",
  "score": 0-10,
  "detected_error_category": "Grammar | Vocabulary | Spelling | ...",
  "detected_subcategory": "Specific concept (e.g. Subjonctif, Artikel, Accord)"
}}

Prüfe jetzt die Antwort als JSON:"""


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
