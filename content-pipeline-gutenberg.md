# Content-Pipeline: Von Gutenberg zum Sprachabenteuer

## Executive Summary

Dieses Dokument beschreibt, wie wir gemeinfreie Literatur von Project Gutenberg in interaktive Sprachlern-Abenteuer transformieren. Der Ansatz kombiniert bewährte Narrative mit KI-gestützter Adaption und modernem Game-Design.

**Kernidee:** Der Spieler *liest* nicht "Les Misérables" – er *lebt* als Charakter in Hugos Paris und beeinflusst die Geschichte durch seine Sprachfähigkeit.

---

## Teil 1: Philosophie der Transformation

### 1.1 Warum klassische Literatur?

| Vorteil | Erklärung |
|---------|-----------|
| **Bewährte Narrative** | Millionen Menschen haben diese Geschichten geliebt. Die emotionale Wirkung ist bewiesen. |
| **Kultureller Mehrwert** | Der Spieler lernt nicht nur Sprache, sondern französische/deutsche/spanische Kultur. |
| **Kostenlos & Legal** | Keine Lizenzgebühren, keine rechtlichen Risiken. |
| **Reiches Vokabular** | Klassiker decken alle Register ab: von Straßenslang bis Hofsprache. |
| **Bekanntheitsgrad** | Viele kennen die Geschichten – das senkt die kognitive Last und erhöht die Neugier ("Wie ist es, *in* dieser Welt zu sein?"). |

### 1.2 Das Transformations-Prinzip

```
PASSIV                           AKTIV
────────────────────────────────────────────────────
Lesen                    →       Erleben
Beobachten               →       Entscheiden
Protagonist folgen       →       Eigene Rolle spielen
Linearer Plot            →       Branching Narrative
Historische Sprache      →       Level-adaptive Sprache
Fertige Geschichte       →       Beeinflussbares Schicksal
```

### 1.3 Die "Seitentür"-Methode

Der Spieler ist NIE der Hauptprotagonist. Warum?

1. **Kanonbruch vermeiden**: Wenn du Jean Valjean "bist", muss die Geschichte genau so ablaufen wie im Buch. Langweilig.
2. **Freiheit ermöglichen**: Als Nebencharakter kannst du die Welt beeinflussen, ohne den Kernplot zu zerstören.
3. **Entdeckungsfreude**: Du erlebst die bekannte Geschichte aus einer neuen Perspektive.

**Beispiele für Spielerrollen:**

| Buch | Protagonist | Spielerrolle |
|------|-------------|--------------|
| Les Misérables | Jean Valjean | Ein Arbeiter in Fantines Fabrik |
| Der kleine Prinz | Der Pilot | Ein Bewohner eines der Planeten |
| Monte Cristo | Edmond Dantès | Ein Mitgefangener im Château d'If |
| Die drei Musketiere | D'Artagnan | Ein Diener im Haushalt der Königin |

---

## Teil 2: Die Transformations-Pipeline

### 2.1 Übersicht

```
┌─────────────────────────────────────────────────────────────────┐
│                     CONTENT PIPELINE                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 1: EXTRAKTION                                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ Setting      │  │ Charaktere   │  │ Plot-Struktur        │   │
│  │ Extraktion   │  │ Analyse      │  │ Mapping              │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 2: DESIGN                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ Spielerrolle │  │ Interaktive  │  │ Branching            │   │
│  │ Definition   │  │ Szenen       │  │ Opportunities        │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 3: ADAPTION                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ Sprach-      │  │ NPC-Persona  │  │ Lernziel             │   │
│  │ Modernisier. │  │ Erstellung   │  │ Integration          │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 4: PRODUKTION                                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ Story-       │  │ Dialog       │  │ Quality              │   │
│  │ Scripting    │  │ Generierung  │  │ Assurance            │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Phase 1: Extraktion

#### 2.2.1 Setting-Extraktion

**Input:** Volltext des Buches (von Gutenberg)

**Output:** Strukturierte Setting-Datenbank

```typescript
interface ExtractedSetting {
  // Geografische Orte
  locations: {
    id: string;
    name: string;
    description: string;
    atmosphere: string;
    timeperiod: string;
    socialClass: 'upper' | 'middle' | 'lower' | 'mixed';
    originalQuotes: string[];  // Originalbeschreibungen aus dem Buch
  }[];
  
  // Zeitlicher Kontext
  timeline: {
    startYear: number;
    endYear: number;
    historicalEvents: string[];
    seasonalRelevance: boolean;
  };
  
  // Soziales Milieu
  socialContext: {
    classes: string[];
    tensions: string[];
    customs: string[];
    languageRegisters: string[];  // Welche Sprachebenen kommen vor
  };
}
```

**KI-Prompt für Setting-Extraktion:**

```
Analysiere den folgenden Roman und extrahiere alle relevanten Settings.

ROMAN: {{book_text}}

Für jeden Ort, extrahiere:
1. Name und Beschreibung
2. Atmosphäre (düster, fröhlich, geheimnisvoll, etc.)
3. Welche Gesellschaftsschicht verkehrt dort
4. 2-3 Original-Zitate, die den Ort beschreiben
5. Welche Schlüsselszenen dort stattfinden

Antworte im JSON-Format gemäß dem Schema.
```

#### 2.2.2 Charakter-Analyse

**Output:** NPC-Datenbank mit Persönlichkeitsprofilen

```typescript
interface ExtractedCharacter {
  // Basis-Info
  id: string;
  name: string;
  role: string;  // "Antagonist", "Mentor", "Love Interest", etc.
  
  // Persönlichkeit (aus Verhalten im Buch abgeleitet)
  personality: {
    traits: string[];  // "loyal", "bitter", "naive", etc.
    motivations: string[];
    fears: string[];
    secrets: string[];
  };
  
  // Sprachmuster (aus Dialogen extrahiert)
  speechPattern: {
    vocabulary: 'simple' | 'educated' | 'aristocratic' | 'street';
    sentenceComplexity: 'short' | 'medium' | 'elaborate';
    quirks: string[];  // Besondere Ausdrücke, Akzente, etc.
    exampleQuotes: string[];
  };
  
  // Beziehungen
  relationships: {
    characterId: string;
    type: 'friend' | 'enemy' | 'family' | 'romantic' | 'professional';
    dynamicDescription: string;
  }[];
  
  // Story-Relevanz
  storyRelevance: {
    appearsInChapters: number[];
    keyMoments: string[];
    transformationArc: string;  // Wie verändert sich der Charakter
  };
  
  // Interaktionspotential für Spieler
  interactionPotential: {
    canBeAlly: boolean;
    canBeEnemy: boolean;
    hasSecretsToShare: boolean;
    potentialQuestGiver: boolean;
  };
}
```

#### 2.2.3 Plot-Struktur-Mapping

**Output:** Kapitelstruktur mit Branching-Potenzial

```typescript
interface PlotStructure {
  acts: {
    actNumber: number;
    title: string;
    chapters: {
      chapterNumber: number;
      summary: string;
      
      // Kernszenen
      keyScenes: {
        id: string;
        description: string;
        charactersInvolved: string[];
        location: string;
        emotionalBeat: string;  // "Hoffnung", "Verrat", "Erkenntnis"
        
        // Interaktionspotenzial
        interactionType: 'observe' | 'participate' | 'influence' | 'pivot';
        branchingPotential: 'none' | 'low' | 'medium' | 'high';
      }[];
      
      // Lernpotenzial
      languageOpportunities: {
        grammar: string[];
        vocabulary: string[];
        communicativeFunctions: string[];
      };
    }[];
  }[];
  
