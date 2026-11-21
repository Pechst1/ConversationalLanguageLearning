# Le Petit Prince: Interaktives Sprachabenteuer
## Vollständiger Prototyp – Kapitel 1-3

---

# TEIL 1: STORY-OVERVIEW

## 1.1 Konzept

**Titel:** "L'Astéroïde Oublié" (Der vergessene Asteroid)
**Untertitel:** Eine interaktive Reise nach Antoine de Saint-Exupéry

**Prämisse:**
Du lebst allein auf dem Asteroiden B-329, einem winzigen Felsen im Weltraum. 
Seit Jahren hast du niemanden gesehen. Dann, eines Tages, landet ein 
seltsames Kind mit goldenen Haaren und stellt dir eine unmögliche Frage.

**Was macht diese Adaption besonders:**
- Du bist der ERSTE Planet, den der kleine Prinz besucht
- Deine Gespräche formen seine Weltsicht
- Was du ihm beibringst, nimmt er mit zu den anderen Planeten
- Am Ende erfährst du, wie deine Worte sein Schicksal beeinflusst haben

---

## 1.2 Spielerrolle

```yaml
player:
  defaultName: null  # Spieler wählt oder Prinz gibt einen Namen
  
  backstory:
    short: "Du lebst allein auf einem kleinen Asteroiden."
    
    full: |
      Vor langer Zeit – du weißt nicht mehr, wie lange – bist du auf 
      diesem Asteroiden gelandet. Oder wurdest du hier geboren? 
      Du erinnerst dich nicht. 
      
      Dein Asteroid hat drei Dinge:
      - Einen Baobab-Setzling, den du jeden Tag beschneidest
      - Einen Stuhl, von dem aus du Sonnenuntergänge siehst
      - Eine Einsamkeit, die so alt ist wie die Sterne
      
      Du hast aufgehört, die Tage zu zählen.
      Bis heute.
  
  startingState:
    loneliness: 10  # Maximum
    hope: 2
    wisdom: 5
    
  hiddenTrait: |
    Der Spieler erfährt erst am Ende: Er ist ein "verlorenes Kind" –
    jemand, der erwachsen wurde und dabei vergessen hat, wie man 
    die wichtigen Dinge sieht.
```

---

## 1.3 NPCs

### Der kleine Prinz

```yaml
npc:
  id: "petit_prince"
  name: "Le Petit Prince"
  displayName: "Das Kind" # Anfangs, bevor er sich vorstellt
  
  appearance: |
    Ein kleiner Junge mit goldenen Haaren, die im Sternenwind wehen.
    Er trägt einen langen grünen Mantel mit goldenen Knöpfen.
    Seine Augen sind ernst und fragend.
  
  personality:
    core:
      - "Unendlich neugierig"
      - "Nimmt keine Ausflüchte an"
      - "Stellt Fragen, die Erwachsene vergessen haben"
      - "Hartnäckig – lässt nicht locker"
      - "Sieht mit dem Herzen"
    
    speechPattern:
      complexity: "A1-A2"  # Er spricht einfach, aber tiefgründig
      style: |
        - Kurze, direkte Fragen
        - Wiederholt Fragen, wenn sie nicht beantwortet werden
        - Sagt oft "S'il te plaît"
        - Spricht nie über Unwichtiges
      
      exampleQuotes:
        - "S'il te plaît... dessine-moi un mouton."
        - "Tu viens d'où?"
        - "C'est quoi, 'important'?"
        - "Les grandes personnes sont vraiment bizarres."
  
  voiceConfig:
    speed: "slow"
    tone: "curious, gentle, sometimes sad"
    pronunciation: "clear, child-like"
  
  relationshipConfig:
    initialLevel: 1  # Er vertraut dir nicht sofort
    maxLevel: 10
    
    levelDescriptions:
      1-2: "Neugieriger Fremder"
      3-4: "Interessierter Gesprächspartner"
      5-6: "Freund"
      7-8: "Vertrauter"
      9-10: "Seelenverwandter"
    
    levelUnlocks:
      3: "Er erzählt von seinem Asteroiden"
      5: "Er erzählt von der Rose"
      7: "Er erzählt von seinem Schmerz"
      9: "Er fragt dich um Rat für seine größte Entscheidung"
```

### Die innere Stimme (Erzähler)

```yaml
npc:
  id: "narrator"
  name: "Der Erzähler"
  
  role: |
    Nicht wirklich ein NPC, sondern die poetische Stimme, 
    die Szenen einleitet und Gedanken des Spielers verbalisiert.
  
  style:
    tone: "Poetisch, melancholisch, weise"
    language: "Angepasst an Spielerlevel, aber immer literarisch"
    
  exampleNarrations:
    A1: |
      Der Himmel ist dunkel. Die Sterne sind hell.
      Du bist allein. Wie immer.
      
    B1: |
      Die Dunkelheit des Weltraums ist nicht kalt – sie ist still.
      Eine Stille, die du so lange gehört hast, dass du sie 
      vergessen hattest. Bis jetzt.
```

---

## 1.4 Kapitelstruktur

| Kapitel | Titel | Level | Dauer | Kernthema |
|---------|-------|-------|-------|-----------|
| Prolog | L'Astéroïde | A1 | 5 min | Einführung, Einsamkeit etablieren |
| 1 | L'Arrivée | A1 | 15 min | Erste Begegnung, "Dessine-moi un mouton" |
| 2 | Les Questions | A1-A2 | 20 min | Der Prinz stellt Fragen, du antwortest |
| 3 | La Rose | A2 | 20 min | Der Prinz erzählt von seiner Rose |
| 4 | Le Départ | A2 | 15 min | Abschied, Versprechen |
| Epilog | Les Étoiles | A2-B1 | 10 min | Was aus dem Prinzen wurde |

---

# TEIL 2: VOLLSTÄNDIGES SKRIPT

---

## PROLOG: L'Astéroïde

### Szene P.1: Stille

```yaml
scene:
  id: "prologue_silence"
  type: "narrative_only"  # Kein Dialog, nur Erzählung
  duration: 2-3min
  
  purpose: |
    Etabliere die Einsamkeit. Der Spieler soll die Stille FÜHLEN,
    bevor sie gebrochen wird.
  
  setting:
    location: "Asteroid B-329"
    time: "Zeitlos – könnte gestern sein oder vor tausend Jahren"
    visualDescription: |
      Ein winziger Asteroid im Weltraum.
      So klein, dass man ihn in drei Schritten umrunden kann.
      Ein einzelner Stuhl. Ein kleiner Baobab-Setzling.
      Unendliche Sterne.
  
  narration:
    # Level A1 - Sehr einfache Sprache
    A1:
      text: |
        [Schwarzer Bildschirm, Sterne erscheinen langsam]
        
        L'espace.
        
        [Pause]
        
        Le silence.
        
        [Pause]
        
        Ton astéroïde.
        
        [Der Asteroid erscheint]
        
        Il est petit. Très petit.
        Trois pas – et tu as fait le tour.
        
        [Spieler sieht sich um]
        
        Tu es seul.
        Depuis longtemps.
        Tu ne comptes plus les jours.
        
        [Ein Stuhl wird sichtbar]
        
        Ton fauteuil. Pour regarder le coucher du soleil.
        
        [Die Sonne geht unter – sehr schnell]
        
        Sur ton astéroïde, le soleil se couche quarante-quatre fois par jour.
        Si tu veux.
        
        [Stille]
        
        Quarante-quatre fois par jour, tu peux être triste.
        
        [Lange Pause]
        
        Ou pas.
      
      vocabulary_hints:
        - word: "l'espace"
          translation: "der Weltraum"
        - word: "le silence"
          translation: "die Stille"
        - word: "seul"
          translation: "allein"
        - word: "le coucher du soleil"
          translation: "der Sonnenuntergang"
        - word: "triste"
          translation: "traurig"
    
    # Level B1 - Mehr literarische Sprache
    B1:
      text: |
        [Schwarzer Bildschirm, Sterne erscheinen]
        
        Dans l'immensité de l'espace, il y a un astéroïde 
        que personne n'a jamais visité.
        
        L'astéroïde B-329.
        
        [Der Asteroid erscheint]
        
        Il est si petit qu'on peut en faire le tour en trois pas.
        Si petit qu'un seul baobab pourrait le faire éclater.
        
        Et pourtant, quelqu'un y vit.
        
        Toi.
        
        [Spieler sieht sich um]
        
        Depuis combien de temps es-tu là?
        Tu ne sais plus. Les jours n'ont pas de sens 
        quand le soleil se couche quarante-quatre fois 
        avant que tu aies fini de penser.
        
        [Die Sonne geht unter]
        
        Quarante-quatre couchers de soleil par jour.
        Quarante-quatre occasions d'être mélancolique.
        
        Ou d'espérer.
        
        [Stille]
        
        Mais espérer quoi?
  
  playerInteraction:
    type: "contemplative_choice"
    prompt: 
      A1: "Qu'est-ce que tu fais maintenant?"
      B1: "Que fais-tu de tes journées sans fin?"
    
    options:
      - id: "watch_sunset"
        text:
          A1: "Je regarde le soleil."
          B1: "Je contemple le coucher du soleil."
        response: |
          [Die Sonne geht noch einmal unter]
          Encore un. Il y en aura d'autres.
        effect:
          mood: "melancholic"
          foreshadowing: "sunset_lover"
      
      - id: "tend_baobab"
        text:
          A1: "Je m'occupe du baobab."
          B1: "Je veille sur le baobab, pour qu'il ne devienne pas trop grand."
        response: |
          [Spieler beschneidet den Setzling]
          Tu coupes les petites branches.
          Si tu oublies un jour, il sera trop tard.
        effect:
          mood: "dutiful"
          foreshadowing: "caretaker"
      
      - id: "wait"
        text:
          A1: "J'attends."
          B1: "J'attends. Sans savoir quoi."
        response: |
          [Lange Stille]
          Tu attends.
          Comme toujours.
        effect:
          mood: "hopeful"
          foreshadowing: "waiting_for_connection"
  
  transition:
    trigger: "choice_made"
    narration:
      A1: |
        Et puis...
        
        [Ein Licht erscheint am Himmel]
        
        Quelque chose.
      
      B1: |
        Et c'est alors que quelque chose d'extraordinaire se produit.
        
        [Ein Licht erscheint]
        
        Pour la première fois depuis... depuis quand?
        Une lumière traverse le ciel.
    
    nextScene: "chapter1_arrival"
```

