import { useCallback, useEffect, useRef, useState } from 'react';
import api from '@/services/api';
import { useWebSocket } from '@/services/websocket';

export type ChatMessage = { id: string; role: 'user' | 'assistant'; content: string };

export function useLearningSession(sessionId: string) {
  const [session, setSession] = useState<any>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const ws = useWebSocket(sessionId);
  const mounted = useRef(false);

  const load = useCallback(async () => {
    const s = await api.get(`/sessions/${sessionId}`);
    setSession(s);
    const m = await api.get(`/sessions/${sessionId}/messages`);
    setMessages(m);
  }, [sessionId]);

  useEffect(() => {
    if (mounted.current) return;
    mounted.current = true;
    load();
    ws.connect();

    ws.onMessage('turn_result', (data: any) => {
      setMessages((prev) => [
        ...prev,
        { id: crypto.randomUUID(), role: 'assistant', content: data.reply?.content ?? '' },
      ]);
    });

    return () => {
      ws.disconnect();
    };
  }, [load, ws]);

  const send = useCallback(
    async (text: string, suggested?: number[]) => {
      setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: 'user', content: text }]);
      await api.post(`/sessions/${sessionId}/messages`, {
        content: text,
        suggested_words: suggested,
      });
      ws.sendMessage(text, suggested);
    },
    [sessionId, ws]
  );

  return { session, messages, send };
}
