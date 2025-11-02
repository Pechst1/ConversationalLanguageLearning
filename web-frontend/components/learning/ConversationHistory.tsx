import React from 'react';
import toast from 'react-hot-toast';
import type { ChatMessage, TargetWord } from '@/hooks/useLearningSession';
import apiService from '@/services/api';

type Props = {
  messages: ChatMessage[];
  onWordInteract?: (wordId: number, exposureType: 'hint' | 'translation') => void;
  onWordFlag?: (wordId: number) => void;
  activeSessionId?: string; // Add session context for marking difficult words
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
  
  if (typeof id === 'number' && Number.isFinite(id) && id > 0) {
    return Math.floor(id);
  }
  
  if (typeof id === 'string') {
    const parsed = parseInt(id, 10);
    if (Number.isInteger(parsed) && parsed > 0) return parsed;
  }
  
  return null;
};

// Check if translation indicates word is known
const isKnown = (translation: string | null | undefined): boolean => {
  return Boolean(translation) && 
         translation.trim().length > 0 && 
         !['Übersetzung nicht verfügbar', 'Translation unavailable', '—', '-'].includes(translation.trim());
};

// Enhanced logging for debugging
const debugLog = (message: string, data?: any) => {
  if (process.env.NODE_ENV === 'development') {
    console.log(`[ConversationHistory] ${message}`, data);
  }
};

