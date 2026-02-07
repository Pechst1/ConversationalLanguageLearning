import React, { useState, useRef, useEffect } from 'react';
import apiService from '@/services/api';
import toast from 'react-hot-toast';

interface WordDefinition {
  word: string;
  translation?: string;
  difficulty?: number;
  id?: number;
}

interface InteractiveTextProps {
  text: string;
  className?: string;
  language?: 'french' | 'german' | 'spanish';
  enableTranslation?: boolean;
  activeSessionId?: string;
}

const LocalTranslate: Record<string, Record<string, string>> = {
  french: { bonjour: 'Hallo', merci: 'Danke', projet: 'Projekt', entreprise: 'Unternehmen' }
};

async function bumpWordDifficulty(wordId: number) {
  try {
    await apiService.post(`/progress/bump/${wordId}`);
    return true;
  } catch {
    return false;
  }
}

export const InteractiveText: React.FC<InteractiveTextProps> = ({
  text,
  className = '',
  language = 'french',
  enableTranslation = true,
  activeSessionId,
}) => {
  const [hoveredWord, setHoveredWord] = useState<string | null>(null);
  const [tooltipPosition, setTooltipPosition] = useState<{ x: number; y: number } | null>(null);
  const [definition, setDefinition] = useState<WordDefinition | null>(null);
  const [bumpedWords, setBumpedWords] = useState<Set<number>>(new Set());
  const tooltipRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const wordsInText = (t: string) => t.match(/\b[a-zA-ZàâäéèêëïîôùûüÿçÀÂÄÉÈÊËÏÎÔÙÛÜŸÇäöüßÄÖÜñáéíóúÑÁÉÍÓÚ]{3,}\b/g) || [];

  const handleClick = async (word: string, e: React.MouseEvent) => {
    e.preventDefault();
    // If we have a word ID from the lookup, bump its difficulty
    if (definition?.id && !bumpedWords.has(definition.id)) {
      const success = await bumpWordDifficulty(definition.id);
      if (success) {
        setBumpedWords(prev => new Set(Array.from(prev).concat([definition.id!])));
        // Show feedback to user
        toast.success(`"${word}" wird jetzt früher abgefragt!`, { duration: 2000 });
      }
    }
  };

  const handleHover = async (word: string, e: React.MouseEvent) => {
    if (!enableTranslation) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const containerRect = containerRef.current?.getBoundingClientRect();
    if (!containerRect) return;
    setTooltipPosition({ x: rect.left + rect.width / 2 - containerRect.left, y: rect.top - containerRect.top - 10 });
    setHoveredWord(word);

    try {
      // Use the lookup endpoint which returns full vocabulary data including german_translation
      const res = await apiService.get(`/vocabulary/lookup?word=${encodeURIComponent(word)}&language=${language === 'french' ? 'fr' : language}`);
      const data = res as any;
      // Prefer german_translation, fall back to english_translation
      const translation = data.german_translation || data.english_translation || undefined;
      setDefinition({ word, translation, id: data.id, difficulty: data.difficulty_level });
    } catch {
      const t = LocalTranslate[language]?.[word.toLowerCase()] || undefined;
      setDefinition({ word, translation: t });
    }
  };

  useEffect(() => {
    if (tooltipRef.current && tooltipPosition && containerRef.current) {
      const tip = tooltipRef.current.getBoundingClientRect();
      const cont = containerRef.current.getBoundingClientRect();
      let x = tooltipPosition.x, y = tooltipPosition.y;
      if (x + tip.width / 2 > cont.width) x = cont.width - tip.width / 2 - 8;
      if (x - tip.width / 2 < 0) x = tip.width / 2 + 8;
      if (y < tip.height + 8) y = tooltipPosition.y + 30;
      if (x !== tooltipPosition.x || y !== tooltipPosition.y) setTooltipPosition({ x, y });
    }
  }, [tooltipPosition]);

  const parts = text.split(/(\b[a-zA-ZàâäéèêëïîôùûüÿçÀÂÄÉÈÊËÏÎÔÙÛÜŸÇäöüßÄÖÜñáéíóúÑÁÉÍÓÚ]{3,}\b)/);
  const dict = new Set(wordsInText(text));

  return (
    <div className={`relative ${className}`} ref={containerRef}>
      {parts.map((part, i) => dict.has(part) ? (
        <span
          key={i}
          className="cursor-pointer px-1 py-0.5 rounded transition-colors hover:bg-blue-100 hover:text-blue-800 border-b border-dotted border-transparent hover:border-blue-400"
          onClick={(e) => handleClick(part, e)}
          onMouseEnter={(e) => handleHover(part, e)}
          onMouseLeave={() => { setHoveredWord(null); setTooltipPosition(null); setDefinition(null); }}
          title={`Zum Wortpool hinzufügen bzw. Schwierigkeit erhöhen: "${part}"`}
        >
          {part}
        </span>
      ) : (
        <span key={i}>{part}</span>
      ))}

      {hoveredWord && tooltipPosition && (
        <div
          ref={tooltipRef}
          className="absolute z-50 bg-gray-800 text-white px-3 py-2 rounded-lg shadow-lg text-sm max-w-xs"
          style={{ left: tooltipPosition.x, top: tooltipPosition.y, transform: 'translateX(-50%) translateY(-100%)' }}
        >
          <div className="font-semibold mb-1">{hoveredWord}</div>
          {definition?.translation ? (
            <div className="text-green-300">{definition.translation}</div>
          ) : definition === null ? (
            <div className="text-gray-400 italic">Lade...</div>
          ) : (
            <div className="text-gray-400">Keine Übersetzung gefunden</div>
          )}
          {definition?.id && !bumpedWords.has(definition.id) && (
            <div className="text-xs text-blue-300 mt-1 border-t border-gray-600 pt-1">
              Klicken zum Wiederholen
            </div>
          )}
          {definition?.id && bumpedWords.has(definition.id) && (
            <div className="text-xs text-green-400 mt-1 border-t border-gray-600 pt-1">
              ✓ Wird früher abgefragt
            </div>
          )}
          <div className="absolute top-full left-1/2 -translate-x-1/2 w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent border-t-gray-800" />
        </div>
      )}
    </div>
  );
};

export default InteractiveText;
