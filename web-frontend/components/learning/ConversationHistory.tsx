import React, { useCallback, useRef, useState } from 'react';
import toast from 'react-hot-toast';
import type { ChatMessage, TargetWord } from '@/hooks/useLearningSession';
import apiService from '@/services/api';

type Props = {
  messages: ChatMessage[];
  onWordInteract?: (wordId: number, exposureType: 'hint' | 'translation') => void;
  onWordFlag?: (wordId: number) => void;
};

const familiarityClasses: Record<string, string> = {
  new: 'bg-red-100 text-red-800',
  learning: 'bg-yellow-100 text-yellow-900',
  familiar: 'bg-green-100 text-green-800',
};

const defaultHighlightClass = 'bg-blue-100 text-blue-900';

const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

export default function ConversationHistory({ messages, onWordInteract, onWordFlag }: Props) {
  const [hovered, setHovered] = useState<Record<number, boolean>>({});
  const [hoveredWord, setHoveredWord] = useState<string | null>(null);
  const [tooltipPosition, setTooltipPosition] = useState<{ x: number; y: number } | null>(null);
  const [wordDefinition, setWordDefinition] = useState<{ word: string; translation: string } | null>(null);
  const lookupCache = useRef<Record<string, { id?: number; translation: string }>>({});

  const handleHover = (target: TargetWord) => {
    if (hovered[target.id]) return;
    setHovered((prev) => ({ ...prev, [target.id]: true }));
    onWordInteract?.(target.id, 'hint');
  };

  const handleClick = (target: TargetWord) => {
    if (target.translation) {
      toast(`Added "${target.word}" to practice`, {
        icon: '🧠',
        duration: 3500,
      });
    }
    onWordInteract?.(target.id, 'translation');
    onWordFlag?.(target.id);
  };

  const handleWordLeave = useCallback(() => {
    setHoveredWord(null);
    setTooltipPosition(null);
    setWordDefinition(null);
  }, []);

  const ensureLookup = useCallback(async (word: string) => {
    const key = word.toLowerCase();
    if (lookupCache.current[key]) {
      return lookupCache.current[key];
    }
    try {
      const result = await apiService.lookupVocabulary(word);
      const entry = {
        id: result?.id,
        translation:
          result?.english_translation ||
          result?.definition ||
          result?.example_translation ||
          'Translation unavailable',
      };
      lookupCache.current[key] = entry;
      return entry;
    } catch (error) {
      const fallback = { translation: 'Translation unavailable' };
      lookupCache.current[key] = fallback;
      return fallback;
    }
  }, []);

  const handleGenericWordHover = useCallback(
    async (word: string, event: React.MouseEvent<HTMLSpanElement>) => {
      const rect = event.currentTarget.getBoundingClientRect();
      setHoveredWord(word);
      setTooltipPosition({
        x: rect.left + rect.width / 2,
        y: rect.top,
      });

      const entry = await ensureLookup(word);
      setWordDefinition({
        word,
        translation: entry.translation,
      });

      if (entry.id) {
        onWordInteract?.(entry.id, 'hint');
      }
    },
    [ensureLookup, onWordInteract]
  );

  const handleGenericWordClick = useCallback(
    async (word: string) => {
      const entry = await ensureLookup(word);
      if (entry.id) {
        toast.success(`"${word}" added to practice`, { icon: '🧠', duration: 2500 });
        onWordFlag?.(entry.id);
        onWordInteract?.(entry.id, 'translation');
      } else {
        toast(`Lookup for "${word}" not found`, { icon: '❓', duration: 2000 });
      }
    },
    [ensureLookup, onWordFlag, onWordInteract]
  );

  // Add a helper function to make plain text interactive
  const renderInteractiveSegment = useCallback((text: string, keyPrefix: string): React.ReactNode[] => {
    if (!text) return [];
    // Split text into words and non-words
    const parts = text.split(/(\b\w+\b)/);
    return parts.map((part, index) => {
      // Check if the part is a word
      if (/\b\w+\b/.test(part)) {
        return (
          <span
            key={`${keyPrefix}-${index}`}
            className="rounded-md px-1 transition-colors hover:shadow-sm cursor-pointer bg-gray-100 text-gray-700 hover:bg-gray-200" // Style for generic words
            onMouseEnter={(e) => handleGenericWordHover(part, e)}
            onMouseLeave={handleWordLeave}
            onClick={() => handleGenericWordClick(part)}
            title={`Look up "${part}"`}
          >
            {part}
          </span>
        );
      }
      return part; // Return non-word parts (spaces, punctuation) as is
    });
  }, [handleGenericWordHover, handleGenericWordClick, handleWordLeave]);

  const renderContent = useCallback(
    (message: ChatMessage) => {
      // User messages remain non-interactive
      if (message.role === 'user') {
        return message.content;
      }
      
      // If there are no targets, make the *entire* message generically interactive
      if (!message.targets?.length) {
        return renderInteractiveSegment(message.content, message.id);
      }

      const sortedTargets = [...message.targets].sort((a, b) => b.word.length - a.word.length);
      return sortedTargets.reduce<React.ReactNode[] | string>((nodes, target) => {
        const segments = Array.isArray(nodes) ? nodes : [nodes];
        return segments.flatMap((segment, segmentIndex) => {
          if (typeof segment !== 'string') {
            return [segment];
          }

          const regex = new RegExp(`\\b${escapeRegExp(target.word)}\\b`, 'gi');
          const parts: React.ReactNode[] = [];
          let lastIndex = 0;
          segment.replace(regex, (match, offset) => {
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
                className={`rounded-md px-1 font-semibold transition-colors hover:shadow-sm cursor-pointer ${className}`}
                onMouseEnter={() => handleHover(target)}
                onMouseLeave={handleWordLeave}
                onClick={() => handleClick(target)}
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
    },
    [renderInteractiveSegment, onWordInteract, onWordFlag]
  );

  return (
    <div className="space-y-4">
      {messages.map((message) => (
        <div
          key={message.id}
          className={`message-bubble ${message.role === 'user' ? 'message-user' : 'message-ai'} relative`}
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
            top: tooltipPosition.y - 12,
            transform: 'translateX(-50%) translateY(-100%)',
            zIndex: 1000,
            background: 'white',
            border: '1px solid #d1d5db',
            borderRadius: '6px',
            padding: '8px 10px',
            boxShadow: '0 8px 20px rgba(15, 23, 42, 0.15)',
            maxWidth: '220px',
          }}
        >
          <p className="text-sm font-semibold text-gray-900">{wordDefinition.word}</p>
          <p className="text-xs text-gray-600">{wordDefinition.translation}</p>
        </div>
      )}
    </div>
  );
}
