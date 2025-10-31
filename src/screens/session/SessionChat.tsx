import React, { useEffect, useRef, useState, useCallback } from "react";
import { WebSocketClient, SessionSummaryPayload } from "../../services/realtime/WebSocketClient";
import { VocabularyChip } from "../../components/VocabularyChip";
import { InteractiveText } from "../../components/InteractiveText";
import { XPProgress } from "../../components/XPProgress";
import { TypingIndicator } from "../../components/TypingIndicator";
import { VocabularyManager, LearnerSettings, WordStatus } from "../../services/vocabulary/VocabularyManager";

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
  learnerSettings?: LearnerSettings;
  onSummary?: (summary: SessionSummaryPayload) => void;
  onVocabularyUpdate?: (words: string[]) => void;
}

const DEFAULT_LEARNER_SETTINGS: LearnerSettings = {
  mode: 'mixed',
  maxWordsPerSession: 10,
  difficultyPreference: 'adaptive',
};

export const SessionChat: React.FC<SessionChatProps> = ({
  sessionId,
  websocketUrl,
  token,
  initialMessages = [],
  targetVocabulary = [],
  learnerSettings = DEFAULT_LEARNER_SETTINGS,
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
  const [currentVocabulary, setCurrentVocabulary] = useState<string[]>(targetVocabulary);
  const [wordStatuses, setWordStatuses] = useState<Map<string, WordStatus>>(new Map());
  const [selectedWord, setSelectedWord] = useState<string | null>(null);
  
  const listRef = useRef<HTMLDivElement>(null);
  const clientRef = useRef<WebSocketClient>();
  const vocabularyManagerRef = useRef<VocabularyManager>();
  const lastProcessedMessageIndex = useRef<number>(-1);

  // Initialize vocabulary manager
  useEffect(() => {
    vocabularyManagerRef.current = new VocabularyManager(
      learnerSettings,
      targetVocabulary,
      Array.from(wordStatuses.values())
    );
    
    // Generate initial proposals
    const initialProposals = vocabularyManagerRef.current.generateProposals();
    setCurrentVocabulary(initialProposals);
    onVocabularyUpdate?.(initialProposals);
  }, [learnerSettings, targetVocabulary]);

  // Process new messages for vocabulary updates
  useEffect(() => {
    if (!vocabularyManagerRef.current || messages.length <= lastProcessedMessageIndex.current + 1) {
      return;
    }

    const newMessages = messages.slice(lastProcessedMessageIndex.current + 1);
    let userMessage = "";
    let aiMessage = "";

    // Find the latest user-ai message pair
    for (let i = newMessages.length - 1; i >= 0; i--) {
      if (newMessages[i].author === "ai" && !aiMessage) {
        aiMessage = newMessages[i].text;
      } else if (newMessages[i].author === "user" && !userMessage && aiMessage) {
        userMessage = newMessages[i].text;
        break;
      }
    }

    if (userMessage && aiMessage && !newMessages[newMessages.length - 1].error) {
      const vocabularyUpdate = vocabularyManagerRef.current.processConversationTurn(
        userMessage,
        aiMessage
      );
      
      setCurrentVocabulary(vocabularyUpdate.newWords);
      
      // Update word statuses
      const newWordStatuses = new Map<string, WordStatus>();
      vocabularyUpdate.updatedStatuses.forEach(status => {
        newWordStatuses.set(status.word, status);
      });
      setWordStatuses(newWordStatuses);
      
      onVocabularyUpdate?.(vocabularyUpdate.newWords);
    }

    lastProcessedMessageIndex.current = messages.length - 1;
  }, [messages, onVocabularyUpdate]);

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
          case "vocabulary_update":
            // Handle vocabulary updates from server
            if (data.words && Array.isArray(data.words)) {
              setCurrentVocabulary(data.words);
              onVocabularyUpdate?.(data.words);
            }
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
  }, [websocketUrl, token, onSummary, onVocabularyUpdate]);

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
    setSelectedWord(word);
    
    // Mark word as used if it's in current vocabulary
    if (vocabularyManagerRef.current && currentVocabulary.includes(word)) {
      vocabularyManagerRef.current.markWordsAsUsed([word], true);
      
      // Update word status
      const status = vocabularyManagerRef.current.getWordStatus(word);
      if (status) {
        setWordStatuses(prev => new Map(prev).set(word, status));
      }
    }
    
    // You could also send this to the server for tracking
    clientRef.current?.send({
      type: "word_interaction",
      sessionId,
      word,
      action: "click"
    });
  }, [sessionId, currentVocabulary]);

  const handleVocabularyChipClick = useCallback((word: string) => {
    // Insert word into pending message
    setPendingMessage(prev => {
      const trimmed = prev.trim();
      return trimmed ? `${trimmed} ${word}` : word;
    });
    
    handleWordClick(word);
  }, [handleWordClick]);

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
        <h3>Wort Vorschläge</h3>
        <div className="session-chat__vocabulary">
          {currentVocabulary.length === 0 && <p>Keine aktuellen Wortvorschläge.</p>}
          {currentVocabulary.map((word) => {
            const status = wordStatuses.get(word);
            return (
              <VocabularyChip 
                key={word} 
                word={word} 
                mastered={status?.mastered || false}
                onClick={handleVocabularyChipClick}
              />
            );
          })}
        </div>

        {selectedWord && (
          <div className="session-chat__word-details">
            <h4>Ausgewähltes Wort</h4>
            <p><strong>{selectedWord}</strong></p>
            {wordStatuses.get(selectedWord) && (
              <div className="word-progress">
                <p>Versuche: {wordStatuses.get(selectedWord)?.attempts || 0}</p>
                <p>Schwierigkeit: {wordStatuses.get(selectedWord)?.difficulty || 'medium'}</p>
              </div>
            )}
          </div>
        )}

        <XPProgress totalXP={xpEarned} />
        {summary && (
          <div className="session-chat__summary">
            <h4>Sitzungszusammenfassung</h4>
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
            placeholder="Write your reply in the target language"
            rows={3}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                handleSend();
              }
            }}
          />
          <button type="button" onClick={handleSend} disabled={!pendingMessage.trim()}>
            Send
          </button>
        </div>
      </div>
    </div>
  );
};

export default SessionChat;