  // Kritische Wendepunkte
  pivotPoints: {
    chapterId: string;
    description: string;
    originalOutcome: string;
    alternativeOutcomes: string[];  // Wie könnte es anders laufen?
  }[];
}
```

### 2.3 Phase 2: Design

#### 2.3.1 Spielerrolle definieren

```typescript
interface PlayerRoleDefinition {
  // Wer ist der Spieler?
  identity: {
    name: string | null;  // Kann Spieler wählen lassen
    occupation: string;
    socialClass: string;
    backstory: string;
    
    // Warum ist der Spieler in dieser Welt?
    motivation: string;
    personalGoal: string;
  };
  
  // Beziehung zu Hauptcharakteren
  relationshipToProtagonist: {
    type: 'knows' | 'meets' | 'observes' | 'serves';
    initialStanding: 'stranger' | 'acquaintance' | 'friend' | 'subordinate';
    canInfluence: boolean;
  };
  
  // Handlungsspielraum
  agency: {
    canPreventBadEvents: boolean;  // Kann Spieler Fantine retten?
    canAccelerateGoodEvents: boolean;
    canDiscoverSecrets: boolean;
    hasOwnSubplot: boolean;
  };
  
  // Narrative Grenzen
  constraints: {
    mustWitness: string[];  // Kernszenen, die passieren müssen
    cannotChange: string[];  // Plot-Punkte, die fix sind
    canInfluence: string[];  // Bereiche mit Spielereinfluss
  };
}
```

**Beispiel: Spielerrolle in "Les Misérables"**

```yaml
playerRole:
  identity:
    name: null  # Spieler wählt
    occupation: "Arbeiter/in in M. Madeleines Fabrik"
    socialClass: "Arbeiterklasse"
    backstory: |
      Du bist vor drei Monaten nach Montreuil-sur-Mer gekommen, 
      auf der Suche nach Arbeit. M. Madeleine hat dich eingestellt.
      Du hast Gerüchte über seine mysteriöse Vergangenheit gehört...
    motivation: "Überleben und vielleicht ein besseres Leben finden"
    personalGoal: "Das Geheimnis von M. Madeleine lüften"
    
  relationshipToProtagonist:
    type: "serves"
    initialStanding: "subordinate"
    canInfluence: true
    
  agency:
    canPreventBadEvents: false  # Fantine stirbt trotzdem
    canAccelerateGoodEvents: true  # Kannst Cosettes Rettung beschleunigen
    canDiscoverSecrets: true  # Kannst Valjeans Identität früher entdecken
    hasOwnSubplot: true  # Eigene Romanzen/Konflikte möglich
    
  constraints:
    mustWitness:
      - "Fantines Entlassung"
      - "Madeleines Geständnis vor Gericht"
      - "Die Barrikade"
    cannotChange:
      - "Valjeans Verhaftung (nur verzögern)"
      - "Javerts Obsession"
      - "Éponines Tod"
    canInfluence:
      - "Fantines Behandlung vor ihrem Tod"
      - "Cosettes Kindheit (weniger Leid)"
      - "Marius' Überleben auf der Barrikade"
```

#### 2.3.2 Interaktive Szenen identifizieren

Nicht jede Buchszene wird zu einer interaktiven Szene. Wir identifizieren:

**Kriterien für interaktive Szenen:**

1. **Dialog-reich**: Es wird viel gesprochen (Sprache übbar)
2. **Emotional geladen**: Der Spieler hat Grund, sich zu engagieren
3. **Entscheidungsmoment**: Es gibt etwas zu entscheiden oder zu beeinflussen
4. **Lernziel-relevant**: Die Szene passt zu einem Grammatik/Vokabel-Ziel

```typescript
interface InteractiveSceneDesign {
  originalScene: {
    bookChapter: number;
    summary: string;
    originalDialogue: string[];
  };
  
  transformation: {
    playerPresence: 'active_participant' | 'observer_who_can_intervene' | 'hidden_observer';
    
    // Was kann der Spieler tun?
    playerActions: {
      id: string;
      description: string;
      languageRequired: string;  // "Muss um Hilfe bitten", "Muss verhandeln"
      consequenceType: 'story' | 'relationship' | 'both';
    }[];
    
    // Branching
    branches: {
      trigger: string;  // Was der Spieler sagen/tun muss
      outcome: string;
      affectsMainPlot: boolean;
    }[];
  };
  
  // Sprachliche Ziele
  learningIntegration: {
    primaryGrammar: string;
    vocabularyTheme: string;
    communicativeFunction: string;
    culturalNote: string;  // Historischer/kultureller Kontext
  };
}
```

### 2.4 Phase 3: Adaption

#### 2.4.1 Sprach-Modernisierung

Das Originalwerk verwendet oft archaische Sprache. Wir erstellen Level-Varianten:

```typescript
interface LanguageAdaptation {
  originalText: string;  // Aus dem Buch
  
  // Level-spezifische Versionen
  adaptations: {
    A1: {
      text: string;
      simplifications: string[];  // Was wurde vereinfacht
      vocabularyHelp: { word: string; translation: string }[];
    };
    A2: {
      text: string;
      simplifications: string[];
    };
    B1: {
      text: string;
      // Näher am Original, aber modernisiert
      archaicToModern: { original: string; modern: string }[];
    };
    B2: {
      text: string;
      // Größtenteils original, nur schwierigste Stellen angepasst
    };
    C1: {
      text: string;
      // Original mit Kontext-Hilfen für historische Begriffe
      historicalNotes: { term: string; explanation: string }[];
    };
  };
}
```

**KI-Prompt für Sprach-Adaption:**

```
Du bist ein Experte für Sprachdidaktik und französische Literatur.

ORIGINALTEXT (aus "Les Misérables", 1862):
"{{original_text}}"

Erstelle Adaptionen für verschiedene CEFR-Level:

A1 (Absolute Anfänger):
- Maximal 8 Wörter pro Satz
- Nur Präsens
- Grundvokabular
- Der Kern der Aussage muss erhalten bleiben

A2 (Elementar):
- Maximal 12 Wörter pro Satz
- Präsens + Passé Composé erlaubt
- Erweitertes Grundvokabular

B1 (Mittelstufe):
- Natürliche Satzlänge
- Alle Zeitformen außer Passé Simple
- Modernisiere archaische Ausdrücke

B2 (Obere Mittelstufe):
- Nahe am Original
- Passé Simple erlaubt
- Nur unverständliche Archaismen ersetzen

C1 (Fortgeschritten):
- Originaltext
- Füge Erklärungen für historische Begriffe hinzu

Behalte bei allen Versionen:
- Den emotionalen Ton
- Die Charakterstimme
- Die narrative Funktion
```

#### 2.4.2 NPC-Persona-Erstellung

Aus extrahierten Charakteren werden spielbare NPCs:

```typescript
interface NPCPersonaCreation {
  sourceCharacter: ExtractedCharacter;
  
