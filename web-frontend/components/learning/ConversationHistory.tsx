import React, { useCallback, useEffect, useRef, useState } from 'react';
import toast from 'react-hot-toast';
import type { ChatMessage, TargetWord } from '@/hooks/useLearningSession';
import apiService from '@/services/api';
import InteractiveText from './InteractiveText';
import StageDirection, { parseMessageContent } from './StageDirection';
import { AlertTriangle, Volume2, Eye, Ear } from 'lucide-react';
import { useSpeakingMode } from '@/contexts/SpeakingModeContext';

type Props = {
  messages: ChatMessage[];
  onWordInteract?: (wordId: number, exposureType: 'hint' | 'translation') => void;
  onWordFlag?: (wordId: number) => void;
  activeSessionId?: string;
};

const familiarityClasses: Record<string, string> = {
  new: 'border-black bg-bauhaus-red/10 text-bauhaus-red',
  learning: 'border-black bg-bauhaus-yellow/20 text-black',
  familiar: 'border-black bg-bauhaus-blue/15 text-bauhaus-blue',
};

const defaultHighlightClass = 'border-black bg-white text-black';

// Hidden Message component for audio-only mode
const HiddenMessage: React.FC<{
  messageId: string;
  onReveal: () => void;
  isSpeaking?: boolean;
  onReplay?: () => void;
}> = ({ messageId, onReveal, isSpeaking, onReplay }) => {
  return (
    <div className="relative">
      {/* Blurred placeholder */}
      <div className="relative min-h-[96px] overflow-hidden rounded-none border-4 border-dashed border-black bg-[var(--app-sheet)] p-6 shadow-[4px_4px_0px_0px_#000]">
        {/* Decorative blur bars to simulate hidden text */}
        <div className="space-y-2">
          <div className="h-4 bg-black/10 rounded blur-[2px] w-full" />
          <div className="h-4 bg-black/10 rounded blur-[2px] w-4/5" />
          <div className="h-4 bg-black/10 rounded blur-[2px] w-3/5" />
        </div>

        {/* Overlay with actions */}
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-white/80 backdrop-blur-sm">
          <div className="flex items-center gap-2 text-black">
            <Ear className={`w-5 h-5 ${isSpeaking ? 'animate-pulse' : ''}`} />
            <span className="font-bold text-sm uppercase tracking-wider">
              {isSpeaking ? 'Listening...' : 'Listen carefully!'}
            </span>
          </div>

          <div className="flex items-center gap-2">
            {onReplay && (
              <button
                onClick={onReplay}
                className="flex items-center gap-1 rounded-none border-2 border-black bg-bauhaus-yellow px-3 py-1.5 text-xs font-bold text-black transition-all hover:-translate-y-0.5 hover:shadow-[2px_2px_0px_0px_#000]"
              >
                <Volume2 className="w-3 h-3" />
                Replay
              </button>
            )}
            <button
              onClick={onReveal}
              className="flex items-center gap-1 rounded-none border-2 border-black bg-white px-3 py-1.5 text-xs font-bold text-black transition-all hover:-translate-y-0.5 hover:shadow-[2px_2px_0px_0px_#000]"
            >
              <Eye className="w-3 h-3" />
              Reveal
            </button>
          </div>

          <p className="text-[10px] font-bold text-[var(--app-ink-3)] uppercase tracking-wider mt-1">
            Click reveal after listening or respond to show text
          </p>
        </div>
      </div>
    </div>
  );
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

  // Audio-only mode context
  const {
    isAudioOnlyMode,
    revealedMessages,
    revealMessage,
    speakText,
    isSpeaking
  } = useSpeakingMode();

  // Track which message is currently being spoken
  const [speakingMessageId, setSpeakingMessageId] = useState<string | null>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const fetchWordTranslation = useCallback(async (wordId: number) => {
    if (!Number.isFinite(wordId)) {
      return;
    }

    if (wordTranslations[wordId] || loadingTranslations.has(wordId)) {
      return;
    }

    setLoadingTranslations(prev => new Set(prev).add(wordId));

    try {
      // Use the correct endpoint to get full vocabulary data
      const response = await apiService.get(`/vocabulary/${wordId}`);
      const data = response as any;
      // Prefer german_translation, fall back to english_translation
      const translation = data.german_translation || data.english_translation || 'Keine Übersetzung';
      setWordTranslations(prev => ({
        ...prev,
        [wordId]: translation
      }));
    } catch (error) {
      console.error('Failed to fetch word translation:', error);
      // Don't show toast on every failed translation, just log it
    } finally {
      setLoadingTranslations(prev => {
        const newSet = new Set(prev);
        newSet.delete(wordId);
        return newSet;
      });
    }
  }, [wordTranslations, loadingTranslations]);

  const handleWordHover = useCallback((wordId: number) => {
    if (!Number.isFinite(wordId)) {
      return;
    }

    setHoveredWord(wordId);
    fetchWordTranslation(wordId);
    onWordInteract?.(wordId, 'hint');
  }, [fetchWordTranslation, onWordInteract]);

  const handleWordClick = useCallback((wordId: number) => {
    if (!Number.isFinite(wordId)) {
      return;
    }

    fetchWordTranslation(wordId);
    onWordInteract?.(wordId, 'translation');
  }, [fetchWordTranslation, onWordInteract]);

  const handleWordFlag = useCallback(async (wordId: number) => {
    if (!Number.isFinite(wordId)) {
      toast.error('Unable to mark this word as difficult');
      return;
    }

    if (onWordFlag) {
      try {
        await Promise.resolve(onWordFlag(wordId));
      } catch (error) {
        console.error('Failed to mark word as difficult via handler:', error);
        toast.error('Failed to mark word as difficult');
      }
      return;
    }

    if (!activeSessionId) {
      toast.error('No active session to mark difficult words');
      return;
    }

    try {
      await apiService.post(`/sessions/${activeSessionId}/difficult_words`, {
        word_id: wordId,
      });
      toast.success('Word marked as difficult');
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

    const usedPositions = new Set<number>();
    const enhancedTargets = targets.map((target) => {
      const highlightText = target.text || target.word || '';
      let position = typeof target.position === 'number' ? target.position : undefined;

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
      };
    });

    // Sort targets by derived position to avoid overlap issues
    const sortedTargets = [...enhancedTargets].sort((a, b) => {
      const positionA = typeof a.position === 'number' ? a.position : Number.POSITIVE_INFINITY;
      const positionB = typeof b.position === 'number' ? b.position : Number.POSITIVE_INFINITY;
      return positionA - positionB;
    });
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
      const isHovered = hoveredWord === target.id;
      const translation = wordTranslations[target.id];
      const isLoading = loadingTranslations.has(target.id);

      const hasValidId = Number.isFinite(target.id);

      const className = target.familiarity
        ? familiarityClasses[target.familiarity]
        : defaultHighlightClass;

      elements.push(
        <span
          key={`word-${target.id}`}
          className={`${className} relative mx-0.5 inline-block cursor-pointer rounded-none border border-black px-1.5 py-0.5 text-[0.95em] font-bold shadow-[2px_2px_0px_0px_#000] hover:-translate-y-0.5 hover:shadow-[3px_3px_0px_0px_#000] transition-all`}
          onMouseEnter={hasValidId ? () => handleWordHover(target.id) : undefined}
          onMouseLeave={() => setHoveredWord(null)}
          onClick={hasValidId ? () => handleWordClick(target.id) : undefined}
          onDoubleClick={hasValidId ? () => handleWordFlag(target.id) : undefined}
          title={`Double-click to mark as difficult${translation ? ` | Translation: ${translation}` : ''}`}
        >
          {target.text}
          {isHovered && (
            <div className="absolute bottom-full left-1/2 z-50 mb-3 min-w-[120px] -translate-x-1/2 whitespace-nowrap rounded-none border-2 border-black bg-white px-3 py-2 text-center text-sm font-bold text-[var(--app-ink)] shadow-[3px_3px_0px_0px_#000]">
              {isLoading ? 'Loading...' : translation || (hasValidId ? 'Click for translation' : target.text)}
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
    <div className="flex h-[min(68vh,720px)] flex-col overflow-hidden rounded-none border-4 border-black bg-white shadow-[8px_8px_0px_0px_#000]">
      <div className="flex-1 overflow-y-auto px-4 py-6 sm:px-6">
        {messages.map((message, index) => (
          <div
            key={message.id || index}
            className={`mb-8 flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`w-full max-w-2xl ${message.role === 'user' ? 'max-w-xl' : ''}`}
            >
              <div className={`mb-2 text-[11px] font-black uppercase tracking-[0.18em] ${
                message.role === 'user' ? 'text-[var(--app-ink-3)] text-right' : 'text-[var(--app-ink-2)]'
              }`}>
                {message.role === 'user' ? 'You' : 'Tutor'}
              </div>
              <div
                className={`rounded-none border-4 border-black px-5 py-4 shadow-[4px_4px_0px_0px_#000] ${
                  message.role === 'user'
                    ? 'bg-[var(--app-paper-2)] text-[var(--app-ink)]'
                    : 'bg-white text-[var(--app-ink)]'
                }`}
              >
              {message.role === 'assistant' ? (() => {
                // Parse message to separate scene directions from dialogue
                const { sceneContent, dialogueContent } = parseMessageContent(message.content);

                // Check if this message should be hidden in audio-only mode
                const isRevealed = !isAudioOnlyMode ||
                  revealedMessages.has(message.id) ||
                  revealedMessages.has('__ALL__') ||
                  // Auto-reveal if there's a user message after this one (user responded)
                  (index < messages.length - 1 && messages.slice(index + 1).some(m => m.role === 'user'));

                // Handler to replay this message's audio
                const handleReplay = async () => {
                  setSpeakingMessageId(message.id);
                  await speakText(dialogueContent);
                  setSpeakingMessageId(null);
                };

                // If in audio-only mode and not revealed, show hidden placeholder
                if (isAudioOnlyMode && !isRevealed) {
                  return (
                    <HiddenMessage
                      messageId={message.id}
                      onReveal={() => revealMessage(message.id)}
                      isSpeaking={isSpeaking && speakingMessageId === message.id}
                      onReplay={handleReplay}
                    />
                  );
                }

                return (
                  <>
                    {/* Audio-only mode: Show replay button when revealed */}
                    {isAudioOnlyMode && (
                      <div className="flex items-center gap-2 mb-2">
                        <button
                          onClick={handleReplay}
                          className={`flex items-center gap-1 rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${isSpeaking && speakingMessageId === message.id
                            ? 'bg-amber-100 text-amber-700 animate-pulse'
                            : 'bg-white text-stone-600 ring-1 ring-stone-200 hover:bg-stone-50'
                            }`}
                        >
                          <Volume2 className="w-3 h-3" />
                          {isSpeaking && speakingMessageId === message.id ? 'Playing...' : 'Replay'}
                        </button>
                        <span className="text-xs text-gray-400">Revealed</span>
                      </div>
                    )}
                    {sceneContent && (
                      <StageDirection content={sceneContent} />
                    )}
                    {message.targets && message.targets.length > 0 ? (
                      <div className="text-[17px] leading-8 font-normal text-stone-800">
                        {renderWordWithHighlighting(dialogueContent, message.targets)}
                      </div>
                    ) : (
                      <InteractiveText
                        text={dialogueContent}
                        language={detectLanguage(dialogueContent)}
                        enableTranslation={true}
                        activeSessionId={activeSessionId}
                        className="text-[17px] leading-8 font-normal text-stone-800"
                      />
                    )}
                  </>
                );
              })() : (
                <div className="flex flex-col gap-3">
                  <span className="text-[17px] leading-8">{message.content}</span>
                  {/* Inline corrected sentence - concise single-line correction */}
                  {message.errors && message.errors.errors && message.errors.errors.length > 0 && (() => {
                    // Build the corrected sentence by replacing each error span
                    let correctedSentence = message.content;
                    // Sort errors by position (longer spans first to avoid overlap issues)
                    const sortedErrors = [...message.errors.errors].sort((a, b) => {
                      const posA = correctedSentence.indexOf(a.span);
                      const posB = correctedSentence.indexOf(b.span);
                      return posB - posA; // Reverse order to replace from end to start
                    });
                    for (const err of sortedErrors) {
                      if (err.span && err.suggestion) {
                        correctedSentence = correctedSentence.replace(err.span, err.suggestion);
                      }
                    }
                    // Only show if the sentence actually changed
                    if (correctedSentence !== message.content) {
                      return (
                        <div className="rounded-none border-2 border-black bg-emerald-50 px-3 py-3 text-sm text-emerald-900 shadow-[3px_3px_0px_0px_#000]">
                          <span className="font-bold uppercase tracking-wider text-[10px] bg-emerald-600 text-white px-1.5 py-0.5 mr-2">Try</span>{' '}
                          <span className="italic font-medium">{correctedSentence}</span>
                        </div>
                      );
                    }
                    return null;
                  })()}
                  {message.errors && message.errors.errors && message.errors.errors.length > 0 && (
                    <div className="mt-1 border-t-2 border-black pt-4 text-sm">
                      <p className="mb-3 flex items-center gap-2 text-[11px] font-black uppercase tracking-[0.18em] text-[var(--app-ink-2)]">
                        <AlertTriangle className="w-4 h-4 text-bauhaus-red" />
                        Corrections
                      </p>
                      <ul className="space-y-4">
                        {message.errors.errors.map((err, i) => (
                          <li key={i} className="rounded-none border-2 border-black bg-white px-3 py-3 shadow-[3px_3px_0px_0px_#000]">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="text-sm text-stone-400 line-through font-medium">{err.span}</span>
                              <span className="text-stone-400">→</span>
                              <span className="font-bold text-rose-700">{err.suggestion}</span>
                            </div>
                            {err.message && (
                              <p className="mt-1 border-l-2 border-black pl-2 text-xs italic text-stone-600">
                                {err.message}
                              </p>
                            )}
                            <div className="flex items-center gap-2 mt-2">
                              <span className={`rounded-none border border-black px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
                                err.category === 'grammar' ? 'bg-bauhaus-red text-white' :
                                err.category === 'spelling' ? 'bg-bauhaus-yellow text-black' :
                                err.category === 'vocabulary' ? 'bg-bauhaus-blue text-white' :
                                'bg-white text-black'
                                }`}>
                                {err.category}
                              </span>
                              {(err as any).occurrence_count > 1 && (
                                <span className="rounded-full bg-stone-100 px-2 py-1 text-[10px] font-medium text-stone-500">
                                  Seen {(err as any).occurrence_count} times
                                </span>
                              )}
                            </div>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
              </div>
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>
    </div>
  );
};

export default ConversationHistory;
