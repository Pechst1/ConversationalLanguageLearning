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

  const renderContent = useCallback(
    (message: ChatMessage) => {
      if (!message.targets?.length) {
        return message.content;
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
            if (before) parts.push(before);

            const className = familiarityClasses[target.familiarity ?? ''] ?? defaultHighlightClass;

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
          if (remainder) parts.push(remainder);
          return parts;
        });
      }, message.content);
    },
    [handleHover, handleClick]
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
