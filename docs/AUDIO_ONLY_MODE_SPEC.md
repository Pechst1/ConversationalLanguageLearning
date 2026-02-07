# 🎧 Audio-Only Mode: Refined Design

## Core Philosophy
> "One tap, 5 minutes of engaging French practice. Zero decisions."

## Status
- **Phase 1 (UI Foundation)**: ✅ In Progress
  - Hide AI text by default in listening mode
  - Reveal button + auto-reveal when user responds
  - Replay audio button
- **Phase 2 (Smart Context)**: 🔲 Planned
- **Phase 3 (Search LLM)**: 🔲 Planned
- **Phase 4 (Variety Engine)**: 🔲 Planned

---

## Smart Auto-Context Signals

| Signal | How It's Used |
|--------|---------------|
| User's past errors | AI crafts sentences that naturally require the grammar the user struggles with. If they nail it now → SRS rating improves automatically. |
| User interests (via search LLM) | "Tu as vu les nouvelles sur Tesla?" – conversation touches real, current topics the user cares about. |
| Recent vocabulary | New words from last session are woven into AI's speech. |
| Time of day | Morning: café/news discussion. Evening: reflection on the day. |
| Conversation history | Ensures variety – won't repeat the same scenario within 5 sessions. |

---

## Error Weaving (Natural, Not Didactic)

Instead of: "You made a subjunctive error. Let's practice."

The AI naturally creates contexts forcing correct usage:

**User struggled with: passé composé vs imparfait**

AI says:
```
"Hier, je marchais dans la rue quand j'ai vu quelque chose 
d'incroyable. Et toi, qu'est-ce que tu faisais hier soir?"
```

**Tracking:** If user responds correctly → backend updates the error's SRS rating positively. If they fail → rating adjusts downward, error reappears sooner.

---

## Interest-Driven Conversations (Search LLM)

### Before session starts (async, ~1s):
- Quick search query based on user profile: "latest news [user interest: tech, football, cooking...]"
- Result feeds into AI's context

### During conversation:
- AI can reference real facts: "J'ai lu que Apple vient de sortir..."
- Makes conversation feel current and personal

**Tech approach:** Perplexity API or OpenAI with web search tool. Cached for cost efficiency.

---

## Never Boring: Variety + Personality Engine

### Conversation Styles (rotated automatically):
1. **Casual chat** – Like talking to a French friend
2. **Curious interviewer** – AI asks about YOUR life/opinions
3. **Playful debate** – AI gently disagrees to provoke reasoning
4. **Storytelling** – AI starts a story, user continues

### Personality Traits:
- Slight humor, not robotic
- Occasionally expresses opinions
- Asks follow-up questions based on user's response
- Can say "Je ne suis pas d'accord, pourquoi tu penses ça?"

### Variety Rules:
- No topic category repeated within 3 sessions
- Different conversation style every session
- AI "remembers" things from previous conversations

---

## Technical Architecture (Simplified)

```
┌─────────────────────────────────────────────────────┐
│  User taps "🎧 Écoute Active"                       │
└──────────────────┬──────────────────────────────────┘
                   ▼
┌─────────────────────────────────────────────────────┐
│  1. Fetch user context (errors, interests, history) │
│  2. Search LLM: get current topic from interests    │
│  3. Generate opening prompt with error targets      │
└──────────────────┬──────────────────────────────────┘
                   ▼
┌─────────────────────────────────────────────────────┐
│  AI speaks (ElevenLabs TTS)                         │
│  → Pre-buffer first response for instant start      │
└──────────────────┬──────────────────────────────────┘
                   ▼
┌─────────────────────────────────────────────────────┐
│  User speaks (Whisper transcription)                │
│  → Error detection in background                    │
│  → If error relates to past mistake → update SRS    │
└──────────────────┬──────────────────────────────────┘
                   ▼
┌─────────────────────────────────────────────────────┐
│  Loop for ~5 min, then natural wrap-up              │
│  "C'était super de parler avec toi. À demain!"     │
└─────────────────────────────────────────────────────┘
```

---

## Session Flow

| Time | What Happens |
|------|--------------|
| 0:00 | AI greets + sets scene based on auto-context |
| 0:30 | Conversation flows, AI weaves in target grammar |
| 2:30 | AI naturally pivots to a new angle or topic |
| 4:30 | AI starts winding down "Bon, je dois bientôt y aller..." |
| 5:00 | Clean exit OR user says "on continue" → extends 3 min |

---

## Key Differentiators from Current Conversation Mode

| Current Mode | Audio-Only Mode |
|--------------|-----------------|
| User picks topic, duration | Zero decisions |
| Text + Audio | Audio only (text on demand) |
| Generic prompts | Personalized via interests + search |
| Errors flagged after | Errors woven into conversation naturally |
| Static difficulty | Adapts based on real-time performance |

---

## Implementation Phases

### Phase 1: UI Foundation ✅ In Progress
- [x] Add `isAudioOnlyMode` to SpeakingModeContext
- [x] Create HiddenMessage component with blur effect
- [x] Add "Listening Mode" toggle button
- [x] Auto-reveal when user responds
- [x] Replay audio button
- [ ] Test and polish UI

### Phase 2: Smart Context Engine
- [ ] Add user interests model in backend
- [ ] Integrate error history into session prompts
- [ ] Time-of-day based greeting/topics
- [ ] Session variety tracking (prevent repeats)

### Phase 3: Search LLM Integration
- [ ] Research API options (Perplexity, OpenAI web search)
- [ ] Implement interest-based news fetching
- [ ] Cache layer for cost efficiency
- [ ] Inject current events into AI context

### Phase 4: Variety & Personality Engine
- [ ] Define conversation style templates
- [ ] Implement style rotation logic
- [ ] Add personality traits to system prompts
- [ ] Cross-session memory for continuity

### Phase 5: Timed Sessions
- [ ] 5-minute session timer
- [ ] Natural wrap-up prompts
- [ ] "Continue" option for session extension
- [ ] Session summary at completion