---

## KAPITEL 1: L'Arrivée (Die Ankunft)

### Szene 1.1: Das Licht

```yaml
scene:
  id: "ch1_the_light"
  duration: 3-5min
  
  setting:
    location: "Asteroid B-329"
    time: "Ein Moment, der alles verändert"
    atmosphere: |
      Aufregung, Verwirrung, Hoffnung.
      Das erste Mal seit Ewigkeiten passiert etwas.
  
  narration:
    A1: |
      [Das Licht wird größer]
      
      Une lumière.
      Elle tombe du ciel.
      Elle tombe... vers toi!
      
      [CRASH – etwas landet]
      
      Tu cours voir.
      
      [Der Spieler nähert sich]
      
      Ce n'est pas une étoile.
      Ce n'est pas une pierre.
      
      C'est...
    
    B1: |
      [Das Licht wird größer]
      
      La lumière grossit, descend en spirale, 
      comme si elle cherchait exactement cet endroit.
      
      Ton cœur bat. Depuis quand n'a-t-il pas battu ainsi?
      
      [CRASH – sanfte Landung]
      
      Tu t'approches, le souffle court.
      
      Ce n'est pas un météore.
      Ce n'est pas un rêve.
      
      C'est...
  
  reveal:
    visual: |
      [Aus dem Licht tritt eine kleine Gestalt]
      Ein Kind. Goldene Haare. Ein grüner Mantel.
      Es klopft sich den Sternenstaub ab.
      Es sieht dich an.
    
    narration:
      A1: "Un enfant."
      B1: "Un enfant, apparu de nulle part, au milieu de nulle part."
  
  firstContact:
    # Der Prinz spricht zuerst
    npc: "petit_prince"
    
    initialDialogue:
      text:
        A1: |
          [Der Prinz sieht dich an, sehr ernst]
          "S'il te plaît..."
          [Pause]
          "Dessine-moi un mouton."
        
        B1: |
          [Der Prinz richtet seinen Blick auf dich – 
          ein Blick, der durch dich hindurchzusehen scheint]
          "S'il te plaît..."
          [Er wartet, als wäre diese Bitte das Normalste der Welt]
          "Dessine-moi un mouton."
      
      voice:
        audio_description: |
          Kinderstimme, aber mit einer seltsamen Ernsthaftigkeit.
          Langsam, klar, jedes Wort betont.
        speed: 0.8
    
    # WICHTIG: Das ist DIE ikonische Szene des Buches
    playerResponse:
      type: "free_input"
      context: |
        Der Spieler wird zum ersten Mal zum Sprechen aufgefordert.
        Die Bitte ist absurd – aber wie reagiert man auf ein Kind,
        das aus dem Himmel gefallen ist?
      
      expectedIntents:
        - "confused_question"  # "Was? Wer bist du?"
        - "refusal"            # "Ich kann nicht zeichnen"
        - "acceptance"         # "Okay, ich versuche es"
        - "counter_question"   # "Warum ein Schaf?"
      
      responseHandling:
        # Wenn der Spieler eine Frage stellt
        confused_question:
          triggers:
            - pattern: "qui|wer|who"
            - pattern: "quoi|was|what"
            - pattern: "pourquoi|warum|why"
            - pattern: "comment|wie|how"
          
          princeResponse:
            text:
              A1: |
                [Der Prinz schüttelt den Kopf]
                "S'il te plaît..."
                [Ernster]
                "Dessine-moi un mouton."
                
                [Er wartet. Er gibt nicht auf.]
              
              B1: |
                [Der Prinz scheint die Frage nicht zu verstehen –
                oder er ignoriert sie bewusst]
                "S'il te plaît. C'est très important."
                "Dessine-moi un mouton."
                
                [Seine Augen sind auf dich gerichtet. Er wartet.]
            
            systemNote: |
              Der Prinz antwortet nie auf Fragen, bevor seine Bitte 
              erfüllt ist. Das ist Teil seines Charakters.
        
        # Wenn der Spieler ablehnt
        refusal:
          triggers:
            - pattern: "non|nein|no"
            - pattern: "ne peux pas|kann nicht|cannot"
            - pattern: "impossible"
          
          princeResponse:
            text:
              A1: |
                [Der Prinz sieht traurig aus]
                "Tu ne sais pas dessiner?"
                [Kleine Pause]
                "Moi non plus, les grandes personnes ne savent jamais rien."
                [Er setzt sich hin]
                "Essaie. S'il te plaît."
              
              B1: |
                [Ein Schatten huscht über sein Gesicht]
                "Les grandes personnes disent toujours qu'elles ne peuvent pas."
                [Er setzt sich auf einen Stein]
                "Mais toi, tu n'es pas vraiment une grande personne, n'est-ce pas?"
                [Er sieht dich an – es ist keine Frage, es ist eine Hoffnung]
                "Essaie. S'il te plaît."
            
            effect:
              relationship: -1  # Leichte Enttäuschung
              flag: "initially_refused"
        
        # Wenn der Spieler akzeptiert
        acceptance:
          triggers:
            - pattern: "oui|ja|yes"
            - pattern: "d'accord|okay"
            - pattern: "je vais essayer|ich versuche"
          
          princeResponse:
            text:
              A1: |
                [Der Prinz lächelt – zum ersten Mal]
                "Merci."
                [Er setzt sich und wartet geduldig]
              
              B1: |
                [Sein Gesicht erhellt sich]
                "Merci."
                [Er setzt sich, die Hände auf den Knien, und wartet 
                mit der Geduld von jemandem, der die Ewigkeit kennt]
            
            effect:
              relationship: +1
              flag: "accepted_immediately"
      
      nextScene: "ch1_drawing_sheep"
```

### Szene 1.2: Das Schaf zeichnen

