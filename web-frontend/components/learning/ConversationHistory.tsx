import React, { useCallback, useRef, useState, useEffect } from 'react';
import toast from 'react-hot-toast';
import type { ChatMessage, TargetWord } from '@/hooks/useLearningSession';
import apiService from '@/services/api';

type Props = {
  messages: ChatMessage[];
  onWordInteract?: (wordId: number, exposureType: 'hint' | 'translation') => void;
  onWordFlag?: (wordId: number) => void;
};

const familiarityClasses: Record<string, string> = {
  new: 'bg-red-100 text-red-800 border border-red-200',
  learning: 'bg-yellow-100 text-yellow-900 border border-yellow-200',
  familiar: 'bg-green-100 text-green-800 border border-green-200',
};

const defaultHighlightClass = 'bg-blue-100 text-blue-900 border border-blue-200';

const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

export default function ConversationHistory({ messages, onWordInteract, onWordFlag }: Props) {
  const [hovered, setHovered] = useState<Record<number, boolean>>({});
  const [hoveredWord, setHoveredWord] = useState<string | null>(null);
  const [tooltipPosition, setTooltipPosition] = useState<{ x: number; y: number } | null>(null);
  const [wordDefinition, setWordDefinition] = useState<{ word: string; translation: string } | null>(null);
  const [highlightedSuggestions, setHighlightedSuggestions] = useState<Set<string>>(new Set());
  const lookupCache = useRef<Record<string, { id?: number; translation: string }>>({});
  const hoverTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const debounceTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Clear timeouts on unmount
  useEffect(() => {
    return () => {
      if (hoverTimeoutRef.current) {
        clearTimeout(hoverTimeoutRef.current);
      }
      if (debounceTimeoutRef.current) {
        clearTimeout(debounceTimeoutRef.current);
      }
    };
  }, []);

  const handleHover = React.useCallback(
    (target: TargetWord) => {
      const wordId = parseInt(String(target.id), 10);
      if (!Number.isFinite(wordId) || hovered[wordId]) return;
      
      setHovered((prev) => {
        if (prev[wordId]) {
          return prev;
        }
        return { ...prev, [wordId]: true };
      });
      onWordInteract?.(wordId, 'hint');
    },
    [hovered, onWordInteract]
  );

  const handleClick = React.useCallback(
    (target: TargetWord) => {
      const wordId = parseInt(String(target.id), 10);
      if (!Number.isFinite(wordId)) return;
      
      if (target.translation) {
        toast(`Added "${target.word}" to practice`, {
          icon: '🧠',
          duration: 3500,
        });
      }
      onWordInteract?.(wordId, 'translation');
      onWordFlag?.(wordId);
    },
    [onWordFlag, onWordInteract]
  );

  const handleWordLeave = useCallback(() => {
    // Clear any existing timeout
    if (hoverTimeoutRef.current) {
      clearTimeout(hoverTimeoutRef.current);
    }
    
    // Set a small delay before hiding tooltip to prevent flickering
    hoverTimeoutRef.current = setTimeout(() => {
      setHoveredWord(null);
      setTooltipPosition(null);
      setWordDefinition(null);
    }, 150);
  }, []);

  const ensureLookup = useCallback(async (word: string) => {
    const key = word.toLowerCase();
    if (lookupCache.current[key]) {
      return lookupCache.current[key];
    }
    try {
      const result = await apiService.lookupVocabulary(word);
      // Ensure proper integer parsing for word_id
      const rawId = result?.id;
      const parsedId = rawId != null ? parseInt(String(rawId), 10) : undefined;
      const wordId = Number.isFinite(parsedId) ? parsedId : undefined;
      
      const entry = {
        id: wordId,
        translation:
          result?.english_translation ||
          result?.definition ||
          result?.example_translation ||
          'Translation unavailable',
      };
      lookupCache.current[key] = entry;
      return entry;
    } catch (error) {
      console.error('Lookup error for word:', word, error);
      const fallback = { translation: 'Translation unavailable' };
      lookupCache.current[key] = fallback;
      return fallback;
    }
  }, []);

  const handleGenericWordHover = useCallback(
    async (word: string, event: React.MouseEvent<HTMLSpanElement>) => {
      // Clear any existing timeouts to prevent race conditions
      if (hoverTimeoutRef.current) {
        clearTimeout(hoverTimeoutRef.current);
      }
      if (debounceTimeoutRef.current) {
        clearTimeout(debounceTimeoutRef.current);
      }

      const rect = event.currentTarget.getBoundingClientRect();
      setHoveredWord(word);
      setTooltipPosition({
        x: rect.left + rect.width / 2,
        y: rect.top - 8,
      });

      // Add to highlighted suggestions
      setHighlightedSuggestions(prev => new Set([...prev, word.toLowerCase()]));

      // Debounce the API call
      debounceTimeoutRef.current = setTimeout(async () => {
        const entry = await ensureLookup(word);
        setWordDefinition({
          word,
          translation: entry.translation,
        });
      }, 100);
    },
    [ensureLookup]
  );

  const handleGenericWordClick = useCallback(
    async (word: string) => {
      const entry = await ensureLookup(word);
      const wordId = entry.id;
      if (wordId && Number.isFinite(wordId)) {
        toast.success(`"${word}" added to practice`, { icon: '🧠', duration: 2500 });
        onWordFlag?.(wordId);
        onWordInteract?.(wordId, 'translation');
      } else {
        toast(`Lookup for "${word}" not found`, { icon: '❓', duration: 2000 });
      }
    },
    [ensureLookup, onWordFlag, onWordInteract]
  );

  const handleTargetHover = useCallback(
    (target: TargetWord, event: React.MouseEvent<HTMLSpanElement>) => {
      // Clear any existing timeouts
      if (hoverTimeoutRef.current) {
        clearTimeout(hoverTimeoutRef.current);
      }
      
      const wordId = parseInt(String(target.id), 10);
      if (!Number.isFinite(wordId)) {
        return;
      }

      if (!hovered[wordId]) {
        setHovered((prev) => (prev[wordId] ? prev : { ...prev, [wordId]: true }));
        onWordInteract?.(wordId, 'hint');
      }

      const rect = event.currentTarget.getBoundingClientRect();
      setHoveredWord(target.word);
      setTooltipPosition({ x: rect.left + rect.width / 2, y: rect.top - 8 });
      setWordDefinition({
        word: target.word,
        translation: target.translation || target.hintTranslation || 'Übersetzung nicht verfügbar',
      });
      
      // Add to highlighted suggestions
      setHighlightedSuggestions(prev => new Set([...prev, target.word.toLowerCase()]));
    },
    [hovered, onWordInteract]
  );

  const handleTargetClick = useCallback(
    (target: TargetWord) => {
      const wordId = parseInt(String(target.id), 10);
      if (!Number.isFinite(wordId)) {
        return;
      }

      if (target.translation) {
        toast(`"${target.word}" zur Wiederholung vorgemerkt`, {
          icon: '🧠',
          duration: 3000,
        });
      }
      onWordInteract?.(wordId, 'translation');
      onWordFlag?.(wordId);
    },
    [onWordFlag, onWordInteract]
  );

  // Add a helper function to make plain text interactive (Unicode-aware)
  const renderInteractiveSegment = useCallback((text: string, keyPrefix: string): React.ReactNode[] => {
    if (!text) return [];
    const WORD_SPLIT_REGEX = /(\p{L}+(?:['\-']\p{L}+)*)/gu;
    const parts = text.split(WORD_SPLIT_REGEX);
    return parts.map((part, index) => {
      if (part) {
        WORD_SPLIT_REGEX.lastIndex = 0;
        if (WORD_SPLIT_REGEX.test(part)) {
          WORD_SPLIT_REGEX.lastIndex = 0;
          const isHighlighted = highlightedSuggestions.has(part.toLowerCase());
          return (
            <span
              key={`${keyPrefix}-${index}`}
              className={`px-1 py-0.5 rounded cursor-pointer transition-all duration-200 ${
                isHighlighted 
                  ? 'bg-blue-100 text-blue-900 border border-blue-200 shadow-sm' 
                  : 'text-gray-700 hover:text-gray-900 hover:bg-gray-100'
              } hover:underline`}
              onMouseEnter={(e) => handleGenericWordHover(part, e)}
              onMouseLeave={handleWordLeave}
              onClick={() => handleGenericWordClick(part)}
              title={`"${part}" übersetzen`}
            >
              {part}
            </span>
          );
        }
      }
      return part;
    });
  }, [handleGenericWordHover, handleGenericWordClick, handleWordLeave, highlightedSuggestions]);

  const renderContent = useCallback(
    (message: ChatMessage) => {
      if (message.role === 'user') {
        return message.content;
      }

      if (!message.targets?.length) {
        return renderInteractiveSegment(message.content, message.id);
      }

      const sortedTargets = [...message.targets].sort((a, b) => b.word.length - a.word.length);
      let matchedAny = false;
      const reduced = sortedTargets.reduce<React.ReactNode[] | string>((nodes, target) => {
        const segments = Array.isArray(nodes) ? nodes : [nodes];
        return segments.flatMap((segment, segmentIndex) => {
          if (typeof segment !== 'string') {
            return [segment];
          }

          const regex = new RegExp(`\\b${escapeRegExp(target.word)}\\b`, 'gi');
          const parts: React.ReactNode[] = [];
          let lastIndex = 0;
          segment.replace(regex, (match, offset) => {
            matchedAny = true;
            const before = segment.slice(lastIndex, offset);
            
            // Make the 'before' segment interactive
            if (before) {
              parts.push(
                ...renderInteractiveSegment(before, `${target.id}-${offset}-before`)
              );
            }

            const className = familiarityClasses[target.familiarity ?? ''] ?? defaultHighlightClass;

            // Push the original target word span
            parts.push(
              <span
                key={`${target.id}-${offset}-${segmentIndex}`}
                className={`rounded-md px-2 py-1 font-semibold transition-all duration-200 hover:shadow-md cursor-pointer ${className}`}
                onMouseEnter={(e) => handleTargetHover(target, e)}
                onMouseLeave={handleWordLeave}
                onClick={() => handleTargetClick(target)}
                title={target.translation || target.hintTranslation || ''}
              >
                {match}
              </span>
            );
            lastIndex = offset + match.length;
            return match;
          });

          const remainder = segment.slice(lastIndex);
          // Make the 'remainder' segment interactive
          if (remainder) {
            parts.push(
              ...renderInteractiveSegment(remainder, `${target.id}-remainder`)
            );
          }
          return parts;
        });
      }, message.content);

      if (!matchedAny) {
        const nodes = Array.isArray(reduced) ? reduced : [reduced];
        return nodes.flatMap((node, index) => {
          if (typeof node === 'string') {
            return renderInteractiveSegment(node, `${message.id}-fallback-${index}`);
          }
          return [node];
        });
      }

      return reduced;
    },
    [renderInteractiveSegment, handleTargetHover, handleWordLeave, handleTargetClick]
  );

  return (
    <div className="space-y-4">
      {messages.map((message) => (
        <div
          key={message.id}
          className={`message-bubble ${
            message.role === 'user' ? 'message-user' : 'message-ai'
          } relative`}
        >
          {message.role === 'user' && Number(message.xp) > 0 && (
            <span className="absolute -top-2 -right-2 rounded-full bg-amber-400 px-2 py-0.5 text-xs font-semibold text-amber-900 shadow">
              +{Number(message.xp)} XP
            </span>
          )}
          <div className="whitespace-pre-wrap leading-relaxed">{renderContent(message)}</div>
        </div>
      ))}

      {hoveredWord && tooltipPosition && wordDefinition && (
        <div
          style={{
            position: 'fixed',
            left: tooltipPosition.x,
            top: tooltipPosition.y,
            transform: 'translateX(-50%) translateY(-100%)',
            zIndex: 1000,
            background: 'white',
            border: '1px solid #d1d5db',
            borderRadius: '8px',
            padding: '10px 12px',
            boxShadow: '0 10px 25px rgba(15, 23, 42, 0.15)',
            maxWidth: '250px',
            minWidth: '180px',
          }}
          onMouseEnter={() => {
            // Keep tooltip visible when hovering over it
            if (hoverTimeoutRef.current) {
              clearTimeout(hoverTimeoutRef.current);
            }
          }}
          onMouseLeave={handleWordLeave}
        >
          <p className="text-sm font-semibold text-gray-900 mb-1">{wordDefinition.word}</p>
          <p className="text-xs text-gray-600 leading-relaxed">{wordDefinition.translation}</p>
        </div>
      )}
    </div>
  );
}
