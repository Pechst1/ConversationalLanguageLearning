# 💡 Future Feature Ideas

## Story RPG Feature Integrationen

### Bereits in Conversational implementiert (können übertragen werden):

#### 1. Vokabel-Tracking pro NPC-Antwort
- **Konzept**: NPCs könnten gezielt neue Vokabeln einführen
- **Benefit**: Diese werden automatisch zum Anki-Deck hinzugefügt
- **Implementierung**: `_detect_unknown_words_used()` aus `SessionService` nutzen
- **Status**: ✅ Technisch vorhanden, nur Integration nötig

#### 2. Targeted Error Practice
- **Konzept**: NPCs könnten Sätze formulieren, die bekannte Fehler des Users gezielt üben
- **Benefit**: Personalisiertes Lernen basierend auf individuellen Schwächen
- **Implementierung**: `_fetch_due_errors()` aus `SessionService` liefert die top Fehler
- **Status**: ✅ Error Tracking bereits aktiv, nur NPC-Prompting fehlt

#### 3. Combo-Bonuses
- **Konzept**: Wenn User mehrere neue Vokabeln in einer Nachricht verwendet → Extra XP
- **Benefit**: Motiviert zur Nutzung von gelernten Vokabeln
- **Implementierung**: XP-System erweitern mit Combo-Multiplikator
- **Status**: 🔄 XP-System vorhanden, Combo-Logic fehlt

---

## Story-spezifische Features

### 4. Philosophische Learnings (Le Petit Prince)
- **Konzept**: Lebensweisheiten werden während der Story freigeschaltet
- **UI**: Können als "Sammelkarten" angezeigt werden
- **Beispiele**:
  - "L'essentiel est invisible pour les yeux"
  - "On ne connaît que les choses que l'on apprivoise"
- **DB**: `StoryProgress.philosophical_learnings` bereits vorhanden
- **Status**: 🟡 Backend bereit, Frontend-UI fehlt

### 5. Buch-Zitate freischalten
- **Konzept**: Originale Zitate aus dem Buch werden als Belohnung freigeschaltet
- **Beispiele**:
  - "On ne voit bien qu'avec le cœur..."
  - "C'est le temps que tu as perdu pour ta rose..."
- **UI**: Achievement-Popup + Galerie-Ansicht
- **DB**: `StoryProgress.book_quotes_unlocked` bereits vorhanden
- **Status**: 🟡 Backend bereit, Frontend-UI fehlt

### 6. NPC-Erinnerungen
- **Konzept**: NPCs erinnern sich an frühere Gespräche
- **Effekt**: Beeinflussen zukünftige Dialoge und Beziehungen
- **Implementierung**: 
  - `NPCMemory` Modell bereits vorhanden
  - `npc_service.add_memory()` wird bereits aufgerufen
  - Memories müssen in LLM-Prompts integriert werden
- **Status**: 🟡 Backend teilweise implementiert, LLM-Integration fehlt

---

## Prioritäten für nächste Schritte

### High Priority (Quick Wins)
1. **Philosophische Learnings UI** - Backend fertig, nur Frontend Card-Component nötig
2. **Buch-Zitate UI** - Backend fertig, nur Achievement-Popup nötig
3. **NPC-Memories in Prompts** - Nur Generator-Prompt erweitern

### Medium Priority (Mehr Aufwand)
4. **Vokabel-Tracking Integration** - Service-Calls hinzufügen
5. **Targeted Error Practice** - LLM-Prompt Engineering

### Low Priority (Nice to Have)
6. **Combo-Bonuses** - XP-System Refactoring nötig
7. **Mehr Ziele pro Szene** - Aktuell gibt es oft nur 1 Ziel pro Szene, was zu schnellem Durchspielen führt. Mehr Ziele würden die Lernzeit pro Szene erhöhen und mehr Gesprächsübung bieten.

---

## Technische Notes

- Alle DB-Modelle für Story-Features sind bereits vorhanden
- Error Detection & SRS sind vollständig integriert
- Hauptarbeit liegt in Frontend-UI und LLM-Prompt-Engineering
- Conversational Session Features können als Referenz dienen