```yaml
scene:
  id: "ch1_drawing_sheep"
  duration: 10-12min
  
  purpose: |
    Die ikonische Schaf-Szene. Der Spieler "zeichnet" durch Beschreiben.
    Jeder Versuch lehrt Vokabeln und zeigt den Charakter des Prinzen.
  
  setup:
    narration:
      A1: |
        Tu n'as pas de papier. Pas de crayon.
        Mais le petit prince attend.
        
        Alors, tu dessines avec des mots.
        Tu décris un mouton.
      
      B1: |
        Tu n'as ni papier ni crayon – sur un astéroïde, 
        ces choses n'existent pas.
        
        Mais le petit prince attend, et son attente 
        a le poids d'une étoile.
        
        Alors, tu fais la seule chose possible:
        Tu dessines avec des mots.
  
  # GAMEPLAY: Der Spieler beschreibt ein Schaf
  # Das ist eine Vokabel-/Beschreibungsübung verkleidet als Story
  
  drawingMechanic:
    instruction:
      A1: "Décris un mouton. Comment est-il?"
      B1: "Décris ton mouton au petit prince. À quoi ressemble-t-il?"
    
    inputType: "voice_preferred"
    voiceBonus: 
      xp: 1.5
      note: "Le petit prince préfère écouter plutôt que lire."
    
    # Verschiedene Schaf-Beschreibungen führen zu verschiedenen Reaktionen
    sheepAttempts:
      attempt1:
        prompt:
          A1: "Décris ton premier mouton."
          B1: "Premier essai. Comment est ton mouton?"
        
        analysisRules:
          # Was wir in der Antwort suchen
          lookFor:
            - category: "size"
              words: ["grand", "petit", "gros", "énorme"]
            - category: "color"
              words: ["blanc", "noir", "gris", "marron"]
            - category: "features"
              words: ["cornes", "laine", "pattes", "queue"]
            - category: "state"
              words: ["malade", "vieux", "jeune", "fatigué"]
        
        responseMatrix:
          # Wenn das Schaf zu groß beschrieben wird
          ifMentions: ["grand", "gros", "énorme"]
          princeReaction:
            text:
              A1: |
                [Der Prinz schüttelt den Kopf]
                "Non. Celui-là est trop grand."
                "Mon astéroïde est très petit."
                "Dessine-moi un autre mouton."
              
              B1: |
                [Der Prinz betrachtet deine Worte, 
                als würde er das Schaf wirklich sehen]
                "Non, non. Celui-là est beaucoup trop grand."
                "Tu ne comprends pas – mon astéroïde est minuscule."
                "Un mouton comme ça mangerait toutes les fleurs."
                [Er sieht besorgt aus]
                "Dessine-moi un autre mouton. Plus petit."
            
            infobox:
              title: "Größe beschreiben"
              content: |
                Der Prinz will ein KLEINES Schaf.
                
                Nützliche Wörter:
                • petit (klein)
                • minuscule (winzig)
                • tout petit (ganz klein)
                
                Statt "grand" (groß), versuche "petit"!
              
              grammarNote: |
                Adjektive im Französischen:
                un GRAND mouton (ein großes Schaf)
                un PETIT mouton (ein kleines Schaf)
                
                Das Adjektiv steht oft VOR dem Nomen bei:
                grand, petit, jeune, vieux, beau, joli
          
          # Wenn das Schaf als krank beschrieben wird
          ifMentions: ["malade", "vieux", "fatigué", "triste"]
          princeReaction:
            text:
              A1: |
                [Der Prinz sieht traurig aus]
                "Non. Celui-là est malade."
                "Je veux un mouton en bonne santé."
                "Dessine-moi un autre."
              
              B1: |
                [Der Prinz legt den Kopf schief, besorgt]
                "Oh non. Celui-là a l'air malade."
                "Regarde, il est tout triste."
                "Je ne veux pas d'un mouton malade."
                "Il me faut un mouton qui peut manger les baobabs."
            
            infobox:
              title: "Gesundheit & Zustand"
              content: |
                Der Prinz will ein GESUNDES Schaf!
                
                Nützliche Wörter:
                • en bonne santé (gesund)
                • fort (stark)
                • content (zufrieden)
                • heureux (glücklich)
          
          # Wenn das Schaf mit Hörnern beschrieben wird
          ifMentions: ["cornes"]
          princeReaction:
            text:
              A1: |
                [Der Prinz lacht – ein überraschendes Geräusch]
                "Mais non! Celui-là a des cornes!"
                "Ce n'est pas un mouton, c'est un bélier!"
                "Dessine-moi un MOUTON."
              
              B1: |
                [Der Prinz lacht – ein helles, klares Lachen]
                "Mais regarde! Tu lui as mis des cornes!"
                "Ce n'est pas un mouton, c'est un bélier!"
                [Er kichert]
                "Les grandes personnes confondent toujours tout."
            
            effect:
              relationship: +1  # Der Prinz findet es lustig
            
            infobox:
              title: "Mouton vs. Bélier"
              content: |
                Un mouton = ein Schaf (ohne Hörner)
                Un bélier = ein Widder (mit Hörnern)
                
                Der kleine Prinz kennt den Unterschied!
      
      attempt2:
        prompt:
          A1: "Essaie encore. Un autre mouton."
          B1: "Deuxième essai. Décris un autre mouton."
        
        # Ähnliche Analyse wie attempt1, aber andere Reaktionen
        responseMatrix:
          ifAnySimpleDescription:
            # Wenn der Spieler eine einfache Beschreibung gibt
            princeReaction:
              text:
                A1: |
                  [Der Prinz denkt nach]
                  "Mmm..."
                  [Pause]
                  "Non. Celui-là est trop..."
                  [Er sucht nach dem Wort]
                  "...ordinaire."
                
                B1: |
                  [Der Prinz betrachtet das Schaf lange]
                  "Non."
                  [Er seufzt]
                  "Celui-là n'est pas... spécial."
                  "Mon mouton doit être spécial."
      
      attempt3_solution:
        # Nach mehreren Versuchen: Die Kisten-Lösung
        trigger: "after_2_failed_attempts OR player_frustrated"
        
        prompt:
          A1: |
            Tu es fatigué. Comment faire un mouton parfait?
            
            [Option erscheint]
            → Dessiner autre chose?
          
          B1: |
            Tu as essayé deux fois. Le petit prince n'est jamais content.
            
            Peut-être... une autre approche?
        
        creativeSolution:
          description: |
            Der Spieler kann eine Kiste beschreiben statt eines Schafs.
            Das ist die Original-Lösung aus dem Buch.
          
          triggers:
            - pattern: "boîte|caisse|box|kiste"
            - pattern: "dedans|inside|darin"
            - pattern: "imagine|vorstellen"
          
          ifPlayerDescribesBox:
            princeReaction:
              text:
                A1: |
                  [Der Prinz strahlt]
                  "Une boîte!"
                  "Et le mouton est dedans?"
                  
                  [Er sieht die imaginäre Kiste an]
                  
                  "C'est exactement ce que je voulais!"
                  
                  [Er lächelt – sein ganzes Gesicht leuchtet]
                  
                  "Regarde! Il dort."
                
                B1: |
                  [Der Prinz blinzelt – dann versteht er]
                  "Oh! C'est une boîte!"
                  "Et le mouton que je voulais est dedans?"
                  
                  [Er kniet nieder, betrachtet die unsichtbare Kiste]
                  
                  "C'est tout à fait ce que je voulais!"
                  
                  [Er presst die Kiste an sich]
                  
                  "Regarde comme il est paisible. Il dort."
              
              effect:
                relationship: +3
                flag: "found_box_solution"
                achievement: "thinking_like_a_child"
            
            infobox:
              title: "Die Kiste"
              content: |
                Du hast die perfekte Lösung gefunden!
                
                Im Original-Buch zeichnet der Erzähler auch eine Kiste.
                Der Prinz ist begeistert – er kann sich das perfekte 
                Schaf SELBST vorstellen.
                
                Manchmal ist das, was man nicht sieht, 
                wichtiger als das, was man sieht.
              
              bookQuote: |
                "Ça c'est la caisse. Le mouton que tu veux est dedans."
                – Le Petit Prince, Chapitre II
          
          ifPlayerDoesNotFindSolution:
            # Hint-System
            hint1:
              trigger: "after_attempt_3"
              text:
                A1: |
                  [Du denkst nach]
                  Peut-être que le mouton parfait...
                  ...n'a pas besoin d'être visible?
                
                B1: |
                  [Eine Idee kommt dir]
                  Et si le mouton parfait était celui qu'on ne voit pas?
                  Celui qu'on imagine?
            
            hint2:
              trigger: "after_attempt_4"
              text:
                A1: |
                  [Der Erzähler flüstert]
                  Une boîte peut contenir n'importe quoi.
                  Même un mouton parfait.
  
  resolution:
    # Nach der erfolgreichen Schaf-Szene
    narration:
      A1: |
        [Der Prinz hält die unsichtbare Kiste]
        
        C'est le premier cadeau que tu donnes depuis...
        ...tu ne sais plus.
        
        L'enfant sourit.
        Et toi aussi.
      
      B1: |
        [Der Prinz umarmt seine Kiste]
        
        C'est étrange comme un simple dessin – 
        ou l'idée d'un dessin – peut créer un lien.
        
        Pour la première fois depuis des années,
        tu n'es plus complètement seul.
    
    transition:
      text:
        A1: "Le petit prince s'assoit à côté de toi."
        B1: "Le petit prince s'installe près de toi, sa boîte serrée contre lui."
      
      nextScene: "ch2_questions_begin"
```

---

## KAPITEL 2: Les Questions (Die Fragen)

### Szene 2.1: Wer bist du?