  gameNPC: {
    // Basis aus Extraktion
    id: string;
    name: string;
    
    // Angereicherte Persönlichkeit
    personality: {
      coreTraits: string[];  // Aus dem Buch
      addedDepth: string[];  // Für Interaktivität hinzugefügt
      
      // Wie reagiert der NPC auf verschiedene Spieleraktionen
      reactionPatterns: {
        toFlattery: 'receptive' | 'suspicious' | 'immune';
        toHonesty: 'appreciates' | 'neutral' | 'offended';
        toHumor: 'enjoys' | 'tolerates' | 'dislikes';
        toFormality: 'expects' | 'prefers_casual' | 'flexible';
      };
    };
    
    // Sprach-Persona
    voice: {
      baseLevel: CEFRLevel;
      adaptToPlayer: boolean;
      
      // Sprachliche Eigenheiten
      vocabularyDomain: string[];  // "legal", "street", "aristocratic"
      catchphrases: string[];
      grammarQuirks: string[];  // z.B. "Verwendet nie Fragen, nur Aussagen"
      
      // Level-spezifische Beispieldialoge
      sampleDialogues: {
        level: CEFRLevel;
        situation: string;
        dialogue: string;
      }[];
    };
    
    // Beziehungsmechanik
    relationshipConfig: {
      initialLevel: number;
      maxLevel: number;
      
      // Was verbessert/verschlechtert die Beziehung
      likesWhen: string[];
      dislikesWhen: string[];
      
      // Level-Belohnungen
      levelRewards: {
        level: number;
        unlocks: string;  // Information, Quest, Item
      }[];
    };
    
    // Story-Integration
    storyRole: {
      appearsInScenes: string[];
      canDieInStory: boolean;
      alternativeOutcomes: string[];  // Wie kann Spieler sein Schicksal ändern
    };
  };
}
```

#### 2.4.3 Lernziel-Integration

Jede Szene hat explizite Lernziele:

```typescript
interface LearningIntegration {
  scene: string;
  
  // Primäre Lernziele
  primary: {
    grammar: {
      structure: string;  // z.B. "conditionnel"
      whyHere: string;  // Warum passt diese Struktur zur Szene
      naturalUsage: string;  // Wie wird sie natürlich eingebettet
    };
    
    vocabulary: {
      theme: string;  // z.B. "Gefühle des Verlusts"
      words: string[];
      contextInScene: string;
    };
    
    communicativeFunction: {
      function: string;  // z.B. "Trost spenden"
      phrases: string[];
      emotionalContext: string;
    };
  };
  
  // Kulturelle Lernziele
  cultural: {
    historicalContext: string;
    socialNorms: string;
    comparison: string;  // Vergleich mit heute
  };
  
  // Versteckte Lernziele (Spieler merkt es nicht direkt)
  implicit: {
    pronunciation: string[];  // Schwierige Laute, die vorkommen
    listeningComprehension: string;  // Was muss der Spieler verstehen
    inferencing: string;  // Was muss er ableiten
  };
}
```

### 2.5 Phase 4: Produktion

#### 2.5.1 Story-Scripting

Das finale Format für das Spiel:

```yaml
# story_les_miserables_fantine.yaml

metadata:
  id: "les_mis_act1_fantine"
  title: "Die Schatten von Montreuil"
  subtitle: "Nach Victor Hugo"
  
  source:
    book: "Les Misérables"
    author: "Victor Hugo"
    year: 1862
    gutenbergId: "135"
    adaptationNote: |
      Diese interaktive Adaption basiert auf dem ersten Akt 
      von Victor Hugos Meisterwerk. Die Kerngeschichte bleibt 
      erhalten, aber du erlebst sie aus einer neuen Perspektive.
  
  targetLevels: ["A2", "B1", "B2"]
  estimatedDuration: 120  # Minuten für alle Kapitel
  
  themes:
    - "Gerechtigkeit und Gnade"
    - "Armut und Würde"
    - "Geheimnisse und Identität"
    
  historicalPeriod:
    years: "1815-1823"
    context: "Restauration in Frankreich nach Napoleon"

playerRole:
  title: "Der/Die Neue in der Fabrik"
  description: |
    Du bist vor kurzem in Montreuil-sur-Mer angekommen und 
    arbeitest in der Fabrik von Monsieur Madeleine. 
    Die Arbeit ist hart, aber fair bezahlt. 
    Doch irgendetwas stimmt nicht mit deinem Arbeitgeber...
  
  personalMystery: |
    Du hast einen Brief gefunden, der Madeleine mit einem 
    Sträfling namens "24601" in Verbindung bringt.
    
  goals:
    - "Überlebe den Winter"
    - "Finde heraus, wer Madeleine wirklich ist"
    - "Entscheide, auf welcher Seite du stehst"

npcs:
  - id: "madeleine_valjean"
    name: "Monsieur Madeleine"
    trueIdentity: "Jean Valjean"
    role: "Fabrikbesitzer und Bürgermeister"
    
    personality:
      coreTraits: ["gütig", "geheimnisvoll", "stark"]
      hiddenTraits: ["geplagt von Schuld", "auf der Flucht"]
      
    voice:
      baseLevel: "B1"
      adaptToPlayer: true
      style: "Formal, aber warmherzig. Vermeidet Fragen über seine Vergangenheit."
      catchphrases:
        - "Die Vergangenheit ist ein anderes Land."
        - "Jeder verdient eine zweite Chance."
        
    relationshipConfig:
      initialLevel: 2  # Du bist sein Angestellter
      maxLevel: 8  # Er wird dir nie ganz vertrauen
      
      levelRewards:
        - level: 4
          unlocks: "Er erzählt von seiner 'Schwester' (Erfindung)"
        - level: 6
          unlocks: "Du entdeckst seine Silberleuchter"
        - level: 8
          unlocks: "Er gesteht dir seine wahre Identität"
          
  - id: "fantine"
    name: "Fantine"
    role: "Arbeiterin, alleinerziehende Mutter"
    
    personality:
      coreTraits: ["verzweifelt", "liebend", "stolz"]
      arc: "Von Hoffnung zu Verzweiflung zu Frieden"
      
    voice:
      baseLevel: "A2"
      adaptToPlayer: false  # Sie ist zu erschöpft für komplexe Sprache
      style: "Kurze Sätze. Oft müde. Spricht viel von Cosette."
      
    relationshipConfig:
      initialLevel: 1
      maxLevel: 5
      
      levelRewards:
        - level: 3
          unlocks: "Sie zeigt dir Cosettes Briefe"
        - level: 5
          unlocks: "Sie bittet dich, Cosette zu finden"
          
  - id: "javert"
    name: "Inspektor Javert"
    role: "Polizeiinspektor"
    
    personality:
      coreTraits: ["unnachgiebig", "pflichtbewusst", "blind für Gnade"]
      
    voice:
      baseLevel: "B2"
      adaptToPlayer: false  # Er spricht, wie er spricht
      style: "Kalt, präzise, formell. Spricht in Gesetzessprache."
      catchphrases:
        - "Das Gesetz ist das Gesetz."
        - "Niemand entkommt der Gerechtigkeit."
        
    relationshipConfig:
      initialLevel: 0  # Neutral
      specialMechanic: |
        Javert hat keine normale Beziehung. 
        Stattdessen: Verdachts-Meter (0-10).
        Bei 10 verhaftet er dich als Komplizen.

