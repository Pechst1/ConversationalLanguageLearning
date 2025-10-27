import React, { useEffect, useRef, useState } from "react";
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
  const listRef = useRef<HTMLDivElement>(null);
  const clientRef = useRef<WebSocketClient>();

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
        <h3>Target vocabulary</h3>
        <div className="session-chat__vocabulary">
          {targetVocabulary.length === 0 && <p>No specific targets for this session.</p>}
          {targetVocabulary.map((word) => (
            <VocabularyChip key={word} word={word} />
          ))}
        </div>

        <XPProgress totalXP={xpEarned} />
        {summary && (
          <div className="session-chat__summary">
            <h4>Session summary</h4>
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
              className={`session-chat__message session-chat__message--${message.author} ${message.error ? "session-chat__message--error" : ""}`}
            >
              <p>{message.text}</p>
              {message.error && <span className="session-chat__message-error">We'll resend once connected.</span>}
            </div>
          ))}

          {isTyping && (
            <TypingIndicator label="Assistant is typing" />
          )}
        </div>

        <div className="session-chat__composer">
          <textarea
            value={pendingMessage}
            onChange={(event) => setPendingMessage(event.target.value)}
            placeholder="Write your reply in the target language"
            rows={3}
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
