import React from 'react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';

type MessageInputProps = {
  value: string;
  onChange: (val: string) => void;
  onSubmit: (val: string) => Promise<void> | void;
};

export default function MessageInput({ value, onChange, onSubmit }: MessageInputProps) {
  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = value.trim();
    if (!trimmed) {
      return;
    }
    await onSubmit(trimmed);
    onChange('');
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
      <Button type="submit">Senden</Button>
    </form>
  );
}
