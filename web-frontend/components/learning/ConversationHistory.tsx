import React, { useCallback, useEffect, useRef, useState } from 'react';
import toast from 'react-hot-toast';
import type { ChatMessage, TargetWord } from '@/hooks/useLearningSession';
import apiService from '@/services/api';
import InteractiveText from './InteractiveText';

type Props = {
  messages: ChatMessage[];
  onWordInteract?: (wordId: number, exposureType: 'hint' | 'translation') => void;
  onWordFlag?: (wordId: number) => void;
  activeSessionId?: string;
};

const familiarityClasses: Record<string, string> = {
  new: 'bg-red-100 text-red-800 border border-red-200',
  learning: 'bg-yellow-100 text-yellow-900 border border-yellow-200',
  familiar: 'bg-green-100 text-green-800 border border-green-200',
};

const defaultHighlightClass = 'bg-blue-100 text-blue-900 border border-blue-200';

// Enhanced word ID validation function
const validateWordId = (id: any): number | null => {
  // Handle null/undefined
  if (id === null || id === undefined) {
    return null;
  }
  
  // Already a valid number
  if (typeof id === 'number' && Number.isFinite(id) && id > 0) {
    return Math.floor(id);
  }
  
  // Try string conversion
  if (typeof id === 'string') {
    const trimmed = id.trim();
    if (trimmed === '' || trimmed === 'null' || trimmed === 'undefined') {
      return null;
    }
    const parsed = parseInt(trimmed, 10);
    if (Number.isFinite(parsed) && parsed > 0) {
      return parsed;
    }
  }
  
  // Log invalid IDs in development
  if (process.env.NODE_ENV === 'development') {
    console.warn('[WordInteraction] Invalid word ID:', { id, type: typeof id });
  }
  
  return null;
};

