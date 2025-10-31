import React, { useCallback, useState } from 'react';
import toast from 'react-hot-toast';
import type { ChatMessage, TargetWord } from '@/hooks/useLearningSession';

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

  // Add new handlers for generic (non-target) words
  const handleGenericWordHover = useCallback((word: string) => {
    console.log('Hovered over generic word:', word);
    // Future enhancement: Trigger a new prop, e.g., onWordLookup(word: string)
  }, []);

  const handleGenericWordClick = useCallback((word: string) => {
    toast(`Clicked on "${word}"`, {
      icon: '❓',
      duration: 2000,
    });
    // This could also trigger a lookup API call
  }, []);

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
            onMouseEnter={() => handleGenericWordHover(part)}
            onClick={() => handleGenericWordClick(part)}
            title={`Look up "${part}"`}
          >
            {part}
          </span>
        );
      }
      return part; // Return non-word parts (spaces, punctuation) as is
    });
  }, [handleGenericWordHover, handleGenericWordClick]);

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
    </div>
  );
}