import React from 'react';

type Message = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at?: string;
};

type Props = {
  messages: Message[];
};

export default function ConversationHistory({ messages }: Props) {
  return (
    <div className="space-y-4">
      {messages.map((m) => (
        <div key={m.id} className={`message-bubble ${m.role === 'user' ? 'message-user' : 'message-ai'}`}>
          <p className="whitespace-pre-wrap">{m.content}</p>
        </div>
      ))}
    </div>
  );
}