const ConversationHistory: React.FC<Props> = ({
  messages,
  onWordInteract,
  onWordFlag,
  activeSessionId,
}) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [hoveredWord, setHoveredWord] = useState<number | null>(null);
  const [wordTranslations, setWordTranslations] = useState<Record<number, string>>({});
  const [loadingTranslations, setLoadingTranslations] = useState<Set<number>>(new Set());
  const [apiErrors, setApiErrors] = useState<Set<number>>(new Set());
  const [retryAttempts, setRetryAttempts] = useState<Map<number, number>>(new Map());
  
  // Debouncing refs
  const hoverTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const translationTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Cleanup timeouts on unmount
  useEffect(() => {
    return () => {
      if (hoverTimeoutRef.current) {
        clearTimeout(hoverTimeoutRef.current);
      }
      if (translationTimeoutRef.current) {
        clearTimeout(translationTimeoutRef.current);
      }
    };
  }, []);

  const fetchWordTranslation = useCallback(async (wordId: number) => {
    const validId = validateWordId(wordId);
    if (!validId) {
      console.warn('[WordTranslation] Invalid word ID provided:', wordId);
      return;
    }

    // Skip if already loading, has translation, or has persistent error
    if (loadingTranslations.has(validId) || 
        wordTranslations[validId] || 
        (apiErrors.has(validId) && (retryAttempts.get(validId) || 0) >= 3)) {
      return;
    }

    setLoadingTranslations(prev => new Set([...prev, validId]));
    
    try {
      const response = await apiService.get(`/vocabulary/words/${validId}/translation`);
      
      if (response && response.translation) {
        setWordTranslations(prev => ({
          ...prev,
          [validId]: response.translation
        }));
        
        // Remove from error set if successful
        setApiErrors(prev => {
          const newSet = new Set(prev);
          newSet.delete(validId);
          return newSet;
        });
        
        // Reset retry count
        setRetryAttempts(prev => {
          const newMap = new Map(prev);
          newMap.delete(validId);
          return newMap;
        });
      } else {
        throw new Error('Invalid response format');
      }
    } catch (error) {
      console.error(`[WordTranslation] Failed to fetch translation for word ${validId}:`, error);
      
      const currentAttempts = retryAttempts.get(validId) || 0;
      setRetryAttempts(prev => new Map(prev.set(validId, currentAttempts + 1)));
      
      if (currentAttempts >= 2) {
        setApiErrors(prev => new Set([...prev, validId]));
        setWordTranslations(prev => ({
          ...prev,
          [validId]: 'Translation unavailable'
        }));
      }
      
      // Only show toast for first failure
      if (currentAttempts === 0) {
        toast.error('Failed to load translation', { duration: 2000 });
      }
    } finally {
      setLoadingTranslations(prev => {
        const newSet = new Set(prev);
        newSet.delete(validId);
        return newSet;
      });
    }
  }, [wordTranslations, loadingTranslations, apiErrors, retryAttempts]);

  const handleWordHover = useCallback((wordId: number) => {
    const validId = validateWordId(wordId);
    if (!validId) {
      return;
    }

    // Clear any existing hover timeout
    if (hoverTimeoutRef.current) {
      clearTimeout(hoverTimeoutRef.current);
    }

    setHoveredWord(validId);
    
    // Debounce translation fetching to avoid too many API calls
    if (translationTimeoutRef.current) {
      clearTimeout(translationTimeoutRef.current);
    }
    
    translationTimeoutRef.current = setTimeout(() => {
      fetchWordTranslation(validId);
    }, 200);
    
    // Safe callback execution
    try {
      onWordInteract?.(validId, 'hint');
    } catch (error) {
      console.error('[WordInteraction] Error in hover callback:', error);
    }
  }, [fetchWordTranslation, onWordInteract]);

  const handleWordLeave = useCallback(() => {
    // Delay hiding to prevent flickering
    hoverTimeoutRef.current = setTimeout(() => {
      setHoveredWord(null);
    }, 150);
  }, []);

  const handleWordClick = useCallback((wordId: number) => {
    const validId = validateWordId(wordId);
    if (!validId) {
      toast.error('Cannot interact with this word - invalid ID');
      return;
    }

    // Clear any pending hide timeout
    if (hoverTimeoutRef.current) {
      clearTimeout(hoverTimeoutRef.current);
    }

    // Immediately fetch translation if not available
    if (!wordTranslations[validId] && !loadingTranslations.has(validId)) {
      fetchWordTranslation(validId);
    }
    
    // Safe callback execution
    try {
      onWordInteract?.(validId, 'translation');
      toast.success('Word added to practice', { duration: 2000 });
    } catch (error) {
      console.error('[WordInteraction] Error in click callback:', error);
      toast.error('Failed to add word to practice');
    }
  }, [fetchWordTranslation, onWordInteract, wordTranslations, loadingTranslations]);

  const handleWordFlag = useCallback(async (wordId: number) => {
    const validId = validateWordId(wordId);
    if (!validId) {
      toast.error('Cannot mark this word as difficult - invalid ID');
      return;
    }

    if (onWordFlag) {
      try {
        await Promise.resolve(onWordFlag(validId));
        toast.success('Word marked as difficult');
      } catch (error) {
        console.error('[WordInteraction] Failed to mark word as difficult via handler:', error);
        toast.error('Failed to mark word as difficult');
      }
      return;
    }

    if (!activeSessionId) {
      toast.error('No active session to mark difficult words');
      return;
    }

    try {
      await apiService.post(`/sessions/${activeSessionId}/difficult-words`, {
        word_id: validId,
      });
      toast.success('Word marked as difficult');
    } catch (error) {
      console.error('[WordInteraction] Failed to mark word as difficult:', error);
      toast.error('Failed to mark word as difficult');
    }
  }, [activeSessionId, onWordFlag]);

  // Enhanced language detection
  const detectLanguage = useCallback((text: string): 'french' | 'german' | 'spanish' => {
    const frenchPatterns = /\b(bonjour|merci|comment|pourquoi|très|français|nouveau|entreprise|marché|avec|pour|dans|être|avoir)\b/gi;
    const germanPatterns = /\b(hallo|danke|wie|warum|sehr|deutsch|neu|unternehmen|markt|mit|für|in|sein|haben)\b/gi;
    const spanishPatterns = /\b(hola|gracias|cómo|muy|español|nuevo|empresa|mercado|con|para|en|ser|tener)\b/gi;
    
    const frenchMatches = (text.match(frenchPatterns) || []).length;
    const germanMatches = (text.match(germanPatterns) || []).length;
    const spanishMatches = (text.match(spanishPatterns) || []).length;
    
    if (frenchMatches >= germanMatches && frenchMatches >= spanishMatches) {
      return 'french';
    } else if (germanMatches >= spanishMatches) {
      return 'german';
    }
    return 'spanish';
  }, []);

  const renderWordWithHighlighting = useCallback((text: string, targets: TargetWord[]) => {
    if (!targets || targets.length === 0) {
      return <span>{text}</span>;
    }

    const usedPositions = new Set<number>();
    const enhancedTargets = targets.map((target) => {
      const highlightText = target.text || target.word || '';
      let position = typeof target.position === 'number' ? target.position : undefined;
      const validId = validateWordId(target.id);

      if ((position === undefined || position < 0) && highlightText) {
        let searchStart = 0;
        let foundIndex = -1;
        while (searchStart < text.length) {
          const idx = text.indexOf(highlightText, searchStart);
          if (idx === -1) {
            break;
          }
          if (!usedPositions.has(idx)) {
            foundIndex = idx;
            usedPositions.add(idx);
            break;
          }
          searchStart = idx + highlightText.length;
        }
        position = foundIndex >= 0 ? foundIndex : undefined;
      } else if (typeof position === 'number') {
        usedPositions.add(position);
      }

      return {
        ...target,
        text: highlightText,
        position,
        validId,
      };
    });

    // Sort targets by position to avoid overlap
    const sortedTargets = [...enhancedTargets]
      .filter(target => target.text && typeof target.position === 'number' && target.position >= 0)
      .sort((a, b) => a.position! - b.position!);

    const elements: React.ReactNode[] = [];
    let lastIndex = 0;

    sortedTargets.forEach((target, index) => {
      if (!target.text || typeof target.position !== 'number' || target.position < 0) {
        return;
      }

      // Add text before this target
      if (target.position > lastIndex) {
        elements.push(
          <span key={`text-${index}`}>
            {text.slice(lastIndex, target.position)}
          </span>
        );
      }

      // Add the highlighted target word
      const wordEnd = target.position + target.text.length;
      const isHovered = hoveredWord === target.validId;
      const translation = target.validId ? wordTranslations[target.validId] : null;
      const isLoading = target.validId ? loadingTranslations.has(target.validId) : false;
      const hasError = target.validId ? apiErrors.has(target.validId) : false;

      const className = target.familiarity
        ? familiarityClasses[target.familiarity]
        : defaultHighlightClass;

      elements.push(
        <span
          key={`word-${target.id}-${index}`}
          className={`${className} ${
            target.validId
              ? 'cursor-pointer hover:shadow-lg transform hover:scale-105'
              : 'cursor-not-allowed opacity-60'
          } ${hasError ? 'border-red-300 bg-red-50' : ''} px-2 py-1 rounded-md transition-all duration-200 relative group font-medium`}
          onMouseEnter={target.validId ? () => handleWordHover(target.validId!) : undefined}
          onMouseLeave={handleWordLeave}
          onClick={target.validId ? () => handleWordClick(target.validId!) : undefined}
          onDoubleClick={target.validId ? () => handleWordFlag(target.validId!) : undefined}
          title={
            !target.validId
              ? 'Invalid word - cannot interact'
              : hasError
              ? 'Translation service unavailable'
              : `Click: Add to practice | Double-click: Mark as difficult${
                  translation ? ` | Translation: ${translation}` : ''
                }`
          }
        >
          {target.text}
          {isHovered && target.validId && (
            <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-3 py-2 bg-gray-900 text-white text-sm rounded-lg whitespace-nowrap z-20 shadow-lg">
              {isLoading ? (
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                  Loading...
                </div>
              ) : hasError ? (
                'Translation unavailable'
              ) : translation ? (
                <div>
                  <div className="font-semibold">{target.text}</div>
                  <div className="text-xs opacity-80">{translation}</div>
                </div>
              ) : (
                'Click for translation'
              )}
              <div className="absolute top-full left-1/2 transform -translate-x-1/2 w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent border-t-gray-900"></div>
            </div>
          )}
        </span>
      );

      lastIndex = wordEnd;
    });

    // Add remaining text
    if (lastIndex < text.length) {
      elements.push(
        <span key="text-end">
          {text.slice(lastIndex)}
        </span>
      );
    }

    return <div className="leading-relaxed">{elements}</div>;
  }, [hoveredWord, wordTranslations, loadingTranslations, apiErrors, handleWordHover, handleWordLeave, handleWordClick, handleWordFlag]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message, index) => (
          <div
            key={`message-${index}-${message.timestamp || Date.now()}`}
            className={`flex ${
              message.role === 'user' ? 'justify-end' : 'justify-start'
            }`}
          >
            <div
              className={`max-w-xs lg:max-w-md px-4 py-3 rounded-lg shadow-sm ${
                message.role === 'user'
                  ? 'bg-blue-500 text-white'
                  : 'bg-gray-100 text-gray-800 border border-gray-200'
              }`}
            >
              {message.role === 'assistant' ? (
                message.targets && message.targets.length > 0 ? (
                  renderWordWithHighlighting(message.content, message.targets)
                ) : (
                  <InteractiveText
                    text={message.content}
                    language={detectLanguage(message.content)}
                    enableTranslation={true}
                    activeSessionId={activeSessionId}
                    className="ai-message-interactive"
                  />
                )
              ) : (
                <span className="whitespace-pre-wrap">{message.content}</span>
              )}
            </div>
            
            {/* XP indicator for user messages */}
            {message.role === 'user' && message.xp && message.xp > 0 && (
              <div className="ml-2 flex items-center">
                <span className="bg-amber-400 text-amber-900 text-xs px-2 py-1 rounded-full font-semibold shadow-sm">
                  +{message.xp} XP
                </span>
              </div>
            )}
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>
      
      {/* Debug info in development */}
      {process.env.NODE_ENV === 'development' && apiErrors.size > 0 && (
        <div className="p-2 bg-yellow-50 border-t border-yellow-200 text-xs text-yellow-700">
          <details>
            <summary className="cursor-pointer font-semibold">
              API Errors ({apiErrors.size})
            </summary>
            <div className="mt-1 space-y-1">
              {Array.from(apiErrors).map(wordId => (
                <div key={wordId} className="flex justify-between">
                  <span>Word ID: {wordId}</span>
                  <span>Retries: {retryAttempts.get(wordId) || 0}</span>
                </div>
              ))}
            </div>
          </details>
        </div>
      )}
    </div>
  );
};

export default ConversationHistory;