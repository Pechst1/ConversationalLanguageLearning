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
- Integrate LLM with internet search capabilities (or news summarization)
- Allow users to discuss current daily news events in French
- **Goal**: Enable learning through topics of personal interest and real-world relevance

### Audio-Only Conversation Mode
- "Talking Only" mode where AI text is hidden
- User must rely solely on auditory comprehension
- **Visuals**: Text is revealed only when user speaks or for error correction
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
