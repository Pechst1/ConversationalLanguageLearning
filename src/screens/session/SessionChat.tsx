import React, { useEffect, useRef, useState, useCallback } from "react";
import { WebSocketClient, SessionSummaryPayload } from "../../services/realtime/WebSocketClient";
import { VocabularyChip } from "../../components/VocabularyChip";
import { XPProgress } from "../../components/XPProgress";
import { TypingIndicator } from "../../components/TypingIndicator";

export interface ChatMessage {
  id: string;
  author: "user" | "ai";
  text: string;
  createdAt: string;
  error?: boolean;
}

export interface SessionChatProps {
  sessionId: string;
  websocketUrl: string;
  token?: string;
  initialMessages?: ChatMessage[];
  targetVocabulary?: string[];
  onSummary?: (summary: SessionSummaryPayload) => void;
}

interface WordEntry {
  word: string;
  difficulty: number;
  context: string;
  frequency: number;
  isNew: boolean;
}

interface LearningState {
  usedWords: Set<string>;
  availableWords: Map<string, WordEntry>;
  sessionWords: string[];
  extractedWords: string[];
  language: string;
}

// Enhanced vocabulary service with intelligent LLM integration
class IntelligentVocabularyService {
  private learningState: LearningState;
  private learningMode: 'new_words' | 'mixed' | 'heavy_repetition';
  
