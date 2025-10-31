import React, { useState } from "react";

interface WordDefinition {
  word: string;
  definition: string;
  translation?: string;
  pronunciation?: string;
}

interface InteractiveTextProps {
  text: string;
  onWordClick?: (word: string) => void;
  onWordHover?: (word: string, definition?: WordDefinition) => void;
  className?: string;
}

export const InteractiveText: React.FC<InteractiveTextProps> = ({
  text,
  onWordClick,
  onWordHover,
  className = "",
}) => {
  const [hoveredWord, setHoveredWord] = useState<string | null>(null);
  const [tooltipPosition, setTooltipPosition] = useState<{ x: number; y: number } | null>(null);
  const [wordDefinition, setWordDefinition] = useState<WordDefinition | null>(null);

  // Simple word extraction - can be enhanced with better language processing
  const extractWords = (text: string): string[] => {
    return text.match(/\b\w+\b/g) || [];
  };

  const handleWordClick = (word: string, event: React.MouseEvent) => {
    event.preventDefault();
    onWordClick?.(word);
  };

  const handleWordHover = async (word: string, event: React.MouseEvent) => {
    const rect = event.currentTarget.getBoundingClientRect();
    setTooltipPosition({
      x: rect.left + rect.width / 2,
      y: rect.top - 10,
    });
    setHoveredWord(word);
    
    // Here you could fetch word definition from an API
    // For now, we'll use a placeholder
    const mockDefinition: WordDefinition = {
      word,
      definition: `Definition for "${word}"`,
      translation: `Translation of "${word}"`,
    };
    
    setWordDefinition(mockDefinition);
    onWordHover?.(word, mockDefinition);
  };

  const handleWordLeave = () => {
    setHoveredWord(null);
    setTooltipPosition(null);
    setWordDefinition(null);
  };

  const renderInteractiveText = () => {
    const words = extractWords(text);
    const parts = text.split(/(\b\w+\b)/);
    
    return parts.map((part, index) => {
      if (words.includes(part)) {
        return (
          <span
            key={index}
            className="interactive-word"
            onClick={(e) => handleWordClick(part, e)}
            onMouseEnter={(e) => handleWordHover(part, e)}
            onMouseLeave={handleWordLeave}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                handleWordClick(part, e as any);
              }
            }}
          >
            {part}
          </span>
        );
      }
      return part;
    });
  };

  return (
    <div className={`interactive-text ${className}`}>
      <span>{renderInteractiveText()}</span>
      
      {hoveredWord && tooltipPosition && wordDefinition && (
        <div
          className="word-tooltip"
          style={{
            position: 'fixed',
            left: tooltipPosition.x,
            top: tooltipPosition.y,
            transform: 'translateX(-50%) translateY(-100%)',
            zIndex: 1000,
          }}
        >
          <div className="word-tooltip__content">
            <strong>{wordDefinition.word}</strong>
            <p>{wordDefinition.definition}</p>
            {wordDefinition.translation && (
              <p className="word-tooltip__translation">{wordDefinition.translation}</p>
            )}
            {wordDefinition.pronunciation && (
              <p className="word-tooltip__pronunciation">[{wordDefinition.pronunciation}]</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default InteractiveText;