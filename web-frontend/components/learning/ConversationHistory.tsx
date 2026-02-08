import React, { useCallback, useEffect, useRef, useState } from 'react';
import toast from 'react-hot-toast';
import type { ChatMessage, TargetWord, TargetedError } from '@/hooks/useLearningSession';
import apiService from '@/services/api';
import InteractiveText from './InteractiveText';
import StageDirection, { parseMessageContent } from './StageDirection';
import { Target, AlertTriangle, Volume2, Eye, EyeOff, Ear } from 'lucide-react';
import { useSpeakingMode } from '@/contexts/SpeakingModeContext';

type Props = {
  messages: ChatMessage[];
  onWordInteract?: (wordId: number, exposureType: 'hint' | 'translation') => void;
  onWordFlag?: (wordId: number) => void;
  activeSessionId?: string;
};

const familiarityClasses: Record<string, string> = {
  new: 'bg-bauhaus-red text-white border-2 border-black font-bold shadow-[2px_2px_0px_0px_#000]',
  learning: 'bg-bauhaus-yellow text-black border-2 border-black font-bold shadow-[2px_2px_0px_0px_#000]',
  familiar: 'bg-green-500 text-white border-2 border-black font-bold shadow-[2px_2px_0px_0px_#000]',
};

const defaultHighlightClass = 'bg-bauhaus-blue text-white border-2 border-black font-bold shadow-[2px_2px_0px_0px_#000]';

const errorCategoryLabels: Record<string, string> = {
  grammar: 'Grammatik',
  spelling: 'Rechtschreibung',
  vocabulary: 'Wortschatz',
  style: 'Stil',
  syntax: 'Satzbau',
};

const subcategoryLabels: Record<string, string> = {
  gender_agreement: 'Genus / Artikel',
  verb_tenses: 'Zeitformen',
  subjonctif: 'Subjonctif',
  conditional: 'Konditional',
  negation: 'Verneinung',
  prepositions: 'Präpositionen',
  articles: 'Artikel',
  pronouns: 'Pronomen',
  word_order: 'Wortstellung',
  subject_verb_agreement: 'Subjekt-Verb',
  accents: 'Akzente',
  common_misspellings: 'Rechtschreibung',
  false_friends: 'Falsche Freunde',
  word_choice: 'Wortwahl',
  capitalization: 'Großschreibung',
  quotation_marks: 'Anführungszeichen',
};

const formatErrorLabel = (category: string, pattern?: string) => {
  const catLabel = errorCategoryLabels[category] || category;
  if (!pattern) return catLabel;

  const cleanPattern = pattern.replace(/^llm_/, '');

  // If pattern is just the category name (redundant) or unknown, hide it
  if (cleanPattern === category || cleanPattern === 'unknown' || cleanPattern === 'grammar') {
    return catLabel;
  }

  const subLabel = subcategoryLabels[cleanPattern] || cleanPattern.replace(/_/g, ' ');
  return `${catLabel}: ${subLabel}`;
};

