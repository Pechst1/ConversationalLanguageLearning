import React, { useState } from "react";

export interface SessionTopic {
  id: string;
  label: string;
  description: string;
  vocabulary: string[];
}

export interface SessionDurationOption {
  id: string;
  label: string;
  minutes: number;
}

export interface SessionLobbyProps {
  topics: SessionTopic[];
  durations: SessionDurationOption[];
  isSubmitting?: boolean;
  onCreate: (payload: { topicId: string; durationMinutes: number }) => Promise<void> | void;
  error?: string | null;
}

export const SessionLobby: React.FC<SessionLobbyProps> = ({
  topics,
  durations,
  onCreate,
  isSubmitting = false,
  error,
}) => {
  const [topicId, setTopicId] = useState<string>(topics[0]?.id ?? "");
  const [duration, setDuration] = useState<number>(durations[0]?.minutes ?? 15);
  const [localError, setLocalError] = useState<string | null>(null);

  const handleCreate = async () => {
    if (!topicId || !duration) {
      setLocalError("Please choose a topic and duration");
      return;
    }

    setLocalError(null);
    await onCreate({ topicId, durationMinutes: duration });
  };

  return (
    <div className="session-lobby">
      <header className="session-lobby__header">
        <h1>Start a new session</h1>
        <p>Choose a topic and how long you want to practice.</p>
      </header>

      <section className="session-lobby__topics">
        <h2>Topics</h2>
        <div className="session-lobby__topic-grid">
          {topics.map((topic) => (
            <button
              key={topic.id}
              type="button"
              className={`session-lobby__topic ${topicId === topic.id ? "session-lobby__topic--selected" : ""}`}
              onClick={() => setTopicId(topic.id)}
            >
              <h3>{topic.label}</h3>
              <p>{topic.description}</p>
              <div className="session-lobby__topic-vocabulary">
                {topic.vocabulary.map((word) => (
                  <span key={word} className="session-lobby__topic-chip">
                    {word}
                  </span>
                ))}
              </div>
            </button>
          ))}
        </div>
      </section>

      <section className="session-lobby__duration">
        <h2>Duration</h2>
        <div className="session-lobby__duration-options">
          {durations.map((option) => (
            <label key={option.id} className={`session-lobby__duration-option ${duration === option.minutes ? "session-lobby__duration-option--selected" : ""}`}>
              <input
                type="radio"
                name="duration"
                value={option.minutes}
                checked={duration === option.minutes}
                onChange={() => setDuration(option.minutes)}
              />
              <span>{option.label}</span>
            </label>
          ))}
        </div>
      </section>

      {(error || localError) && <p className="session-lobby__error">{error ?? localError}</p>}

      <footer className="session-lobby__footer">
        <button type="button" onClick={handleCreate} className="session-lobby__submit" disabled={isSubmitting}>
          {isSubmitting ? "Creating session…" : "Start session"}
        </button>
      </footer>
    </div>
  );
};

export default SessionLobby;
