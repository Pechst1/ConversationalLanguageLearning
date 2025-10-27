import React from "react";

interface VocabularyChipProps {
  word: string;
  mastered?: boolean;
  onClick?: (word: string) => void;
}

export const VocabularyChip: React.FC<VocabularyChipProps> = ({ word, mastered = false, onClick }) => {
  return (
    <button
      type="button"
      className={`vocabulary-chip ${mastered ? "vocabulary-chip--mastered" : ""}`}
      onClick={() => onClick?.(word)}
    >
      <span>{word}</span>
      {mastered && <span className="vocabulary-chip__status">✓</span>}
    </button>
  );
};

export default VocabularyChip;
