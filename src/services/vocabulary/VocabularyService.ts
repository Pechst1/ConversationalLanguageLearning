export interface WordEntry {
  word: string;
  language: string;
  difficulty: 1 | 2 | 3 | 4 | 5;
  frequency: number;
  category: 'common' | 'business' | 'academic' | 'casual' | 'advanced';
  partOfSpeech: 'noun' | 'verb' | 'adjective' | 'adverb' | 'other';
  definition?: string;
  examples?: string[];
  sourceMessage?: string;
  addedAt: Date;
  lastSeen?: Date;
  practiceCount: number;
  successRate: number;
}

export interface LearningPreferences {
  targetLanguage: string;
  difficultyRange: [number, number]; // [min, max] difficulty
  categories: string[];
  wordsPerSession: number;
  repetitionMode: 'new_words' | 'mixed' | 'heavy_repetition';
}

export class VocabularyService {
  private vocabularyPool: Map<string, WordEntry> = new Map();
  private currentSession: Set<string> = new Set();
  private usedInSession: Set<string> = new Set();
  
  // Common word frequency lists for different languages
  private static readonly COMMON_WORDS = {
    'french': [
      'le', 'de', 'et', 'à', 'un', 'il', 'être', 'et', 'en', 'avoir', 'que', 'pour',
      'dans', 'ce', 'son', 'une', 'sur', 'avec', 'ne', 'se', 'pas', 'tout', 'plus',
      'par', 'grand', 'premier', 'en', 'même', 'suivre', 'son', 'jour', 'plus',
      'autre', 'bien', 'où', 'maintenant', 'très', 'homme', 'ici', 'temps', 'main',
      'chose', 'vie', 'yeux', 'monde', 'tête', 'gouvernement', 'système', 'après',
      'travail', 'trois', 'tous', 'encore', 'place', 'end', 'way', 'même', 'année',
      'travail', 'premier', 'jamais', 'américain', 'être', 'groupe', 'partie',
      'entreprise', 'client', 'produit', 'service', 'marché', 'prix', 'qualité',
      'nouveau', 'développement', 'projet', 'équipe', 'résultat', 'problème',
      'solution', 'objectif', 'stratégie', 'performance', 'innovation', 'croissance'
    ],
    'german': [
      'der', 'die', 'und', 'in', 'den', 'von', 'zu', 'das', 'mit', 'sich', 'des',
      'auf', 'für', 'ist', 'im', 'dem', 'nicht', 'ein', 'eine', 'als', 'auch',
      'es', 'an', 'werden', 'aus', 'er', 'hat', 'dass', 'sie', 'nach', 'wird',
      'bei', 'einer', 'um', 'am', 'sind', 'noch', 'wie', 'einem', 'über', 'einen',
      'so', 'zum', 'war', 'haben', 'nur', 'oder', 'aber', 'vor', 'zur', 'bis',
      'mehr', 'durch', 'man', 'sein', 'wurde', 'sei', 'hier', 'alle', 'wenn',
      'Unternehmen', 'Kunden', 'Produkt', 'Service', 'Markt', 'Preis', 'Qualität',
      'neu', 'Entwicklung', 'Projekt', 'Team', 'Ergebnis', 'Problem', 'Lösung'
    ],
    'spanish': [
      'el', 'la', 'de', 'que', 'y', 'a', 'en', 'un', 'ser', 'se', 'no', 'te',
      'lo', 'le', 'da', 'su', 'por', 'son', 'con', 'para', 'al', 'una', 'con',
      'todo', 'pero', 'más', 'hacer', 'o', 'poder', 'decir', 'este', 'ir', 'otro',
      'ese', 'la', 'si', 'me', 'ya', 'ver', 'porque', 'dar', 'cuando', 'él',
      'muy', 'sin', 'vez', 'mucho', 'saber', 'qué', 'sobre', 'mi', 'alguno',
      'empresa', 'cliente', 'producto', 'servicio', 'mercado', 'precio', 'calidad',
      'nuevo', 'desarrollo', 'proyecto', 'equipo', 'resultado', 'problema', 'solución'
    ]
  };

  constructor(private preferences: LearningPreferences) {
    this.initializeCommonWords();
  }

  /**
   * Initialize vocabulary pool with common words
   */
  private initializeCommonWords(): void {
    const commonWords = VocabularyService.COMMON_WORDS[this.preferences.targetLanguage as keyof typeof VocabularyService.COMMON_WORDS] || [];
    
    commonWords.forEach((word, index) => {
      // Skip very common words (articles, prepositions) for learning
      if (word.length > 2 && index > 20) {
        const difficulty = this.calculateWordDifficulty(word, index);
        const category = this.categorizeWord(word, index);
        
        this.vocabularyPool.set(word.toLowerCase(), {
          word: word.toLowerCase(),
          language: this.preferences.targetLanguage,
          difficulty,
          frequency: Math.max(1, 1000 - index * 10),
          category,
          partOfSpeech: 'other',
          addedAt: new Date(),
          practiceCount: 0,
          successRate: 0,
        });
      }
    });
  }

