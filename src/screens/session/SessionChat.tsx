import React, { useEffect, useRef, useState, useCallback } from "react";
import { WebSocketClient, SessionSummaryPayload } from "../../services/realtime/WebSocketClient";
import { VocabularyChip } from "../../components/VocabularyChip";
import { InteractiveText } from "../../components/InteractiveText";
import { XPProgress } from "../../components/XPProgress";
import { TypingIndicator } from "../../components/TypingIndicator";
import { VocabularyService, LearningPreferences, WordEntry } from "../../services/vocabulary/VocabularyService";

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
  targetLanguage?: string;
  learningMode?: 'new_words' | 'mixed' | 'heavy_repetition';
  onSummary?: (summary: SessionSummaryPayload) => void;
  onVocabularyUpdate?: (words: string[]) => void;
}

// Detect language from the conversation
const detectLanguage = (text: string): string => {
  // Simple language detection based on common words and patterns
  const frenchPatterns = /\b(le|la|les|un|une|des|et|avec|pour|dans|sur|à|de|du|entreprise|client|nouveau|très)\b/gi;
  const germanPatterns = /\b(der|die|das|und|mit|für|in|auf|von|zu|ist|sind|haben|werden|Unternehmen|neu|sehr|über)\b/gi;
  const spanishPatterns = /\b(el|la|los|las|un|una|y|con|para|en|de|del|empresa|cliente|nuevo|muy|sobre)\b/gi;
  
  const frenchMatches = (text.match(frenchPatterns) || []).length;
  const germanMatches = (text.match(germanPatterns) || []).length;
  const spanishMatches = (text.match(spanishPatterns) || []).length;
  
  if (frenchMatches > germanMatches && frenchMatches > spanishMatches) return 'french';
  if (germanMatches > frenchMatches && germanMatches > spanishMatches) return 'german';
  if (spanishMatches > frenchMatches && spanishMatches > germanMatches) return 'spanish';
  
  return 'french'; // Default fallback
};

