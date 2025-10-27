import React from 'react';
import { useForm } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import * as yup from 'yup';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';

type MessageInputProps = {
  value: string;
  onChange: (val: string) => void;
  onSubmit: (val: string) => void;
};

const schema = yup.object({
  message: yup.string().trim().min(1).required(),
});

type FormData = yup.InferType<typeof schema>;

export default function MessageInput({ value, onChange, onSubmit }: MessageInputProps) {
  const { register, handleSubmit, reset } = useForm<FormData>({
    resolver: yupResolver(schema),
    defaultValues: { message: value },
  });

  const submit = (data: FormData) => {
    onSubmit(data.message);
    reset({ message: '' });
  };

  return (
    <form onSubmit={handleSubmit(submit)} className="flex items-end space-x-2">
      <div className="flex-1">
        <Input
          {...register('message')}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Schreibe deine Nachricht..."
        />
      </div>
      <Button type="submit">Senden</Button>
    </form>
  );
}
