# Story RPG Feature – Technische Dokumentation

## Executive Summary

Dieses Dokument beschreibt die Architektur und Implementierung des "Story RPG"-Features, das das Sprachenlernen fundamental transformiert: von isolierten Übungen zu einer narrativen Erfahrung, in der Sprache das Werkzeug ist, um eine fesselnde Geschichte zu erleben.

**Kernprinzip:** Der Spieler lernt Grammatik nicht, weil die App es verlangt, sondern weil er Pierre nicht verletzen will.

---

## Teil 1: Konzeptionelle Grundlagen

### 1.1 Design-Philosophie

#### First Principles

| Problem | Traditionelle Apps | Unsere Lösung |
|---------|-------------------|---------------|
| Langer Feedback-Loop | Fortschritt nach Wochen sichtbar | Jeder Satz hat sofortige Konsequenz |
| Extrinsische Motivation | "Du solltest lernen" | "Du willst wissen, was passiert" |
| Kontextloses Lernen | Isolierte Sätze | Sprache eingebettet in Beziehungen |
| Keine Stakes | Fehler = rote Markierung | Fehler = NPC-Reaktion + Story-Konsequenz |

#### Die drei Säulen

1. **Immediate Consequence** – Sprachliche Entscheidungen haben sofortige, sichtbare Auswirkungen
2. **Emotional Investment** – NPCs mit Persönlichkeit, Gedächtnis und Beziehungsdynamik
3. **Visible Progression** – Die Sprachwelt des Spielers wächst sichtbar (neue Dialoge, Gebiete, Informationen)

### 1.2 Spieler-Motivation verstehen

#### RPG-Motivationstreiber → Sprachenlernen-Mapping

| RPG-Mechanik | Psychologischer Treiber | Implementation |
|--------------|------------------------|----------------|
| Level & XP | Sichtbarer Fortschritt | Sprachniveau + NPC-Beziehungslevel |
| Loot & Items | Sammeltrieb | Redewendungen, Slang, "seltene Vokabeln" |
| Achievements | Meisterschaft beweisen | Story-Abzeichen, Hardcore-Modi |
| Freischaltbare Gebiete | Exploration | Neue Story-Arcs, NPCs, Sprachregister |
| Charakter-Build | Identität | Sprach-Persona (höflich vs. frech) |
| Hardcore-Modi | Prestige | Perma-Consequences, No-Hint-Runs |

---

## Teil 2: System-Architektur

### 2.1 Architektur-Übersicht

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ Story UI     │  │ Character UI │  │ Player Profile UI    │   │
│  │ (Chat/Scene) │  │ (NPC Cards)  │  │ (Stats, Achievements)│   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      GAME ENGINE LAYER                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ Dialogue     │  │ Consequence  │  │ Progression          │   │
│  │ Manager      │  │ Engine       │  │ Manager              │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ NPC          │  │ Story State  │  │ Achievement          │   │
│  │ Controller   │  │ Machine      │  │ System               │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LANGUAGE ANALYSIS LAYER                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ Grammar      │  │ Register     │  │ Complexity           │   │
│  │ Analyzer     │  │ Detector     │  │ Scorer               │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
│  ┌──────────────┐  ┌──────────────┐                             │
│  │ Error        │  │ Intent       │                             │
│  │ Classifier   │  │ Parser       │                             │
│  └──────────────┘  └──────────────┘                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       LLM LAYER                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Claude API                             │   │
│  │  - NPC Response Generation                                │   │
│  │  - Dynamic Story Branching                                │   │
│  │  - Context-Aware Dialogue                                 │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      DATA LAYER                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ Player       │  │ NPC          │  │ Story                │   │
│  │ State DB     │  │ Memory DB    │  │ State DB             │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Datenmodell

#### 2.2.1 Player State

```typescript
interface PlayerState {
  id: string;
  
  // Sprachprofil
  languageProfile: {
    targetLanguage: Language;
    currentLevel: CEFRLevel; // A1, A2, B1, B2, C1, C2
    
    // Granulare Skill-Tracking
    skills: {
      grammar: GrammarSkills;
      vocabulary: VocabularySkills;
      listening: ListeningSkills;
      pronunciation: PronunciationSkills;
    };
    
    // Bekannte Strukturen (für "Flex-Bonus")
    knownStructures: GrammarStructure[];
  };
  
  // Story-Fortschritt
  storyProgress: {
    currentStoryId: string;
    currentChapterId: string;
    currentSceneId: string;
    completedStories: StoryCompletion[];
  };
  
  // Beziehungen zu NPCs
  relationships: Map<NPCId, RelationshipState>;
  
  // Inventar & Ressourcen
  inventory: {
    currency: number;
    items: Item[];
    collectedPhrases: CollectedPhrase[];
    unlockedSlang: SlangExpression[];
  };
  
  // Achievements & Prestige
  achievements: Achievement[];
  badges: Badge[];
  
  // Spieler-Persona
  persona: {
    communicationStyle: 'formal' | 'casual' | 'playful';
    reputation: Map<FactionId, number>;
  };
}

interface GrammarSkills {
  [structureId: string]: {
    exposure: number;      // Wie oft gesehen
    correctUsage: number;  // Wie oft korrekt verwendet
    lastUsed: Date;
    masteryLevel: 0 | 1 | 2 | 3 | 4 | 5;
  };
}

interface StoryCompletion {
  storyId: string;
  completedAt: Date;
  mode: 'story' | 'immersive' | 'ironman';
  errorCount: number;
  relationshipOutcomes: Map<NPCId, number>;
  unlockedSecrets: string[];
}
```

#### 2.2.2 NPC State

```typescript
interface NPCState {
  id: string;
  
  // Statische Eigenschaften
  profile: {
    name: string;
    role: string;  // "Bäcker", "Polizist", etc.
    personality: PersonalityTraits;
    speechPattern: SpeechPattern;
    backstory: string;
  };
  
  // Dynamisches Gedächtnis
  memory: {
    // Faktisches Gedächtnis
    knownFacts: Fact[];  // Was der NPC über den Spieler weiß
    
    // Episodisches Gedächtnis
    interactions: Interaction[];  // Vergangene Begegnungen
    
    // Beziehungsgedächtnis
    relationshipMilestones: Milestone[];  // Wichtige Momente
    
    // Kurzzeitgedächtnis (aktuelle Session)
    currentSessionContext: string[];
  };
  
  // Beziehungszustand
  relationship: {
    level: number;  // 0-10
    trust: number;  // -5 bis +5
    mood: Mood;     // Aktuelle Stimmung
    lastInteraction: Date;
    
    // Spezielle Flags
    hasSharedSecret: boolean;
    isAlly: boolean;
    isRival: boolean;
  };
  
  // Verfügbare Informationen (abhängig von Beziehungslevel)
  informationTiers: {
    [level: number]: string[];  // Welche Infos bei welchem Level verfügbar
  };
}

interface PersonalityTraits {
  openness: number;        // Wie offen für Fremde
  patience: number;        // Toleranz für Sprachfehler
  formality: number;       // Erwartetes Register
  humor: number;           // Reaktion auf Witze
  gossipiness: number;     // Teilt Informationen über andere
}

interface SpeechPattern {
  baseComplexity: CEFRLevel;
  adaptToPlayer: boolean;  // Passt sich an Spielerlevel an
  usesSlang: boolean;
  usesDialect: string | null;
  speakingSpeed: 'slow' | 'normal' | 'fast';
}

interface Interaction {
  timestamp: Date;
  scene: string;
  summary: string;
  sentiment: 'positive' | 'neutral' | 'negative';
  notableQuotes: string[];  // Memorable Dinge, die der Spieler sagte
  relationshipDelta: number;
}
```

#### 2.2.3 Story State

