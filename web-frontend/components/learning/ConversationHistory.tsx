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

// Robust word ID normalization function
const normalizeWordId = (id: any): number | null => {
  if (id === null || id === undefined) return null;
  
  // If it's already a valid number
  if (typeof id === 'number' && Number.isFinite(id) && id > 0) {
    return Math.floor(id); // Ensure integer
  }
  
  // Try to parse as string
  if (typeof id === 'string') {
    const parsed = parseInt(id.trim(), 10);
    if (Number.isFinite(parsed) && parsed > 0) {
      return parsed;
    }
  }
  
  // Log the problematic ID for debugging
  console.warn('Invalid word ID encountered:', { id, type: typeof id });
  return null;
};

// Enhanced logging for debugging
const debugLog = (message: string, data?: any) => {
  if (process.env.NODE_ENV === 'development') {
    console.log(`[ConversationHistory] ${message}`, data);
  }
};

export default function ConversationHistory({ messages, onWordInteract, onWordFlag }: Props) {
  const [hovered, setHovered] = useState<Record<number, boolean>>({});
  const [hoveredWord, setHoveredWord] = useState<string | null>(null);
  const [tooltipPosition, setTooltipPosition] = useState<{ x: number; y: number } | null>(null);
  const [wordDefinition, setWordDefinition] = useState<{ word: string; translation: string } | null>(null);
  const [highlightedSuggestions, setHighlightedSuggestions] = useState<Set<string>>(new Set());
  const [apiErrors, setApiErrors] = useState<Set<string>>(new Set());
  const lookupCache = useRef<Record<string, { id?: number; translation: string; error?: boolean }>>({});
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

  const handleTargetWordHover = useCallback(
    (target: TargetWord) => {
      const wordId = normalizeWordId(target.id);
      if (wordId === null) {
        debugLog('Invalid target word ID', { target });
        return;
      }
      
      if (hovered[wordId]) return;
      
      debugLog('Target word hover', { word: target.word, id: wordId });
      
      setHovered((prev) => ({ ...prev, [wordId]: true }));
      
      // Safe callback with error handling
      try {
        onWordInteract?.(wordId, 'hint');
      } catch (error) {
        console.error('Error in onWordInteract callback:', error);
      }
    },
    [hovered, onWordInteract]
  );

  const handleTargetWordClick = useCallback(
    (target: TargetWord) => {
      const wordId = normalizeWordId(target.id);
      if (wordId === null) {
        debugLog('Invalid target word ID on click', { target });
        toast.error('Invalid word ID - cannot process');
        return;
      }
      
      debugLog('Target word click', { word: target.word, id: wordId });
      
      if (target.translation) {
        toast(`"${target.word}" zur Wiederholung vorgemerkt`, {
          icon: '🧠',
          duration: 3000,
        });
      }
      
      // Safe callbacks with error handling
      try {
        onWordInteract?.(wordId, 'translation');
        onWordFlag?.(wordId);
      } catch (error) {
        console.error('Error in word interaction callbacks:', error);
        toast.error('Error processing word interaction');
      }
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
    const key = word.toLowerCase().trim();
    if (!key) return { translation: 'Invalid word' };
    
    // Return cached result if available
    if (lookupCache.current[key]) {
      return lookupCache.current[key];
    }
    
    // Check if we've had repeated errors for this word
    if (apiErrors.has(key)) {
      const fallback = { translation: 'Translation currently unavailable', error: true };
      lookupCache.current[key] = fallback;
      return fallback;
    }
    
    try {
      debugLog('API lookup for word', { word: key });
      const result = await apiService.lookupVocabulary(word);
      
      debugLog('API lookup result', { word: key, result });
      
      // Enhanced ID normalization from API result
      const normalizedId = normalizeWordId(result?.id || result?.word_id);
      
      const entry = {
        id: normalizedId || undefined,
        translation:
          result?.english_translation ||
          result?.german_translation ||
          result?.definition ||
          result?.example_translation ||
          'Translation not available',
      };
      
      lookupCache.current[key] = entry;
      return entry;
    } catch (error) {
      console.error('Lookup error for word:', word, error);
      
      // Track API errors to avoid repeated failed requests
      setApiErrors(prev => new Set([...prev, key]));
      
      const fallback = { 
        translation: 'Translation service temporarily unavailable', 
        error: true 
      };
      lookupCache.current[key] = fallback;
      return fallback;
    }
  }, [apiErrors]);

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
      const cleanWord = word.trim();
      
      if (!cleanWord) return;
      
      setHoveredWord(cleanWord);
      setTooltipPosition({
        x: rect.left + rect.width / 2,
        y: rect.top - 8,
      });

      // Add to highlighted suggestions
      setHighlightedSuggestions(prev => new Set([...prev, cleanWord.toLowerCase()]));

      // Debounce the API call to prevent too many requests
      debounceTimeoutRef.current = setTimeout(async () => {
        const entry = await ensureLookup(cleanWord);
        
        // Only update if this word is still being hovered
        if (hoveredWord === cleanWord) {
          setWordDefinition({
            word: cleanWord,
            translation: entry.translation,
          });
        }
      }, 200); // Increased debounce time
    },
    [ensureLookup, hoveredWord]
  );

  const handleGenericWordClick = useCallback(
    async (word: string) => {
      const cleanWord = word.trim();
      if (!cleanWord) return;
      
      debugLog('Generic word click', { word: cleanWord });
      
      const entry = await ensureLookup(cleanWord);
      
      if (entry.error) {
        toast.warning(`Translation for "${cleanWord}" is currently unavailable`, { 
          icon: '⚠️', 
          duration: 3000 
        });
        return;
      }
      
      const wordId = entry.id;
      if (wordId && Number.isFinite(wordId)) {
        debugLog('Generic word processed successfully', { word: cleanWord, id: wordId });
        toast.success(`"${cleanWord}" added to practice`, { icon: '🧠', duration: 2500 });
        
        try {
          onWordFlag?.(wordId);
          onWordInteract?.(wordId, 'translation');
        } catch (error) {
          console.error('Error in generic word callbacks:', error);
          toast.error('Error adding word to practice');
        }
      } else {
        debugLog('No valid ID found for generic word', { word: cleanWord, entry });
        toast(`Word "${cleanWord}" found but cannot be added to practice`, { 
          icon: 'ℹ️', 
          duration: 2000 
        });
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
      
      const wordId = normalizeWordId(target.id);
      if (wordId === null) {
        debugLog('Invalid target word ID on hover', { target });
        return;
      }

      // Track hover state
      if (!hovered[wordId]) {
        setHovered((prev) => ({ ...prev, [wordId]: true }));
        try {
          onWordInteract?.(wordId, 'hint');
        } catch (error) {
          console.error('Error in target hover callback:', error);
        }
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
          const hasApiError = apiErrors.has(part.toLowerCase());
          
          return (
            <span
              key={`${keyPrefix}-${index}`}
              className={`px-1 py-0.5 rounded cursor-pointer transition-all duration-200 ${
                hasApiError 
                  ? 'text-gray-400 hover:text-gray-500 opacity-50' // Dimmed for API errors
                : isHighlighted 
                  ? 'bg-blue-100 text-blue-900 border border-blue-200 shadow-sm' 
                  : 'text-gray-700 hover:text-gray-900 hover:bg-gray-100'
              } hover:underline`}
              onMouseEnter={(e) => !hasApiError && handleGenericWordHover(part, e)}
              onMouseLeave={handleWordLeave}
              onClick={() => !hasApiError && handleGenericWordClick(part)}
              title={hasApiError ? `Translation temporarily unavailable for "${part}"` : `"${part}" übersetzen`}
            >
              {part}
            </span>
          );
        }
      }
      return part;
    });
  }, [handleGenericWordHover, handleGenericWordClick, handleWordLeave, highlightedSuggestions, apiErrors]);

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
            const wordId = normalizeWordId(target.id);

            // Push the original target word span
            parts.push(
              <span
                key={`${target.id}-${offset}-${segmentIndex}`}
                className={`rounded-md px-2 py-1 font-semibold transition-all duration-200 hover:shadow-md cursor-pointer ${
                  wordId === null ? 'opacity-50 cursor-not-allowed' : ''
                } ${className}`}
                onMouseEnter={(e) => wordId !== null && handleTargetHover(target, e)}
                onMouseLeave={handleWordLeave}
                onClick={() => wordId !== null && handleTargetWordClick(target)}
                title={wordId === null 
                  ? 'Invalid word ID - cannot interact' 
                  : target.translation || target.hintTranslation || ''
                }
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
    [renderInteractiveSegment, handleTargetHover, handleWordLeave, handleTargetWordClick]
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
      
      {/* Debug info in development */}
      {process.env.NODE_ENV === 'development' && apiErrors.size > 0 && (
        <div className="fixed bottom-4 right-4 bg-yellow-100 border border-yellow-400 text-yellow-700 px-3 py-2 rounded text-xs max-w-xs">
          <p className="font-semibold">API Lookup Errors:</p>
          <p>{Array.from(apiErrors).slice(0, 3).join(', ')}</p>
          {apiErrors.size > 3 && <p>...and {apiErrors.size - 3} more</p>}
        </div>
      )}
    </div>
  );
}