export default function ConversationHistory({ messages, onWordInteract, onWordFlag, activeSessionId }: Props) {
  const [hovered, setHovered] = useState<Record<number, boolean>>({});
  const [hoveredWord, setHoveredWord] = useState<string | null>(null);
  const [tooltipPosition, setTooltipPosition] = useState<{ x: number; y: number } | null>(null);
  const [wordDefinition, setWordDefinition] = useState<{ word: string; translation: string } | null>(null);
  const [highlightedSuggestions, setHighlightedSuggestions] = useState<Set<string>>(new Set());
  const [processingWords, setProcessingWords] = useState<Set<string>>(new Set());
  const lookupCache = useRef<Record<string, { id?: number; translation: string; error?: boolean }>>({});
  const hoverTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const debounceTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Clear timeouts on unmount
  useEffect(() => {
    return () => {
      if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current);
      if (debounceTimeoutRef.current) clearTimeout(debounceTimeoutRef.current);
    };
  }, []);

  // Robust resolve-or-create with fallbacks
  const resolveOrCreate = useCallback(async (raw: string, lang = 'fr'): Promise<{ id: number | null; translation: string }> => {
    const key = raw.toLowerCase().trim();
    if (!key) return { id: null, translation: '' };
    
    // Return cached result if available
    if (lookupCache.current[key] && !lookupCache.current[key].error) {
      return {
        id: lookupCache.current[key].id || null,
        translation: lookupCache.current[key].translation || ''
      };
    }

    debugLog('Resolving word', { word: key, lang });

    // 1) Try normal lookup first
    try {
      const result = await apiService.lookupVocabulary(raw, lang);
      const id = normalizeWordId(result?.id || result?.word_id);
      const translation = result?.german_translation || result?.english_translation || result?.definition || '';
      
      if (id && translation) {
        const entry = { id, translation };
        lookupCache.current[key] = entry;
        debugLog('Lookup success', { word: key, id, translation });
        return entry;
      }
    } catch (error) {
      debugLog('Lookup failed', { word: key, error });
    }

    // 2) Try resolve-or-create endpoint
    try {
      const result = await apiService.resolveVocabulary({ word: raw, language: lang });
      const id = normalizeWordId(result?.id || result?.word_id);
      const translation = result?.german_translation || result?.english_translation || result?.definition || '';
      
      const entry = { id, translation: translation || '' };
      lookupCache.current[key] = entry;
      debugLog('Resolve success', { word: key, id, translation });
      return entry;
    } catch (error) {
      debugLog('Resolve failed', { word: key, error });
      const errorEntry = { translation: '', error: true };
      lookupCache.current[key] = errorEntry;
      return { id: null, translation: '' };
    }
  }, []);

  const handleWordLeave = useCallback(() => {
    if (hoverTimeoutRef.current) {
      clearTimeout(hoverTimeoutRef.current);
    }
    
    hoverTimeoutRef.current = setTimeout(() => {
      setHoveredWord(null);
      setTooltipPosition(null);
      setWordDefinition(null);
    }, 150);
  }, []);

  const handleGenericWordHover = useCallback(
    async (word: string, event: React.MouseEvent<HTMLSpanElement>) => {
      // Clear any existing timeouts
      if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current);
      if (debounceTimeoutRef.current) clearTimeout(debounceTimeoutRef.current);

      onWordInteract?.(wordId, 'hint');

      const rect = event.currentTarget.getBoundingClientRect();
      const translation = await ensureTranslation(target.word, target.translation || target.hintTranslation);

      setTooltip({
        x: rect.left + rect.width / 2,
        y: rect.top,
        word: target.word,
        translation,
      });

      // Add to highlighted suggestions
      setHighlightedSuggestions(prev => new Set([...prev, cleanWord.toLowerCase()]));

      // Debounce the API call
      debounceTimeoutRef.current = setTimeout(async () => {
        const { translation } = await resolveOrCreate(cleanWord, 'fr');
        
        // Only update if this word is still being hovered
        if (hoveredWord === cleanWord) {
          setWordDefinition({
            word: cleanWord,
            translation: translation || '—',
          });
        }
      }, 200);
    },
    [resolveOrCreate, hoveredWord]
  );

  const handleGenericWordClick = useCallback(
    async (word: string) => {
      const cleanWord = word.trim();
      if (!cleanWord) return;
      
      // Prevent double-processing
      if (processingWords.has(cleanWord)) return;
      setProcessingWords(prev => new Set([...prev, cleanWord]));
      
      try {
        debugLog('Generic word click', { word: cleanWord });
        
        // 1) Resolve or create to get ID and translation
        const { id, translation } = await resolveOrCreate(cleanWord, 'fr');

        if (!id) {
          toast('Keine ID verfügbar – Bewertung nicht möglich', { icon: '⚠️', duration: 3000 });
          return;
        }

        // 2) Determine rating: unknown → q=0 (Again), known → q=1 (Hard)
        const rating = isKnown(translation) ? 1 : 0;
        const ratingLabel = rating === 0 ? 'Again' : 'Hard';
        
        debugLog('Submitting review', { word: cleanWord, id, rating, translation });

        // 3) Submit review
        await apiService.submitReview({ word_id: id, rating });

        // 4) Optional: Mark as difficult in session context
        if (activeSessionId && rating === 0) {
          try {
            await apiService.markWordDifficult(activeSessionId, { word_id: id });
          } catch (error) {
            debugLog('Failed to mark word difficult in session', { error });
          }
        }

        // 5) Visual feedback
        toast.success(
          `[translate:${cleanWord}] als "${ratingLabel}" bewertet – früher fällig`,
          { icon: '🧠', duration: 3000 }
        );
        
        // 6) Trigger progress refresh
        window.dispatchEvent(new CustomEvent('progressDataDirty', {
          detail: { wordId: id, rating, word: cleanWord }
        }));
        
      } catch (error) {
        console.error('Error in generic word click:', error);
        toast.error('Konnte Bewertung nicht speichern', { duration: 3000 });
      } finally {
        // Remove from processing set
        setProcessingWords(prev => {
          const next = new Set(prev);
          next.delete(cleanWord);
          return next;
        });
      }
    },
    [resolveOrCreate, activeSessionId, processingWords]
  );

  const handleTargetHover = useCallback(
    (target: TargetWord, event: React.MouseEvent<HTMLSpanElement>) => {
      if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current);
      
      const wordId = normalizeWordId(target.id);
      if (wordId === null) {
        toast.error('Wort konnte nicht markiert werden.');
        return;
      }

      if (target.translation) {
        toast(`"${target.word}" zur Wiederholung vorgemerkt`, { icon: '🧠', duration: 2500 });
      }

      const rect = event.currentTarget.getBoundingClientRect();
      setHoveredWord(target.word);
      setTooltipPosition({ x: rect.left + rect.width / 2, y: rect.top - 8 });
      setWordDefinition({
        word: target.word,
        translation: target.translation || target.hintTranslation || 'Übersetzung nicht verfügbar',
      });
      
      setHighlightedSuggestions(prev => new Set([...prev, target.word.toLowerCase()]));
    },
    [onWordFlag, onWordInteract]
  );

  const handleTargetClick = useCallback(
    async (target: TargetWord) => {
      const cleanWord = target.word.trim();
      if (processingWords.has(cleanWord)) return;
      setProcessingWords(prev => new Set([...prev, cleanWord]));
      
      try {
        let wordId = normalizeWordId(target.id);
        let translation = (target.translation || target.hintTranslation || '').trim();

        // If target doesn't have reliable ID/translation, resolve it
        if (!wordId || !isKnown(translation)) {
          debugLog('Target needs resolution', { target, wordId, translation });
          const resolved = await resolveOrCreate(target.word, 'fr');
          wordId = resolved.id;
          translation = translation || resolved.translation;
        }
        
        if (!wordId) {
          toast('Keine ID verfügbar – Bewertung nicht möglich', { icon: '⚠️', duration: 3000 });
          return;
        }

        const rating = isKnown(translation) ? 1 : 0;
        const ratingLabel = rating === 0 ? 'Again' : 'Hard';
        
        debugLog('Target click review', { word: cleanWord, id: wordId, rating, translation });

        await apiService.submitReview({ word_id: wordId, rating });

        if (activeSessionId && rating === 0) {
          try {
            await apiService.markWordDifficult(activeSessionId, { word_id: wordId });
          } catch (error) {
            debugLog('Failed to mark target word difficult in session', { error });
          }
        }

        toast.success(
          `[translate:${cleanWord}] als "${ratingLabel}" bewertet – früher fällig`,
          { icon: '🧠', duration: 3000 }
        );
        
        window.dispatchEvent(new CustomEvent('progressDataDirty', {
          detail: { wordId, rating, word: cleanWord }
        }));
        
      } catch (error) {
        console.error('Error in target click:', error);
        toast.error('Konnte Bewertung nicht speichern', { duration: 3000 });
      } finally {
        setProcessingWords(prev => {
          const next = new Set(prev);
          next.delete(cleanWord);
          return next;
        });
      }
    },
    [resolveOrCreate, activeSessionId, processingWords]
  );

  // Add a helper function to make plain text interactive
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
          const isProcessing = processingWords.has(part);
          
          return (
            <span
              key={`${keyPrefix}-${index}`}
              className={`px-1 py-0.5 rounded cursor-pointer transition-all duration-200 ${
                isProcessing 
                  ? 'bg-gray-300 text-gray-600 cursor-wait animate-pulse' 
                : isHighlighted 
                  ? 'bg-blue-100 text-blue-900 border border-blue-200 shadow-sm hover:shadow-md' 
                  : 'text-gray-700 hover:text-gray-900 hover:bg-gray-100'
              } hover:underline`}
              onMouseEnter={(e) => !isProcessing && handleGenericWordHover(part, e)}
              onMouseLeave={handleWordLeave}
              onClick={() => !isProcessing && handleGenericWordClick(part)}
              title={isProcessing ? 'Verarbeitung läuft...' : `[translate:${part}] bewerten`}
            >
              {part}
            </span>
          );
        }
      }
      return part;
    });
  }, [handleGenericWordHover, handleGenericWordClick, handleWordLeave, highlightedSuggestions, processingWords]);

  const renderContent = useCallback(
    (message: ChatMessage) => {
      if (message.role === 'user') {
        return message.content;
      }

      const targets = Array.isArray(message.targets) ? [...message.targets] : [];
      if (!targets.length) {
        return message.content;
      }

      targets.sort((a, b) => b.word.length - a.word.length);

      const highlighted = targets.reduce<React.ReactNode[] | string>((nodes, target) => {
        const segments = Array.isArray(nodes) ? nodes : [nodes];
        const regex = new RegExp(`(?<!\\p{L})${escapeRegExp(target.word)}(?!\\p{L})`, 'gi');
        const className = familiarityClasses[target.familiarity ?? ''] ?? defaultHighlightClass;

        return segments.flatMap((segment, segmentIndex) => {
          if (typeof segment !== 'string') {
            return [segment];
          }

          const parts: React.ReactNode[] = [];
          let lastIndex = 0;

          segment.replace(regex, (match, offset) => {
            const before = segment.slice(lastIndex, offset);
            
            if (before) {
              parts.push(before);
            }

            const className = familiarityClasses[target.familiarity ?? ''] ?? defaultHighlightClass;
            const wordId = normalizeWordId(target.id);
            const isProcessing = processingWords.has(target.word);

            parts.push(
              <span
                key={`${target.id}-${offset}-${segmentIndex}`}
                className={`rounded-md px-2 py-1 font-semibold transition-all duration-200 hover:shadow-md cursor-pointer ${
                  isProcessing ? 'animate-pulse cursor-wait opacity-70' : ''
                } ${
                  wordId === null ? 'opacity-50 cursor-not-allowed' : ''
                } ${className}`}
                onMouseEnter={(e) => wordId !== null && !isProcessing && handleTargetHover(target, e)}
                onMouseLeave={handleWordLeave}
                onClick={() => wordId !== null && !isProcessing && handleTargetClick(target)}
                title={isProcessing 
                  ? 'Verarbeitung läuft...' 
                  : wordId === null 
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
          if (remainder) {
            parts.push(remainder);
          }
          return parts.length ? parts : [segment];
        });
      }, message.content);

      return highlighted;
    },
    [renderInteractiveSegment, handleTargetHover, handleWordLeave, handleTargetClick]
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

      {tooltip && (
        <div
          style={{
            position: 'fixed',
            left: tooltip.x,
            top: tooltip.y,
            transform: 'translate(-50%, -110%)',
            zIndex: 1000,
            background: 'white',
            border: '1px solid #d1d5db',
            borderRadius: '6px',
            padding: '8px 10px',
            boxShadow: '0 8px 20px rgba(15, 23, 42, 0.15)',
            maxWidth: '220px',
          }}
          onMouseEnter={() => {
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
      {process.env.NODE_ENV === 'development' && processingWords.size > 0 && (
        <div className="fixed bottom-4 left-4 bg-blue-100 border border-blue-400 text-blue-700 px-3 py-2 rounded text-xs max-w-xs">
          <p className="font-semibold">Processing:</p>
          <p>{Array.from(processingWords).join(', ')}</p>
        </div>
      )}
    </div>
  );
}