  /**
   * Extract vocabulary words from AI response
   */
  extractVocabularyFromMessage(message: string, isAIMessage: boolean = true): WordEntry[] {
    if (!isAIMessage) return [];

    const words = this.tokenizeText(message);
    const newWords: WordEntry[] = [];

    words.forEach(word => {
      const cleanWord = word.toLowerCase().replace(/[^\w]/g, '');
      
      // Skip if word is too short, already exists, or is too common
      if (cleanWord.length < 3 || this.vocabularyPool.has(cleanWord)) {
        return;
      }

      // Skip very common words that shouldn't be learned
      const veryCommonWords = ['the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 'how', 'its', 'may', 'new', 'now', 'old', 'see', 'two', 'who', 'boy', 'did', 'she', 'use', 'her', 'oil', 'sit', 'set'];
      if (veryCommonWords.includes(cleanWord)) {
        return;
      }

      const difficulty = this.estimateWordDifficulty(cleanWord, message);
      const category = this.categorizeWordFromContext(cleanWord, message);
      const partOfSpeech = this.guessPartOfSpeech(cleanWord, message);

      const wordEntry: WordEntry = {
        word: cleanWord,
        language: this.preferences.targetLanguage,
        difficulty,
        frequency: this.estimateFrequency(cleanWord),
        category,
        partOfSpeech,
        sourceMessage: message,
        addedAt: new Date(),
        practiceCount: 0,
        successRate: 0,
      };

      this.vocabularyPool.set(cleanWord, wordEntry);
      newWords.push(wordEntry);
    });

    return newWords;
  }

  /**
   * Generate word proposals for current session
   */
  generateWordProposals(): string[] {
    const { wordsPerSession, repetitionMode, difficultyRange, categories } = this.preferences;
    
    // Get candidate words
    let candidates = Array.from(this.vocabularyPool.values())
      .filter(word => {
        // Filter by difficulty range
        if (word.difficulty < difficultyRange[0] || word.difficulty > difficultyRange[1]) {
          return false;
        }
        
        // Filter by categories if specified
        if (categories.length > 0 && !categories.includes(word.category)) {
          return false;
        }
        
        // Don't repeat words used in current session
        if (this.usedInSession.has(word.word)) {
          return false;
        }
        
        return true;
      });

    // Apply repetition mode logic
    switch (repetitionMode) {
      case 'new_words':
        candidates = candidates.filter(word => word.practiceCount === 0);
        break;
      case 'heavy_repetition':
        candidates = candidates.filter(word => word.practiceCount > 0 && word.successRate < 0.7);
        break;
      case 'mixed':
        // Mix of new words (60%) and review words (40%)
        const newWords = candidates.filter(word => word.practiceCount === 0);
        const reviewWords = candidates.filter(word => word.practiceCount > 0);
        
        const newWordCount = Math.ceil(wordsPerSession * 0.6);
        const reviewWordCount = wordsPerSession - newWordCount;
        
        candidates = [
          ...this.selectRandomWords(newWords, newWordCount),
          ...this.selectRandomWords(reviewWords, reviewWordCount)
        ];
        break;
    }

    // Sort by priority (difficulty, frequency, success rate)
    candidates.sort((a, b) => {
      // Prioritize words within target difficulty
      const aDiffScore = Math.abs(a.difficulty - ((difficultyRange[0] + difficultyRange[1]) / 2));
      const bDiffScore = Math.abs(b.difficulty - ((difficultyRange[0] + difficultyRange[1]) / 2));
      
      if (aDiffScore !== bDiffScore) {
        return aDiffScore - bDiffScore;
      }
      
      // Then by success rate (lower success rate = higher priority for practice)
      if (a.successRate !== b.successRate) {
        return a.successRate - b.successRate;
      }
      
      // Finally by frequency (more common words first)
      return b.frequency - a.frequency;
    });

    const selectedWords = candidates.slice(0, wordsPerSession).map(word => word.word);
    
    // Keep track of current session words
    selectedWords.forEach(word => this.currentSession.add(word));
    
    return selectedWords;
  }

  /**
   * Mark words as used in current session
   */
  markWordsAsUsed(words: string[], successful: boolean = true): void {
    words.forEach(word => {
      this.usedInSession.add(word);
      
      const entry = this.vocabularyPool.get(word);
      if (entry) {
        entry.practiceCount += 1;
        entry.lastSeen = new Date();
        
        // Update success rate
        const previousTotal = entry.practiceCount - 1;
        const previousSuccesses = Math.round(entry.successRate * previousTotal);
        const newSuccesses = previousSuccesses + (successful ? 1 : 0);
        entry.successRate = newSuccesses / entry.practiceCount;
        
        this.vocabularyPool.set(word, entry);
      }
    });
  }

  /**
   * Reset session state
   */
  resetSession(): void {
    this.currentSession.clear();
    this.usedInSession.clear();
  }

  /**
   * Update learning preferences
   */
  updatePreferences(newPreferences: Partial<LearningPreferences>): void {
    this.preferences = { ...this.preferences, ...newPreferences };
  }

  /**
   * Get vocabulary statistics
   */
  getVocabularyStats() {
    const total = this.vocabularyPool.size;
    const practiced = Array.from(this.vocabularyPool.values()).filter(w => w.practiceCount > 0).length;
    const mastered = Array.from(this.vocabularyPool.values()).filter(w => w.successRate >= 0.8 && w.practiceCount >= 3).length;
    
    return {
      total,
      practiced,
      mastered,
      remaining: total - mastered,
    };
  }

  private tokenizeText(text: string): string[] {
    return text.match(/\b\w+\b/g) || [];
  }

  private calculateWordDifficulty(word: string, frequencyIndex: number): 1 | 2 | 3 | 4 | 5 {
    if (frequencyIndex < 30) return 1;
    if (frequencyIndex < 60) return 2;
    if (frequencyIndex < 90) return 3;
    if (frequencyIndex < 120) return 4;
    return 5;
  }

  private categorizeWord(word: string, index: number): 'common' | 'business' | 'academic' | 'casual' | 'advanced' {
    const businessWords = ['entreprise', 'client', 'produit', 'service', 'marché', 'prix', 'qualité', 'développement', 'projet', 'équipe', 'résultat', 'problème', 'solution', 'objectif', 'stratégie', 'performance', 'innovation', 'croissance'];
    
    if (businessWords.includes(word)) return 'business';
    if (index < 50) return 'common';
    if (index < 100) return 'casual';
    return 'advanced';
  }

  private estimateWordDifficulty(word: string, context: string): 1 | 2 | 3 | 4 | 5 {
    let difficulty = 3; // Default middle difficulty
    
    // Longer words tend to be more difficult
    if (word.length > 8) difficulty += 1;
    if (word.length < 4) difficulty -= 1;
    
    // Complex characters or patterns
    if (/[àâäéèêëïîôùûüÿç]/.test(word)) difficulty += 0.5; // French accents
    if (/[äöüß]/.test(word)) difficulty += 0.5; // German umlauts
    
    // Context clues
    const contextWords = context.toLowerCase();
    if (contextWords.includes('entreprise') || contextWords.includes('business') || contextWords.includes('marché')) {
      difficulty += 0.5; // Business context tends to be more difficult
    }
    
    return Math.max(1, Math.min(5, Math.round(difficulty))) as 1 | 2 | 3 | 4 | 5;
  }

  private categorizeWordFromContext(word: string, context: string): 'common' | 'business' | 'academic' | 'casual' | 'advanced' {
    const lowerContext = context.toLowerCase();
    
    if (lowerContext.includes('entreprise') || lowerContext.includes('client') || lowerContext.includes('marché') || lowerContext.includes('business')) {
      return 'business';
    }
    
    if (lowerContext.includes('université') || lowerContext.includes('recherche') || lowerContext.includes('étude')) {
      return 'academic';
    }
    
    return 'casual';
  }

  private guessPartOfSpeech(word: string, context: string): 'noun' | 'verb' | 'adjective' | 'adverb' | 'other' {
    // Simple heuristics - could be enhanced with NLP
    if (word.endsWith('tion') || word.endsWith('ment') || word.endsWith('ité')) {
      return 'noun';
    }
    if (word.endsWith('er') || word.endsWith('ir') || word.endsWith('re')) {
      return 'verb';
    }
    if (word.endsWith('eux') || word.endsWith('able') || word.endsWith('ique')) {
      return 'adjective';
    }
    if (word.endsWith('ment')) {
      return 'adverb';
    }
    return 'other';
  }

  private estimateFrequency(word: string): number {
    // Simple frequency estimation based on word characteristics
    let frequency = 100;
    
    if (word.length < 4) frequency += 200;
    if (word.length > 8) frequency -= 50;
    
    return Math.max(1, frequency);
  }

  private selectRandomWords<T>(array: T[], count: number): T[] {
    const shuffled = [...array].sort(() => Math.random() - 0.5);
    return shuffled.slice(0, count);
  }
}