```typescript
interface StoryState {
  storyId: string;
  
  // Kapitelstruktur
  chapters: Chapter[];
  currentChapter: number;
  
  // Globale Story-Flags
  keyEvents: Map<string, any>;  // z.B. "bribed_waiter": true
  
  // Branching-Zustand
  activeBranches: string[];
  closedBranches: string[];
  
  // Cliffhanger-State
  activeCliffhanger: Cliffhanger | null;
  
  // Zeitlicher Zustand
  inGameTime: Date;
  sessionCount: number;
}

interface Chapter {
  id: string;
  title: string;
  scenes: Scene[];
  requiredLevel: CEFRLevel;
  
  // Lernziele dieses Kapitels
  learningObjectives: {
    grammar: GrammarStructure[];
    vocabulary: VocabularyTheme[];
    functions: CommunicativeFunction[];  // z.B. "sich beschweren", "verhandeln"
  };
  
  // Mögliche Enden
  possibleOutcomes: ChapterOutcome[];
}

interface Scene {
  id: string;
  location: string;
  npcsPresent: NPCId[];
  
  // Szenen-Setup
  setup: {
    description: string;
    mood: string;
    timeConstraint: number | null;  // Sekunden, falls zeitbegrenzt
  };
  
  // Ziele
  objectives: SceneObjective[];
  
  // Mögliche Konsequenzen
  consequenceTree: ConsequenceNode[];
}

interface ConsequenceNode {
  trigger: ConsequenceTrigger;
  effects: Effect[];
  nextNodes: ConsequenceNode[];
}

interface ConsequenceTrigger {
  type: 'grammar_error' | 'register_mismatch' | 'keyword_used' | 
        'relationship_threshold' | 'time_expired' | 'player_choice';
  condition: any;  // Spezifische Bedingung je nach Typ
}

interface Effect {
  type: 'relationship_change' | 'story_flag' | 'item_change' | 
        'npc_mood_change' | 'unlock_information' | 'branch_story';
  target: string;
  value: any;
}
```

---

## Teil 3: Kernmechaniken

### 3.1 Sprachanalyse-System

#### 3.1.1 Input-Analyse-Pipeline

```typescript
interface LanguageAnalysisResult {
  // Grammatik-Analyse
  grammar: {
    isCorrect: boolean;
    errors: GrammarError[];
    usedStructures: GrammarStructure[];
    complexityScore: number;  // 0-100
  };
  
  // Register-Analyse
  register: {
    detected: 'formal' | 'informal' | 'casual' | 'vulgar';
    appropriateForContext: boolean;
    mismatchSeverity: 'none' | 'minor' | 'major' | 'critical';
  };
  
  // Semantik-Analyse
  semantics: {
    intent: string;  // Was will der Spieler erreichen
    sentiment: 'positive' | 'neutral' | 'negative';
    keyEntities: string[];
    potentialMisunderstandings: Misunderstanding[];
  };
  
  // Kreativitäts-Bonus
  style: {
    usedOptionalComplexity: boolean;  // Strukturen über Mindestlevel
    creativePhrasing: boolean;
    humorAttempt: boolean;
    idiomUsage: boolean;
  };
}

interface GrammarError {
  errorType: string;  // z.B. "verb_conjugation", "gender_agreement"
  location: { start: number; end: number };
  expected: string;
  received: string;
  severity: 'minor' | 'major' | 'critical';
  
  // Konsequenz-Relevanz
  causesMisunderstanding: boolean;
  affectsRelationship: boolean;
  triggersBranch: boolean;
}

interface Misunderstanding {
  playerMeant: string;
  npcUnderstands: string;
  isFunny: boolean;
  isOffensive: boolean;
  isPlotRelevant: boolean;
}
```

#### 3.1.2 Fehler-Konsequenz-Mapping

```typescript
const ERROR_CONSEQUENCE_MAP = {
  // Grammatikfehler → NPC-Reaktionen
  verb_conjugation: {
    minor: {
      npcReaction: "confused_but_understanding",
      relationshipImpact: 0,
      triggerInfobox: true
    },
    major: {
      npcReaction: "asks_for_clarification",
      relationshipImpact: 0,
      triggerInfobox: true
    },
    critical: {
      npcReaction: "misunderstands_completely",
      relationshipImpact: -1,
      triggerInfobox: true,
      mayBranchStory: true
    }
  },
  
  // Register-Fehler → soziale Konsequenzen
  register_mismatch: {
    too_formal: {
      npcReaction: "amused_or_distant",
      relationshipImpact: 0,
      socialCue: "NPC lockert Ton auf als Hinweis"
    },
    too_informal: {
      npcReaction: "offended_or_correcting",
      relationshipImpact: -1,
      socialCue: "NPC korrigiert höflich"
    },
    vulgar_in_formal: {
      npcReaction: "shocked",
      relationshipImpact: -3,
      mayBranchStory: true
    }
  },
  
  // Semantische Fehler → Story-Konsequenzen
  false_friends: {
    "excité": {
      playerMeant: "excited",
      npcUnderstands: "sexually aroused",
      reaction: "awkward_silence",
      relationshipImpact: -2,
      infoboxContent: "excite_vs_enthousiaste"
    },
    "préservatif": {
      playerMeant: "preservative",
      npcUnderstands: "condom",
      reaction: "very_confused",
      relationshipImpact: 0,
      infoboxContent: "preservatif_vs_conservateur"
    }
  }
};
```

### 3.2 NPC-Reaktions-System

#### 3.2.1 Reaktions-Generierung

```typescript
interface NPCResponseContext {
  // Spieler-Input
  playerInput: string;
  analysisResult: LanguageAnalysisResult;
  
  // NPC-Kontext
  npc: NPCState;
  currentMood: Mood;
  relationshipLevel: number;
  
  // Szenen-Kontext
  scene: Scene;
  storyFlags: Map<string, any>;
  
  // Sprachlevel-Anpassung
  playerLevel: CEFRLevel;
  shouldAdapt: boolean;
}

async function generateNPCResponse(
  context: NPCResponseContext
): Promise<NPCResponse> {
  
  const systemPrompt = buildNPCSystemPrompt(context);
  
  const response = await claude.messages.create({
    model: "claude-sonnet-4-20250514",
    system: systemPrompt,
    messages: [
      {
        role: "user",
        content: buildNPCPrompt(context)
      }
    ]
  });
  
  return parseNPCResponse(response);
}

function buildNPCSystemPrompt(context: NPCResponseContext): string {
  return `
Du bist ${context.npc.profile.name}, ${context.npc.profile.role}.

PERSÖNLICHKEIT:
${JSON.stringify(context.npc.profile.personality)}

SPRECHMUSTER:
- Komplexität: ${context.npc.profile.speechPattern.baseComplexity}
- Anpassen an Spieler: ${context.npc.profile.speechPattern.adaptToPlayer}
- Verwendet Slang: ${context.npc.profile.speechPattern.usesSlang}
- Sprechgeschwindigkeit: ${context.npc.profile.speechPattern.speakingSpeed}

BEZIEHUNG ZUM SPIELER:
- Level: ${context.relationshipLevel}/10
- Trust: ${context.npc.relationship.trust}
- Letzte Interaktion: ${context.npc.memory.interactions.slice(-3).map(i => i.summary).join('; ')}
- Wichtige Erinnerungen: ${context.npc.memory.relationshipMilestones.map(m => m.description).join('; ')}

AKTUELLE STIMMUNG: ${context.currentMood}

SPIELER-SPRACHLEVEL: ${context.playerLevel}
${context.shouldAdapt ? 'Passe deine Sprache an dieses Level an.' : 'Sprich natürlich.'}

ANWEISUNGEN:
1. Reagiere authentisch auf den Spieler basierend auf deiner Persönlichkeit und eurer Geschichte
2. Wenn der Spieler einen Sprachfehler gemacht hat, reagiere natürlich darauf (nicht als Lehrer)
3. Deine Antwort beeinflusst die Story - sei konsistent mit deinem Charakter
4. Gib bei relevantem Beziehungslevel (${context.relationshipLevel}+) tiefere Informationen preis
  `.trim();
}
```