export const SessionChat: React.FC<SessionChatProps> = ({
  sessionId,
  websocketUrl,
  token,
  initialMessages = [],
  targetLanguage = 'french',
  learningMode = 'mixed',
  onSummary,
  onVocabularyUpdate,
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [pendingMessage, setPendingMessage] = useState<string>("");
  const [isTyping, setIsTyping] = useState<boolean>(false);
  const [connectionState, setConnectionState] = useState<"connected" | "reconnecting" | "offline">("connected");
  const [error, setError] = useState<string | null>(null);
  const [xpEarned, setXpEarned] = useState<number>(0);
  const [summary, setSummary] = useState<SessionSummaryPayload | null>(null);
  const [currentProposals, setCurrentProposals] = useState<string[]>([]);
  const [detectedLanguage, setDetectedLanguage] = useState<string>(targetLanguage);
  const [vocabularyStats, setVocabularyStats] = useState({ total: 0, practiced: 0, mastered: 0, remaining: 0 });
  
  const listRef = useRef<HTMLDivElement>(null);
  const clientRef = useRef<WebSocketClient>();
  const vocabularyServiceRef = useRef<VocabularyService>();

  // Initialize vocabulary service
  useEffect(() => {
    const preferences: LearningPreferences = {
      targetLanguage: detectedLanguage,
      difficultyRange: [2, 4], // Medium difficulty range
      categories: ['common', 'business', 'casual'],
      wordsPerSession: 8,
      repetitionMode: learningMode,
    };

    vocabularyServiceRef.current = new VocabularyService(preferences);
    
    // Generate initial proposals
    const initialProposals = vocabularyServiceRef.current.generateWordProposals();
    setCurrentProposals(initialProposals);
    setVocabularyStats(vocabularyServiceRef.current.getVocabularyStats());
    
    console.log('Initial vocabulary proposals:', initialProposals);
    onVocabularyUpdate?.(initialProposals);
  }, [detectedLanguage, learningMode, onVocabularyUpdate]);

  // Process messages to extract vocabulary and detect language
  useEffect(() => {
    if (messages.length === 0) return;

    const lastMessage = messages[messages.length - 1];
    
    // Detect language from the conversation
    if (lastMessage.author === 'ai' && lastMessage.text.length > 20) {
      const detected = detectLanguage(lastMessage.text);
      if (detected !== detectedLanguage) {
        console.log('Language detected changed to:', detected);
        setDetectedLanguage(detected);
      }
    }

    // Extract vocabulary from AI messages
    if (lastMessage.author === 'ai' && vocabularyServiceRef.current && !lastMessage.error) {
      console.log('Extracting vocabulary from AI message:', lastMessage.text);
      
      const extractedWords = vocabularyServiceRef.current.extractVocabularyFromMessage(
        lastMessage.text, 
        true
      );
      
      console.log('Extracted words:', extractedWords.map(w => w.word));
      
      // Generate new proposals after extraction
      const newProposals = vocabularyServiceRef.current.generateWordProposals();
      console.log('New proposals generated:', newProposals);
      
      setCurrentProposals(newProposals);
      setVocabularyStats(vocabularyServiceRef.current.getVocabularyStats());
      onVocabularyUpdate?.(newProposals);
    }
  }, [messages, detectedLanguage, onVocabularyUpdate]);

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

    // Check if user used any proposed words
    if (vocabularyServiceRef.current) {
      const usedWords = currentProposals.filter(word => 
        trimmed.toLowerCase().includes(word.toLowerCase())
      );
      
      if (usedWords.length > 0) {
        console.log('User used words:', usedWords);
        vocabularyServiceRef.current.markWordsAsUsed(usedWords, true);
        setVocabularyStats(vocabularyServiceRef.current.getVocabularyStats());
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
    console.log('Word clicked:', word);
    
    if (vocabularyServiceRef.current) {
      vocabularyServiceRef.current.markWordsAsUsed([word], true);
      setVocabularyStats(vocabularyServiceRef.current.getVocabularyStats());
    }
    
    // Send interaction to server
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

  const handleWordHover = useCallback((word: string) => {
    console.log('Word hovered:', word);
    
    // Send hover interaction to server
    try {
      clientRef.current?.send({
        type: "word_interaction",
        sessionId,
        word,
        action: "hover",
        timestamp: new Date().toISOString(),
      });
    } catch (err) {
      console.warn('Failed to send word hover:', err);
    }
  }, [sessionId]);

  const handleProposalClick = (word: string) => {
    // Insert word into the text input
    setPendingMessage(prev => {
      const trimmed = prev.trim();
      return trimmed ? `${trimmed} ${word}` : word;
    });
    
    handleWordClick(word);
  };

  const handleRefreshProposals = () => {
    if (vocabularyServiceRef.current) {
      const newProposals = vocabularyServiceRef.current.generateWordProposals();
      setCurrentProposals(newProposals);
      onVocabularyUpdate?.(newProposals);
      console.log('Refreshed proposals:', newProposals);
    }
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
          <div className="vocabulary-header">
            <h3>Vokabelvorschläge</h3>
            <button 
              type="button" 
              onClick={handleRefreshProposals}
              className="refresh-btn"
              title="Neue Vorschläge generieren"
            >
              ↻
            </button>
          </div>
          
          <p className="vocabulary-instruction">
            Tippe auf ein Wort, um es in deine Antwort einzufügen und XP zu verdienen. 
            Versuche mindestens drei zu verwenden.
          </p>
          
          <div className="session-chat__vocabulary">
            {currentProposals.length === 0 && (
              <div className="no-proposals">
                <p>Keine Vorschläge verfügbar.</p>
                <button onClick={handleRefreshProposals}>Vorschläge generieren</button>
              </div>
            )}
            {currentProposals.map((word) => (
              <VocabularyChip 
                key={word} 
                word={word} 
                onClick={handleProposalClick}
              />
            ))}
          </div>
          
          <div className="vocabulary-stats">
            <p><strong>Sprache:</strong> {detectedLanguage}</p>
            <p><strong>Wörter gelernt:</strong> {vocabularyStats.practiced}</p>
            <p><strong>Gemeistert:</strong> {vocabularyStats.mastered}</p>
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
                <InteractiveText 
                  text={message.text}
                  onWordClick={handleWordClick}
                  onWordHover={handleWordHover}
                  className="session-chat__message-text"
                />
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