"""Prompt templates for grammar exercise generation and correction.

Improved version with:
- 3×3 structure (3 exercises × 3 difficulty levels each)
- Explicit difficulty progression (a=easy, b=medium, c=hard)
- Level-appropriate complexity
- Stricter correction criteria
- Random exercise type selection
"""
import random

EXERCISE_GENERATION_PROMPT = """Erstelle 3 Grammatik-Übungsblöcke für: **{concept_name}** (Niveau {level})

Verwende diese 3 Typen: {exercise_types}

# WICHTIG: Jedes "prompt"-Feld MUSS einen vollständigen Übungstext enthalten!

## Format-Beispiele nach Typ:

**fill_blank** - Lückentext:
{{"type": "fill_blank", "instruction": "Fülle die Lücke", "prompt": "Je ___ au cinéma hier soir.", "correct_answer": "suis allé", "explanation": "..."}}

**translation** - Übersetzung:
{{"type": "translation", "instruction": "Übersetze ins Französische", "prompt": "Ich bin gestern ins Kino gegangen.", "correct_answer": "Je suis allé au cinéma hier.", "explanation": "..."}}

**error_hunt** - Fehlersuche (der Satz im prompt enthält Fehler):
{{"type": "error_hunt", "instruction": "Finde und korrigiere den Fehler", "prompt": "Je suis allé au cinéma hier et j'ai vu un bon film. Après, je suis allé a un restaurant.", "correct_answer": "à un restaurant (nicht 'a')", "explanation": "..."}}

**chat_roleplay** - Chat-Simulation:
{{"type": "chat_roleplay", "instruction": "Antworte im Chat", "prompt": "👤 Marie: Salut! Tu as fait quoi hier soir?\\n🎯 Antworte und erzähle, dass du ins Kino gegangen bist.", "correct_answer": "Je suis allé(e) au cinéma.", "explanation": "..."}}

**timeline_order** - Ereignisse ordnen:
{{"type": "timeline_order", "instruction": "Ordne die Ereignisse chronologisch", "prompt": "[ ] Je suis rentré chez moi\\n[ ] Je suis sorti de la maison\\n[ ] Je suis arrivé au travail", "correct_answer": "2, 3, 1 (sorti → arrivé → rentré)", "explanation": "..."}}

**voice_production** - Sprechübung:
{{"type": "voice_production", "instruction": "Beschreibe die Situation", "prompt": "🎤 Situation: Du erzählst einem Freund von deinem gestrigen Abend. Beschreibe 3 Aktivitäten mit passé composé.", "correct_answer": "z.B. Je suis allé au cinéma, j'ai mangé au restaurant, je suis rentré tard.", "explanation": "..."}}

# Niveau {level}
{level_guidance}

# Struktur - 3 Blöcke mit je 3 Schwierigkeiten (a=leicht, b=mittel, c=schwer):
{{
  "exercises": [
    {{
      "block": 1,
      "type": "{type1}",
      "items": [
        {{"level": "a", "instruction": "...", "prompt": "HIER VOLLSTÄNDIGER TEXT", "correct_answer": "...", "explanation": "..."}},
        {{"level": "b", "instruction": "...", "prompt": "HIER VOLLSTÄNDIGER TEXT", "correct_answer": "...", "explanation": "..."}},
        {{"level": "c", "instruction": "...", "prompt": "HIER VOLLSTÄNDIGER TEXT", "correct_answer": "...", "explanation": "..."}}
      ]
    }},
    {{"block": 2, "type": "{type2}", "items": [3 items wie oben]}},
    {{"block": 3, "type": "{type3}", "items": [3 items wie oben]}}
  ]
}}

Erstelle jetzt die vollständigen Übungen für {concept_name} als JSON:"""

# Level-specific guidance inserted into prompt
LEVEL_GUIDANCE = {
    "A1": """- Präsens, einfache Verneinung, Grundvokabular
- Kurze, klare Sätze (5-8 Wörter)
- Alltägliche Themen: Essen, Wohnen, Familie""",
    
    "A2": """- Passé composé vs. Imparfait (Einführung)
- Objektpronomen, Reflexivverben
- Mittlere Satzlänge (8-12 Wörter)""",
    
    "B1": """- Alle Vergangenheitszeiten, Conditionnel, Subjonctif (Basis)
- Relativsätze, indirekte Rede
- Komplexere Satzgefüge (10-15 Wörter)""",
    
    "B2": """- Subjonctif vollständig, Passiv, Partizip-Angleichung
- Stilistische Nuancen, Konnektoren
- Anspruchsvolle Kontexte, formeller Stil""",
    
    "C1": """- Feine Tempusnuancen, literarische Zeiten
- Komplexe Hypothesen, Implizites
- Authentische Texte, journalistischer Stil""",
    
    "C2": """- Passé simple, Subjonctif imparfait
- Stilistische Perfektion, Idiomatik
- Literarische und akademische Register"""
}