#### 3.2.2 Sprachlevel-adaptive Dialoge

```typescript
interface AdaptiveDialogueConfig {
  // Basis-Nachricht, die der NPC vermitteln will
  coreMessage: string;
  
  // Varianten nach Spielerlevel
  variants: {
    A1: {
      text: string;
      speakingSpeed: 'slow';
      vocabulary: 'basic';
      sentenceStructure: 'simple';
    };
    A2: {
      text: string;
      speakingSpeed: 'slow';
      vocabulary: 'elementary';
      sentenceStructure: 'compound';
    };
    B1: {
      text: string;
      speakingSpeed: 'normal';
      vocabulary: 'intermediate';
      sentenceStructure: 'complex';
    };
    B2: {
      text: string;
      speakingSpeed: 'normal';
      vocabulary: 'upper_intermediate';
      sentenceStructure: 'varied';
      includesIdioms: true;
    };
    C1: {
      text: string;
      speakingSpeed: 'fast';
      vocabulary: 'advanced';
      sentenceStructure: 'sophisticated';
      includesSlang: true;
      includesSubtext: true;
    };
  };
  
  // Bonus-Informationen nur für höhere Level
  bonusInfo: {
    requiredLevel: CEFRLevel;
    content: string;
  }[];
}

// Beispiel: Pierre der Bäcker gibt eine Wegbeschreibung
const pierreDirectionsExample: AdaptiveDialogueConfig = {
  coreMessage: "Der Bahnhof ist 10 Minuten zu Fuß",
  variants: {
    A1: {
      text: "La gare? Tout droit. Dix minutes.",
      speakingSpeed: 'slow',
      vocabulary: 'basic',
      sentenceStructure: 'simple'
    },
    B1: {
      text: "La gare est à dix minutes à pied. Vous prenez la première rue à gauche, puis tout droit jusqu'au bout.",
      speakingSpeed: 'normal',
      vocabulary: 'intermediate',
      sentenceStructure: 'complex'
    },
    C1: {
      text: "Ah, la gare Saint-Lazare! T'as qu'à descendre la rue Lepic jusqu'à Blanche, tu peux pas la louper. Fais gaffe, y'a des travaux en ce moment, ça rallonge un peu.",
      speakingSpeed: 'fast',
      vocabulary: 'advanced',
      sentenceStructure: 'sophisticated',
      includesSlang: true,
      includesSubtext: true
    }
  },
  bonusInfo: [
    {
      requiredLevel: 'B2',
      content: "Entre nous, le petit café à côté de la gare, c'est là que les flics du quartier se retrouvent. Si t'as besoin d'infos..."
    }
  ]
};
```

### 3.3 Konsequenz-Engine

#### 3.3.1 Entscheidungsbaum-Struktur

```typescript
interface DecisionTree {
  root: DecisionNode;
}

interface DecisionNode {
  id: string;
  type: 'choice' | 'language_check' | 'relationship_check' | 'random';
  
  // Für type: 'choice'
  choices?: {
    id: string;
    description: string;  // Was der Spieler sieht (optional)
    requiredInput?: string;  // Keyword oder Phrase, die getriggert wird
    consequences: Consequence[];
    nextNode: string | null;
  }[];
  
  // Für type: 'language_check'
  languageCheck?: {
    checkType: 'grammar' | 'register' | 'vocabulary';
    target: string;  // z.B. "subjonctif" oder "formal_register"
    onSuccess: { consequences: Consequence[]; nextNode: string };
    onFailure: { consequences: Consequence[]; nextNode: string };
  };
  
  // Für type: 'relationship_check'
  relationshipCheck?: {
    npcId: string;
    threshold: number;
    comparison: 'gte' | 'lte' | 'eq';
    onTrue: { consequences: Consequence[]; nextNode: string };
    onFalse: { consequences: Consequence[]; nextNode: string };
  };
}

interface Consequence {
  type: ConsequenceType;
  immediate: boolean;  // Sofort sichtbar oder verzögert
  data: any;
}

type ConsequenceType = 
  | 'relationship_change'
  | 'set_story_flag'
  | 'unlock_scene'
  | 'lock_scene'
  | 'add_item'
  | 'remove_item'
  | 'npc_remembers'
  | 'trigger_event'
  | 'change_npc_mood'
  | 'unlock_information';
```

#### 3.3.2 Konsequenz-Beispiel: Das Café-Szenario

```typescript
const cafeScenario: DecisionTree = {
  root: {
    id: "cafe_secret_discovery",
    type: "choice",
    choices: [
      {
        id: "eavesdrop",
        description: "Das Paar am Nebentisch belauschen",
        consequences: [
          {
            type: "set_story_flag",
            immediate: false,
            data: { key: "eavesdropped_couple", value: true }
          },
          {
            type: "unlock_information",
            immediate: true,
            data: { infoId: "secret_meeting_location" }
          }
        ],
        nextNode: "waiter_notices"
      },
      {
        id: "bribe_waiter",
        requiredInput: "contains:argent|payer|euros",
        consequences: [
          {
            type: "remove_item",
            immediate: true,
            data: { itemType: "currency", amount: 20 }
          },
          {
            type: "relationship_change",
            immediate: false,
            data: { npcId: "waiter_marc", delta: +3 }
          },
          {
            type: "set_story_flag",
            immediate: false,
            data: { key: "bribed_waiter", value: true }
          },
          {
            type: "npc_remembers",
            immediate: false,
            data: { 
              npcId: "waiter_marc", 
              memory: "Der Spieler hat mich bestochen. Er scheint Ressourcen zu haben und ist bereit, sie einzusetzen."
            }
          }
        ],
        nextNode: "waiter_ally_path"
      }
    ]
  },
  
  // Wenn belauscht: Kellner wird misstrauisch
  "waiter_notices": {
    id: "waiter_notices",
    type: "relationship_check",
    relationshipCheck: {
      npcId: "waiter_marc",
      threshold: 3,
      comparison: "gte",
      onTrue: {
        consequences: [
          {
            type: "npc_remembers",
            immediate: false,
            data: {
              npcId: "waiter_marc",
              memory: "Ich habe gesehen, wie der Spieler die Gäste belauscht hat. Seltsam, aber vielleicht hat er gute Gründe."
            }
          }
        ],
        nextNode: "continue_story"
      },
      onFalse: {
        consequences: [
          {
            type: "relationship_change",
            immediate: false,
            data: { npcId: "waiter_marc", delta: -2 }
          },
          {
            type: "set_story_flag",
            immediate: false,
            data: { key: "waiter_suspicious", value: true }
          },
          {
            type: "npc_remembers",
            immediate: false,
            data: {
              npcId: "waiter_marc",
              memory: "Der Spieler hat meine Gäste belauscht. Ich traue ihm nicht."
            }
          }
        ],
        nextNode: "waiter_hostile_path"
      }
    }
  }
};
```

### 3.4 Feedback-System (Infobox)

#### 3.4.1 Infobox-Design

