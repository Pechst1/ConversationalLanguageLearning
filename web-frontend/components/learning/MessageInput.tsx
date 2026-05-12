import React from 'react';
import VoiceInput from './VoiceInput';
import { useSpeakingMode } from '@/contexts/SpeakingModeContext';

type MessageInputProps = {
  value: string;
  onChange: (val: string) => void;
  onSubmit: (val: string) => Promise<void> | void;
  disabled?: boolean;
  placeholder?: string;
  helperText?: string;
};

export default function MessageInput({
  value,
  onChange,
  onSubmit,
  disabled = false,
  placeholder,
  helperText,
}: MessageInputProps) {
  const { isSpeakingMode } = useSpeakingMode();

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = value.trim();
    if (!trimmed || disabled) {
      return;
    }
    await onSubmit(trimmed);
    onChange('');
  };

  const handleTranscript = (text: string) => {
    const newValue = value ? `${value} ${text}` : text;
    onChange(newValue);
  };

  const handleKeyDown = async (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== 'Enter' || event.shiftKey) {
      return;
    }

    event.preventDefault();
    const trimmed = value.trim();
    if (!trimmed || disabled) {
      return;
    }

    await onSubmit(trimmed);
    onChange('');
  };

  return (
    <form onSubmit={handleSubmit} className="rounded-[28px] border border-stone-200 bg-white px-4 py-3 shadow-sm">
      <div className="flex items-end gap-3">
        <div className="min-w-0 flex-1">
          <textarea
            value={value}
            onChange={(event) => onChange(event.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            placeholder={placeholder || (
              isSpeakingMode
                ? 'Type or dictate your reply...'
                : 'Write your next reply...'
            )}
            disabled={disabled}
            className="min-h-[56px] w-full resize-none border-0 bg-transparent px-0 py-2 text-[15px] leading-6 text-stone-900 placeholder:text-stone-400 focus:outline-none disabled:cursor-not-allowed disabled:text-stone-400"
          />
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-stone-400">
            <span>{helperText || 'Enter sends. Shift+Enter adds a line break.'}</span>
            {disabled ? (
              <span>Complete the prompt above to continue.</span>
            ) : isSpeakingMode ? (
              <span>Voice mode is on. Use the mic to dictate.</span>
            ) : (
              <span>Tap a focus word above to stage it for this reply.</span>
            )}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <VoiceInput onTranscript={handleTranscript} disabled={disabled} />
          <button
            type="submit"
            className="inline-flex h-11 items-center justify-center rounded-full bg-stone-900 px-5 text-sm font-medium text-stone-50 transition-colors hover:bg-stone-800 disabled:cursor-not-allowed disabled:bg-stone-300"
            disabled={disabled || !value.trim()}
          >
            Send
          </button>
        </div>
      </div>
    </form>
  );
}
