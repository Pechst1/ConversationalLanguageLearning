import React, { useState } from 'react';
import { ChevronRight, HelpCircle } from 'lucide-react';
import { Button } from '@/components/ui/Button';

interface Choice {
  choice_id: string;
  text: string;
  hint?: string;
}

interface NarrativeChoiceCardProps {
  choices: Choice[];
  onChoiceSelected: (choiceId: string) => void;
  narrativeText?: string;
  disabled?: boolean;
}

export default function NarrativeChoiceCard({
  choices,
  onChoiceSelected,
  narrativeText,
  disabled = false,
}: NarrativeChoiceCardProps) {
  const [selectedChoice, setSelectedChoice] = useState<string | null>(null);
  const [hoveredChoice, setHoveredChoice] = useState<string | null>(null);

  const handleChoiceClick = (choiceId: string) => {
    if (disabled) return;
    setSelectedChoice(choiceId);
    // Small delay for visual feedback before triggering the callback
    setTimeout(() => {
      onChoiceSelected(choiceId);
    }, 200);
  };

  return (
    <div className="bg-gradient-to-br from-amber-50 to-orange-50 border-2 border-amber-300 rounded-xl p-6 shadow-lg">
      {/* Narrative text (if provided) */}
      {narrativeText && (
        <div className="mb-6">
          <div className="flex items-start gap-2 mb-2">
            <div className="flex-shrink-0 w-8 h-8 bg-amber-400 rounded-full flex items-center justify-center">
              <span className="text-white text-sm font-bold">?</span>
            </div>
            <div className="flex-1">
              <p className="text-gray-800 text-base leading-relaxed">
                {narrativeText}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Choices header */}
      <div className="mb-4">
        <div className="flex items-center gap-2">
          <div className="h-1 flex-1 bg-gradient-to-r from-amber-400 to-orange-400 rounded-full"></div>
          <span className="text-sm font-bold text-amber-900 uppercase tracking-wide">
            Make Your Choice
          </span>
          <div className="h-1 flex-1 bg-gradient-to-r from-orange-400 to-amber-400 rounded-full"></div>
        </div>
      </div>

      {/* Choice buttons */}
      <div className="space-y-3">
        {choices.map((choice, index) => {
          const isSelected = selectedChoice === choice.choice_id;
          const isHovered = hoveredChoice === choice.choice_id;

          return (
            <button
              key={choice.choice_id}
              onClick={() => handleChoiceClick(choice.choice_id)}
              onMouseEnter={() => setHoveredChoice(choice.choice_id)}
              onMouseLeave={() => setHoveredChoice(null)}
              disabled={disabled || selectedChoice !== null}
              className={`
                w-full p-4 rounded-lg text-left transition-all duration-200
                border-2 relative overflow-hidden group
                ${
                  isSelected
                    ? 'bg-amber-500 border-amber-600 text-white shadow-lg scale-105'
                    : isHovered
                    ? 'bg-white border-amber-400 shadow-md scale-102'
                    : 'bg-white border-amber-200 hover:border-amber-400'
                }
                ${disabled || selectedChoice !== null ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'}
              `}
            >
              {/* Choice number badge */}
              <div className={`
                absolute top-3 left-3 w-7 h-7 rounded-full flex items-center justify-center
                text-sm font-bold transition-colors
                ${
                  isSelected
                    ? 'bg-white text-amber-600'
                    : 'bg-amber-100 text-amber-700 group-hover:bg-amber-200'
                }
              `}>
                {index + 1}
              </div>

              {/* Choice content */}
              <div className="ml-10">
                <div className="flex items-start justify-between gap-3">
                  <p className={`
                    font-semibold text-base transition-colors
                    ${isSelected ? 'text-white' : 'text-gray-900'}
                  `}>
                    {choice.text}
                  </p>
                  <ChevronRight className={`
                    h-5 w-5 flex-shrink-0 transition-all
                    ${
                      isSelected
                        ? 'text-white translate-x-1'
                        : 'text-amber-600 group-hover:translate-x-1'
                    }
                  `} />
                </div>

                {/* Hint text */}
                {choice.hint && (
                  <div className={`
                    flex items-start gap-2 mt-2 text-sm
                    ${isSelected ? 'text-amber-100' : 'text-gray-600'}
                  `}>
                    <HelpCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
                    <p className="italic">{choice.hint}</p>
                  </div>
                )}
              </div>

              {/* Selection indicator */}
              {isSelected && (
                <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent animate-shimmer"></div>
              )}
            </button>
          );
        })}
      </div>

      {/* Helper text */}
      <div className="mt-4 text-center">
        <p className="text-xs text-amber-800 italic">
          Choose wisely - your decision will affect how the story unfolds
        </p>
      </div>
    </div>
  );
}

/**
 * Parse choice markers from AI message content.
 * Expected format: [[CHOICE: choice_id | Choice text in French]]
 *
 * @param messageContent - The message content from the AI
 * @returns Object with narrative text and parsed choices
 */
export function parseChoicesFromMessage(messageContent: string): {
  narrativeText: string;
  choices: Choice[];
} {
  const choiceRegex = /\[\[CHOICE:\s*([^\|]+)\s*\|\s*([^\]]+)\]\]/g;
  const choices: Choice[] = [];
  let match;

  // Extract all choices
  while ((match = choiceRegex.exec(messageContent)) !== null) {
    const choiceId = match[1].trim();
    const text = match[2].trim();

    choices.push({
      choice_id: choiceId,
      text: text,
    });
  }

  // Remove choice markers from narrative text
  const narrativeText = messageContent.replace(choiceRegex, '').trim();

  return {
    narrativeText,
    choices,
  };
}

/**
 * Check if a message contains choice markers
 */
export function hasChoiceMarkers(messageContent: string): boolean {
  return /\[\[CHOICE:/.test(messageContent);
}