  // Language-specific word patterns for better extraction
  private languagePatterns = {
    french: {
      articles: /\b(le|la|les|un|une|des|du|de|d')\s+/gi,
      commonWords: ['le', 'la', 'les', 'un', 'une', 'des', 'et', 'à', 'de', 'du', 'dans', 'sur', 'avec', 'pour', 'par', 'ne', 'pas', 'que', 'qui', 'où', 'quand', 'comment', 'pourquoi'],
      businessWords: ['entreprise', 'client', 'produit', 'service', 'marché', 'prix', 'qualité', 'développement', 'projet', 'équipe', 'résultat', 'solution', 'objectif', 'stratégie', 'performance', 'innovation', 'croissance', 'vente', 'achat', 'budget', 'investissement'],
      detectPatterns: /\b(entreprise|marché|très|français|nouveau|développement|système|problème|solution)\b/gi
    },
    german: {
      articles: /\b(der|die|das|den|dem|des|ein|eine|einer|eines)\s+/gi,
      commonWords: ['der', 'die', 'das', 'und', 'in', 'den', 'von', 'zu', 'mit', 'sich', 'auf', 'für', 'ist', 'im', 'dem', 'nicht', 'ein', 'eine', 'als', 'auch', 'es', 'an', 'werden', 'aus'],
      businessWords: ['Unternehmen', 'Kunde', 'Produkt', 'Service', 'Markt', 'Preis', 'Qualität', 'Entwicklung', 'Projekt', 'Team', 'Ergebnis', 'Lösung', 'Ziel', 'Strategie', 'Leistung', 'Innovation', 'Wachstum', 'Verkauf', 'Kauf', 'Budget', 'Investition'],
      detectPatterns: /\b(Unternehmen|Markt|sehr|deutsch|neu|Entwicklung|System|Problem|Lösung)\b/gi
    },
    spanish: {
      articles: /\b(el|la|los|las|un|una|del|de|al|a)\s+/gi,
      commonWords: ['el', 'la', 'los', 'las', 'de', 'que', 'y', 'a', 'en', 'un', 'es', 'se', 'no', 'te', 'lo', 'le', 'da', 'su', 'por', 'son', 'con', 'para', 'al', 'una'],
      businessWords: ['empresa', 'cliente', 'producto', 'servicio', 'mercado', 'precio', 'calidad', 'desarrollo', 'proyecto', 'equipo', 'resultado', 'solución', 'objetivo', 'estrategia', 'rendimiento', 'innovación', 'crecimiento', 'venta', 'compra', 'presupuesto', 'inversión'],
      detectPatterns: /\b(empresa|mercado|muy|español|nuevo|desarrollo|sistema|problema|solución)\b/gi
    }
  };

  constructor(initialVocabulary: string[] = [], mode: 'new_words' | 'mixed' | 'heavy_repetition' = 'mixed') {
    this.learningMode = mode;
    this.learningState = {
      usedWords: new Set(),
      availableWords: new Map(),
      sessionWords: [...initialVocabulary],
      extractedWords: [],
      language: 'french'
    };
    
    // Initialize with provided vocabulary
    initialVocabulary.forEach(word => {
      this.addWord(word, 'provided', 2, false);
    });
  }

  // Intelligent language detection
  detectLanguage(text: string): string {
    const scores = { french: 0, german: 0, spanish: 0 };
    const lowerText = text.toLowerCase();
    
    Object.entries(this.languagePatterns).forEach(([lang, patterns]) => {
      const matches = lowerText.match(patterns.detectPatterns);
      scores[lang as keyof typeof scores] = matches ? matches.length : 0;
    });
    
    const detectedLang = Object.entries(scores)
      .sort(([,a], [,b]) => b - a)[0][0];
    
    return detectedLang;
  }

  // Smart word extraction from LLM responses
  extractVocabulary(message: string, isAIMessage: boolean = true): string[] {
    if (!isAIMessage) return [];
    
    console.log('🔍 Extracting vocabulary from:', message.substring(0, 100) + '...');
    
    // Detect language first
    const detectedLang = this.detectLanguage(message);
    this.learningState.language = detectedLang;
    
    const langPatterns = this.languagePatterns[detectedLang as keyof typeof this.languagePatterns];
    if (!langPatterns) return [];
    
    // Remove articles and clean text
    const cleanedText = message.replace(langPatterns.articles, ' ');
    
    // Extract words (3+ characters, alphabetic)
    const words = cleanedText.match(/\b[a-zA-ZàâäéèêëïîôùûüÿçÀÂÄÉÈÊËÏÎÔÙÛÜŸÇäöüßÄÖÜñáéíóúÑÁÉÍÓÚ]{3,}\b/g) || [];
    
    // Filter and score words
    const candidateWords = words
      .map(word => word.toLowerCase())
      .filter((word, index, arr) => arr.indexOf(word) === index) // Remove duplicates
      .filter(word => !langPatterns.commonWords.includes(word)) // Remove common words
      .filter(word => !this.learningState.availableWords.has(word)) // Skip already known words
      .map(word => ({
        word,
        difficulty: this.calculateWordDifficulty(word, message, detectedLang),
        context: this.extractContext(word, message),
        frequency: langPatterns.businessWords.includes(word) ? 10 : 5,
        isNew: true
      }))
      .sort((a, b) => b.frequency - a.frequency || a.difficulty - b.difficulty) // Sort by importance
      .slice(0, 12); // Limit extraction
    
    // Add words to available pool
    candidateWords.forEach(entry => {
      this.addWord(entry.word, entry.context, entry.difficulty, entry.isNew);
    });
    
    const extractedWordsList = candidateWords.map(w => w.word);
    this.learningState.extractedWords.push(...extractedWordsList);
    
    console.log('📝 Extracted words:', extractedWordsList);
    console.log('🌍 Detected language:', detectedLang);
    
    return extractedWordsList;
  }

  // Calculate word difficulty intelligently
  private calculateWordDifficulty(word: string, context: string, language: string): number {
    let difficulty = 3; // Base difficulty
    
    // Length-based difficulty
    if (word.length > 8) difficulty += 1;
    if (word.length < 4) difficulty -= 1;
    
    // Language-specific patterns
    if (language === 'french') {
      if (/[àâäéèêëïîôùûüÿç]/.test(word)) difficulty += 0.5;
      if (word.endsWith('tion') || word.endsWith('ment')) difficulty += 0.5;
    } else if (language === 'german') {
      if (/[äöüß]/.test(word)) difficulty += 0.5;
      if (word[0] === word[0].toUpperCase()) difficulty += 0.3; // Nouns
    }
    
    // Context-based difficulty
    if (context.toLowerCase().includes('business') || context.toLowerCase().includes('technical')) {
      difficulty += 1;
    }
    
    return Math.max(1, Math.min(5, Math.round(difficulty)));
  }

  // Extract meaningful context for a word
  private extractContext(word: string, fullText: string): string {
    const sentences = fullText.split(/[.!?]+/);
    const wordSentence = sentences.find(s => s.toLowerCase().includes(word.toLowerCase()));
    return wordSentence ? wordSentence.trim().substring(0, 100) : 'AI response';
  }

  // Add word to vocabulary pool
  private addWord(word: string, context: string, difficulty: number, isNew: boolean): void {
    this.learningState.availableWords.set(word, {
      word,
      difficulty,
      context,
      frequency: isNew ? 1 : 5,
      isNew
    });
  }

  // Generate word proposals based on learning mode and LLM context
  generateProposals(maxWords: number = 8): string[] {
    const available = Array.from(this.learningState.availableWords.values())
      .filter(entry => !this.learningState.usedWords.has(entry.word))
      .sort((a, b) => {
        // Prioritize by learning mode
        if (this.learningMode === 'new_words' && a.isNew !== b.isNew) {
          return b.isNew ? 1 : -1;
        }
        // Then by frequency and difficulty
        return b.frequency - a.frequency || a.difficulty - b.difficulty;
      });

    let selectedWords: string[] = [];
    
    switch (this.learningMode) {
      case 'new_words':
        selectedWords = available
          .filter(w => w.isNew)
          .slice(0, maxWords)
          .map(w => w.word);
        break;
      case 'mixed':
        const newWords = available.filter(w => w.isNew).slice(0, Math.ceil(maxWords * 0.6));
        const reviewWords = available.filter(w => !w.isNew).slice(0, maxWords - newWords.length);
        selectedWords = [...newWords, ...reviewWords].map(w => w.word);
        break;
      case 'heavy_repetition':
        const reviewFirst = available.filter(w => !w.isNew).slice(0, Math.ceil(maxWords * 0.7));
        const newSecond = available.filter(w => w.isNew).slice(0, maxWords - reviewFirst.length);
        selectedWords = [...reviewFirst, ...newSecond].map(w => w.word);
        break;
    }
    
    // Fallback: if not enough words, add from session words
    if (selectedWords.length < maxWords) {
      const remainingSlots = maxWords - selectedWords.length;
      const sessionWords = this.learningState.sessionWords
        .filter(w => !selectedWords.includes(w) && !this.learningState.usedWords.has(w))
        .slice(0, remainingSlots);
      selectedWords.push(...sessionWords);
    }
    
    console.log('🎯 Generated proposals:', selectedWords);
    return selectedWords;
  }

  // Mark words as used
  markAsUsed(words: string[]): void {
    words.forEach(word => this.learningState.usedWords.add(word));
    console.log('✅ Marked as used:', words);
  }

  // Get learning statistics
  getStats() {
    return {
      totalWords: this.learningState.availableWords.size,
      usedWords: this.learningState.usedWords.size,
      extractedWords: this.learningState.extractedWords.length,
      language: this.learningState.language,
      sessionWords: this.learningState.sessionWords.length
    };
  }
}

export const SessionChat: React.FC<SessionChatProps> = ({
  sessionId,
  websocketUrl,
  token,
  initialMessages = [],
  targetVocabulary = [],
  onSummary,
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [pendingMessage, setPendingMessage] = useState<string>("");
  const [isTyping, setIsTyping] = useState<boolean>(false);
  const [connectionState, setConnectionState] = useState<"connected" | "reconnecting" | "offline">("connected");
  const [error, setError] = useState<string | null>(null);
  const [xpEarned, setXpEarned] = useState<number>(0);
  const [summary, setSummary] = useState<SessionSummaryPayload | null>(null);
  const [currentProposals, setCurrentProposals] = useState<string[]>([]);
  const [vocabularyStats, setVocabularyStats] = useState({ totalWords: 0, usedWords: 0, extractedWords: 0, language: 'french', sessionWords: 0 });
  
  const listRef = useRef<HTMLDivElement>(null);
  const clientRef = useRef<WebSocketClient>();
  const vocabularyServiceRef = useRef<IntelligentVocabularyService>();

  // Initialize intelligent vocabulary service
  useEffect(() => {
    vocabularyServiceRef.current = new IntelligentVocabularyService(targetVocabulary, 'mixed');
    const initialProposals = vocabularyServiceRef.current.generateProposals(8);
    setCurrentProposals(initialProposals);
    setVocabularyStats(vocabularyServiceRef.current.getStats());
    console.log('🚀 Initialized vocabulary service with proposals:', initialProposals);
  }, [targetVocabulary]);

  // Process AI messages for intelligent vocabulary extraction
  useEffect(() => {
    if (!vocabularyServiceRef.current || messages.length === 0) return;
    
    const lastMessage = messages[messages.length - 1];
    
    // Process AI messages only
    if (lastMessage.author === 'ai' && !lastMessage.error && lastMessage.text.length > 10) {
      console.log('🤖 Processing AI message for intelligent extraction');
      
      // Extract vocabulary intelligently
      const extractedWords = vocabularyServiceRef.current.extractVocabulary(lastMessage.text, true);
      
      if (extractedWords.length > 0) {
        // Generate new proposals based on extraction
        const newProposals = vocabularyServiceRef.current.generateProposals(8);
        setCurrentProposals(newProposals);
        setVocabularyStats(vocabularyServiceRef.current.getStats());
        
        console.log('📊 Updated stats:', vocabularyServiceRef.current.getStats());
      }
    }
  }, [messages]);

  useEffect(() => {
    const client = new WebSocketClient({ url: websocketUrl, token });
    clientRef.current = client;

    const handleMessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        switch (data.type) {
          case "chat_message":
            setMessages((prev) => [
              ...prev,
              {
                id: data.id,
                author: data.author,
                text: data.text,
                createdAt: data.createdAt,
              },
            ]);
            setIsTyping(false);
            break;
          case "typing":
            setIsTyping(Boolean(data.isTyping));
            break;
          case "xp_gain":
            setXpEarned((prev) => prev + Number(data.amount ?? 0));
            break;
          default:
            break;
        }
      } catch (err) {
        setError("We had trouble understanding a message from the server.");
      }
    };

    const handleSummary = (payload: SessionSummaryPayload) => {
      setSummary(payload);
      onSummary?.(payload);
    };

    const handleReconnecting = () => setConnectionState("reconnecting");
    const handleReconnected = () => setConnectionState("connected");
    const handleOffline = () => setConnectionState("offline");
    const handleOnline = () => setConnectionState("connected");
    const handleError = () => setError("The conversation is having trouble staying connected.");

    client.on("message", handleMessage);
    client.on("summary", handleSummary);
    client.on("reconnecting", handleReconnecting);
    client.on("reconnected", handleReconnected);
    client.on("offline", handleOffline);
    client.on("online", handleOnline);
    client.on("error", handleError);

    client.connect();

    return () => {
      client.off("message", handleMessage);
      client.off("summary", handleSummary);
      client.off("reconnecting", handleReconnecting);
      client.off("reconnected", handleReconnected);
      client.off("offline", handleOffline);
      client.off("online", handleOnline);
      client.off("error", handleError);
      client.disconnect();
    };
  }, [websocketUrl, token, onSummary]);

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages, isTyping]);

  const handleSend = () => {
    const trimmed = pendingMessage.trim();
    if (!trimmed) {
      return;
    }

    const optimistic: ChatMessage = {
      id: `temp-${Date.now()}`,
      author: "user",
      text: trimmed,
      createdAt: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimistic]);
    setPendingMessage("");

    // Track word usage intelligently
    if (vocabularyServiceRef.current) {
      const usedWords = currentProposals.filter(word => 
        trimmed.toLowerCase().includes(word.toLowerCase())
      );
      
      if (usedWords.length > 0) {
        vocabularyServiceRef.current.markAsUsed(usedWords);
        setVocabularyStats(vocabularyServiceRef.current.getStats());
        
        // Generate fresh proposals
        const freshProposals = vocabularyServiceRef.current.generateProposals(8);
        setCurrentProposals(freshProposals);
      }
    }

    try {
      clientRef.current?.send({ type: "chat_message", sessionId, text: trimmed });
    } catch (err) {
      setMessages((prev) =>
        prev.map((message) =>
          message.id === optimistic.id ? { ...message, error: true } : message,
        ),
      );
      setError("We couldn't send your message. It'll be retried when you're back online.");
    }
  };

  const handleWordClick = useCallback((word: string) => {
    console.log('🎯 Word clicked:', word);
    
    // Add to message
    setPendingMessage(prev => {
      const trimmed = prev.trim();
      return trimmed ? `${trimmed} ${word}` : word;
    });
    
    // Mark as used
    if (vocabularyServiceRef.current) {
      vocabularyServiceRef.current.markAsUsed([word]);
      setVocabularyStats(vocabularyServiceRef.current.getStats());
    }
    
    // Send interaction to server for analytics
    try {
      clientRef.current?.send({
        type: "word_interaction",
        sessionId,
        word,
        action: "click",
        timestamp: new Date().toISOString(),
      });
    } catch (err) {
      console.warn('Failed to send word interaction:', err);
    }
  }, [sessionId]);

  const handleRefreshProposals = () => {
    if (vocabularyServiceRef.current) {
      const newProposals = vocabularyServiceRef.current.generateProposals(8);
      setCurrentProposals(newProposals);
      console.log('🔄 Refreshed proposals:', newProposals);
    }
  };

  // Render AI messages with clickable words
  const renderAIMessage = (text: string) => {
    // Split text into words and non-word characters
    const parts = text.split(/(\b[a-zA-ZàâäéèêëïîôùûüÿçÀÂÄÉÈÊËÏÎÔÙÛÜŸÇäöüßÄÖÜñáéíóúÑÁÉÍÓÚ]{3,}\b)/);
    
    return (
      <p style={{ margin: 0, lineHeight: 1.6 }}>
        {parts.map((part, index) => {
          // Check if this part is a meaningful word (3+ chars, alphabetic)
          const isWord = /^[a-zA-ZàâäéèêëïîôùûüÿçÀÂÄÉÈÊËÏÎÔÙÛÜŸÇäöüßÄÖÜñáéíóúÑÁÉÍÓÚ]{3,}$/.test(part);
          
          if (isWord) {
            return (
              <span
                key={index}
                onClick={() => handleWordClick(part)}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = '#e3f2fd';
                  e.currentTarget.style.color = '#1976d2';
                  e.currentTarget.style.cursor = 'pointer';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = 'transparent';
                  e.currentTarget.style.color = 'inherit';
                }}
                style={{
                  padding: '1px 2px',
                  borderRadius: '3px',
                  transition: 'all 0.2s ease',
                  cursor: 'pointer',
                  display: 'inline'
                }}
                title={`Click to add "${part}" to your message`}
              >
                {part}
              </span>
            );
          }
          return <span key={index}>{part}</span>;
        })}
      </p>
    );
  };

  const connectionBanner = (
    <div className={`session-chat__banner session-chat__banner--${connectionState}`}>
      {connectionState === "reconnecting" && "Reconnecting…"}
      {connectionState === "offline" && "You're offline. We'll retry when you return."}
    </div>
  );

  return (
    <div className="session-chat">
      {connectionState !== "connected" && connectionBanner}
      {error && <div className="session-chat__error">{error}</div>}

      <aside className="session-chat__sidebar">
        <div className="vocabulary-section">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <h3 style={{ margin: 0, fontSize: '16px' }}>Vokabelvorschläge</h3>
            <button 
              type="button" 
              onClick={handleRefreshProposals}
              style={{
                background: 'none',
                border: '1px solid #ddd',
                borderRadius: '4px',
                padding: '4px 8px',
                cursor: 'pointer',
                fontSize: '12px'
              }}
              title="Neue Vorschläge generieren"
            >
              🔄
            </button>
          </div>
          
          <p style={{ fontSize: '12px', color: '#666', marginBottom: '12px', lineHeight: 1.4 }}>
            Intelligente Wortvorschläge basierend auf dem Gespräch. Klicke auf Wörter in AI-Nachrichten!
          </p>
          
          <div className="session-chat__vocabulary">
            {currentProposals.length === 0 && (
              <div style={{ textAlign: 'center', padding: '20px', color: '#666' }}>
                <p style={{ marginBottom: '10px' }}>Keine Vorschläge verfügbar.</p>
                <button 
                  onClick={handleRefreshProposals}
                  style={{
                    backgroundColor: '#1976d2',
                    color: 'white',
                    border: 'none',
                    padding: '8px 16px',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    fontSize: '12px'
                  }}
                >
                  Vorschläge generieren
                </button>
              </div>
            )}
            {currentProposals.map((word) => (
              <VocabularyChip 
                key={word} 
                word={word} 
                onClick={() => handleWordClick(word)}
              />
            ))}
          </div>
          
          <div style={{ marginTop: '15px', paddingTop: '15px', borderTop: '1px solid #eee', fontSize: '12px', color: '#666' }}>
            <p style={{ margin: '4px 0' }}><strong>Sprache:</strong> {vocabularyStats.language}</p>
            <p style={{ margin: '4px 0' }}><strong>Gesamte Wörter:</strong> {vocabularyStats.totalWords}</p>
            <p style={{ margin: '4px 0' }}><strong>Verwendet:</strong> {vocabularyStats.usedWords}</p>
            <p style={{ margin: '4px 0' }}><strong>Aus KI extrahiert:</strong> {vocabularyStats.extractedWords}</p>
          </div>
        </div>

        <XPProgress totalXP={xpEarned} />
        
        {summary && (
          <div className="session-chat__summary">
            <h4>Session Summary</h4>
            <p>{summary.feedback}</p>
            <ul>
              {summary.vocabularyLearned.map((word) => (
                <li key={word}>{word}</li>
              ))}
            </ul>
          </div>
        )}
      </aside>

      <div className="session-chat__main">
        <div className="session-chat__messages" ref={listRef}>
          {messages.map((message) => (
            <div
              key={message.id}
              className={`session-chat__message session-chat__message--${message.author} ${
                message.error ? "session-chat__message--error" : ""
              }`}
            >
              {message.author === "ai" ? (
                renderAIMessage(message.text)
              ) : (
                <p>{message.text}</p>
              )}
              {message.error && <span className="session-chat__message-error">We'll resend once connected.</span>}
            </div>
          ))}

          {isTyping && <TypingIndicator label="Assistant is typing" />}
        </div>

        <div className="session-chat__composer">
          <textarea
            value={pendingMessage}
            onChange={(event) => setPendingMessage(event.target.value)}
            placeholder="Schreibe deine Nachricht..."
            rows={3}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                handleSend();
              }
            }}
          />
          <button type="button" onClick={handleSend} disabled={!pendingMessage.trim()}>
            Senden
          </button>
        </div>
      </div>
    </div>
  );
};

export default SessionChat;