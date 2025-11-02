import React from 'react';
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

const normalizeWordId = (id: unknown): number | null => {
  if (typeof id === 'number' && Number.isInteger(id) && id > 0) return id;
  if (typeof id === 'string') {
    const parsed = parseInt(id, 10);
    if (Number.isInteger(parsed) && parsed > 0) return parsed;
  }
  return null;
};

export default function ConversationHistory({ messages, onWordInteract, onWordFlag }: Props) {
  const [tooltip, setTooltip] = React.useState<{ x: number; y: number; word: string; translation: string } | null>(null);
  const lookupCache = React.useRef<Record<string, string>>({});

  const ensureTranslation = React.useCallback(async (word: string, fallback?: string | null): Promise<string> => {
    const key = word.toLowerCase();
    if (fallback && fallback.trim()) {
      lookupCache.current[key] = fallback.trim();
      return fallback.trim();
    }
    if (lookupCache.current[key]) {
      return lookupCache.current[key];
    }
    try {
      const result = await apiService.lookupVocabulary(word);
      const translation =
        result?.german_translation ||
        result?.english_translation ||
        result?.french_translation ||
        result?.definition ||
        result?.example_translation ||
        'Übersetzung nicht verfügbar';
      lookupCache.current[key] = translation;
      return translation;
    } catch (error) {
      console.debug('Vocabulary lookup failed', error);
      lookupCache.current[key] = 'Übersetzung nicht verfügbar';
      return 'Übersetzung nicht verfügbar';
    }
  }, []);

  const handleTargetEnter = React.useCallback(
    async (event: React.MouseEvent<HTMLSpanElement>, target: TargetWord) => {
      const wordId = normalizeWordId(target.id);
      if (wordId === null) {
        return;
      }

      onWordInteract?.(wordId, 'hint');

      const rect = event.currentTarget.getBoundingClientRect();
      const translation = await ensureTranslation(target.word, target.translation || target.hintTranslation);

      setTooltip({
        x: rect.left + rect.width / 2,
        y: rect.top,
        word: target.word,
        translation,
      });
    },
    [ensureTranslation, onWordInteract]
  );

  const handleTargetLeave = React.useCallback(() => {
    setTooltip(null);
  }, []);

  const handleTargetClick = React.useCallback(
    (target: TargetWord) => {
      const wordId = normalizeWordId(target.id);
      if (wordId === null) {
        toast.error('Wort konnte nicht markiert werden.');
        return;
      }

      if (target.translation) {
        toast(`"${target.word}" zur Wiederholung vorgemerkt`, { icon: '🧠', duration: 2500 });
      }

      onWordInteract?.(wordId, 'translation');
      onWordFlag?.(wordId);
    },
    [onWordFlag, onWordInteract]
  );

  const renderContent = React.useCallback(
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

            parts.push(
              <span
                key={`${target.id}-${segmentIndex}-${offset}`}
                className={`rounded-md px-1 font-semibold cursor-pointer transition-colors hover:shadow-sm ${className}`}
                onMouseEnter={(e) => handleTargetEnter(e, target)}
                onMouseLeave={handleTargetLeave}
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
          if (remainder) {
            parts.push(remainder);
          }
          return parts.length ? parts : [segment];
        });
      }, message.content);

      return highlighted;
    },
    [handleTargetClick, handleTargetEnter, handleTargetLeave]
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
        >
          <p className="text-sm font-semibold text-gray-900">{tooltip.word}</p>
          <p className="text-xs text-gray-600">{tooltip.translation}</p>
        </div>
      )}
    </div>
  );
}
