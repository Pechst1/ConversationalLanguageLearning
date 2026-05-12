# Feature Ideas Backlog

## High Priority (Future)

### Unified SRS System
> Goal: User completes all due cards (vocab + grammar + conversation errors) within 1hr of daily practice

- Create abstract `LearningItem` model spanning vocab, grammar concepts, and conversation errors
- Single `/daily-practice` page showing total due items
- Intelligent scheduling that balances different learning types
- Time tracking and pacing suggestions

### Voice Input for Answers
- Add microphone button next to each answer field
- Use Whisper API (already integrated for conversations) to transcribe
- Benefits: Pronunciation practice, faster input, more natural
- Show both transcription and allow editing before submit

### French-Only Interface (B2+)
- Detect user level from progress
- Switch UI language to French for immersion
- Keep German tooltips on hover for support

### Daily News Chat Integration
- Integrate LLM with internet search capabilities (or news summarization) (maybe there is a suitable API for that?)
- Allow users to discuss current daily news events in French
- **Goal**: Enable learning through topics of personal interest and real-world relevance

### Atelier Graphic Novel Mode
> Goal: Add an optional visual reading/exercise mode that turns current French or Paris news into an Atelier-style illustrated grammar scene.

- Working name: `IV · Feuilleton` or `Illustrated Reading`
- Use a sourced France/Paris news fragment as context, then fictionalize the scene when needed to avoid misleading depictions of real people/events
- Generate 4-6 graphic-novel panels in the existing Atelier/Bauhaus/editorial design language
- Do not rely on the image model for exercise text, blanks, or answer controls
- Generate image panels as visual context, then overlay speech bubbles, cloze blanks, choices, and correction UI as HTML/SVG for accessibility, responsiveness, and reliable checking
- Select content from the user's due grammar concepts, due errata, and weak vocabulary items
- Possible tasks:
  - fill missing verb forms inside dialogue
  - choose the right pronoun/article/tense in a speech bubble
  - repair one panel's sentence
  - read the scene and answer one short production prompt
- Integrate with Atelier SRS:
  - closed items use deterministic checking
  - open repairs use Atelier correction schema
  - grammar mistakes become errata
  - lexical mistakes link to vocabulary progress
- Cache generated scripts and images by source story, concept set, model, and prompt version to control cost and latency
- Best placement: after the core Atelier flow is reliable, either as an optional post-recap exercise or a once-per-session enrichment mode

### Audio-Only Conversation Mode
- "Talking Only" mode where AI text is hidden
- User must rely solely on auditory comprehension
- ElevenLabs has a feature for that, check it out, evaluate the costs and benefits.
- **Visuals**: Text is revealed only when user speaks and for error correction
- **Goal**: Force improvement of listening skills and auditory processing

## Medium Priority

### Adaptive Difficulty
- Track success rate per exercise type
- Automatically adjust complexity based on performance
- Skip easy levels if user consistently scores 9-10

### Spaced Grammar Integration
- Link grammar errors from conversations to specific concepts
- Auto-schedule concept review when errors occur
- Show "This concept is weak" indicators

## Research-Backed Feature Candidates (May 2026)

Evidence notes:
- User research on mobile-assisted language learning repeatedly points to gaps in speaking/communication, writing, grammar practice, offline/review support, cultural/news content, and cumulative diagnosis of learner problems.
- Review sentiment around Duolingo/Babbel commonly praises convenience and motivation, while negative feedback clusters around redundancy, shallow depth, pricing, and weak personalization.
- Cognitive learning research gives the strongest support to retrieval practice and distributed practice; corrective feedback in SLA shows durable value when it is specific enough to guide repair.
- Current major apps already cover parts of this space: Duolingo Max has AI roleplay/video calls and Babbel has spaced vocabulary review plus Babbel Speak. The opportunity for Atelier is tighter integration: every correction becomes a scheduled, explainable future learning item across grammar, vocabulary, writing, and speech.

### Error Memory Across All Modes
> Goal: Make every meaningful mistake trainable again, not just visible once.

- Persist grammar, vocabulary, pronunciation, and task-compliance mistakes as first-class review items
- Show why an item reappears: e.g. `Pronoun choice: en -> la`, `tenir vs soutenir`, `background vs event`
- Route each erratum into the right future format: recognition, transform, conversation, writing, or listening
- Let users mark an erratum repaired after a targeted review
- Highest fit: Atelier Today queue, Atelier recap, conversation feedback, vocabulary progress

### Guided Output Ladder
> Goal: Solve the common app problem where users can understand exercises but cannot produce language.

- Add a sequence from constrained output to free output:
  - choose/fill
  - guided rewrite
  - sentence from prompt
  - short paragraph
  - spoken answer
  - conversation
- Offer hints only on request, so learners still retrieve actively
- Score both accuracy and communicative adequacy
- Highest fit: Atelier Transform + Produce, conversation prep, audio-only mode

### Explainable Grammar Notebook
> Goal: Replace scattered explanations with a personal grammar memory.

- Build a user-specific grammar notebook from concepts, examples, own mistakes, and repaired errata
- Each rule page should include:
  - short rule
  - when to use it
  - contrast against nearby rules
  - user's own past mistakes
  - next due review
- Highest fit: `/grammar` as concept/catalog/reference view, linked from Atelier corrections

### Real-World Scenario Missions
> Goal: Move from isolated drills to task-based use.

- Create small missions around concrete goals:
  - ask for help at a station
  - explain a plan change
  - summarize a news item
  - write a message to a landlord
- Missions should pull in due vocabulary and grammar concepts
- Highest fit: after Atelier session or as a separate weekly practice mode

### Personal Input Feed
> Goal: Increase reading/listening time without losing SRS targeting.

- Generate or import short texts/audio around topics the user cares about
- Highlight due grammar and vocabulary in context
- Add one or two retrieval prompts after reading/listening
- Highest fit: news chat, graphic-novel mode, story/audio features

### Pronunciation + Prosody Repair
> Goal: Go beyond speech recognition and train the sounds that block communication.

- Store pronunciation slips as reviewable items
- Compare target and learner audio at word/phrase level
- Practice minimal pairs, liaison, rhythm, and intonation
- Highest fit: audio-only mode and conversation recap
