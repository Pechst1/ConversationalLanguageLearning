import React, { useCallback, useMemo, useState } from "react";
import useSWR from "swr";
import SessionLobby, { SessionDurationOption, SessionTopic } from "./SessionLobby";
import SessionChat, { ChatMessage } from "./SessionChat";
import { SessionSummaryPayload } from "../../services/realtime/WebSocketClient";

interface SessionScreenProps {
  apiBaseUrl: string;
  websocketUrl: string;
  authToken?: string;
}

interface SessionConfigResponse {
  topics: SessionTopic[];
  durations: SessionDurationOption[];
}

interface CreateSessionResponse {
  id: string;
  targetVocabulary: string[];
  messages: ChatMessage[];
}

const fetcher = (url: string, token?: string) =>
  fetch(url, {
    headers: token
      ? {
          Authorization: `Bearer ${token}`,
        }
      : undefined,
  }).then((response) => {
    if (!response.ok) {
      throw new Error("Failed to load session presets");
    }
    return response.json();
  });

export const SessionScreen: React.FC<SessionScreenProps> = ({ apiBaseUrl, websocketUrl, authToken }) => {
  const { data, error: presetsError } = useSWR<SessionConfigResponse>(
    ["session-config", `${apiBaseUrl}/api/v1/sessions/presets`, authToken],
    ([, url, token]) => fetcher(url, token),
  );
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [targetVocabulary, setTargetVocabulary] = useState<string[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [creationError, setCreationError] = useState<string | null>(null);
  const [summary, setSummary] = useState<SessionSummaryPayload | null>(null);

  const topics = useMemo(() => data?.topics ?? [], [data]);
  const durations = useMemo(() => data?.durations ?? [], [data]);

  const handleCreateSession = useCallback(
    async ({ topicId, durationMinutes }: { topicId: string; durationMinutes: number }) => {
      if (!apiBaseUrl) return;
      setIsSubmitting(true);
      setCreationError(null);
      setSummary(null);

      try {
        const response = await fetch(`${apiBaseUrl}/api/v1/sessions`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
          },
          body: JSON.stringify({ topicId, durationMinutes }),
        });

        if (!response.ok) {
          const errorPayload = await response.json().catch(() => ({ message: "Failed to create session" }));
          throw new Error(errorPayload.message || "Failed to create session");
        }

        const payload = (await response.json()) as CreateSessionResponse;
        setActiveSessionId(payload.id);
        setTargetVocabulary(payload.targetVocabulary);
        setMessages(payload.messages ?? []);
      } catch (err) {
        setCreationError(err instanceof Error ? err.message : "Could not start the session");
      } finally {
        setIsSubmitting(false);
      }
    },
    [apiBaseUrl, authToken],
  );

  const handleSummary = useCallback((sessionSummary: SessionSummaryPayload) => {
    setSummary(sessionSummary);
  }, []);

  const handleStartOver = () => {
    setActiveSessionId(null);
    setTargetVocabulary([]);
    setMessages([]);
    setSummary(null);
  };

  if (presetsError) {
    return <div role="alert">We couldn't load the session presets. Please try again later.</div>;
  }

  if (!data) {
    return <div className="session-screen__loading">Loading session options…</div>;
  }

  if (!activeSessionId) {
    return (
      <SessionLobby
        topics={topics}
        durations={durations}
        onCreate={handleCreateSession}
        isSubmitting={isSubmitting}
        error={creationError}
      />
    );
  }

  return (
    <div className="session-screen">
      <SessionChat
        sessionId={activeSessionId}
        websocketUrl={`${websocketUrl}/api/v1/sessions/${activeSessionId}/stream`}
        token={authToken}
        initialMessages={messages}
        targetVocabulary={targetVocabulary}
        onSummary={handleSummary}
      />

      {summary && (
        <div className="session-screen__summary">
          <div className="session-screen__summary-card">
            <h2>Great work!</h2>
            <p>{summary.feedback}</p>
            <h3>Vocabulary highlights</h3>
            <ul>
              {summary.vocabularyLearned.map((word) => (
                <li key={word}>{word}</li>
              ))}
            </ul>
            <p className="session-screen__summary-xp">XP earned: {summary.xpEarned}</p>
            <button type="button" onClick={handleStartOver}>
              Start another session
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default SessionScreen;