chapters:
  - id: "ch1_arrival"
    title: "Ankunft in Montreuil"
    targetLevel: "A2"
    
    learningFocus:
      grammar: ["présent", "articles", "négation"]
      vocabulary: ["Fabrik", "Arbeit", "Stadt"]
      functions: ["sich vorstellen", "um Arbeit bitten"]
      
    scenes:
      - id: "sc1_factory_gates"
        title: "Vor den Fabrik-Toren"
        location: "Fabrikeingang, Montreuil-sur-Mer"
        
        setup:
          narratorText:
            A2: |
              Es ist kalt. Du stehst vor einer großen Fabrik.
              Ein Schild sagt: "Arbeiter gesucht".
              Du brauchst Arbeit. Du brauchst Geld.
            B1: |
              Der Januarwind beißt durch deine dünne Jacke.
              Vor dir erheben sich die Mauern der Madeleine-Fabrik,
              dem größten Arbeitgeber der Stadt.
              Ein verwittertes Schild verspricht Arbeit für fleißige Hände.
              
        npcsPresent: ["foreman_dubois"]
        
        objectives:
          - id: "get_job"
            description: "Überzeuge den Vorarbeiter, dir eine Chance zu geben"
            type: "convince"
            successCriteria: "Höfliche Vorstellung + Motivation erklären"
            
        dialogueTree:
          # Vorarbeiter ist zunächst skeptisch
          initial:
            npc: "foreman_dubois"
            text:
              A2: "Was willst du? Wir haben viele Bewerber."
              B1: "Noch einer. Was unterscheidet dich von den anderen zwanzig, die heute schon hier waren?"
            
          playerOptions:
            - trigger: "mentions:travail|arbeiten|work"
              response:
                npc: "foreman_dubois"
                text: "Arbeit, ja. Kannst du überhaupt arbeiten? Woher kommst du?"
                relationshipEffect: 0
                
            - trigger: "polite_introduction"  # Wenn Spieler sich höflich vorstellt
              response:
                npc: "foreman_dubois"
                text: "Hmm. Wenigstens hast du Manieren. Das ist selten geworden."
                relationshipEffect: +1
                
            - trigger: "rude_or_demanding"
              response:
                npc: "foreman_dubois"
                text: "Verschwinde. Wir brauchen keine Unruhestifter."
                consequence: "scene_ends_badly"
                
        consequences:
          - trigger: "job_obtained"
            effects:
              - type: "unlock_chapter"
                target: "ch1_first_day"
              - type: "set_flag"
                key: "has_job"
                value: true
                
    cliffhanger:
      text: |
        Der erste Arbeitstag ist überstanden. 
        Als du die Fabrik verlässt, siehst du Monsieur Madeleine.
        Er spricht mit einem Mann in Polizeiuniform.
        Der Polizist zeigt ihm ein Bild. Madeleine wird blass.
        Wer ist der Mann auf dem Bild?
      hook: "Das Geheimnis beginnt..."
      
  - id: "ch2_fantines_fall"
    title: "Fantines Sturz"
    targetLevel: "A2-B1"
    
    learningFocus:
      grammar: ["passé composé", "imparfait introduction"]
      vocabulary: ["Gefühle", "Familie", "Geld"]
      functions: ["Mitgefühl zeigen", "um Hilfe bitten"]
      
    # Kritische Szene: Fantines Entlassung
    scenes:
      - id: "sc_fantine_fired"
        title: "Die Entlassung"
        emotionalBeat: "Ungerechtigkeit"
        
        historicalNote: |
          Im 19. Jahrhundert konnten unverheiratete Mütter 
          ihre Arbeit verlieren, wenn ihr "Geheimnis" bekannt wurde.
          Es gab keinen Kündigungsschutz.
          
        # PIVOT POINT: Spieler kann eingreifen
        pivotPoint:
          originalOutcome: "Fantine wird entlassen, niemand hilft"
          playerCanIntervene: true
          interventionOptions:
            - action: "Sprich mit der Aufseherin"
              difficulty: "B1"
              requiredRelationship: 3  # mit Aufseherin
              outcome: "Fantine bekommt eine Woche Aufschub"
              
            - action: "Sprich direkt mit Madeleine"
              difficulty: "B2"
              requiredRelationship: 4  # mit Madeleine
              outcome: "Madeleine untersucht den Fall persönlich"
              plotChange: "Fantine wird nicht entlassen, aber Geschichte ändert sich"
              
            - action: "Schweige"
              outcome: "Originalverlauf - Fantine wird entlassen"
              
        consequenceWarning: |
          [SYSTEM] Diese Entscheidung beeinflusst Fantines Schicksal.
          Es gibt kein Zurück.

# Voice-First Bonus Configuration
voiceConfig:
  defaultMode: "voice"
  textAllowed: true
  
  voiceBonuses:
    xpMultiplier: 1.5
    relationshipMultiplier: 1.25
    
  voiceOnlyScenes:
    - "interrogation_javert"  # Verhör muss mündlich sein
    - "final_confession"
    
  pronunciationChallenges:
    - scene: "sc1_factory_gates"
      focusSounds: ["r français", "u/ou distinction"]
      
    - scene: "sc_fantine_fired"
      focusSounds: ["liaisons", "e muet"]

# Alternative Endings
endings:
  - id: "ending_canonical"
    name: "Der Lauf der Geschichte"
    description: "Die Ereignisse verlaufen wie im Buch."
    conditions:
      - "did_not_intervene_fantine"
      - "did_not_expose_valjean"
      
  - id: "ending_savior"
    name: "Der Retter"
    description: "Du hast Fantine gerettet. Die Geschichte nimmt einen anderen Lauf."
    conditions:
      - "intervened_fantine"
      - "fantine_relationship >= 5"
    plotChange: "Fantine überlebt und wird Zeugin bei Valjeans Geständnis."
    
  - id: "ending_betrayer"
    name: "Der Verräter"
    description: "Du hast Valjean an Javert verraten."
    conditions:
      - "exposed_valjean_to_javert"
    plotChange: "Valjean wird früher verhaftet. Cosette bleibt bei den Thénardiers."
    moralWeight: "Du hast nach dem Gesetz gehandelt. Aber war es richtig?"
```

#### 2.5.2 Dialog-Generierung

Für dynamische Dialoge, die nicht vorscripted sind:

```typescript
interface DynamicDialogueGeneration {
  // Kontext für die KI
  context: {
    scene: SceneDefinition;
    npc: NPCPersona;
    playerInput: string;
    conversationHistory: Message[];
    storyFlags: Map<string, any>;
    playerLevel: CEFRLevel;
  };
  
  // Constraints für die Generierung
  constraints: {
    mustMention: string[];  // Plot-relevante Informationen
    mustNotReveal: string[];  // Geheimnisse, die noch nicht enthüllt werden dürfen
    emotionalTone: string;
    maxComplexity: CEFRLevel;
  };
}

// KI-Prompt Template
const DYNAMIC_DIALOGUE_PROMPT = `
Du generierst Dialog für ein interaktives Sprachlern-Abenteuer basierend auf "{{book.title}}".

SZENE: {{scene.description}}
ORT: {{scene.location}}
ZEIT: {{scene.time}}

NPC: {{npc.name}}
Persönlichkeit: {{npc.personality}}
Sprechmuster: {{npc.voice}}
Beziehung zum Spieler: Level {{relationship.level}}/{{relationship.max}}
Aktuelle Stimmung: {{npc.currentMood}}

SPIELER-LEVEL: {{player.level}}
Passe die Sprachkomplexität an dieses Level an.

BISHERIGES GESPRÄCH:
{{#each conversationHistory}}
{{this.role}}: {{this.content}}
{{/each}}

SPIELER SAGT: "{{playerInput}}"

CONSTRAINTS:
- Diese Informationen MÜSSEN erwähnt werden: {{constraints.mustMention}}
- Diese Geheimnisse dürfen NICHT enthüllt werden: {{constraints.mustNotReveal}}
- Emotionaler Ton: {{constraints.emotionalTone}}

ANWEISUNGEN:
1. Antworte als {{npc.name}}, treu zu seiner Persönlichkeit
2. Reagiere natürlich auf den Spieler
3. Treibe die Szene voran, ohne zu forcieren
4. Wenn der Spieler Sprachfehler macht, reagiere im Charakter (nicht als Lehrer)
5. Beende mit etwas, das den Spieler zum Antworten einlädt

Antworte NUR mit dem Dialog von {{npc.name}}.
`;
```

#### 2.5.3 Quality Assurance

```typescript
interface QAChecklist {
  // Sprachliche Qualität
  language: {
    levelAppropriate: boolean;  // Ist die Sprache dem Level angemessen?
    grammarCorrect: boolean;
    culturallyAccurate: boolean;
    periodAppropriate: boolean;  // Keine modernen Anachronismen?
  };
  