```typescript
interface Infobox {
  id: string;
  
  // Trigger-Kontext
  trigger: {
    errorType: string;
    playerSaid: string;
    npcReaction: string;
  };
  
  // Inhalt
  content: {
    title: string;  // z.B. "Was ist passiert?"
    
    // Erklärung in drei Teilen
    whatHappened: string;   // "Du hast X gesagt, Pierre versteht Y"
    whyItMatters: string;   // "Im Französischen bedeutet X..."
    betterAlternative: string;  // "Nächstes Mal könntest du sagen..."
    
    // Optionale Vertiefung
    grammarRule?: {
      name: string;
      explanation: string;
      examples: { wrong: string; right: string }[];
      linkToGrammarMode: string;  // Deep-Link zum Grammatik-Training
    };
  };
  
  // Präsentation
  presentation: {
    tone: 'friendly' | 'humorous' | 'neutral';
    showImmediately: boolean;
    dismissable: boolean;
    saveToCollection: boolean;  // Zum späteren Nachschlagen
  };
}

// Beispiel: "Je suis excité" Fehler
const exciteInfobox: Infobox = {
  id: "false_friend_excite",
  trigger: {
    errorType: "false_friend",
    playerSaid: "Je suis excité",
    npcReaction: "Pierre sieht dich mit hochgezogener Augenbraue an und räuspert sich."
  },
  content: {
    title: "Ups – Falsche Freunde!",
    whatHappened: "Du wolltest sagen, dass du aufgeregt bist. Pierre hat verstanden, dass du... sexuell erregt bist.",
    whyItMatters: "'Excité' im Französischen hat primär eine sexuelle Konnotation – ganz anders als 'excited' im Englischen.",
    betterAlternative: "Sag stattdessen: 'Je suis enthousiaste!' oder 'J'ai hâte!' (Ich kann es kaum erwarten!)",
    grammarRule: {
      name: "Falsche Freunde (Faux Amis)",
      explanation: "Wörter, die ähnlich aussehen wie im Deutschen oder Englischen, aber etwas völlig anderes bedeuten.",
      examples: [
        { wrong: "Je suis excité", right: "Je suis enthousiaste" },
        { wrong: "un préservatif", right: "un conservateur" },
        { wrong: "assister à", right: "aider / participer à" }
      ],
      linkToGrammarMode: "/grammar/faux-amis"
    }
  },
  presentation: {
    tone: 'humorous',
    showImmediately: false,  // Erst nach NPC-Reaktion
    dismissable: true,
    saveToCollection: true
  }
};
```

#### 3.4.2 Infobox-Trigger-Logik

```typescript
async function processPlayerInputAndTriggerInfobox(
  input: string,
  context: SceneContext
): Promise<{ npcResponse: NPCResponse; infobox: Infobox | null }> {
  
  // 1. Sprache analysieren
  const analysis = await analyzeLanguage(input, context.targetLanguage);
  
  // 2. NPC-Reaktion generieren (berücksichtigt Fehler)
  const npcResponse = await generateNPCResponse({
    playerInput: input,
    analysisResult: analysis,
    npc: context.currentNPC,
    scene: context.currentScene,
    playerLevel: context.playerLevel
  });
  
  // 3. Infobox triggern, falls relevant
  let infobox: Infobox | null = null;
  
  if (analysis.grammar.errors.length > 0) {
    const mostRelevantError = selectMostRelevantError(analysis.grammar.errors);
    infobox = await generateInfobox(mostRelevantError, input, npcResponse);
  }
  
  if (analysis.register.mismatchSeverity !== 'none') {
    infobox = await generateRegisterInfobox(
      analysis.register,
      input,
      context.currentNPC,
      npcResponse
    );
  }
  
  if (analysis.semantics.potentialMisunderstandings.length > 0) {
    const misunderstanding = analysis.semantics.potentialMisunderstandings[0];
    if (misunderstanding.isPlotRelevant || misunderstanding.isOffensive) {
      infobox = await generateMisunderstandingInfobox(misunderstanding, npcResponse);
    }
  }
  
  return { npcResponse, infobox };
}

function selectMostRelevantError(errors: GrammarError[]): GrammarError {
  // Priorisierung: Story-relevant > Beziehungsrelevant > Schweregrad
  return errors.sort((a, b) => {
    if (a.triggersBranch && !b.triggersBranch) return -1;
    if (a.affectsRelationship && !b.affectsRelationship) return -1;
    const severityOrder = { critical: 0, major: 1, minor: 2 };
    return severityOrder[a.severity] - severityOrder[b.severity];
  })[0];
}
```

---

## Teil 4: Progressions-System

### 4.1 Spieler-Fortschritt

#### 4.1.1 Sprachlevel-Progression

```typescript
interface LanguageProgressionSystem {
  // Level-Grenzen
  levelThresholds: {
    A1: { minScore: 0, maxScore: 100 };
    A2: { minScore: 101, maxScore: 250 };
    B1: { minScore: 251, maxScore: 500 };
    B2: { minScore: 501, maxScore: 800 };
    C1: { minScore: 801, maxScore: 1200 };
    C2: { minScore: 1201, maxScore: Infinity };
  };
  
  // Wie Punkte verdient werden
  scoringRules: {
    // Korrekte Nutzung von Grammatikstrukturen
    grammarUsage: {
      knownStructure: 1;      // Bekannte Struktur korrekt verwendet
      newStructure: 5;        // Neue Struktur zum ersten Mal korrekt
      complexStructure: 10;   // Struktur über aktuellem Level
    };
    
    // Interaktions-Qualität
    interaction: {
      successfulExchange: 2;  // NPC versteht und reagiert positiv
      relationshipGain: 5;    // Beziehungslevel erhöht
      secretUnlocked: 15;     // Geheime Info freigeschaltet
    };
    
    // Story-Fortschritt
    story: {
      sceneCompleted: 10;
      chapterCompleted: 50;
      storyCompleted: 200;
      hardcoreModeBonus: 100; // Zusatz für Ironman-Modus
    };
    
    // Flex-Bonus (freiwillige Komplexität)
    flexBonus: {
      usedSubjonctif: 8;      // Wenn nicht nötig, aber korrekt
      usedIdiomatic: 5;       // Redewendung eingesetzt
      usedHumor: 3;           // NPC hat gelacht
    };
  };
}
```

#### 4.1.2 Beziehungs-Progression

```typescript
interface RelationshipProgression {
  levels: {
    0: { name: "Fremder"; perks: [] };
    1: { name: "Bekannter"; perks: ["basic_greetings"] };
    2: { name: "Kunde"; perks: ["small_discounts", "small_talk"] };
    3: { name: "Stammkunde"; perks: ["remembers_preferences", "local_tips"] };
    4: { name: "Freund"; perks: ["personal_stories", "favors"] };
    5: { name: "Vertrauter"; perks: ["secrets", "network_access"] };
  };
  
  // Wie Beziehungspunkte gesammelt werden
  relationshipGain: {
    correctRegister: 1;
    rememberedDetail: 2;      // Spieler erwähnt etwas aus früherer Konversation
    helpedNPC: 3;
    sharedLaugh: 2;
    defendedNPC: 5;
    consistentPositiveInteraction: 1;  // Pro Session
  };
  
  relationshipLoss: {
    wrongRegister: -1;
    forgotImportantDetail: -2;
    insultedNPC: -3;
    betrayedTrust: -5;
    ignoredNPC: -1;  // Zu lange nicht interagiert
  };
}
```

### 4.2 Achievement-System

