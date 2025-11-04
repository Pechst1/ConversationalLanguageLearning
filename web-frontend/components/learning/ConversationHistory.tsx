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

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const fetchWordTranslation = useCallback(async (wordId: number) => {
    if (wordTranslations[wordId] || loadingTranslations.has(wordId)) {
      return;
    }

    setLoadingTranslations(prev => new Set(prev).add(wordId));
    
    try {
      const response = await apiService.get(`/vocabulary/words/${wordId}/translation`);
      setWordTranslations(prev => ({
        ...prev,
        [wordId]: response.translation
      }));
    } catch (error) {
      console.error('Failed to fetch word translation:', error);
      toast.error('Failed to load translation');
    } finally {
      setLoadingTranslations(prev => {
        const newSet = new Set(prev);
        newSet.delete(wordId);
        return newSet;
      });
    }
  }, [wordTranslations, loadingTranslations]);

  const handleWordHover = useCallback((wordId: number) => {
    setHoveredWord(wordId);
    fetchWordTranslation(wordId);
    onWordInteract?.(wordId, 'hint');
  }, [fetchWordTranslation, onWordInteract]);

  const handleWordClick = useCallback((wordId: number) => {
    fetchWordTranslation(wordId);
    onWordInteract?.(wordId, 'translation');
  }, [fetchWordTranslation, onWordInteract]);

  const handleWordFlag = useCallback(async (wordId: number) => {
    if (!activeSessionId) {
      toast.error('No active session to mark difficult words');
      return;
    }

    try {
      await apiService.post(`/sessions/${activeSessionId}/difficult-words`, {
        word_id: wordId
      });
      toast.success('Word marked as difficult');
      onWordFlag?.(wordId);
    } catch (error) {
      console.error('Failed to mark word as difficult:', error);
      toast.error('Failed to mark word as difficult');
    }
  }, [activeSessionId, onWordFlag]);

  // Language detection for InteractiveText
  const detectLanguage = useCallback((text: string): 'french' | 'german' | 'spanish' => {
    const frenchPatterns = /\b(bonjour|merci|comment|pourquoi|très|français|nouveau|entreprise|marché)\b/gi;
    const germanPatterns = /\b(hallo|danke|wie|warum|sehr|deutsch|neu|unternehmen|markt)\b/gi;
    const spanishPatterns = /\b(hola|gracias|cómo|muy|español|nuevo|empresa|mercado)\b/gi;
    
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

  const renderWordWithHighlighting = (text: string, targets: TargetWord[]) => {
    if (!targets || targets.length === 0) {
      return <span>{text}</span>;
    }

    // Sort targets by position to avoid overlap issues
    const sortedTargets = [...targets].sort((a, b) => a.position - b.position);
    const elements: React.ReactNode[] = [];
    let lastIndex = 0;

    sortedTargets.forEach((target, index) => {
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
      const isHovered = hoveredWord === target.id;
      const translation = wordTranslations[target.id];
      const isLoading = loadingTranslations.has(target.id);
      
      const className = target.familiarity 
        ? familiarityClasses[target.familiarity] 
        : defaultHighlightClass;

      elements.push(
        <span
          key={`word-${target.id}`}
          className={`${className} px-1 py-0.5 rounded cursor-pointer transition-all duration-200 hover:shadow-md relative group`}
          onMouseEnter={() => handleWordHover(target.id)}
          onMouseLeave={() => setHoveredWord(null)}
          onClick={() => handleWordClick(target.id)}
          onDoubleClick={() => handleWordFlag(target.id)}
          title={`Double-click to mark as difficult${translation ? ` | Translation: ${translation}` : ''}`}
        >
          {target.text}
          {isHovered && (
            <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-2 py-1 bg-gray-800 text-white text-sm rounded whitespace-nowrap z-10">
              {isLoading ? 'Loading...' : translation || 'Click for translation'}
              <div className="absolute top-full left-1/2 transform -translate-x-1/2 w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent border-t-gray-800"></div>
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

    return <span>{elements}</span>;
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message, index) => (
          <div
            key={index}
            className={`flex ${
              message.role === 'user' ? 'justify-end' : 'justify-start'
            }`}
          >
            <div
              className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
                message.role === 'user'
                  ? 'bg-blue-500 text-white'
                  : 'bg-gray-200 text-gray-800'
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
                <span>{message.content}</span>
              )}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>
    </div>
  );
};

export default ConversationHistory;