  // Narrative Qualität
  narrative: {
    characterConsistent: boolean;  // Verhalten sich NPCs konsistent?
    plotCoherent: boolean;  // Macht die Geschichte Sinn?
    emotionallyEngaging: boolean;
    branchingLogical: boolean;  // Sind alle Verzweigungen logisch?
  };
  
  // Pädagogische Qualität
  educational: {
    learningObjectivesClear: boolean;
    grammarNaturallyIntegrated: boolean;
    vocabularyContextualized: boolean;
    progressionAppropriate: boolean;
  };
  
  // Technische Qualität
  technical: {
    allPathsPlayable: boolean;
    noDeadEnds: boolean;
    voiceRecognitionTested: boolean;
    loadTimesAcceptable: boolean;
  };
  
  // Sensitivitäts-Check
  sensitivity: {
    historicalAccuracy: boolean;
    noProblemataticContent: boolean;
    difficultThemesHandledWell: boolean;  // z.B. Fantines Schicksal
  };
}
```

---

## Teil 3: Konkrete Beispiel-Adaptionen

### 3.1 "Le Petit Prince" (Der kleine Prinz)

**Warum dieses Buch?**
- Universell geliebt
- Philosophisch, aber zugänglich
- Kurze Kapitel = perfekte Episode-Länge
- Bereits verwendete einfache Sprache
- Tiefgründige Themen für Erwachsene, einfache Oberfläche für Anfänger

**Spielerrolle:**

```yaml
playerRole:
  title: "Der Bewohner des Asteroiden B-329"
  
  setup: |
    Du lebst allein auf einem kleinen Asteroiden.
    Eines Tages landet ein seltsames Kind mit goldenen Haaren.
    Er stellt dir eine Frage: "Bitte... zeichne mir ein Schaf!"
    
  twist: |
    Du bist der ERSTE Planet, den der kleine Prinz besucht.
    Deine Gespräche mit ihm formen, wer er wird.
    Was du ihm beibringst, nimmt er mit auf seine Reise.
    
  mechanicUnique: |
    Der kleine Prinz stellt philosophische Fragen.
    Deine Antworten beeinflussen seine Weltsicht.
    Am Ende des Spiels siehst du, wie deine Worte 
    sein Verhalten auf den anderen Planeten beeinflusst haben.
```

**Kapitelstruktur:**

| Kapitel | Thema | Level | Lernfokus |
|---------|-------|-------|-----------|
| 1: Die Ankunft | Der Prinz landet bei dir | A1 | Fragen stellen, "Qu'est-ce que c'est?" |
| 2: Das Schaf | Du versuchst, ein Schaf zu zeichnen | A1 | Beschreibungen, Adjektive |
| 3: Die Rose | Der Prinz erzählt von seiner Rose | A2 | Gefühle, Beziehungen |
| 4: Der Abschied | Der Prinz muss weiterziehen | A2 | Abschied, Versprechen |
| Epilog | Jahre später... | B1 | Passé composé, Erinnerungen |

**Besondere Mechanik: Die Philosophie-Gespräche**

```yaml
philosophyMechanic:
  description: |
    Der kleine Prinz stellt existenzielle Fragen.
    Es gibt keine "richtige" Antwort, aber verschiedene 
    Antworten führen zu verschiedenen Erkenntnissen.
    
  example:
    princeQuestion: "Was bedeutet 'zähmen'?"
    
    playerResponses:
      - response: "Das bedeutet, jemanden zu besitzen."
        princeReaction: |
          Der kleine Prinz schüttelt den Kopf.
          "Die großen Leute denken immer ans Besitzen.
           Aber man besitzt nur, was man nicht liebt."
        insight: "Besitz ≠ Liebe"
        
      - response: "Das bedeutet, eine Verbindung zu schaffen."
        princeReaction: |
          Der kleine Prinz lächelt.
          "Ja! Wenn du mich zähmst, werden wir einander brauchen.
           Du wirst für mich einzig sein in der Welt."
        insight: "Zähmen = Einzigartigkeit durch Beziehung"
        
      - response: "Ich weiß nicht."
        princeReaction: |
          Der kleine Prinz setzt sich neben dich.
          "Das ist die beste Antwort. 
           Lass es mich dir zeigen..."
        insight: "Manchmal ist Nicht-Wissen der Anfang des Wissens"
```

### 3.2 "Les Misérables" (Die Elenden)

**Warum dieses Buch?**
- Episches Drama
- Viele Charaktere = viele NPCs
- Moralische Komplexität
- Historischer Kontext = Kulturlernen
- Lange genug für ein ganzes "Spiel"

**Spielerrolle:**

```yaml
playerRole:
  title: "Der Zeuge"
  
  description: |
    Du bist ein gewöhnlicher Mensch im Frankreich des 19. Jahrhunderts.
    Dein Weg kreuzt sich mit den Schicksalen von Jean Valjean, 
    Fantine, Cosette, und den anderen.
    Du kannst beobachten. Du kannst eingreifen. Du kannst schweigen.
    Aber alles hat Konsequenzen.
    
  roleVariants:
    - variant: "Fabrikarbeiter"
      startingPoint: "Madeleines Fabrik"
      advantage: "Nähe zu Fantine und Valjean"
      
    - variant: "Straßenhändler"
      startingPoint: "Die Gassen von Paris"
      advantage: "Verbindungen zur Unterwelt, Zugang zu den Thénardiers"
      
    - variant: "Jurastudent"
      startingPoint: "Die Sorbonne"
      advantage: "Nähe zu Marius und den Revolutionären"
```

**Story-Arc-Struktur:**

```
ACT 1: FANTINE (Level A2-B1)
├── Kapitel 1: Die Fabrik
├── Kapitel 2: Der Fall
├── Kapitel 3: Das Versprechen
└── PIVOT: Kannst du Fantine retten?

ACT 2: COSETTE (Level B1)
├── Kapitel 4: Das Gasthaus der Hölle (Thénardiers)
├── Kapitel 5: Der Weihnachtsabend
├── Kapitel 6: Die Rettung
└── PIVOT: Hilfst du Valjean oder verrätst du ihn?

ACT 3: MARIUS (Level B1-B2)
├── Kapitel 7: Der Student
├── Kapitel 8: Die Liebe
├── Kapitel 9: Der Konflikt
└── PIVOT: Auf welcher Seite stehst du?