const TargetedErrorIndicator: React.FC<{ errors: TargetedError[] }> = ({ errors }) => {
  const [isTooltipVisible, setIsTooltipVisible] = useState(false);

  if (!errors || errors.length === 0) return null;

  return (
    <div className="relative inline-flex items-center mb-4 mt-2">
      <div
        className="flex items-center gap-2 text-xs font-black text-black bg-bauhaus-yellow px-4 py-2 border-4 border-black cursor-help shadow-[4px_4px_0px_0px_#000] hover:translate-y-[-2px] hover:shadow-[6px_6px_0px_0px_#000] transition-all"
        onMouseEnter={() => setIsTooltipVisible(true)}
        onMouseLeave={() => setIsTooltipVisible(false)}
      >
        <Target className="w-5 h-5 stroke-[2.5]" />
        <span className="uppercase tracking-widest text-sm">FOKUS:</span>
        <span className="truncate max-w-[300px]">
          {errors.slice(0, 2).map((e, i) => (
            <span key={i}>
              {i > 0 && ' + '}
              {formatErrorLabel(e.category, e.pattern)}
            </span>
          ))}
          {errors.length > 2 && ` +${errors.length - 2}`}
        </span>
      </div>
      {isTooltipVisible && (
        <div className="absolute top-full left-0 mt-2 w-80 bg-white border-4 border-black p-5 shadow-[8px_8px_0px_0px_#000] z-50">
          <p className="font-black mb-4 text-black uppercase border-b-4 border-black pb-2 text-lg">
            AKTUELLER LERNFOKUS
          </p>
          <ul className="space-y-4">
            {errors.map((err, i) => (
              <li key={i} className="flex flex-col bg-gray-50 border-l-4 border-bauhaus-blue p-2">
                <span className="font-bold text-black text-sm uppercase mb-1">
                  {formatErrorLabel(err.category, err.pattern)}
                </span>
                {err.correction && (
                  <span className="text-gray-600 text-xs font-mono bg-white p-1 border border-black/20 inline-block">
                    Ziel: &quot;{err.correction}&quot;
                  </span>
                )}
                {(err.lapses > 0 || err.reps > 0) && (
                  <span className="text-gray-500 text-[10px] mt-1 font-bold uppercase tracking-wider">
                    {err.lapses} Fehler • {err.reps} Wiederholungen
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

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
      <div className="relative bg-gradient-to-r from-amber-50 to-orange-50 border-2 border-dashed border-amber-400 rounded-lg p-6 min-h-[80px] overflow-hidden">
        {/* Decorative blur bars to simulate hidden text */}
        <div className="space-y-2">
          <div className="h-4 bg-amber-200/60 rounded blur-[2px] w-full" />
          <div className="h-4 bg-amber-200/60 rounded blur-[2px] w-4/5" />
          <div className="h-4 bg-amber-200/60 rounded blur-[2px] w-3/5" />
        </div>

        {/* Overlay with actions */}
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-white/80 backdrop-blur-sm">
          <div className="flex items-center gap-2 text-amber-700">
            <Ear className={`w-5 h-5 ${isSpeaking ? 'animate-pulse' : ''}`} />
            <span className="font-bold text-sm uppercase tracking-wider">
              {isSpeaking ? 'Listening...' : 'Listen carefully!'}
            </span>
          </div>

          <div className="flex items-center gap-2">
            {onReplay && (
              <button
                onClick={onReplay}
                className="flex items-center gap-1 px-3 py-1.5 bg-amber-100 hover:bg-amber-200 border-2 border-amber-400 text-amber-700 text-xs font-bold uppercase tracking-wider transition-all hover:shadow-md"
              >
                <Volume2 className="w-3 h-3" />
                Replay
              </button>
            )}
            <button
              onClick={onReveal}
              className="flex items-center gap-1 px-3 py-1.5 bg-white hover:bg-gray-50 border-2 border-gray-300 text-gray-600 text-xs font-bold uppercase tracking-wider transition-all hover:shadow-md"
            >
              <Eye className="w-3 h-3" />
              Reveal
            </button>
          </div>

          <p className="text-xs text-gray-500 mt-1">
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
          className={`${className} px-1.5 py-0.5 mx-0.5 rounded-none cursor-pointer transition-all duration-150 hover:-translate-y-0.5 relative group inline-block`}
          onMouseEnter={hasValidId ? () => handleWordHover(target.id) : undefined}
          onMouseLeave={() => setHoveredWord(null)}
          onClick={hasValidId ? () => handleWordClick(target.id) : undefined}
          onDoubleClick={hasValidId ? () => handleWordFlag(target.id) : undefined}
          title={`Double-click to mark as difficult${translation ? ` | Translation: ${translation}` : ''}`}
        >
          {target.text}
          {isHovered && (
            <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-3 px-3 py-2 bg-black border-2 border-white text-white font-bold text-sm shadow-[4px_4px_0px_0px_#fff] whitespace-nowrap z-50 min-w-[120px] text-center">
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
    <div className="flex flex-col h-full bg-white border-4 border-black shadow-[8px_8px_0px_0px_#000]">
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {messages.map((message, index) => (
          <div
            key={index}
            className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'
              }`}
          >
            <div
              className={`max-w-xs lg:max-w-md message-bubble ${message.role === 'user'
                ? 'bg-bauhaus-blue text-white border-4 border-black shadow-[6px_6px_0px_0px_#000]'
                : 'bg-white text-black border-4 border-black shadow-[6px_6px_0px_0px_#000]'
                } p-6`}
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
                          className={`flex items-center gap-1 px-2 py-1 text-xs font-medium rounded transition-all ${isSpeaking && speakingMessageId === message.id
                            ? 'bg-amber-100 text-amber-700 animate-pulse'
                            : 'bg-gray-100 hover:bg-gray-200 text-gray-600'
                            }`}
                        >
                          <Volume2 className="w-3 h-3" />
                          {isSpeaking && speakingMessageId === message.id ? 'Playing...' : 'Replay'}
                        </button>
                        <span className="text-xs text-gray-400">Revealed</span>
                      </div>
                    )}
                    {message.targetedErrors && message.targetedErrors.length > 0 && (
                      <TargetedErrorIndicator errors={message.targetedErrors} />
                    )}
                    {sceneContent && (
                      <StageDirection content={sceneContent} />
                    )}
                    {message.targets && message.targets.length > 0 ? (
                      <div className="text-lg leading-relaxed font-medium">
                        {renderWordWithHighlighting(dialogueContent, message.targets)}
                      </div>
                    ) : (
                      <InteractiveText
                        text={dialogueContent}
                        language={detectLanguage(dialogueContent)}
                        enableTranslation={true}
                        activeSessionId={activeSessionId}
                        className="text-lg leading-relaxed font-medium"
                      />
                    )}
                  </>
                );
              })() : (
                <div className="flex flex-col gap-3">
                  <span className="text-lg font-bold">{message.content}</span>
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
                        <div className="flex items-center gap-2 text-sm bg-bauhaus-green/20 border-l-4 border-bauhaus-green px-3 py-2">
                          <span className="text-green-200 font-medium">✓</span>
                          <span className="text-green-100 italic">{correctedSentence}</span>
                        </div>
                      );
                    }
                    return null;
                  })()}
                  {message.errors && message.errors.errors && message.errors.errors.length > 0 && (
                    <div className="mt-2 pt-4 border-t-2 border-white/20 text-sm">
                      <p className="font-black text-bauhaus-yellow mb-2 uppercase tracking-wider flex items-center gap-2">
                        <AlertTriangle className="w-4 h-4" />
                        Korrekturen
                      </p>
                      <ul className="space-y-3">
                        {message.errors.errors.map((err, i) => (
                          <li key={i} className="bg-bauhaus-red/20 border-2 border-white/30 p-3 shadow-sm">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="line-through text-red-200 text-sm opacity-80">{err.span}</span>
                              <span className="text-white">➜</span>
                              <span className="font-bold text-white bg-bauhaus-green px-1">{err.suggestion}</span>
                            </div>
                            {err.message && (
                              <p className="text-xs text-white/90 mt-1 italic pl-2 border-l-2 border-white/40">
                                {err.message}
                              </p>
                            )}
                            <div className="flex items-center gap-2 mt-2">
                              <span className={`text-[10px] uppercase font-black px-2 py-1 text-black border border-black ${err.category === 'grammar' ? 'bg-bauhaus-red text-white' :
                                err.category === 'spelling' ? 'bg-orange-500 text-white' :
                                  err.category === 'vocabulary' ? 'bg-bauhaus-blue text-white' :
                                    'bg-white'
                                }`}>
                                {err.category}
                              </span>
                              {(err as any).occurrence_count > 1 && (
                                <span className="text-[10px] bg-black text-bauhaus-yellow px-2 py-1 font-bold border border-white/50">
                                  × {(err as any).occurrence_count} mal
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
        ))}
        <div ref={messagesEndRef} />
      </div>
    </div>
  );
};

export default ConversationHistory;