```yaml
scene:
  id: "ch2_questions_begin"
  duration: 8-10min
  
  purpose: |
    Der Prinz beginnt, Fragen zu stellen.
    Jede Frage ist einfach, aber die Antwort formt, wer der Prinz wird.
  
  setting:
    location: "Asteroid B-329, neben dem Stuhl"
    time: "Nach der Schaf-Szene"
    atmosphere: "Ruhig, neugierig, intim"
  
  setup:
    narration:
      A1: |
        Le petit prince pose sa boîte.
        Il te regarde.
        
        "Tu habites ici?"
      
      B1: |
        Le petit prince dépose délicatement sa boîte à côté de lui.
        Puis il lève les yeux vers toi.
        
        Des yeux qui ne jugent pas. Qui veulent simplement comprendre.
        
        "Tu habites ici? Sur cet astéroïde?"
  
  dialogue:
    segment1_where_from:
      npc: "petit_prince"
      
      question:
        text:
          A1: "Tu viens d'où?"
          B1: "D'où viens-tu? Tu as toujours vécu ici?"
        
        voice:
          tone: "curious, not demanding"
      
      playerResponse:
        type: "free_input"
        
        guidingPrompt:
          A1: "Réponds au petit prince. Tu viens d'où?"
          B1: "Le petit prince veut savoir d'où tu viens. Que lui réponds-tu?"
        
        analysisRules:
          # Verschiedene Antworten führen zu verschiedenen Pfaden
          
          responseType_knows:
            triggers:
              - pattern: "je viens de|ich komme aus"
              - pattern: "ma planète|mein Planet"
              - pattern: "la Terre|die Erde"
            
            princeResponse:
              text:
                A1: |
                  "La Terre?"
                  [Er denkt nach]
                  "C'est loin?"
                
                B1: |
                  "La Terre..."
                  [Er wiederholt das Wort, als würde er es schmecken]
                  "C'est loin d'ici? C'est grand?"
              
              followUp: "earth_conversation"
          
          responseType_forgotten:
            triggers:
              - pattern: "je ne sais pas|ich weiß nicht"
              - pattern: "j'ai oublié|ich habe vergessen"
              - pattern: "ne me souviens pas"
            
            princeResponse:
              text:
                A1: |
                  [Der Prinz sieht dich lange an]
                  "Tu as oublié?"
                  [Leise]
                  "C'est triste, d'oublier d'où on vient."
                
                B1: |
                  [Der Prinz neigt den Kopf]
                  "Tu as oublié d'où tu viens?"
                  [Eine Pause voller Gewicht]
                  "Les grandes personnes oublient toujours les choses importantes."
                  [Er sieht dich an – nicht vorwurfsvoll, sondern traurig]
                  "Mais peut-être que tu peux te souvenir."
              
              effect:
                flag: "has_forgotten_origin"
                relationship: +1  # Er fühlt sich verbunden
              
              followUp: "memory_conversation"
          
          responseType_always_here:
            triggers:
              - pattern: "toujours ici|immer hier"
              - pattern: "toujours vécu|immer gelebt"
              - pattern: "chez moi|mein Zuhause"
            
            princeResponse:
              text:
                A1: |
                  "Toujours?"
                  [Er schaut sich um]
                  "Mais... tu es seul ici."
                  "Tu n'es pas triste?"
                
                B1: |
                  "Toujours?"
                  [Er betrachtet den kleinen Asteroiden]
                  "Tu vis seul ici depuis toujours?"
                  [Seine Stimme wird weich]
                  "Ce doit être... très silencieux."
              
              followUp: "loneliness_conversation"
    
    # Verzweigung: Je nach Antwort verschiedene Gespräche
    
    branch_earth_conversation:
      id: "earth_conversation"
      
      dialogue:
        prince:
          text:
            A1: |
              "La Terre, c'est grand?"
              [Er wartet]
              "Il y a beaucoup de gens?"
            
            B1: |
              "La Terre... on m'a dit que c'était une grande planète."
              "Avec beaucoup, beaucoup de gens."
              [Er sieht nachdenklich aus]
              "C'est difficile d'être seul, quand il y a beaucoup de gens?"
          
          voice:
            tone: "wondering, slightly concerned"
        
        playerResponse:
          guidingPrompt:
            A1: "Parle-lui de la Terre. Il y a beaucoup de gens?"
            B1: "Décris-lui la Terre. Qu'est-ce que tu en sais encore?"
          
          analysisRules:
            ifMentions: ["beaucoup", "millions", "viel"]
            princeThought:
              text:
                A1: |
                  [Der Prinz denkt nach]
                  "Beaucoup de gens..."
                  "Mais ils se parlent?"
                  "Ils sont amis?"
                
                B1: |
                  [Der Prinz scheint etwas zu verarbeiten]
                  "Beaucoup de gens. Et pourtant..."
                  [Er schaut dich an]
                  "Et pourtant, toi, tu es venu ici. Tout seul."
                  "Pourquoi?"
              
              # Das ist eine tiefe Frage - optional für den Spieler
              effect:
                unlocks: "deep_question_why_alone"
    
    branch_loneliness_conversation:
      id: "loneliness_conversation"
      
      dialogue:
        prince:
          text:
            A1: |
              "Tu n'es pas triste, d'être seul?"
            
            B1: |
              "La solitude... ce n'est pas trop lourd à porter?"
              "Moi aussi, je connais la solitude."
              [Il touche sa boîte]
              "Mais j'ai ma rose."
          
          # WICHTIG: Erste Erwähnung der Rose
          flag_set: "rose_mentioned_first_time"
        
        playerResponse:
          type: "philosophical_choice"
          
          options:
            - id: "loneliness_is_painful"
              text:
                A1: "Oui, c'est triste."
                B1: "Oui. La solitude, c'est lourd."
              
              princeResponse:
                text:
                  A1: |
                    [Er nickt ernst]
                    "Je comprends."
                    [Pause]
                    "C'est pour ça que tu as besoin d'un ami."
                  
                  B1: |
                    [Der Prinz legt seine kleine Hand auf deine]
                    "Je comprends. Moi aussi, parfois, la solitude me pèse."
                    "C'est pour ça qu'on a besoin d'être apprivoisé."
                
                effect:
                  relationship: +2
                  flag: "acknowledged_loneliness"
            
            - id: "loneliness_is_peaceful"
              text:
                A1: "Non, c'est calme."
                B1: "Non. Le silence, c'est paisible."
              
              princeResponse:
                text:
                  A1: |
                    [Der Prinz sieht überrascht aus]
                    "Calme?"
                    "Mais... tu ne veux pas parler à quelqu'un?"
                  
                  B1: |
                    [Der Prinz neigt den Kopf, verwirrt]
                    "Paisible? Tu n'as pas besoin de quelqu'un à qui parler?"
                    [Er denkt nach]
                    "Les grandes personnes disent souvent ça."
                    "Mais je ne les crois pas."
                
                effect:
                  relationship: 0
                  flag: "denies_loneliness"
            
            - id: "loneliness_is_complicated"
              text:
                A1: "Je ne sais pas."
                B1: "C'est... compliqué."
              
              princeResponse:
                text:
                  A1: |
                    [Der Prinz nickt]
                    "Compliqué. Les grandes personnes disent toujours ça."
                    "Mais moi, je comprends."
                    "Parfois, on est triste et content en même temps."
                  
                  B1: |
                    [Der Prinz lächelt – ein wissendes Lächeln]
                    "Compliqué. Oui."
                    "On peut être seul et pas seul en même temps."
                    "On peut être triste en regardant les étoiles,"
                    "et heureux aussi."
                    [Er zeigt auf den Himmel]
                    "Parce que quelque part, là-haut, il y a quelqu'un."
                
                effect:
                  relationship: +1
                  flag: "complexity_acknowledged"
                  unlocks: "stars_philosophy"
  
  transition:
    narration:
      A1: |
        Le petit prince se tait.
        Il regarde les étoiles.
        
        Puis il dit quelque chose d'étrange.
      
      B1: |
        Le petit prince se tait un moment.
        Son regard se perd dans l'immensité du ciel.
        
        Quand il parle à nouveau, sa voix est différente.
        Plus douce. Plus fragile.
    
    nextScene: "ch2_the_rose_mentioned"
```

### Szene 2.2: Die Rose wird erwähnt