ACT 4: DIE BARRIKADE (Level B2)
├── Kapitel 10: Der Aufstand
├── Kapitel 11: Die lange Nacht
├── Kapitel 12: Der Morgen danach
└── FINALE: Mehrere Enden möglich
```

**Moralisches Dilemma-System:**

```typescript
interface MoralDilemma {
  id: string;
  situation: string;
  
  choices: {
    lawful: {
      description: string;
      consequence: string;
      javertApproval: number;  // +
      valjeanDisapproval: number;  // -
    };
    merciful: {
      description: string;
      consequence: string;
      valjeanApproval: number;  // +
      javertDisapproval: number;  // -
    };
    selfServing: {
      description: string;
      consequence: string;
      // Kurzfristiger Vorteil, langfristige Kosten
    };
  };
  
  // Tracking über das ganze Spiel
  moralAlignment: 'lawful' | 'merciful' | 'pragmatic';
}

// Beispiel
const dilemmaFantine: MoralDilemma = {
  id: "fantine_dismissal",
  situation: |
    Du siehst, wie die Aufseherin Fantine beschuldigt, 
    eine "gefallene Frau" zu sein. Du weißt, dass es wahr ist – 
    du hast die Briefe an ihre Tochter gesehen.
    Die Aufseherin fragt dich: "Stimmt das?"
    
  choices: {
    lawful: {
      description: "Sag die Wahrheit.",
      consequence: "Fantine wird entlassen. Sie flucht dir.",
      javertApproval: +2,
      valjeanDisapproval: -3
    },
    merciful: {
      description: "Lüge, um Fantine zu schützen.",
      consequence: "Die Aufseherin ist skeptisch, aber lässt es sein. Für jetzt.",
      valjeanApproval: +2,
      javertDisapproval: -3
    },
    selfServing: {
      description: "Sag, du weißt nichts.",
      consequence: "Du bleibst neutral. Aber Fantine wird trotzdem entlassen."
    }
  }
};
```

### 3.3 "Der Graf von Monte Christo"

**Warum dieses Buch?**
- Ultimative Rache-Geschichte
- Spannung und Intrigen
- Viele Schauplätze (Marseille, Paris, Rom, Inseln)
- Perfekt für B1-C1 (komplexe Plots erfordern komplexere Sprache)

**Spielerrolle:**

```yaml
playerRole:
  title: "Der Mithäftling"
  
  setup: |
    Du bist unschuldig im Château d'If eingekerkert.
    Die Jahre vergehen. Die Hoffnung stirbt.
    Dann, eines Nachts, hörst du Kratzgeräusche in der Wand...
    
  mechanicUnique: |
    Du gräbst mit dem Abbé Faria und Edmond Dantès.
    Dein Französisch-Level bestimmt, wie viel du von 
    Farias Unterricht verstehst.
    
    Bei A2: Du lernst Grundlagen
    Bei B1: Du erfährst vom Schatz
    Bei B2: Du verstehst Farias Strategien
    Bei C1: Du wirst zu Dantès' rechter Hand bei der Rache
    
  plotTwist: |
    Am Ende von Akt 1 stirbt Faria. 
    Du und Dantès entkommt.
    Aber nur einer kann den Schatz haben...
    
  branchingPoint: |
    Option A: Du verbündest dich mit Dantès (kooperativ)
    Option B: Du versuchst, ihn zu überlisten (kompetitiv)
    Option C: Du gehst deinen eigenen Weg (solo)
```

**Sprachlevel-Progressions-Mechanik:**

```yaml
prisonEducation:
  teacher: "Abbé Faria"
  
  description: |
    Im Gefängnis unterrichtet dich der alte Abbé.
    Je länger du "im Gefängnis" bist (= spielst), 
    desto mehr lernst du.
    
  progression:
    year1:
      narratorText: "Faria beginnt, dir das Alphabet beizubringen."
      unlockedGrammar: ["présent", "articles"]
      unlockedVocab: ["prison", "espoir", "liberté"]
      
    year3:
      narratorText: "Du kannst nun einfache Bücher lesen."
      unlockedGrammar: ["passé composé", "futur proche"]
      unlockedVocab: ["histoire", "géographie", "science"]
      
    year5:
      narratorText: "Faria lehrt dich Strategie und Manipulation."
      unlockedGrammar: ["subjonctif", "conditionnel"]
      unlockedVocab: ["vengeance", "stratégie", "trahison"]
      
    year7:
      narratorText: "Du sprichst nun wie ein Gelehrter."
      unlockedGrammar: ["passé simple", "plus-que-parfait"]
      unlockedVocab: ["littérature", "philosophie", "rhétorique"]
      
  gameplayIntegration: |
    Die "Jahre" sind natürlich komprimiert.
    Jedes "Jahr" = ca. 2-3 Spielsessions.
    Der Spieler erlebt seinen eigenen Sprachfortschritt 
    parallel zur Geschichte.
```

---

## Teil 4: Voice-First Integration

### 4.1 Architektur-Anpassungen

```typescript
interface VoiceFirstArchitecture {
  inputModes: {
    voice: {
      priority: 'primary';
      bonuses: {
        xpMultiplier: 1.5;
        relationshipMultiplier: 1.25;
        exclusiveAchievements: true;
      };
      requirements: {
        minimumAccuracy: 0.7;  // ASR-Confidence
        pronunciationScoring: true;
      };
    };
    text: {
      priority: 'fallback';
      bonuses: {
        xpMultiplier: 1.0;
        relationshipMultiplier: 1.0;
      };
      restrictions: {
        notAllowedInScenes: string[];  // z.B. "interrogation"
      };
    };
  };
  
  pronunciationFeedback: {
    enabled: true;
    realTime: boolean;  // Feedback während des Sprechens?
    detailedAnalysis: boolean;
    gamification: {
      pronunciationScore: 0-100;
      accentBadges: string[];  // "Pariser Akzent", "Québécois", etc.
    };
  };
  
  listeningComprehension: {
    npcSpeechSpeed: {
      A1: 0.7;  // 70% normale Geschwindigkeit
      A2: 0.8;
      B1: 0.9;
      B2: 1.0;
      C1: 1.1;  // Schneller als normal + Umgangssprache
    };
    subtitles: {
      A1: 'always';
      A2: 'on_request';
      B1: 'on_request';
      B2: 'off_by_default';
      C1: 'never';
    };
  };
}
```

### 4.2 Voice-exklusive Szenen

```yaml
voiceOnlyScenes:
  - id: "interrogation_javert"
    reason: |
      Javert verhört dich. Du hast keine Zeit zum Tippen.
      Deine mündliche Reaktionszeit bestimmt seine Einschätzung.
      
    mechanics:
      timeLimit: 10  # Sekunden pro Antwort
      stammering: |
        Wenn du stotterst oder zu lange pausierst, 
        wird Javert misstrauischer.
      wrongAnswer: |
        Grammatikfehler = Javert merkt, dass du nervös bist.
        Zu komplexe Sprache = Er denkt, du versteckst etwas.
        
    tip: "Sprich natürlich. Nicht zu einfach, nicht zu komplex."
    
  - id: "barricade_speech"
    reason: |
      Du stehst auf der Barrikade. Die Menschen schauen zu dir auf.
      Eine getippte Nachricht wäre... unpassend.
      
    mechanics:
      crowdReaction: |
        Die KI analysiert deine Rede:
        - Überzeugungskraft (Inhalt)
        - Eloquenz (Sprache)
        - Leidenschaft (Tonfall via Audio-Analyse)
        
    reward: |
      Eine mitreißende Rede schaltet das Achievement 
      "Stimme der Revolution" frei.
