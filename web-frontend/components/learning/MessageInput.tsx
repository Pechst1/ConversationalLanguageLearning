import React from 'react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Volume2, VolumeX } from 'lucide-react';
import VoiceInput from './VoiceInput';
import { useSpeakingMode } from '@/contexts/SpeakingModeContext';

type MessageInputProps = {
  value: string;
  onChange: (val: string) => void;
  onSubmit: (val: string) => Promise<void> | void;
};

export default function MessageInput({ value, onChange, onSubmit }: MessageInputProps) {
  const { isSpeakingMode, toggleSpeakingMode, isSpeaking } = useSpeakingMode();

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = value.trim();
    if (!trimmed) {
      return;
    }
    await onSubmit(trimmed);
    onChange('');
  };

  const handleTranscript = (text: string) => {
    const newValue = value ? `${value} ${text}` : text;
    onChange(newValue);
  };

  return (
    <form onSubmit={handleSubmit} className="flex items-end space-x-2">
      <div className="flex-1">
        <Input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Schreibe deine Nachricht..."
        />
      </div>
      <VoiceInput onTranscript={handleTranscript} />
      <Button
        type="button"
        variant={isSpeakingMode ? "default" : "secondary"}
        size="icon"
        onClick={toggleSpeakingMode}
        title={isSpeakingMode ? "Speaking mode ON" : "Speaking mode OFF"}
        className={isSpeaking ? "animate-pulse" : ""}
      >
        {isSpeakingMode ? (
          <Volume2 className="h-5 w-5" />
        ) : (
          <VolumeX className="h-5 w-5" />
        )}
      </Button>
      <Button type="submit">Senden</Button>
    </form>
  );
}