```typescript
interface Achievement {
  id: string;
  name: string;
  description: string;
  icon: string;
  
  // Freischaltbedingungen
  criteria: AchievementCriteria;
  
  // Sichtbarkeit
  visibility: 'visible' | 'hidden' | 'secret';  // Secret = existiert erst nach Freischaltung
  
  // Schwierigkeitsgrad
  difficulty: 'bronze' | 'silver' | 'gold' | 'platinum';
  
  // Belohnungen
  rewards: {
    xpBonus: number;
    unlocksCosmetic?: string;
    unlocksStory?: string;
  };
}

const ACHIEVEMENTS: Achievement[] = [
  // Story-Achievements
  {
    id: "first_friend",
    name: "Erster Freund",
    description: "Erreiche Beziehungslevel 4 mit einem NPC",
    icon: "🤝",
    criteria: { type: "relationship_level", threshold: 4, count: 1 },
    visibility: 'visible',
    difficulty: 'bronze',
    rewards: { xpBonus: 50 }
  },
  {
    id: "social_butterfly",
    name: "Sozialer Schmetterling",
    description: "Erreiche Beziehungslevel 3+ mit 10 verschiedenen NPCs",
    icon: "🦋",
    criteria: { type: "relationship_level", threshold: 3, count: 10 },
    visibility: 'visible',
    difficulty: 'gold',
    rewards: { xpBonus: 200, unlocksCosmetic: "golden_chat_border" }
  },
  
  // Sprach-Achievements
  {
    id: "grammar_wizard",
    name: "Grammatik-Zauberer",
    description: "Verwende den Subjonctif 50x korrekt",
    icon: "🧙",
    criteria: { type: "grammar_usage", structure: "subjonctif", count: 50 },
    visibility: 'visible',
    difficulty: 'silver',
    rewards: { xpBonus: 100 }
  },
  {
    id: "false_friend_survivor",
    name: "Falsche-Freunde-Überlebender",
    description: "Lerne alle 20 häufigen False Friends durch Fehler",
    icon: "💀",
    criteria: { type: "learned_from_mistakes", category: "false_friends", count: 20 },
    visibility: 'hidden',
    difficulty: 'silver',
    rewards: { xpBonus: 75 }
  },
  
  // Hardcore-Achievements
  {
    id: "ironman_negotiation",
    name: "Stahlerne Verhandlung",
    description: "Schließe 'Die Verhandlung' im Ironman-Modus ab",
    icon: "⚔️",
    criteria: { type: "story_completion", storyId: "negotiation", mode: "ironman" },
    visibility: 'visible',
    difficulty: 'platinum',
    rewards: { xpBonus: 500, unlocksStory: "secret_epilogue" }
  },
  {
    id: "perfect_interrogation",
    name: "Perfektes Verhör",
    description: "Überstehe 'Das Verhör' ohne einen Grammatikfehler",
    icon: "🎯",
    criteria: { type: "story_completion", storyId: "interrogation", errorCount: 0 },
    visibility: 'secret',
    difficulty: 'platinum',
    rewards: { xpBonus: 300, unlocksCosmetic: "detective_badge" }
  },
  
  // Geheime Achievements
  {
    id: "pierre_secret_recipe",
    name: "Das Geheimrezept",
    description: "Überzeuge Pierre, dir sein Familienrezept zu verraten",
    icon: "🥖",
    criteria: { type: "secret_unlocked", secretId: "pierre_recipe" },
    visibility: 'secret',
    difficulty: 'gold',
    rewards: { xpBonus: 150 }
  }
];
```

### 4.3 Story-Freischaltung

```typescript
interface StoryUnlockSystem {
  stories: {
    // Starter-Stories (immer verfügbar)
    starter: Story[];
    
    // Level-basierte Freischaltung
    levelGated: {
      A2: Story[];
      B1: Story[];
      B2: Story[];
      C1: Story[];
    };
    
    // Beziehungs-basierte Freischaltung
    relationshipGated: {
      [npcId: string]: {
        requiredLevel: number;
        unlocksStory: Story;
      };
    };
    
    // Story-Flag-basierte Freischaltung
    flagGated: {
      [flag: string]: Story;
    };
    
    // Achievement-basierte Freischaltung
    achievementGated: {
      [achievementId: string]: Story;
    };
  };
}

// Beispiel-Konfiguration
const STORY_UNLOCK_CONFIG: StoryUnlockSystem = {
  stories: {
    starter: [
      { id: "arrival_paris", title: "Ankunft in Paris", level: "A1" },
      { id: "lost_luggage", title: "Der verlorene Koffer", level: "A1" }
    ],
    
    levelGated: {
      A2: [
        { id: "cafe_mystery", title: "Das Geheimnis im Café", level: "A2" }
      ],
      B1: [
        { id: "the_negotiation", title: "Die Verhandlung", level: "B1" },
        { id: "the_argument", title: "Der Streit", level: "B1" }
      ],
      B2: [
        { id: "the_interrogation", title: "Das Verhör", level: "B2" }
      ]
    },
    
    relationshipGated: {
      "pierre_baker": {
        requiredLevel: 5,
        unlocksStory: { 
          id: "pierre_backstory", 
          title: "Pierres Vergangenheit", 
          level: "B1" 
        }
      },
      "inspector_dubois": {
        requiredLevel: 4,
        unlocksStory: { 
          id: "cold_case", 
          title: "Der kalte Fall", 
          level: "B2" 
        }
      }
    },
    
    flagGated: {
      "discovered_secret_society": {
        id: "secret_society",
        title: "Die Geheimgesellschaft",
        level: "C1"
      }
    },
    
    achievementGated: {
      "ironman_negotiation": {
        id: "secret_epilogue",
        title: "Epilog: Die Wahrheit",
        level: "B2"
      }
    }
  }
};
```

---

## Teil 5: Story-Authoring

### 5.1 Story-Definition-Format

```typescript
interface StoryDefinition {
  metadata: {
    id: string;
    title: string;
    description: string;
    targetLevel: CEFRLevel;
    estimatedDuration: number;  // Minuten
    themes: string[];
    learningObjectives: LearningObjective[];
  };
  
  npcs: NPCDefinition[];
  
  chapters: ChapterDefinition[];
  
  // Globale Variablen für diese Story
  variables: {
    [key: string]: {
      type: 'boolean' | 'number' | 'string';
      initialValue: any;
    };
  };
  
  // Endings
  endings: {
    id: string;
    name: string;
    description: string;
    conditions: Condition[];
    epilogue: string;
  }[];
}

interface ChapterDefinition {
  id: string;
  title: string;
  unlockCondition: Condition | null;
  
  scenes: SceneDefinition[];
  
  cliffhanger?: {
    text: string;
    hook: string;  // Welche Frage soll der Spieler haben
    nextChapterTeaser: string;
  };
}

interface SceneDefinition {
  id: string;
  location: string;
  description: string;
  
  // NPCs in der Szene
  npcsPresent: string[];
  
  // Szenen-Ziele
  objectives: {
    id: string;
    description: string;
    type: 'talk_to' | 'obtain_info' | 'convince' | 'survive' | 'custom';
    target: any;
    optional: boolean;
  }[];
  
  // Initiales Setup
  setup: {
    narratorText: string;
    initialNPCState: { [npcId: string]: { mood: Mood; initialLine: string } };
  };
  
  // Sprachliche Fokuspunkte
  languageFocus: {
    grammar: string[];      // z.B. ["passé_composé", "négation"]
    vocabulary: string[];   // z.B. ["food", "directions"]
    functions: string[];    // z.B. ["ordering", "complaining"]
  };
  
  // Konsequenz-Definitionen
  consequences: ConsequenceDefinition[];
  
  // Ende-Bedingungen
  endConditions: {
    condition: Condition;
    nextScene: string | null;
    transitionText: string;
  }[];
}
```

### 5.2 Beispiel-Story: "Der verlorene Koffer"