```

### 4.3 Aussprache als Gameplay-Element

```typescript
interface PronunciationAsGameplay {
  // Szenen, wo Aussprache plot-relevant ist
  plotRelevantPronunciation: {
    sceneId: string;
    word: string;
    correctPronunciation: string;
    consequence: {
      correct: string;
      incorrect: string;
    };
  }[];
}

// Beispiel
const pronunciationScenarios: PronunciationAsGameplay = {
  plotRelevantPronunciation: [
    {
      sceneId: "password_scene",
      context: "Du musst ein Passwort nennen, um eingelassen zu werden.",
      word: "chrysanthème",
      correctPronunciation: "/kʁi.zɑ̃.tɛm/",
      consequence: {
        correct: "Die Tür öffnet sich. Du bist drin.",
        incorrect: "Der Wächter zögert. 'Das klang falsch. Wie hast du das Passwort bekommen?'"
      }
    },
    {
      sceneId: "aristocrat_ball",
      context: "Du gibst dich als Adliger aus. Dein Akzent verrät dich.",
      word: "Versailles",
      correctPronunciation: "/vɛʁ.saj/",
      consequence: {
        correct: "Niemand zweifelt an dir.",
        incorrect: "Die Gräfin hebt eine Augenbraue. 'Woher sagten Sie, kommen Sie?'"
      }
    },
    {
      sceneId: "declaration_of_love",
      context: "Du gestehst deine Liebe.",
      word: "je t'aime",
      // Hier geht es nicht um "richtig/falsch", sondern um Emotion
      emotionAnalysis: true,
      consequence: {
        passionate: "Sie lächelt, gerührt von deiner Aufrichtigkeit.",
        flat: "Sie schaut dich an. 'Meinst du das wirklich?'",
        trembling: "Sie nimmt deine Hand. 'Du zitterst. Das ist süß.'"
      }
    }
  ]
};
```

---

## Teil 5: Technische Implementation der Pipeline

### 5.1 Gutenberg-Integration

```typescript
// Service zum Abrufen und Verarbeiten von Gutenberg-Texten

interface GutenbergService {
  // Buch abrufen
  fetchBook(gutenbergId: string): Promise<GutenbergBook>;
  
  // Text vorverarbeiten
  preprocessText(rawText: string, language: Language): ProcessedText;
  
  // Kapitel extrahieren
  extractChapters(text: ProcessedText): Chapter[];
  
  // Dialoge identifizieren
  identifyDialogues(chapter: Chapter): Dialogue[];
}

interface GutenbergBook {
  id: string;
  title: string;
  author: string;
  language: string;
  publicationYear: number;
  rawText: string;
  metadata: {
    subjects: string[];
    downloadCount: number;
  };
}

// Beispiel-Implementierung
async function fetchFromGutenberg(id: string): Promise<GutenbergBook> {
  const metadataUrl = `https://gutenberg.org/ebooks/${id}`;
  const textUrl = `https://gutenberg.org/files/${id}/${id}-0.txt`;
  
  // Fetch und parse...
  return book;
}
```

### 5.2 KI-Pipeline für Extraktion

```typescript
interface ExtractionPipeline {
  // Schritt 1: Grobe Analyse
  async analyzeBook(book: GutenbergBook): Promise<BookAnalysis>;
  
  // Schritt 2: Charakter-Extraktion
  async extractCharacters(analysis: BookAnalysis): Promise<ExtractedCharacter[]>;
  
  // Schritt 3: Setting-Extraktion
  async extractSettings(analysis: BookAnalysis): Promise<ExtractedSetting[]>;
  
  // Schritt 4: Plot-Mapping
  async mapPlot(analysis: BookAnalysis): Promise<PlotStructure>;
  
  // Schritt 5: Interaktive Szenen identifizieren
  async identifyInteractiveScenes(plot: PlotStructure): Promise<InteractiveScene[]>;
}

// Prompts für jeden Schritt
const EXTRACTION_PROMPTS = {
  analyzeBook: `
    Analysiere diesen Roman und erstelle eine Übersicht:
    
    BUCH: {{book.title}} von {{book.author}}
    TEXT: {{book.rawText}}
    
    Extrahiere:
    1. Hauptthemen und Motive
    2. Narrative Struktur (Akte, Wendepunkte)
    3. Zentrale Konflikte
    4. Ton und Atmosphäre
    5. Historischer/kultureller Kontext
    6. Sprachlicher Stil (Komplexität, Register)
    
    Antworte im JSON-Format.
  `,
  
  extractCharacters: `
    Extrahiere alle wichtigen Charaktere aus diesem Roman.
    
    BUCH: {{book.title}}
    ANALYSE: {{bookAnalysis}}
    TEXT: {{book.rawText}}
    
    Für jeden Charakter, extrahiere:
    1. Name und Rolle
    2. Persönlichkeitsmerkmale (belegt durch Zitate)
    3. Sprechmuster (mit Beispieldialogen)
    4. Beziehungen zu anderen Charakteren
    5. Entwicklungsbogen
    6. Potenzial für Spieler-Interaktion
    
    Fokus auf Charaktere, die interessante NPCs wären.
  `,
  
  identifyInteractiveScenes: `
    Identifiziere Szenen, die zu interaktiven Spiel-Szenen werden könnten.
    
    PLOT: {{plotStructure}}
    
    Eine gute interaktive Szene hat:
    - Viel Dialog
    - Emotionale Spannung
    - Entscheidungsmomente
    - Lernpotenzial für Sprache
    
    Für jede Szene, bestimme:
    1. Wo könnte ein Spieler eingreifen?
    2. Welche Grammatik/Vokabeln werden natürlich verwendet?
    3. Welche Konsequenzen könnte Spielerhandeln haben?
    4. Wie beeinflusst es den Hauptplot (oder nicht)?
  `
};
```

### 5.3 Content-Generierungs-Pipeline

```typescript
interface ContentGenerationPipeline {
  // Input: Extrahierte Daten
  // Output: Spielbares Story-Paket
  
  async generateStoryPackage(
    extraction: {
      characters: ExtractedCharacter[];
      settings: ExtractedSetting[];
      plot: PlotStructure;
      interactiveScenes: InteractiveScene[];
    },
    config: {
      targetLevels: CEFRLevel[];
      voiceFirst: boolean;
      maxPlaytime: number;  // Minuten
    }
  ): Promise<StoryPackage>;
}

interface StoryPackage {
  metadata: StoryMetadata;
  npcs: NPCDefinition[];
  chapters: ChapterDefinition[];
  dialogueTemplates: DialogueTemplate[];
  languageAdaptations: LanguageAdaptation[];
  voiceConfig: VoiceConfiguration;
  achievements: Achievement[];
  endings: EndingDefinition[];
}