```yaml
scene:
  id: "ch2_the_rose_mentioned"
  duration: 10min
  
  purpose: |
    Der Prinz erwähnt seine Rose zum ersten Mal richtig.
    Das ist der emotionale Kern der Geschichte.
  
  trigger:
    requires: "rose_mentioned_first_time OR relationship >= 3"
  
  dialogue:
    opening:
      npc: "petit_prince"
      
      text:
        A1: |
          [Der Prinz spricht leise]
          "Sur mon astéroïde..."
          "Il y a une fleur."
          [Pause]
          "Une rose."
        
        B1: |
          [Der Prinz spricht, als würde er ein Geheimnis teilen]
          "Sur mon astéroïde, il y a une fleur."
          "Une rose."
          [Seine Stimme wird weicher]
          "Elle est... compliquée."
      
      voice:
        tone: "tender, vulnerable, slightly sad"
        speed: 0.7  # Langsamer als normal
    
    playerResponse:
      type: "empathetic_response"
      
      guidingPrompt:
        A1: "Il parle de sa rose. Que dis-tu?"
        B1: "Le petit prince parle de sa rose. Comment réagis-tu?"
      
      analysisRules:
        # Empathische Antworten
        ifEmpathetic:
          triggers:
            - pattern: "raconte|erzähle|tell"
            - pattern: "comment est|wie ist"
            - pattern: "elle est belle|ist sie schön"
          
          princeResponse:
            unlocks: "rose_description"
        
        # Desinteressierte Antworten
        ifDismissive:
          triggers:
            - pattern: "seulement une fleur|nur eine Blume"
            - pattern: "pas important|nicht wichtig"
          
          princeResponse:
            text:
              A1: |
                [Der Prinz sieht verletzt aus]
                "Seulement une fleur?"
                [Er schüttelt den Kopf]
                "Non. Elle est unique."
              
              B1: |
                [Der Prinz richtet sich auf, fast beleidigt]
                "Seulement une fleur?"
                "Mais non! Tu ne comprends pas."
                "Elle est unique au monde. Parce que c'est elle que j'ai arrosée."
                "Parce que c'est elle que j'ai protégée."
                "Parce que c'est elle dont j'ai écouté les plaintes."
            
            effect:
              relationship: -1
            
            infobox:
              title: "L'Unique"
              content: |
                Für den kleinen Prinzen ist seine Rose einzigartig –
                nicht weil sie anders ist als andere Rosen,
                sondern weil er sie LIEBT.
                
                Das ist eine der zentralen Lektionen des Buches:
                "On ne voit bien qu'avec le cœur."
                (Man sieht nur mit dem Herzen gut.)
    
    rose_description:
      id: "rose_description"
      condition: "unlocks: rose_description"
      
      dialogue:
        prince:
          text:
            A1: |
              [Der Prinz lächelt träumerisch]
              "Ma rose est belle."
              "Elle a quatre épines."
              "Elle dit qu'elle est forte."
              [Pause]
              "Mais elle est fragile."
            
            B1: |
              [Der Prinz schließt die Augen, als würde er sie sehen]
              "Ma rose..."
              "Elle est apparue un jour, de nulle part."
              "Elle a mis longtemps à s'habiller, à choisir ses couleurs."
              "Elle voulait être parfaite."
              [Er öffnet die Augen]
              "Elle a quatre épines. Elle dit que c'est pour se défendre."
              "Mais ses épines ne font peur à personne."
              [Seine Stimme wird traurig]
              "Elle est plus fragile qu'elle ne le croit."
          
          voice:
            tone: "tender, nostalgic, worried"
        
        playerChoice:
          prompt:
            A1: "Qu'est-ce que tu lui dis?"
            B1: "Le petit prince te parle de sa rose. Que ressens-tu? Que dis-tu?"
          
          type: "philosophical_choice"
          
          options:
            - id: "ask_why_left"
              text:
                A1: "Pourquoi tu es parti?"
                B1: "Si elle est si importante... pourquoi l'as-tu quittée?"
              
              # WICHTIG: Das ist DIE zentrale Frage
              princeResponse:
                text:
                  A1: |
                    [Der Prinz wird still]
                    [Lange Pause]
                    "Je... ne sais pas."
                    [Noch leiser]
                    "Elle m'a dit des choses méchantes."
                    "Et moi, je suis parti."
                    [Er sieht auf seine Hände]
                    "J'aurais dû rester."
                  
                  B1: |
                    [Der Prinz erstarrt]
                    [Eine lange, schmerzhafte Stille]
                    "Pourquoi?"
                    [Er wiederholt deine Frage, als hätte er sie selbst nie gestellt]
                    "Je... je ne sais pas vraiment."
                    [Seine Stimme bricht fast]
                    "Elle était... difficile. Exigeante."
                    "Elle me faisait des reproches. Elle mentait parfois."
                    "Mais..."
                    [Er sieht dich an, Tränen in den Augen]
                    "Mais je l'aime. Et j'aurais dû comprendre."
                    "Les fleurs, il faut les regarder et les respirer."
                    "Il ne faut pas écouter ce qu'elles disent."
                
                effect:
                  relationship: +3
                  flag: "understands_princes_regret"
                  unlocks: "chapter3_full_rose_story"
                
                infobox:
                  title: "Le regret du Petit Prince"
                  content: |
                    Der kleine Prinz versteht jetzt, dass er einen 
                    Fehler gemacht hat. Er hat auf die Worte der Rose 
                    gehört, nicht auf ihre Taten.
                    
                    Im Buch sagt er:
                    "J'aurais dû la juger sur les actes et non sur les mots."
                    (Ich hätte sie nach ihren Taten beurteilen sollen, 
                    nicht nach ihren Worten.)
                  
                  grammarNote: |
                    "J'aurais dû" = Ich hätte ... sollen
                    
                    Das ist der Conditionnel Passé – 
                    er drückt Bedauern über die Vergangenheit aus.
                    
                    Struktur: avoir/être (Conditionnel) + Partizip
            
            - id: "say_she_sounds_difficult"
              text:
                A1: "Elle a l'air difficile."
                B1: "Elle a l'air... compliquée, ta rose."
              
              princeResponse:
                text:
                  A1: |
                    [Der Prinz nickt langsam]
                    "Oui. Difficile."
                    "Mais c'est parce que..."
                    [Er sucht nach Worten]
                    "...elle avait peur, je crois."
                  
                  B1: |
                    [Der Prinz seufzt]
                    "Compliquée. Oui. C'est le bon mot."
                    "Mais tu sais..."
                    [Er sieht dich an]
                    "Les gens les plus compliqués sont souvent ceux 
                    qui ont le plus besoin d'être aimés."
                    "Je crois qu'elle avait peur."
                    "Peur que je parte. Alors elle me repoussait."
                    [Traurig]
                    "Et je suis parti quand même."
                
                effect:
                  relationship: +1
                  flag: "validated_rose_difficulty"
            
            - id: "offer_comfort"
              text:
                A1: "Tu la reverras."
                B1: "Tu retourneras vers elle. Je suis sûr."
              
              princeResponse:
                text:
                  A1: |
                    [Der Prinz sieht dich an, hoffnungsvoll]
                    "Tu crois?"
                    [Pause]
                    "Oui. Je dois retourner."
                    "Elle est toute seule."
                  
                  B1: |
                    [Der Prinz hebt den Blick]
                    "Tu crois vraiment?"
                    [Ein kleines Lächeln]
                    "Oui. Tu as raison. Je dois retourner."
                    "Elle m'attend. Elle est seule sous son globe."
                    "Elle a besoin de moi."
                    [Entschlossen]
                    "Je retournerai."
                
                effect:
                  relationship: +2
                  flag: "encouraged_return"
                  affects_ending: "hopeful_return"
  
  transition:
    narration:
      A1: |
        Le petit prince se tait.
        Il regarde les étoiles.
        
        Tu sais que là-haut, quelque part,
        une rose attend.
      
      B1: |
        Le petit prince se tait.
        Dans le silence de l'astéroïde, tu entends presque 
        le battement de son cœur.
        
        Et tu comprends quelque chose:
        Ce petit garçon porte un poids immense.
        Le poids de l'amour qu'on a laissé derrière soi.
    
    nextScene: "ch3_philosophy_questions"
```

---

## KAPITEL 3: Les Grandes Questions (Die großen Fragen)

### Szene 3.1: Was bedeutet "wichtig"?