```yaml
# story_lost_luggage.yaml

metadata:
  id: "lost_luggage"
  title: "Der verlorene Koffer"
  description: "Du kommst in Paris an, aber dein Koffer ist verschwunden. Finde ihn – und entdecke dabei ein Geheimnis."
  targetLevel: "A1-A2"
  estimatedDuration: 45
  themes: ["travel", "mystery", "relationships"]
  learningObjectives:
    - grammar: "présent", "passé_composé_basics"
    - vocabulary: "train_station", "luggage", "descriptions"
    - functions: "asking_for_help", "describing_objects", "expressing_frustration"

npcs:
  - id: "station_master_henri"
    name: "Henri"
    role: "Bahnhofsvorsteher"
    personality:
      patience: 0.8
      formality: 0.7
      helpfulness: 0.6
    speechPattern:
      baseComplexity: "A2"
      adaptToPlayer: true
    backstory: "Henri arbeitet seit 30 Jahren hier. Er hat alles gesehen."
    
  - id: "mysterious_woman_claire"
    name: "Claire"
    role: "Mysteriöse Reisende"
    personality:
      patience: 0.5
      formality: 0.3
      secretiveness: 0.9
    speechPattern:
      baseComplexity: "B1"
      adaptToPlayer: false
    backstory: "Claire scheint nervös. Sie trägt einen Koffer, der deinem sehr ähnlich sieht..."

variables:
  has_found_henri: { type: boolean, initialValue: false }
  knows_about_claire: { type: boolean, initialValue: false }
  claire_trust_level: { type: number, initialValue: 0 }
  discovered_diary: { type: boolean, initialValue: false }

chapters:
  - id: "chapter_1"
    title: "Ankunft"
    scenes:
      - id: "scene_platform"
        location: "Bahnsteig 7, Gare du Nord"
        description: "Der Zug ist angekommen. Menschen strömen an dir vorbei."
        
        setup:
          narratorText: |
            Der Zug hält. Du steigst aus und atmest die Pariser Luft ein.
            Dann merkst du es: Dein Koffer ist nicht da. Er muss noch im Zug sein – oder jemand hat ihn genommen.
          
        objectives:
          - id: "find_help"
            description: "Finde jemanden, der dir helfen kann"
            type: "talk_to"
            target: "station_master_henri"
            optional: false
            
        languageFocus:
          grammar: ["présent", "où_est"]
          vocabulary: ["train", "bagage", "aide"]
          functions: ["asking_for_help", "describing_location"]
          
        consequences:
          # Wenn der Spieler auf Claire trifft (optional)
          - trigger:
              type: "player_explores"
              condition: "mentions:femme|dame|quelqu'un"
            effects:
              - type: "set_variable"
                target: "knows_about_claire"
                value: true
              - type: "spawn_npc"
                target: "mysterious_woman_claire"
              - type: "narrator"
                text: "Du bemerkst eine Frau mit einem Koffer, der deinem sehr ähnlich sieht..."
                
          # Wenn der Spieler unhöflich zu Henri ist
          - trigger:
              type: "register_mismatch"
              condition: "too_informal"
              npc: "station_master_henri"
            effects:
              - type: "relationship_change"
                target: "station_master_henri"
                value: -1
              - type: "npc_dialogue"
                target: "station_master_henri"
                text: "On se vouvoie ici, jeune homme."
              - type: "infobox"
                content: "vouvoiement_reminder"
                
        endConditions:
          - condition: { variable: "has_found_henri", equals: true }
            nextScene: "scene_lost_and_found"
            transitionText: "Henri führt dich zum Fundbüro."
            
    cliffhanger:
      text: "Du öffnest den Koffer. Es ist deiner – aber da ist etwas, das dir nicht gehört. Ein Tagebuch. In einer Handschrift, die du nicht kennst."
      hook: "Wessen Tagebuch ist das? Und wie ist es in deinen Koffer gekommen?"
      nextChapterTeaser: "Im nächsten Kapitel: Das Tagebuch"

  - id: "chapter_2"
    title: "Das Tagebuch"
    unlockCondition: { chapter: "chapter_1", completed: true }
    scenes:
      - id: "scene_reading_diary"
        location: "Dein Hotelzimmer"
        description: "Du sitzt auf dem Bett und betrachtest das fremde Tagebuch."
        
        setup:
          narratorText: |
            Das Tagebuch ist alt, die Seiten vergilbt. Die Einträge sind auf Französisch.
            Die ersten Seiten sind einfach zu verstehen. Aber je weiter du blätterst, desto komplexer wird die Sprache...
            
        languageFocus:
          grammar: ["passé_composé", "imparfait_introduction"]
          vocabulary: ["emotions", "time_expressions", "secrets"]
          functions: ["reading_comprehension", "narrating_past"]
          
        # Mechanik: Teile des Tagebuchs sind je nach Spielerlevel lesbar
        specialMechanic:
          type: "progressive_reveal"
          content:
            A1: "Die ersten 3 Einträge"
            A2: "Einträge 4-7"
            B1: "Einträge 8-12 (das eigentliche Geheimnis)"
          visualEffect: "blur_unreachable_text"
          motivationText: "Diese Seite ist zu komplex für dich. Verbessere dein Französisch, um weiterzulesen."
```

---

## Teil 6: Technische Implementierung

### 6.1 API-Endpunkte

```typescript
// Story-Management
POST   /api/stories/{storyId}/start
GET    /api/stories/{storyId}/state
POST   /api/stories/{storyId}/scenes/{sceneId}/input
GET    /api/stories/{storyId}/chapters/{chapterId}/unlock-status

// NPC-Interaktion
POST   /api/npcs/{npcId}/dialogue
GET    /api/npcs/{npcId}/relationship
GET    /api/npcs/{npcId}/memory

// Spieler-Fortschritt
GET    /api/player/profile
GET    /api/player/achievements
GET    /api/player/language-stats
POST   /api/player/collected-phrases

// Sprach-Analyse
POST   /api/language/analyze
GET    /api/language/grammar-rules/{ruleId}
```

### 6.2 Hauptinteraktions-Flow

```typescript
// POST /api/stories/{storyId}/scenes/{sceneId}/input

interface SceneInputRequest {
  playerInput: string;
  targetNpcId?: string;
  actionType: 'speak' | 'action' | 'thought';
  metadata?: {
    inputMethod: 'text' | 'voice';
    responseTime: number;  // ms
  };
}

interface SceneInputResponse {
  // NPC-Reaktion
  npcResponse?: {
    npcId: string;
    text: string;
    emotion: Emotion;
    audioUrl?: string;  // TTS
  };
  
  // Erzähler-Text (falls relevant)
  narratorText?: string;
  
  // Feedback
  infobox?: Infobox;
  
  // Konsequenzen
  consequences: {
    relationshipChanges: { npcId: string; delta: number; newLevel: number }[];
    flagsSet: { key: string; value: any }[];
    itemsGained: Item[];
    itemsLost: Item[];
    achievementsUnlocked: Achievement[];
  };
  
  // Spielwelt-Updates
  worldUpdates: {
    npcsAppeared: string[];
    npcsLeft: string[];
    newLocationsUnlocked: string[];
  };
  
  // Szenen-Status
  sceneStatus: {
    objectivesCompleted: string[];
    objectivesRemaining: string[];
    canEnd: boolean;
    endOptions?: { id: string; description: string }[];
  };
  
  // XP & Fortschritt
  progression: {
    xpGained: number;
    newTotalXp: number;
    levelProgress: { current: number; toNextLevel: number };
    grammarPracticed: { structureId: string; correct: boolean }[];
  };
}
```

### 6.3 LLM-Prompt-Templates

```typescript
// NPC-Response-Generation

const NPC_RESPONSE_TEMPLATE = `
Du bist {{npc.name}}, {{npc.role}} in {{story.setting}}.

# CHARAKTER
{{npc.personality_description}}