// Der Generierungsprozess
async function generateStoryPackage(extraction, config): Promise<StoryPackage> {
  // 1. Spielerrolle definieren
  const playerRole = await generatePlayerRole(extraction, config);
  
  // 2. NPCs erstellen
  const npcs = await Promise.all(
    extraction.characters.map(char => 
      transformCharacterToNPC(char, config.targetLevels)
    )
  );
  
  // 3. Kapitel strukturieren
  const chapters = await structureIntoChapters(
    extraction.plot,
    extraction.interactiveScenes,
    config.maxPlaytime
  );
  
  // 4. Sprache adaptieren
  const adaptations = await Promise.all(
    config.targetLevels.map(level =>
      adaptLanguageForLevel(extraction, level)
    )
  );
  
  // 5. Voice-Konfiguration
  const voiceConfig = generateVoiceConfig(chapters, config.voiceFirst);
  
  // 6. Achievements
  const achievements = generateAchievements(npcs, chapters);
  
  // 7. Endings
  const endings = generateEndings(extraction.plot, playerRole);
  
  return {
    metadata: generateMetadata(extraction, config),
    npcs,
    chapters,
    languageAdaptations: adaptations,
    voiceConfig,
    achievements,
    endings
  };
}
```

### 5.4 Quality-Pipeline

```typescript
interface QualityPipeline {
  // Automatisierte Checks
  automatedChecks: {
    languageCheck: (content: StoryPackage) => LanguageReport;
    narrativeCheck: (content: StoryPackage) => NarrativeReport;
    playabilityCheck: (content: StoryPackage) => PlayabilityReport;
  };
  
  // Human Review Points
  humanReviewRequired: {
    sensitiveContent: boolean;
    culturalAccuracy: boolean;
    pedagogicalAppropriateness: boolean;
  };
}

// Automatisierte Sprach-Checks
async function languageCheck(content: StoryPackage): Promise<LanguageReport> {
  const issues: LanguageIssue[] = [];
  
  for (const chapter of content.chapters) {
    for (const scene of chapter.scenes) {
      // Check: Ist die Sprache dem Level angemessen?
      const levelCheck = await checkLanguageLevel(
        scene.dialogues,
        chapter.targetLevel
      );
      
      if (!levelCheck.appropriate) {
        issues.push({
          location: `${chapter.id}/${scene.id}`,
          type: 'level_mismatch',
          description: levelCheck.reason,
          suggestion: levelCheck.fix
        });
      }
      
      // Check: Grammatik korrekt?
      const grammarCheck = await checkGrammar(scene.dialogues);
      issues.push(...grammarCheck.errors);
      
      // Check: Kulturelle Angemessenheit?
      const culturalCheck = await checkCulturalAccuracy(
        scene.dialogues,
        content.metadata.historicalPeriod
      );
      issues.push(...culturalCheck.issues);
    }
  }
  
  return {
    passed: issues.filter(i => i.severity === 'critical').length === 0,
    issues,
    summary: generateSummary(issues)
  };
}

// Playability Check: Alle Pfade spielbar?
async function playabilityCheck(content: StoryPackage): Promise<PlayabilityReport> {
  const issues: PlayabilityIssue[] = [];
  
  // Graph-Analyse aller Story-Pfade
  const storyGraph = buildStoryGraph(content.chapters);
  
  // Check: Gibt es Sackgassen?
  const deadEnds = findDeadEnds(storyGraph);
  for (const deadEnd of deadEnds) {
    issues.push({
      type: 'dead_end',
      location: deadEnd.nodeId,
      description: 'Dieser Pfad führt nirgendwohin'
    });
  }
  
  // Check: Sind alle Endings erreichbar?
  for (const ending of content.endings) {
    const reachable = isEndingReachable(storyGraph, ending);
    if (!reachable) {
      issues.push({
        type: 'unreachable_ending',
        location: ending.id,
        description: 'Dieses Ende ist nicht erreichbar'
      });
    }
  }
  
  // Check: Sind alle Achievements freischaltbar?
  for (const achievement of content.achievements) {
    const achievable = isAchievementAchievable(storyGraph, achievement);
    if (!achievable) {
      issues.push({
        type: 'impossible_achievement',
        location: achievement.id,
        description: 'Dieses Achievement kann nicht erreicht werden'
      });
    }
  }
  
  return {
    passed: issues.length === 0,
    issues,
    graphVisualization: generateGraphVisualization(storyGraph)
  };
}
```

---

## Teil 6: Content-Katalog-Vorschlag

### 6.1 Französisch

| Level | Buch | Gutenberg-ID | Geschätzte Spielzeit | USP |
|-------|------|--------------|---------------------|-----|
| A1-A2 | Le Petit Prince | 2612 | 2-3h | Philosophisch, emotional |
| A2-B1 | Cyrano de Bergerac | 2470 | 4-5h | Romantik, Komödie, Verse |
| B1-B2 | Les Misérables | 135 | 10-15h | Episch, moralisch komplex |
| B1-B2 | Le Comte de Monte-Cristo | 17989 | 8-10h | Rache, Spannung |
| B2-C1 | Madame Bovary | 2413 | 5-6h | Psychologisch, gesellschaftskritisch |
| C1 | Les Trois Mousquetaires | 13951 | 6-8h | Action, Intrigen |

### 6.2 Deutsch

| Level | Buch | Gutenberg-ID | Geschätzte Spielzeit | USP |
|-------|------|--------------|---------------------|-----|
| A1-A2 | Der Struwwelpeter | 24571 | 1-2h | Kurze Geschichten, illustriert |
| A2-B1 | Die Verwandlung | 5200 | 2-3h | Kurz, surreal, philosophisch |
| B1-B2 | Der Prozess | 7849 | 4-5h | Kafkaesk, gesellschaftskritisch |
| B2-C1 | Faust I | 2229 | 5-6h | Klassiker, poetisch |

### 6.3 Spanisch

| Level | Buch | Gutenberg-ID | Geschätzte Spielzeit | USP |
|-------|------|--------------|---------------------|-----|
| A2-B1 | Don Quijote (adaptiert) | 2000 | 6-8h | Komödie, Abenteuer |
| B1-B2 | La Regenta | 54829 | 5-6h | Drama, Gesellschaft |
| B2-C1 | Cien años de soledad* | N/A | N/A | *Noch nicht gemeinfrei |

---

## Teil 7: Roadmap

### Phase 1: Proof of Concept (4 Wochen)
- [ ] Eine vollständige Adaption: "Le Petit Prince"
- [ ] Manuelle Erstellung (kein KI-Pipeline)
- [ ] 3 Kapitel spielbar
- [ ] Voice-Integration
- [ ] Testen mit 10 Nutzern

### Phase 2: Pipeline-Entwicklung (6 Wochen)
- [ ] Automatische Gutenberg-Extraktion
- [ ] KI-basierte Charakter-Analyse
- [ ] KI-basierte Sprach-Adaption
- [ ] Semi-automatische Szenen-Generierung
- [ ] QA-Pipeline

### Phase 3: Content-Produktion (laufend)
- [ ] 2 Stories pro Monat (anfangs)
- [ ] Community-Feedback-Integration
- [ ] Iterative Verbesserung der Pipeline

### Phase 4: Community-Content (langfristig)
- [ ] Story-Editor für Community
- [ ] Moderations-System
- [ ] Revenue-Share für Community-Autoren

---

## Anhang: Ressourcen

### Project Gutenberg
- Hauptseite: https://www.gutenberg.org
- API: https://gutendex.com
- Französische Sammlung: https://www.gutenberg.org/browse/languages/fr

### Urheberrecht
- Werke vor 1928: Gemeinfrei weltweit
- Werke 1928-1977: Prüfung erforderlich
- Übersetzungen: Eigenes Copyright (Originale verwenden!)

### Sprachdidaktik-Referenzen
- CEFR-Deskriptoren: https://www.coe.int/en/web/common-european-framework-reference-languages
- Vokabular-Frequenzlisten: Français Fondamental, Frequency Dictionary of French

---

*Dokumentversion: 1.0*
*Letzte Aktualisierung: {{DATE}}*