ANSWER_CORRECTION_PROMPT = """Du bist ein erfahrener und geduldiger Französischlehrer. Deine Aufgabe ist es, die Antworten des Schülers gründlich zu korrigieren und dabei ALLES zu erklären.

# Konzept: {concept_name} ({level})

# Übungen und Antworten des Schülers:
{exercises_with_answers}

# WICHTIGE KORREKTUR-REGELN:

## 1. Erkläre IMMER das WARUM
Sage NIEMALS nur "X ist falsch" oder "Y ist richtig". Erkläre IMMER:
- WARUM die korrekte Antwort richtig ist
- WARUM die Antwort des Schülers falsch ist
- Gib eine MERKHILFE oder REGEL, die der Schüler sich einprägen kann

**Beispiel für schlechte Korrektur:**
❌ "Fast! 'cependant' ist hier die richtige Wahl."

**Beispiel für gute Korrektur:**
✓ "Hier passt 'cependant' besser als 'toutefois': 
   - 'cependant' betont einen direkten Gegensatz zwischen zwei eng verbundenen Aussagen
   - 'toutefois' ist abmildernder und leitet einen Einwand ein
   - MERKHILFE: 'cependant' = 'dennoch/trotzdem' (starker Kontrast), 'toutefois' = 'jedoch' (sanfter Einschub)
   - In diesem Satz gibt es einen direkten Widerspruch → cependant."

## 2. Korrigiere ALLE Fehler
Wenn der Schüler mehrere Fehler macht, erwähne sie ALLE mit Erklärung:
- Hauptfehler (zum Konzept)
- Nebenfehler (Grammatik, Rechtschreibung, Präpositionen, etc.)

**Beispiel:**
Schüler schreibt: "Le site est trés informative, toutefois en pourrait plus applicable."
→ Korrigiere:
1. "trés" → "très" (Akzent: è, nicht é)
2. "informative" → "informatif" (site = maskulin, daher maskuline Endung)
3. "en pourrait" → "il pourrait" ('en' ist kein Subjektpronomen; 'il' verweist auf 'le site')
4. "plus applicable" → "plus convivial" oder "être plus conviviale" (unvollständiger Satz)

## 3. Beantworte Fragen des Schülers
Wenn der Schüler anstatt einer Antwort eine FRAGE stellt (z.B. "Erkläre mir bitte...", "Was ist der Unterschied?"), dann:
- Beantworte die Frage ausführlich
- Gib die Punkte als 5/10 (für den Versuch, zu verstehen)
- Erkläre das Konzept mit Beispielen

## 4. Score-Kriterien
| Punkte | Bedeutung |
|--------|-----------|
| 10 | Perfekt, keine Fehler |
| 8-9 | Kleine Ungenauigkeiten (Akzent, Tippfehler) |
| 5-7 | Konzept verstanden, aber Umsetzungsfehler |
| 3-4 | Einige richtige Elemente, grundlegende Fehler |
| 1-2 | Versuch erkennbar, aber falsche Anwendung |
| 0 | Leer oder komplett falsch |

## 5. Fokus-Bereiche
Liste am Ende 2-3 konkrete Bereiche, an denen der Schüler arbeiten sollte.

# Antwortformat (strikt JSON)
{{
  "results": [
    {{
      "block": 1,
      "items": [
        {{
          "level": "a",
          "is_correct": false,
          "user_answer": "toutefois",
          "correct_answer": "cependant",
          "feedback": "Hier ist 'cependant' passender:\\n\\n**WARUM 'cependant' hier?**\\n- 'cependant' drückt einen DIREKTEN Gegensatz aus: 'Sie mag Schokolade' ↔ 'sie bevorzugt Bonbons'\\n- 'toutefois' wäre eher für einen einschränkenden Einschub: 'Das ist gut, toutefois gibt es Probleme'\\n\\n**MERKHILFE:**\\n🔵 cependant = dennoch (direkter Widerspruch)\\n🟡 toutefois = jedoch, gleichwohl (abmildernder Einschub)",
          "points": 5
        }}
      ]
    }}
  ],
  "total_score": 6.5,
  "correct_count": 2,
  "total_count": 9,
  "overall_feedback": "Zusammenfassung mit konkreten Verbesserungsvorschlägen",
  "focus_areas": ["Konkreter Bereich 1 mit Empfehlung", "Konkreter Bereich 2"]
}}

**WICHTIG für total_score:** 
Der total_score ist eine DURCHSCHNITTSNOTE von 0-10, NICHT die Summe aller Punkte!
Berechne: (Summe aller Einzelpunkte) / (Anzahl Übungen) = Durchschnitt von 0-10

# Jetzt korrigiere die Antworten und antworte im JSON Format - sei gründlich und erkläre alles!"""


