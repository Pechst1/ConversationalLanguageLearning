import React, { useState, useRef, useEffect } from 'react';
import apiService from '@/services/api';

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

// Lightweight fallback translator (UI only)
const LocalTranslate: Record<string, Record<string, string>> = {
  french: { bonjour: 'Hallo', merci: 'Danke', projet: 'Projekt', entreprise: 'Unternehmen' }
};

async function ensureWordInPool(sessionId: string | undefined, word: string) {
  if (!sessionId) return;
  try {
    // Try to add to pool; backend should upsert or return existing id
    const res = await apiService.post(`/sessions/${sessionId}/vocabulary`, { word });
    return res; // { id, word, difficulty, is_new }
  } catch (e) {
    // As a fallback, try difficulty bump endpoint if backend indicates exists
    try {
      await apiService.post(`/sessions/${sessionId}/vocabulary/difficulty`, { word, delta: 1 });
    } catch {}
  }
}

async function bumpDifficulty(sessionId: string | undefined, word: string) {
  if (!sessionId) return;
  try {
    await apiService.post(`/sessions/${sessionId}/vocabulary/difficulty`, { word, delta: 1 });
  } catch {}
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
  const tooltipRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const wordsInText = (t: string) => t.match(/\b[a-zA-ZàâäéèêëïîôùûüÿçÀÂÄÉÈÊËÏÎÔÙÛÜŸÇäöüßÄÖÜñáéíóúÑÁÉÍÓÚ]{3,}\b/g) || [];

  const handleClick = async (word: string, e: React.MouseEvent) => {
    e.preventDefault();
    // Requirement: clicking adds to pool or bumps difficulty
    await ensureWordInPool(activeSessionId, word);
    await bumpDifficulty(activeSessionId, word); // If new, backend may ignore; if existing, increases difficulty
  };

  const handleHover = async (word: string, e: React.MouseEvent) => {
    if (!enableTranslation) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const containerRect = containerRef.current?.getBoundingClientRect();
    if (!containerRect) return;
    setTooltipPosition({ x: rect.left + rect.width / 2 - containerRect.left, y: rect.top - containerRect.top - 10 });
    setHoveredWord(word);

    // Try backend translation first
    try {
      const res = await apiService.get(`/vocabulary/translate?word=${encodeURIComponent(word)}&from=${language}&to=de`);
      setDefinition({ word, translation: res.translation });
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
          className="absolute z-50 bg-gray-800 text-white px-3 py-2 rounded-lg shadow-lg text-sm max-w-xs pointer-events-none"
          style={{ left: tooltipPosition.x, top: tooltipPosition.y, transform: 'translateX(-50%) translateY(-100%)' }}
        >
          <div className="font-semibold mb-1">{hoveredWord}</div>
          <div className="text-green-300">{definition?.translation ?? 'Keine Übersetzung gefunden'}</div>
          <div className="absolute top-full left-1/2 -translate-x-1/2 w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent border-t-gray-800" />
        </div>
      )}
    </div>
  );
};

export default InteractiveText;
