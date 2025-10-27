import React from "react";

interface TypingIndicatorProps {
  label?: string;
}

export const TypingIndicator: React.FC<TypingIndicatorProps> = ({ label = "Typing…" }) => (
  <div className="typing-indicator" aria-live="polite">
    <span className="typing-indicator__dot" />
    <span className="typing-indicator__dot" />
    <span className="typing-indicator__dot" />
    <span className="typing-indicator__label">{label}</span>
  </div>
);

export default TypingIndicator;