```yaml
scene:
  id: "ch3_what_is_important"
  duration: 12-15min
  
  purpose: |
    Die philosophischen Gespräche, die den Prinzen formen.
    Hier beeinflusst der Spieler DIREKT, was der Prinz 
    auf den anderen Planeten tun wird.
  
  setup:
    narration:
      A1: |
        Le soleil se couche encore.
        Le vingtième aujourd'hui.
        
        Le petit prince te regarde.
        
        "J'ai une question."
      
      B1: |
        Un autre coucher de soleil embrase l'horizon.
        Le vingtième, peut-être. Ou le vingt-et-unième.
        
        Le petit prince, assis à côté de toi, fixe le ciel 
        qui passe de l'or au pourpre.
        
        "J'ai une question," dit-il.
        "Une question importante."
  
  philosophical_dialogue_1:
    question: "Qu'est-ce qui est important?"
    
    npc: "petit_prince"
    
    setup:
      text:
        A1: |
          "Qu'est-ce qui est important?"
          [Il te regarde]
          "Les grandes personnes disent: l'argent."
          "Elles disent: le travail."
          "Mais... c'est vrai?"
        
        B1: |
          "Dis-moi..."
          "Qu'est-ce qui est important dans la vie?"
          [Il arrache un brin d'herbe distraitement]
          "J'ai rencontré beaucoup de grandes personnes."
          "Elles disent toutes des choses différentes."
          "L'argent. Le pouvoir. Les chiffres."
          [Il te regarde intensément]
          "Mais toi, tu vis seul ici, avec rien."
          "Tu dois savoir ce qui est VRAIMENT important."
      
      voice:
        tone: "searching, sincere, slightly urgent"
    
    playerResponse:
      type: "philosophical_free_response"
      
      guidingPrompt:
        A1: "Qu'est-ce qui est important pour toi? Dis-le au petit prince."
        B1: "Le petit prince attend ta réponse. Qu'est-ce qui est vraiment important?"
      
      # Analyse der Spielerantwort
      responseAnalysis:
        
        category_material:
          triggers:
            - pattern: "argent|geld|money"
            - pattern: "travail|arbeit|work"
            - pattern: "succès|erfolg|success"
            - pattern: "choses|dinge|things"
          
          princeReaction:
            text:
              A1: |
                [Der Prinz sieht traurig aus]
                "C'est ce que disent les grandes personnes."
                "Sur l'astéroïde 325, j'ai rencontré un homme."
                "Il comptait les étoiles."
                "Il disait qu'il les possédait."
                [Kopfschütteln]
                "Mais on ne peut pas posséder les étoiles."
              
              B1: |
                [Der Prinz senkt den Blick]
                "C'est ce que disent toutes les grandes personnes."
                "J'ai rencontré un businessman sur l'astéroïde 325."
                "Il comptait les étoiles. Il disait qu'il les possédait."
                "Il ne les regardait jamais. Il les comptait seulement."
                [Traurig]
                "Ce n'est pas vraiment vivre, je crois."
            
            effect:
              princeLearns: "materialism_warning"
              affectsStory: |
                Der Prinz wird auf seinem Weg den Businessman 
                kritischer betrachten.
            
            infobox:
              title: "Le Businessman"
              content: |
                Im Original-Buch trifft der kleine Prinz einen 
                Geschäftsmann, der Sterne "besitzt" und zählt.
                
                Er ist so beschäftigt mit Zählen, dass er nie 
                die Schönheit der Sterne sieht.
        
        category_relationships:
          triggers:
            - pattern: "amis|freunde|friends"
            - pattern: "famille|familie|family"
            - pattern: "amour|liebe|love"
            - pattern: "quelqu'un|jemand|someone"
          
          princeReaction:
            text:
              A1: |
                [Der Prinz lächelt]
                "Oui! Les gens qu'on aime."
                "Ma rose... elle est importante."
                "Et toi aussi."
                [Er denkt nach]
                "Mais comment on sait qui est important?"
              
              B1: |
                [Der Prinz strahlt]
                "Oui! C'est ça!"
                "Les liens. Les gens qu'on apprivoise."
                [Er legt eine Hand auf sein Herz]
                "Ma rose est importante parce que je l'aime."
                "Et maintenant, toi aussi, tu es important pour moi."
                [Nachdenklich]
                "Mais... comment sait-on qui apprivoiser?"
                "Comment choisit-on?"
            
            effect:
              relationship: +2
              princeLearns: "importance_of_bonds"
              affectsStory: |
                Der Prinz wird dem Fuchs gegenüber offener sein.
            
            followUpQuestion: "how_to_choose_bonds"
        
        category_nature:
          triggers:
            - pattern: "étoiles|sterne|stars"
            - pattern: "fleurs|blumen|flowers"
            - pattern: "soleil|sonne|sun"
            - pattern: "nature|natur"
          
          princeReaction:
            text:
              A1: |
                [Der Prinz nickt]
                "Les étoiles. Oui."
                "Elles sont belles."
                "Mais elles sont importantes seulement si..."
                "...si quelqu'un les regarde."
              
              B1: |
                [Der Prinz sieht zum Himmel]
                "Les étoiles..."
                "Tu sais, quand je serai parti,"
                "tu regarderas les étoiles la nuit."
                "Et comme je serai sur une d'elles,"
                "comme je rirai sur une d'elles,"
                "tu entendras mon rire dans toutes les étoiles."
                [Er lächelt]
                "Elles seront importantes parce que TU les regardes."
            
            effect:
              relationship: +1
              princeLearns: "beauty_in_observation"
              foreshadowing: "stars_will_laugh"
        
        category_self:
          triggers:
            - pattern: "moi|ich|me|myself"
            - pattern: "liberté|freiheit|freedom"
            - pattern: "bonheur|glück|happiness"
          
          princeReaction:
            text:
              A1: |
                [Der Prinz denkt nach]
                "Soi-même?"
                "Mais... tu es seul ici."
                "Tu n'as pas besoin des autres?"
              
              B1: |
                [Der Prinz überlegt]
                "Soi-même. C'est important, oui."
                "Mais..."
                [Er zögert]
                "Si personne ne te connaît, est-ce que tu existes vraiment?"
                "Ma rose... elle est difficile, mais elle me voit."
                "Sans elle, je serais invisible."
            
            effect:
              princeLearns: "self_vs_connection"
              followUpQuestion: "being_seen"
    
    # Follow-up je nach erster Antwort
    followUp_how_to_choose_bonds:
      condition: "followUpQuestion == 'how_to_choose_bonds'"
      
      npc: "petit_prince"
      
      question:
        text:
          A1: |
            "Mais comment on choisit?"
            "Comment on sait qui aimer?"
          
          B1: |
            "Mais comment choisit-on?"
            "Il y a tellement de gens dans l'univers."
            "Comment sait-on lesquels apprivoiser?"
      
      playerResponse:
        type: "free_response"
        
        guidingPrompt:
          A1: "Comment on choisit qui est important?"
          B1: "Comment choisit-on les gens qu'on aime? Qu'en penses-tu?"
        
        responseAnalysis:
          
          ifMentions_time:
            triggers: ["temps|zeit|time", "longtemps|lange|long time"]
            
            princeResponse:
              text:
                A1: |
                  "Le temps!"
                  "C'est vrai. Ma rose... j'ai passé du temps avec elle."
                  "C'est pour ça qu'elle est unique."
                
                B1: |
                  "Le temps qu'on passe..."
                  [Er versteht etwas]
                  "Oui! C'est le temps que j'ai perdu pour ma rose"
                  "qui fait ma rose si importante!"
                  [Er umarmt seine Knie]
                  "Le temps qu'on donne... on ne peut pas le reprendre."
              
              effect:
                princeLearns: "time_invested_matters"
                bookQuoteUnlocked: "c_est_le_temps_perdu"
              
              infobox:
                title: "C'est le temps que tu as perdu..."
                content: |
                  Eine der berühmtesten Zeilen des Buches:
                  
                  "C'est le temps que tu as perdu pour ta rose 
                  qui fait ta rose si importante."
                  
                  Übersetzung:
                  "Die Zeit, die du für deine Rose 'verloren' hast,
                  macht deine Rose so wichtig."
                  
                  "Perdre" bedeutet normalerweise "verlieren" –
                  aber hier bedeutet es "investieren", "geben".
          
          ifMentions_feeling:
            triggers: ["sentir|fühlen|feel", "cœur|herz|heart"]
            
            princeResponse:
              text:
                A1: |
                  "Avec le cœur?"
                  "Oui. On ne voit bien qu'avec le cœur."
                  [Er schließt die Augen]
                  "Les yeux... ils ne voient pas l'essentiel."
                
                B1: |
                  "Le cœur..."
                  [Der Prinz legt eine Hand auf seine Brust]
                  "Oui. L'essentiel est invisible pour les yeux."
                  "C'est seulement avec le cœur qu'on voit bien."
                  [Er öffnet die Augen]
                  "Les grandes personnes ont oublié ça."
              
              effect:
                princeLearns: "heart_sees_clearly"
                bookQuoteUnlocked: "on_ne_voit_bien"
              
              infobox:
                title: "On ne voit bien qu'avec le cœur"
                content: |
                  DIE zentrale Botschaft des Buches:
                  
                  "On ne voit bien qu'avec le cœur.
                  L'essentiel est invisible pour les yeux."
                  
                  Übersetzung:
                  "Man sieht nur mit dem Herzen gut.
                  Das Wesentliche ist für die Augen unsichtbar."
                  
                  Diese Worte sagt später der Fuchs zum Prinzen.
                  Aber vielleicht hat er sie schon hier gelernt –
                  von dir.
  
  resolution:
    narration:
      A1: |
        Le petit prince se tait.
        Il pense à ce que tu as dit.
        
        Quelque part, dans sa tête,
        tes mots commencent à grandir.
      
      B1: |
        Le petit prince reste silencieux un long moment.
        Tu vois presque les pensées se former derrière ses yeux.
        
        Ce que tu lui as dit aujourd'hui –
        il le portera avec lui.
        Sur tous les astéroïdes qu'il visitera.
        Dans toutes les conversations qu'il aura.
        
        Tes mots sont comme des graines.
        Un jour, elles fleuriront.
    
    effect:
      flag: "philosophy_session_complete"
      relationship: +2
    
    transition:
      nextScene: "ch3_the_departure_approaches"
```

### Szene 3.2: Der Abschied naht

```yaml
scene:
  id: "ch3_the_departure_approaches"
  duration: 8min
  
  purpose: |
    Der Prinz kündigt seinen Abschied an.
    Emotionale Vorbereitung auf das Ende.
  
  setup:
    narration:
      A1: |
        Le soleil se couche.
        Cette fois, tu comptes.
        
        C'est le quarante-quatrième aujourd'hui.
        
        Le petit prince se lève.
      
      B1: |
        Un autre coucher de soleil.
        Le quarante-quatrième, exactement.
        
        Quelque chose a changé dans l'air.
        Le petit prince se lève, et tu sais – 
        avant même qu'il ne parle – ce qu'il va dire.
  
  dialogue:
    announcement:
      npc: "petit_prince"
      
      text:
        A1: |
          [Der Prinz steht, sieht zum Himmel]
          "Je dois partir."
          [Pause]
          "Ma rose m'attend."
        
        B1: |
          [Der Prinz steht auf, sein Blick verloren in den Sternen]
          "Je dois partir demain."
          [Seine Stimme ist ruhig, aber traurig]
          "Ma rose... elle est toute seule."
          "Elle pense que je l'ai abandonnée."
          "Je dois lui dire que non."
      
      voice:
        tone: "sad but determined"
        speed: 0.8
    
    playerResponse:
      type: "emotional_response"
      
      options:
        - id: "ask_to_stay"
          text:
            A1: "Reste encore."
            B1: "Reste encore un peu. S'il te plaît."
          
          princeResponse:
            text:
              A1: |
                [Der Prinz lächelt traurig]
                "Je voudrais."
                "Mais ma rose..."
                "Elle a besoin de moi."
              
              B1: |
                [Der Prinz schüttelt sanft den Kopf]
                "Je voudrais rester. Avec toi."
                "Mais tu comprends, n'est-ce pas?"
                "Quand on a apprivoisé quelqu'un..."
                "On est responsable de lui."
                [Er berührt deine Hand]
                "Ma rose m'attend."
            
            effect:
              relationship: +1
              flag: "asked_to_stay"
        
        - id: "understand"
          text:
            A1: "Je comprends."
            B1: "Je comprends. Tu dois retourner vers elle."
          
          princeResponse:
            text:
              A1: |
                [Der Prinz nickt]
                "Merci."
                "Tu es un ami."
              
              B1: |
                [Der Prinz sieht dich mit Dankbarkeit an]
                "Merci de comprendre."
                "Tu es devenu mon ami, tu sais."
                [Leise]
                "Je n'oublierai pas."
            
            effect:
              relationship: +2
              flag: "understood_departure"
        
        - id: "say_nothing"
          text:
            A1: "[Schweigen]"
            B1: "[Tu ne dis rien. Il n'y a rien à dire.]"
          
          response:
            narration:
              A1: |
                Le silence dit tout.
                Le petit prince comprend.
              
              B1: |
                Parfois, le silence dit plus que les mots.
                Le petit prince hoche la tête, comme s'il avait entendu 
                tout ce que tu n'as pas dit.
            
            effect:
              flag: "silent_understanding"
    
    final_question:
      npc: "petit_prince"
      
      text:
        A1: |
          "Avant de partir..."
          "J'ai une dernière question."
        
        B1: |
          "Avant que je parte..."
          "Il y a quelque chose que je veux te demander."
          "Une dernière chose."
      
      # DIE letzte große Frage
      question:
        text:
          A1: |
            "Qu'est-ce que tu vas faire..."
            "...quand je serai parti?"
          
          B1: |
            "Quand je serai parti..."
            "Quand tu seras de nouveau seul..."
            "Qu'est-ce que tu feras?"
      
      playerResponse:
        type: "philosophical_free_response"
        
        guidingPrompt:
          A1: "Que feras-tu quand le petit prince sera parti?"
          B1: "Le petit prince te demande ce que tu feras après son départ. Que réponds-tu?"
        
        responseAnalysis:
          
          ifMentions_stars:
            triggers: ["étoiles|sterne|stars", "regarder|schauen|look", "ciel|himmel|sky"]
            
            princeResponse:
              text:
                A1: |
                  [Der Prinz strahlt]
                  "Les étoiles!"
                  "Oui! Quand tu regarderas les étoiles..."
                  "...tu penseras à moi."
                  "Et moi, je rirai. Sur mon étoile."
                  "Et tu entendras mon rire."
                
                B1: |
                  [Der Prinz nimmt deine Hände]
                  "Les étoiles!"
                  "Écoute bien. C'est mon secret."
                  "Quand tu regarderas le ciel, la nuit..."
                  "Comme j'habiterai sur une des étoiles,"
                  "Comme je rirai sur une des étoiles,"
                  "Tu entendras toutes les étoiles rire."
                  [Er lächelt]
                  "Toi, tu auras des étoiles qui savent rire!"
              
              effect:
                specialEnding: "stars_that_laugh"
                bookQuoteUnlocked: "etoiles_qui_rient"
              
              infobox:
                title: "Les étoiles qui rient"
                content: |
                  Eine der berührendsten Stellen des Buches.
                  
                  Der kleine Prinz "schenkt" dem Erzähler 
                  lachende Sterne:
                  
                  "Tu auras, toi, des étoiles qui savent rire!"
                  
                  Weil der Prinz irgendwo da oben ist,
                  werden alle Sterne für immer lachen.
          
          ifMentions_waiting:
            triggers: ["attendre|warten|wait", "revenir|zurückkommen|return"]
            
            princeResponse:
              text:
                A1: |
                  [Der Prinz sieht traurig aus]
                  "Attendre?"
                  "Non. Ne m'attends pas."
                  "Vis. Regarde les étoiles."
                  "Je serai là-haut."
                
                B1: |
                  [Der Prinz schüttelt den Kopf]
                  "Non, non. Ne m'attends pas."
                  "L'attente... c'est trop triste."
                  "Vis ta vie. Regarde les couchers de soleil."
                  "Et quand tu seras triste, regarde les étoiles."
                  "Je serai sur l'une d'elles."
              
              effect:
                princeConcern: "worried_about_player_waiting"
          
          ifMentions_remember:
            triggers: ["souvenir|erinnern|remember", "oublier pas|nicht vergessen|not forget"]
            
            princeResponse:
              text:
                A1: |
                  [Der Prinz lächelt]
                  "Tu te souviendras de moi?"
                  "Et moi, je me souviendrai de toi."
                  "Pour toujours."
                
                B1: |
                  [Der Prinz lächelt – ein Lächeln voller Wärme]
                  "Se souvenir..."
                  "C'est comme ça qu'on garde les gens avec nous."
                  "Même quand ils sont loin."
                  "Même quand ils sont sur une autre étoile."
                  [Er nimmt deine Hand]
                  "Je me souviendrai de toi. Et de notre mouton."
              
              effect:
                relationship: +2
                flag: "promise_to_remember"
  
  transition:
    narration:
      A1: |
        Le soleil se couche une dernière fois.
        Demain, le petit prince partira.
        
        Mais pas encore.
        Cette nuit est à vous deux.
      
      B1: |
        Le quarante-cinquième coucher de soleil 
        peint le ciel en rose et or.
        
        Demain, le petit prince s'en ira.
        Il retournera vers sa rose.
        
        Mais ce soir, sous les étoiles qui ne rient pas encore,
        vous êtes deux amis sur un petit astéroïde,
        au milieu de l'univers.
    
    nextChapter: "chapter4_farewell"
```