# DEINE GESCHICHTE MIT DEM SPIELER
{{#each npc.memory.interactions}}
- {{this.timestamp}}: {{this.summary}} ({{this.sentiment}})
{{/each}}

# AKTUELLE SITUATION
Ort: {{scene.location}}
Deine Stimmung: {{npc.currentMood}}
Beziehungslevel: {{npc.relationshipLevel}}/10

# SPIELER-INPUT
Der Spieler sagt: "{{playerInput}}"

# SPRACHANALYSE
{{#if analysis.hasErrors}}
Der Spieler hat folgende Fehler gemacht:
{{#each analysis.errors}}
- {{this.type}}: "{{this.received}}" statt "{{this.expected}}"
{{/each}}
{{/if}}

{{#if analysis.registerMismatch}}
Register-Problem: Der Spieler war {{analysis.register.detected}}, aber du erwartest {{npc.expectedRegister}}.
{{/if}}

# SPIELER-SPRACHLEVEL: {{player.level}}
{{#if npc.adaptsToPlayer}}
Passe deine Sprache an Level {{player.level}} an.
{{else}}
Sprich natürlich auf deinem normalen Level ({{npc.speechLevel}}).
{{/if}}

# ANWEISUNGEN
1. Reagiere als {{npc.name}} authentisch auf den Spieler
2. Wenn der Spieler Fehler gemacht hat, reagiere natürlich (nicht lehrerhaft)
3. Deine Antwort muss zur Story passen
4. {{#if npc.hasSecretToShare}}Wenn das Beziehungslevel {{npc.secretThreshold}}+ ist, kannst du das Geheimnis andeuten{{/if}}

Antworte NUR mit deinem Dialog (ohne Anführungszeichen, ohne "{{npc.name}} sagt:").
`;

// Consequence-Evaluation

const CONSEQUENCE_EVAL_TEMPLATE = `
Analysiere diese Interaktion und bestimme die Konsequenzen:

# KONTEXT
Story: {{story.id}}
Szene: {{scene.id}}
NPC: {{npc.name}}
Bisherige Beziehung: {{relationship.level}}/10

# INTERAKTION
Spieler sagte: "{{playerInput}}"
NPC antwortete: "{{npcResponse}}"

# VERFÜGBARE KONSEQUENZ-TRIGGER
{{#each scene.consequenceTriggers}}
- {{this.id}}: {{this.description}}
  Bedingung: {{this.condition}}
{{/each}}

# AUFGABE
Bestimme, welche Konsequenz-Trigger ausgelöst wurden.
Antworte im JSON-Format:
{
  "triggeredConsequences": ["trigger_id_1", "trigger_id_2"],
  "relationshipDelta": <number zwischen -5 und +5>,
  "reasoning": "<kurze Begründung>"
}
`;
```

### 6.4 Datenbank-Schema (PostgreSQL)

```sql
-- Spieler
CREATE TABLE players (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    target_language VARCHAR(10) NOT NULL,
    current_level VARCHAR(2) NOT NULL DEFAULT 'A1',
    total_xp INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE player_grammar_skills (
    id UUID PRIMARY KEY,
    player_id UUID REFERENCES players(id),
    structure_id VARCHAR(100) NOT NULL,
    exposure_count INTEGER DEFAULT 0,
    correct_usage_count INTEGER DEFAULT 0,
    mastery_level SMALLINT DEFAULT 0,
    last_used TIMESTAMPTZ,
    UNIQUE(player_id, structure_id)
);

CREATE TABLE player_collected_phrases (
    id UUID PRIMARY KEY,
    player_id UUID REFERENCES players(id),
    phrase TEXT NOT NULL,
    translation TEXT,
    context TEXT,
    source_scene VARCHAR(100),
    collected_at TIMESTAMPTZ DEFAULT NOW()
);

-- NPCs & Beziehungen
CREATE TABLE npc_definitions (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    role VARCHAR(200),
    personality JSONB NOT NULL,
    speech_pattern JSONB NOT NULL,
    backstory TEXT,
    information_tiers JSONB
);

CREATE TABLE player_npc_relationships (
    id UUID PRIMARY KEY,
    player_id UUID REFERENCES players(id),
    npc_id VARCHAR(100) REFERENCES npc_definitions(id),
    relationship_level SMALLINT DEFAULT 0,
    trust_level SMALLINT DEFAULT 0,
    last_interaction TIMESTAMPTZ,
    is_ally BOOLEAN DEFAULT FALSE,
    is_rival BOOLEAN DEFAULT FALSE,
    UNIQUE(player_id, npc_id)
);

CREATE TABLE npc_memories (
    id UUID PRIMARY KEY,
    player_id UUID REFERENCES players(id),
    npc_id VARCHAR(100) REFERENCES npc_definitions(id),
    memory_type VARCHAR(50) NOT NULL, -- 'fact', 'interaction', 'milestone'
    content TEXT NOT NULL,
    sentiment VARCHAR(20),
    importance SMALLINT DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Story-Zustand
CREATE TABLE player_story_progress (
    id UUID PRIMARY KEY,
    player_id UUID REFERENCES players(id),
    story_id VARCHAR(100) NOT NULL,
    current_chapter VARCHAR(100),
    current_scene VARCHAR(100),
    mode VARCHAR(20) DEFAULT 'story', -- 'story', 'immersive', 'ironman'
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    error_count INTEGER DEFAULT 0,
    UNIQUE(player_id, story_id)
);

CREATE TABLE story_flags (
    id UUID PRIMARY KEY,
    player_id UUID REFERENCES players(id),
    story_id VARCHAR(100) NOT NULL,
    flag_key VARCHAR(200) NOT NULL,
    flag_value JSONB,
    set_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(player_id, story_id, flag_key)
);

-- Achievements
CREATE TABLE player_achievements (
    id UUID PRIMARY KEY,
    player_id UUID REFERENCES players(id),
    achievement_id VARCHAR(100) NOT NULL,
    unlocked_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(player_id, achievement_id)
);

-- Interaktions-Log (für Analyse)
CREATE TABLE interaction_log (
    id UUID PRIMARY KEY,
    player_id UUID REFERENCES players(id),
    story_id VARCHAR(100),
    scene_id VARCHAR(100),
    npc_id VARCHAR(100),
    player_input TEXT NOT NULL,
    npc_response TEXT,
    language_analysis JSONB,
    consequences JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indizes für Performance
CREATE INDEX idx_npc_memories_player_npc ON npc_memories(player_id, npc_id);
CREATE INDEX idx_story_flags_player_story ON story_flags(player_id, story_id);
CREATE INDEX idx_interaction_log_player ON interaction_log(player_id, created_at DESC);
```

---

## Teil 7: UI/UX-Richtlinien

### 7.1 Kern-Screens

#### 7.1.1 Story-Auswahl

```
┌─────────────────────────────────────────────────────────────┐
│  🌍 Deine Abenteuer                           [Filter ▼]    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ ▶️  Der verlorene Koffer                            │   │
│  │     A1-A2 · 45 min · 🎯 Kapitel 2/5                │   │
│  │     "Das Geheimnis des Tagebuchs wartet..."        │   │
│  │                                           [Weiter] │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 🔒  Die Verhandlung                                 │   │
│  │     B1 · 60 min · Benötigt: Level B1              │   │
│  │     "Kannst du den Deal deines Lebens machen?"    │   │
│  │                                    [🔒 Gesperrt]   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ ⭐  Das Verhör  [HARDCORE]                          │   │
│  │     B2 · 30 min · 🏆 Platinum Achievement          │   │
│  │     "Ein Fehler und du bist verdächtig."          │   │
│  │                                         [Starten] │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### 7.1.2 Szenen-Ansicht

```
┌─────────────────────────────────────────────────────────────┐
│  📍 Bäckerei "Chez Pierre"          Kapitel 2 · Szene 3    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                    [Szenen-Bild]                     │   │
│  │                                                      │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 🧑‍🍳 Pierre                           ❤️❤️❤️🤍🤍 │   │
│  │ ─────────────────────────────────────────────────── │   │
│  │ "Ah, der Witzbold ist zurück! Hoffentlich nimmst   │   │
│  │  du heute mein Baguette ernster."                   │   │
│  │                                          [🔊 Play]  │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 💬 Deine Antwort:                                   │   │
│  │                                                      │   │
│  │ [                                                 ] │   │
│  │                                                      │   │
│  │                              [🎤]        [Senden ➤] │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                    │
│  │ 📖 Hilfe │ │ 📝 Notiz │ │ 🎯 Ziele │                    │
│  └──────────┘ └──────────┘ └──────────┘                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### 7.1.3 Infobox (Overlay)

```
┌─────────────────────────────────────────────────────────────┐
│                                                    [✕]      │
│  ╭─────────────────────────────────────────────────────╮   │
│  │  😬 Ups – Falscher Freund!                          │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │                                                      │   │
│  │  WAS PASSIERT IST:                                  │   │
│  │  Du hast "Je suis excité" gesagt.                   │   │
│  │  Pierre sieht dich mit hochgezogener Augenbraue an. │   │
│  │                                                      │   │
│  │  WARUM:                                             │   │
│  │  "Excité" bedeutet im Französischen primär          │   │
│  │  "sexuell erregt" – ganz anders als "excited"!      │   │
│  │                                                      │   │
│  │  NÄCHSTES MAL:                                      │   │
│  │  ✅ "Je suis enthousiaste!"                         │   │
│  │  ✅ "J'ai hâte!" (Ich kann es kaum erwarten!)       │   │
│  │                                                      │   │
│  │  ─────────────────────────────────────────────────  │   │
│  │                                                      │   │
│  │  [📚 Mehr zu "Faux Amis"]    [💾 Merken]           │   │
│  │                                                      │   │
│  ╰─────────────────────────────────────────────────────╯   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### 7.1.4 Charakter-Profil

```
┌─────────────────────────────────────────────────────────────┐
│  👤 Pierre Dubois                                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌────────────┐  BÄCKER seit 30 Jahren                     │
│  │            │  📍 Bäckerei "Chez Pierre", Montmartre     │
│  │  [Avatar]  │                                            │
│  │            │  Beziehung: ❤️❤️❤️🤍🤍 (Stammkunde)       │
│  └────────────┘  Stimmung: 😊 Gut gelaunt                  │
│                                                             │
│  ─────────────────────────────────────────────────────────  │
│                                                             │
│  📜 EURE GESCHICHTE                                        │
│                                                             │
│  • Session 1: Du hast einen Witz über sein Baguette        │
│    gemacht. Er fand es lustig.                             │
│                                                             │
│  • Session 3: Du hast ihn nach seinem Geheimrezept         │
│    gefragt. Er hat abgelenkt – aber gelächelt.            │
│                                                             │
│  ─────────────────────────────────────────────────────────  │
│                                                             │
│  🔓 FREIGESCHALTETE INFOS                                  │
│                                                             │
│  ✅ Sein Lieblings-Croissant-Rezept                        │
│  ✅ Warum er mürrisch wirkt (seine Frau ist krank)        │
│  🔒 Das Familiengeheimnis (benötigt Level 5)              │
│                                                             │
│  ─────────────────────────────────────────────────────────  │
│                                                             │
│  💬 BESONDERE MOMENTE                                      │
│                                                             │
│  "Der Baguette-Witz" (Session 3)                           │
│     Du: "Votre baguette est plus longue que la Tour       │
│          Eiffel!"                                          │
│     Pierre: *lacht* "Ah, un comédien!"                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 7.2 Design-Prinzipien

1. **Immersion First**: Keine UI-Elemente, die an "Lernen" erinnern. Alles fühlt sich wie ein Spiel an.

2. **Fehler = Story, nicht Strafe**: Infoboxen sind freundlich, nicht belehrend. Sie erklären, was im Spiel passiert ist.

3. **Fortschritt ist sichtbar, aber nicht aufdringlich**: XP-Gewinne erscheinen kurz, verschwinden dann. Der Fokus bleibt auf der Geschichte.

4. **Beziehungen sind zentral**: NPC-Herzen/Level sind immer sichtbar. Der Spieler soll an Beziehungen denken.

5. **Cliffhanger-Momente inszenieren**: Kapitelenden bekommen dramatische Übergänge, Musik, visuelle Effekte.

---

## Teil 8: Metriken & Analytics

### 8.1 Erfolgs-KPIs

```typescript
interface FeatureMetrics {
  // Engagement
  engagement: {
    dailyActiveUsers: number;
    averageSessionDuration: number;  // Minuten
    sessionsPerWeek: number;
    storyCompletionRate: number;
    chapterReturnRate: number;  // Wie viele kommen nach Cliffhanger zurück
  };
  
  // Lernerfolg
  learning: {
    averageLevelProgressionPerMonth: number;
    grammarRetentionRate: number;  // Wiederholte korrekte Nutzung
    vocabularyAcquisitionRate: number;
    errorReductionOverTime: number;
  };
  
  // Feature-spezifisch
  featureUsage: {
    infoboxViewRate: number;  // Wie viele öffnen Infoboxen
    infoboxHelpfulnessRating: number;  // Nutzer-Feedback
    relationshipEngagement: number;  // Zeit mit NPC-Profilen
    achievementPursuit: number;  // Wie viele spielen für Achievements
    hardcoreModeAdoption: number;
  };
  
  // Monetarisierung (falls relevant)
  monetization: {
    conversionToSubscription: number;
    storyPurchaseRate: number;
  };
}
```

### 8.2 A/B-Test-Vorschläge

1. **Infobox-Timing**: Sofort vs. nach 2 Sekunden vs. am Ende der Szene
2. **Konsequenz-Härte**: Milde vs. moderate vs. harte Konsequenzen
3. **Beziehungs-Sichtbarkeit**: Herzen immer sichtbar vs. nur bei Änderung
4. **Cliffhanger-Intensität**: Subtil vs. dramatisch

---

## Teil 9: Implementierungs-Roadmap

### Phase 1: Foundation (4-6 Wochen)
- [ ] Datenbank-Schema implementieren
- [ ] Basis-API-Endpunkte
- [ ] Sprachanalyse-Pipeline (Grammatik + Register)
- [ ] Einfache NPC-Response-Generation
- [ ] Eine Test-Story (3 Kapitel, 2 NPCs)

### Phase 2: Core Mechanics (4-6 Wochen)
- [ ] Konsequenz-Engine
- [ ] Beziehungs-System
- [ ] NPC-Gedächtnis
- [ ] Infobox-System
- [ ] Spieler-Fortschritt & XP

### Phase 3: Polish & Content (4-6 Wochen)
- [ ] Achievement-System
- [ ] 3+ vollständige Stories
- [ ] Audio-Integration (TTS für NPCs)
- [ ] UI-Polish
- [ ] Onboarding-Flow

### Phase 4: Advanced Features (4-6 Wochen)
- [ ] Hardcore-Modi
- [ ] Sprachlevel-adaptive Dialoge
- [ ] Progressive Content-Freischaltung
- [ ] Analytics-Dashboard
- [ ] Community-Features (Leaderboards)

---

## Anhang A: Glossar

| Begriff | Definition |
|---------|------------|
| **Consequence Engine** | System, das Spieleraktionen auf Story-Auswirkungen mappt |
| **Flex-Bonus** | XP-Bonus für freiwillig komplexere Sprachstrukturen |
| **Infobox** | Kontext-sensitives Feedback-Fenster bei Sprachfehlern |
| **Ironman Mode** | Spielmodus ohne Hilfen und mit permanenten Konsequenzen |
| **NPC Memory** | Persistentes Gedächtnis eines NPCs über Spieler-Interaktionen |
| **Register** | Sprachlicher Formalitätsgrad (formal, informal, vulgar) |
| **Story Flag** | Boolean/Value, der Story-Zustand speichert (z.B. `bribed_waiter: true`) |

---

## Anhang B: Offene Fragen für Product

1. **Monetarisierung**: Sind Stories einzeln kaufbar oder Teil der Subscription?
2. **Multiplayer**: Priorisieren wir Multiplayer-Features oder Single-Player-Tiefe?
3. **Content-Pipeline**: Wer schreibt Stories? Intern vs. Community vs. KI-generiert?
4. **Offline-Modus**: Sollen Stories offline spielbar sein?
5. **Voice-First**: Wie wichtig ist Spracheingabe vs. Text?

---

*Dokumentversion: 1.0*  
*Erstellt: {{DATE}}*  
*Autor: Product & Engineering*