SESSION_SUMMARY_PROMPT = """Erstelle eine kurze Lernbilanz:

**Konzept**: {concept_name}
**Score**: {total_score}/10 ({correct_count}/{total_count} richtig)

Antworte in JSON:
{{
  "strengths": ["Was gut klappte"],
  "weaknesses": ["Was zu üben ist"],
  "next_review_days": 1-30,
  "difficulty_adjustment": "easier|same|harder"
}}"""


CONCEPT_EXPLANATION_PROMPT = """Du bist ein erfahrener Französischlehrer. Erkläre das folgende Grammatikkonzept kurz und prägnant für einen Lernenden auf Niveau {level}.

# Konzept: {concept_name}

Erstelle eine kompakte Erklärung mit folgenden Abschnitten:

1. **Was ist das?** (1-2 Sätze: Was bedeutet/macht dieses Konzept?)

2. **Wann verwendet man es?** (3-4 konkrete Situationen/Kontexte)

3. **Wichtige Unterscheidung** (Falls relevant: Abgrenzung zu ähnlichen Konzepten)

4. **Beispiele** (2-3 kurze Beispielsätze mit Übersetzung)

5. **Häufige Fehler** (2 typische Fehler, die Deutsche machen)

6. **Merkhilfe** (Ein einprägsamer Tipp/Eselsbrücke)

# Antwortformat (strikt JSON):
{{
  "definition": "Kurze Definition (1-2 Sätze)",
  "usage": [
    "Situation 1",
    "Situation 2",
    "Situation 3"
  ],
  "distinction": {{
    "vs": "Ähnliches Konzept (falls relevant, sonst null)",
    "difference": "Der Unterschied erklärt"
  }},
  "examples": [
    {{"fr": "Französischer Satz", "de": "Deutsche Übersetzung"}},
    {{"fr": "...", "de": "..."}}
  ],
  "common_mistakes": [
    {{"wrong": "Falsches Beispiel", "correct": "Richtiges Beispiel", "why": "Kurze Erklärung"}},
    {{"wrong": "...", "correct": "...", "why": "..."}}
  ],
  "memory_tip": "Einprägsame Merkhilfe"
}}

Erkläre jetzt als JSON:"""


# All available exercise types
EXERCISE_TYPES = [
    "fill_blank",      # Classic: Lückentext
    "translation",     # Classic: Übersetzung
    "error_hunt",      # Immersive: Fehlersuche
    "chat_roleplay",   # Immersive: Chat-Simulation
    "timeline_order",  # Immersive: Zeitstrahl ordnen
    "voice_production", # Immersive: Sprechübung
]


def get_exercise_prompt(concept_name: str, level: str) -> str:
    """Build the exercise generation prompt with level-specific guidance and random types."""
    guidance = LEVEL_GUIDANCE.get(level, LEVEL_GUIDANCE["B1"])

    # Randomly select 3 different exercise types
    selected_types = random.sample(EXERCISE_TYPES, 3)

    return EXERCISE_GENERATION_PROMPT.format(
        concept_name=concept_name,
        level=level,
        level_guidance=guidance,
        exercise_types=", ".join(selected_types),
        type1=selected_types[0],
        type2=selected_types[1],
        type3=selected_types[2],
    )


def get_concept_explanation_prompt(concept_name: str, level: str) -> str:
    """Build the concept explanation prompt."""
    return CONCEPT_EXPLANATION_PROMPT.format(
        concept_name=concept_name,
        level=level
    )