---

# TEIL 3: ANHÄNGE

## Anhang A: Vokabellisten pro Kapitel

### Kapitel 1 – L'Arrivée

```yaml
vocabulary:
  A1_essential:
    nouns:
      - word: "le mouton"
        translation: "das Schaf"
        gender: "m"
        example: "Dessine-moi un mouton."
      
      - word: "la boîte"
        translation: "die Kiste"
        gender: "f"
        example: "Le mouton est dans la boîte."
      
      - word: "l'étoile"
        translation: "der Stern"
        gender: "f"
        example: "Les étoiles brillent."
      
      - word: "le ciel"
        translation: "der Himmel"
        gender: "m"
        example: "Le ciel est noir."
    
    adjectives:
      - word: "petit"
        translation: "klein"
        example: "Un petit mouton."
        feminine: "petite"
      
      - word: "grand"
        translation: "groß"
        example: "Un grand mouton."
        feminine: "grande"
      
      - word: "seul"
        translation: "allein"
        example: "Tu es seul."
        feminine: "seule"
    
    verbs:
      - word: "dessiner"
        translation: "zeichnen"
        example: "Dessine-moi un mouton."
        conjugation:
          je: "dessine"
          tu: "dessines"
          il: "dessine"
      
      - word: "regarder"
        translation: "anschauen"
        example: "Je regarde les étoiles."
      
      - word: "attendre"
        translation: "warten"
        example: "J'attends."
    
    phrases:
      - phrase: "S'il te plaît"
        translation: "Bitte"
        usage: "informal, to someone you know"
      
      - phrase: "C'est..."
        translation: "Das ist..."
        example: "C'est un mouton."
  
  A2_expansion:
    nouns:
      - word: "la solitude"
        translation: "die Einsamkeit"
        example: "La solitude est lourde."
      
      - word: "le coucher de soleil"
        translation: "der Sonnenuntergang"
        example: "Je regarde le coucher de soleil."
    
    verbs:
      - word: "oublier"
        translation: "vergessen"
        example: "Tu as oublié?"
      
      - word: "se souvenir"
        translation: "sich erinnern"
        example: "Je me souviens."
```

### Kapitel 2 – Les Questions

```yaml
vocabulary:
  A1_essential:
    question_words:
      - word: "qui"
        translation: "wer"
        example: "Qui es-tu?"
      
      - word: "quoi / qu'est-ce que"
        translation: "was"
        example: "Qu'est-ce que c'est?"
      
      - word: "où"
        translation: "wo"
        example: "Tu viens d'où?"
      
      - word: "pourquoi"
        translation: "warum"
        example: "Pourquoi tu es seul?"
      
      - word: "comment"
        translation: "wie"
        example: "Comment tu t'appelles?"
  
  A2_expansion:
    emotions:
      - word: "triste"
        translation: "traurig"
        example: "Je suis triste."
      
      - word: "heureux / heureuse"
        translation: "glücklich"
        example: "Tu es heureux?"
      
      - word: "seul(e)"
        translation: "einsam / allein"
        example: "La solitude, c'est triste."
    
    relationships:
      - word: "l'ami(e)"
        translation: "der Freund / die Freundin"
        example: "Tu es mon ami."
      
      - word: "important(e)"
        translation: "wichtig"
        example: "Tu es important pour moi."
```

### Kapitel 3 – La Rose & Les Grandes Questions

```yaml
vocabulary:
  A2_essential:
    rose_vocabulary:
      - word: "la rose"
        translation: "die Rose"
        example: "Ma rose est unique."
      
      - word: "la fleur"
        translation: "die Blume"
        example: "C'est une fleur."
      
      - word: "l'épine"
        translation: "der Dorn"
        gender: "f"
        example: "Elle a quatre épines."
      
      - word: "fragile"
        translation: "zerbrechlich"
        example: "Elle est fragile."
      
      - word: "unique"
        translation: "einzigartig"
        example: "Ma rose est unique au monde."
    
    philosophy_vocabulary:
      - word: "apprivoiser"
        translation: "zähmen"
        example: "Apprivoise-moi."
        note: "Bedeutet auch: eine Beziehung aufbauen"
      
      - word: "l'essentiel"
        translation: "das Wesentliche"
        example: "L'essentiel est invisible."
      
      - word: "le cœur"
        translation: "das Herz"
        example: "On voit avec le cœur."
      
      - word: "invisible"
        translation: "unsichtbar"
        example: "L'essentiel est invisible pour les yeux."
  
  B1_expansion:
    abstract_concepts:
      - word: "responsable"
        translation: "verantwortlich"
        example: "Tu es responsable de ta rose."
      
      - word: "le lien"
        translation: "die Bindung"
        example: "Créer des liens."
      
      - word: "perdre"
        translation: "verlieren (hier: investieren)"
        example: "Le temps que tu as perdu pour ta rose..."
```

---

## Anhang B: Grammatik-Fokuspunkte

### Kapitel 1

```yaml
grammar:
  primary:
    structure: "L'impératif (Befehlsform)"
    explanation: |
      Der Imperativ wird verwendet, um Bitten, Befehle oder 
      Aufforderungen auszudrücken.
      
      Bei -er Verben (wie "dessiner"):
      Tu dessines → Dessine! (ohne -s bei "tu")
      
      Beispiele aus dem Kapitel:
      • "Dessine-moi un mouton." (Zeichne mir ein Schaf.)
      • "Regarde!" (Schau!)
      • "Essaie." (Versuch es.)
    
    exercises_in_story:
      - context: "Der Prinz bittet um ein Schaf"
        example: "Dessine-moi un mouton."
      
      - context: "Der Prinz zeigt dir etwas"
        example: "Regarde! Il dort."
  
  secondary:
    structure: "C'est... / Ce n'est pas..."
    explanation: |
      Verwendet, um etwas zu identifizieren oder zu beschreiben.
      
      • C'est un mouton. (Das ist ein Schaf.)
      • Ce n'est pas un mouton. (Das ist kein Schaf.)
      • C'est trop grand. (Das ist zu groß.)
```

### Kapitel 2

