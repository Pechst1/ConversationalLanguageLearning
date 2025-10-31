export interface WordStatus {
  word: string;
  mastered: boolean;
  attempts: number;
  lastSeen: Date;
  difficulty: 'easy' | 'medium' | 'hard';
  addedAt: Date;
}

export interface LearnerSettings {
  mode: 'new_words' | 'mixed' | 'heavy_repetition';
  maxWordsPerSession: number;
  difficultyPreference: 'adaptive' | 'easy' | 'medium' | 'hard';
}

export interface VocabularyUpdate {
  newWords: string[];
  updatedStatuses: WordStatus[];
  wordsToRemove: string[];
}

export class VocabularyManager {
  private wordStatuses: Map<string, WordStatus> = new Map();
  private currentProposals: string[] = [];
  private usedWordsInSession: Set<string> = new Set();
  private wordPool: string[] = [];

  constructor(
    private settings: LearnerSettings,
    initialWordPool: string[] = [],
    existingStatuses: WordStatus[] = []
  ) {
    this.wordPool = [...initialWordPool];
    existingStatuses.forEach(status => {
      this.wordStatuses.set(status.word, status);
    });
  }

  /**
   * Generate new word proposals based on learner settings and current session state
   */
  generateProposals(): string[] {
    const { mode, maxWordsPerSession } = this.settings;
    let candidates: string[] = [];

    switch (mode) {
      case 'new_words':
        candidates = this.getNewWords();
        break;
      case 'mixed':
        candidates = this.getMixedWords();
        break;
      case 'heavy_repetition':
        candidates = this.getRepetitionWords();
        break;
    }

    // Filter out words already used in this session
    candidates = candidates.filter(word => !this.usedWordsInSession.has(word));

    // Limit to max words per session
    const newProposals = candidates.slice(0, maxWordsPerSession);
    
    // Keep unused proposals from previous round
    const unusedProposals = this.currentProposals.filter(
      word => !this.usedWordsInSession.has(word)
    );

    // Combine unused proposals with new ones
    const combinedProposals = [...unusedProposals, ...newProposals]
      .slice(0, maxWordsPerSession);

    this.currentProposals = combinedProposals;
    return this.currentProposals;
  }

  /**
   * Mark words as used and update their status
   */
  markWordsAsUsed(words: string[], successful: boolean = true): void {
    words.forEach(word => {
      this.usedWordsInSession.add(word);
      
      const status = this.wordStatuses.get(word) || {
        word,
        mastered: false,
        attempts: 0,
        lastSeen: new Date(),
        difficulty: 'medium' as const,
        addedAt: new Date(),
      };

      status.attempts += 1;
      status.lastSeen = new Date();
      
      if (successful) {
        // Improve difficulty if consistently successful
        if (status.attempts >= 3 && status.difficulty === 'hard') {
          status.difficulty = 'medium';
        } else if (status.attempts >= 5 && status.difficulty === 'medium') {
          status.difficulty = 'easy';
        } else if (status.attempts >= 7 && status.difficulty === 'easy') {
          status.mastered = true;
        }
      } else {
        // Increase difficulty if struggling
        if (status.difficulty === 'easy') {
          status.difficulty = 'medium';
        } else if (status.difficulty === 'medium') {
          status.difficulty = 'hard';
        }
      }

      this.wordStatuses.set(word, status);
    });
  }

  /**
   * Process a conversation turn and extract vocabulary
   */
  processConversationTurn(userMessage: string, aiMessage: string): VocabularyUpdate {
    const userWords = this.extractWords(userMessage);
    const aiWords = this.extractWords(aiMessage);
    
    // Mark user words as used (they practiced them)
    this.markWordsAsUsed(userWords, true);
    
    // Add new words from AI message to word pool if they're not known
    const newWords = aiWords.filter(word => 
      !this.wordStatuses.has(word) && 
      !this.wordPool.includes(word) &&
      word.length > 2 // Filter out very short words
    );
    
    this.wordPool.push(...newWords);
    
    // Generate new proposals for next turn
    const updatedProposals = this.generateProposals();
    
    return {
      newWords: updatedProposals,
      updatedStatuses: Array.from(this.wordStatuses.values()),
      wordsToRemove: [], // Could implement logic to remove mastered words
    };
  }

  /**
   * Get current word proposals
   */
  getCurrentProposals(): string[] {
    return this.currentProposals;
  }

  /**
   * Get word status
   */
  getWordStatus(word: string): WordStatus | undefined {
    return this.wordStatuses.get(word);
  }

  /**
   * Update learner settings
   */
  updateSettings(newSettings: Partial<LearnerSettings>): void {
    this.settings = { ...this.settings, ...newSettings };
  }

  /**
   * Reset session state (call at start of new session)
   */
  resetSession(): void {
    this.usedWordsInSession.clear();
    this.currentProposals = this.generateProposals();
  }

  private getNewWords(): string[] {
    return this.wordPool.filter(word => !this.wordStatuses.has(word));
  }

  private getMixedWords(): string[] {
    const newWords = this.getNewWords();
    const reviewWords = this.getReviewWords();
    
    // 70% new words, 30% review words
    const newWordCount = Math.ceil(this.settings.maxWordsPerSession * 0.7);
    const reviewWordCount = this.settings.maxWordsPerSession - newWordCount;
    
    return [
      ...newWords.slice(0, newWordCount),
      ...reviewWords.slice(0, reviewWordCount),
    ];
  }

  private getRepetitionWords(): string[] {
    const reviewWords = this.getReviewWords();
    const newWords = this.getNewWords();
    
    // 80% review words, 20% new words
    const reviewWordCount = Math.ceil(this.settings.maxWordsPerSession * 0.8);
    const newWordCount = this.settings.maxWordsPerSession - reviewWordCount;
    
    return [
      ...reviewWords.slice(0, reviewWordCount),
      ...newWords.slice(0, newWordCount),
    ];
  }

  private getReviewWords(): string[] {
    return Array.from(this.wordStatuses.values())
      .filter(status => !status.mastered)
      .sort((a, b) => {
        // Prioritize by difficulty and recency
        if (a.difficulty !== b.difficulty) {
          const difficultyOrder = { hard: 3, medium: 2, easy: 1 };
          return difficultyOrder[b.difficulty] - difficultyOrder[a.difficulty];
        }
        return b.lastSeen.getTime() - a.lastSeen.getTime();
      })
      .map(status => status.word);
  }

  private extractWords(text: string): string[] {
    return (text.match(/\b\w+\b/g) || [])
      .map(word => word.toLowerCase())
      .filter(word => word.length > 2); // Filter out very short words
  }
}

export default VocabularyManager;