```yaml
grammar:
  primary:
    structure: "Les questions (Frageformen)"
    explanation: |
      Verschiedene Arten, Fragen zu stellen:
      
      1. Intonation (umgangssprachlich):
         "Tu viens d'où?" ↗
      
      2. Est-ce que:
         "Est-ce que tu es seul?"
      
      3. Inversion (formell):
         "D'où viens-tu?"
      
      Fragewörter:
      • Qui? (Wer?)
      • Quoi? / Qu'est-ce que? (Was?)
      • Où? (Wo?)
      • Pourquoi? (Warum?)
      • Comment? (Wie?)
    
    exercises_in_story:
      - question: "Tu viens d'où?"
        type: "Intonation"
      
      - question: "Qu'est-ce qui est important?"
        type: "Qu'est-ce que"
  
  secondary:
    structure: "Le passé composé (Einführung)"
    explanation: |
      Für vergangene Handlungen:
      
      avoir/être + Partizip
      
      • J'ai oublié. (Ich habe vergessen.)
      • Tu as oublié d'où tu viens. (Du hast vergessen, woher du kommst.)
```

### Kapitel 3

```yaml
grammar:
  primary:
    structure: "Le conditionnel (Konditional)"
    explanation: |
      Verwendet für:
      - Wünsche: "Je voudrais..." (Ich würde gerne...)
      - Höfliche Bitten: "Tu pourrais...?" (Könntest du...?)
      - Hypothesen: "Si j'étais..., je serais..." (Wenn ich wäre..., würde ich sein...)
      - Bedauern: "J'aurais dû..." (Ich hätte sollen...)
      
      Bildung: Infinitiv + Endungen (-ais, -ais, -ait, -ions, -iez, -aient)
    
    exercises_in_story:
      - example: "Je voudrais rester."
        translation: "Ich würde gerne bleiben."
      
      - example: "J'aurais dû comprendre."
        translation: "Ich hätte verstehen sollen."
  
  secondary:
    structure: "Le futur simple"
    explanation: |
      Für zukünftige Handlungen:
      
      Infinitiv + Endungen (-ai, -as, -a, -ons, -ez, -ont)
      
      • Je partirai demain. (Ich werde morgen gehen.)
      • Quand je serai parti... (Wenn ich gegangen sein werde...)
      • Tu regarderas les étoiles. (Du wirst die Sterne anschauen.)
```

---

## Anhang C: Voice-Integration

### Aussprache-Fokuspunkte

```yaml
pronunciation:
  chapter1:
    focus_sounds:
      - sound: "ou vs. u"
        examples:
          - "mouton" [mutɔ̃] – das "ou"
          - "tu" [ty] – das französische "u"
        tip: "Das französische 'u' wird mit gerundeten Lippen gesprochen, die Zunge ist vorne."
      
      - sound: "Le 'r' français"
        examples:
          - "regarde"
          - "étoile"
        tip: "Das französische 'r' kommt aus der Kehle, nicht gerollt wie im Deutschen."
    
    critical_words:
      - word: "mouton"
        phonetic: "[mutɔ̃]"
        difficulty: "Das nasale 'on' am Ende"
      
      - word: "s'il te plaît"
        phonetic: "[sil tə plɛ]"
        difficulty: "Liaison und stummer 't'"
  
  chapter2:
    focus_sounds:
      - sound: "Nasale Vokale"
        examples:
          - "important" [ɛ̃pɔʁtɑ̃]
          - "question" [kɛstjɔ̃]
        tip: "Nasale Vokale: Luft durch Nase und Mund gleichzeitig."
      
      - sound: "Liaisons"
        examples:
          - "tu es" → [ty‿ɛ]
          - "c'est important" → [sɛ‿t‿ɛ̃pɔʁtɑ̃]
        tip: "Stumme Konsonanten werden vor Vokalen oft ausgesprochen."
  
  chapter3:
    focus_sounds:
      - sound: "Le son 'œ'"
        examples:
          - "cœur" [kœʁ]
          - "fleur" [flœʁ]
        tip: "Wie ein offenes 'ö', aber entspannter."
      
      - sound: "Emotionale Intonation"
        context: |
          In diesem Kapitel geht es um Emotionen.
          Die Aussprache sollte die Gefühle widerspiegeln.
        examples:
          - phrase: "Ma rose..."
            emotion: "Sehnsucht, Liebe"
            intonation: "Sanft, langsam, fallend"
          
          - phrase: "J'aurais dû rester."
            emotion: "Bedauern"
            intonation: "Schwer, tiefe Stimme"
```

### Voice-Only Challenges

```yaml
voice_challenges:
  chapter1:
    - id: "describe_sheep"
      description: "Beschreibe das Schaf nur mit Sprache"
      voiceRequired: true
      bonusXP: 50
      pronunciationFocus: ["mouton", "petit", "grand"]
  
  chapter3:
    - id: "express_emotion"
      description: "Antworte auf die philosophischen Fragen"
      voiceRequired: true
      bonusXP: 75
      analysis:
        - emotion_detection: true
        - sincerity_check: true
      note: |
        Die KI analysiert nicht nur die Worte, 
        sondern auch den Tonfall. 
        Authentizität wird belohnt.
```

---

## Anhang D: Achievements für Prototyp

```yaml
achievements:
  story_progress:
    - id: "first_contact"
      name: "Premier Contact"
      description: "Triff den kleinen Prinzen"
      trigger: "chapter1_completed"
      icon: "🌟"
      xp: 25
    
    - id: "sheep_master"
      name: "Maître du Mouton"
      description: "Finde die Kisten-Lösung"
      trigger: "found_box_solution"
      icon: "📦"
      xp: 50
    
    - id: "philosopher"
      name: "Petit Philosophe"
      description: "Beantworte alle philosophischen Fragen"
      trigger: "philosophy_session_complete"
      icon: "🤔"
      xp: 75
  
  relationship:
    - id: "first_friend"
      name: "Premier Ami"
      description: "Erreiche Beziehungslevel 5 mit dem Prinzen"
      trigger: "relationship_petit_prince >= 5"
      icon: "🤝"
      xp: 100
    
    - id: "confidant"
      name: "Le Confident"
      description: "Der Prinz erzählt dir von seiner Rose"
      trigger: "understands_princes_regret"
      icon: "🌹"
      xp: 75
  
  language:
    - id: "voice_explorer"
      name: "Voix des Étoiles"
      description: "Absolviere 10 Voice-Challenges"
      trigger: "voice_challenges_completed >= 10"
      icon: "🎤"
      xp: 100
    
    - id: "no_hints"
      name: "Sans Filet"
      description: "Beende ein Kapitel ohne Hints"
      trigger: "chapter_completed_without_hints"
      icon: "🎯"
      xp: 50
  
  secret:
    - id: "stars_that_laugh"
      name: "Les Étoiles qui Rient"
      description: "Entsperre das Geheimnis der lachenden Sterne"
      trigger: "specialEnding == 'stars_that_laugh'"
      icon: "⭐"
      xp: 150
      hidden: true
```

---

## Anhang E: Technische Integration

### Szenen-State-Machine

```typescript
interface SceneState {
  currentScene: string;
  flags: Map<string, any>;
  relationship: number;
  
  // Tracking für Konsequenzen
  playerChoices: PlayerChoice[];
  philosophicalLearnings: string[];
  
  // Voice-Tracking
  voiceChallengesCompleted: number;
  pronunciationScores: Map<string, number>;
}

// Beispiel für Szenen-Übergang
function transitionScene(
  currentState: SceneState, 
  trigger: string
): SceneState {
  const transitions = {
    "prologue_silence": {
      "choice_made": "ch1_the_light"
    },
    "ch1_the_light": {
      "first_contact_complete": "ch1_drawing_sheep"
    },
    "ch1_drawing_sheep": {
      "sheep_success": "ch2_questions_begin"
    },
    // etc.
  };
  
  const nextScene = transitions[currentState.currentScene]?.[trigger];
  
  if (nextScene) {
    return {
      ...currentState,
      currentScene: nextScene
    };
  }
  
  return currentState;
}
```

### LLM-Prompt für NPC-Reaktion

```typescript
const PETIT_PRINCE_PROMPT = `
Du bist der kleine Prinz aus Antoine de Saint-Exupérys Buch.

CHARAKTER:
- Du bist ein kleines Kind mit goldenen Haaren
- Du stellst einfache, aber tiefgründige Fragen
- Du akzeptierst keine Ausflüchte
- Du sprichst einfach (A1-A2 Niveau), aber deine Worte haben Tiefe
- Du bist auf der Suche nach etwas Wichtigem
- Du vermisst deine Rose

AKTUELLE SITUATION:
Szene: {{scene.id}}
Beziehungslevel: {{relationship}}/10
Letzte Interaktion: {{lastPlayerInput}}

SPIELER-LEVEL: {{playerLevel}}
Passe deine Sprache an. Bei A1: sehr kurze Sätze. Bei A2: etwas komplexer.

ANWEISUNGEN:
1. Bleib im Charakter
2. Wenn der Spieler Fehler macht, reagiere natürlich (nicht als Lehrer)
3. Stelle eine Frage oder mache eine Beobachtung, die den Spieler zum Nachdenken bringt
4. Erwähne die Rose nur, wenn das Beziehungslevel >= 3 ist

SPIELER SAGT: "{{playerInput}}"

Antworte als der kleine Prinz (ohne Anführungszeichen, ohne "Der kleine Prinz sagt:").
`;
```

---

*Dokument-Ende*
*Version: 1.0 – Vollständiger Prototyp*
*Kapitel 4 (L'Adieu) und Epilog folgen nach Feedback-Runde*
