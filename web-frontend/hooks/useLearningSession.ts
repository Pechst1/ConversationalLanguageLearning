import { useCallback, useEffect, useState } from 'react';
import api from '@/services/api';
import { useWebSocket } from '@/services/websocket';

export type TargetWord = {
  id: number;
  word: string;
  translation?: string;
  familiarity?: 'new' | 'learning' | 'familiar';
  hintSentence?: string | null;
  hintTranslation?: string | null;
  isNew?: boolean;
};

export type ChatMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  targets?: TargetWord[];
  xp?: number;
};

const isValidId = (value: number | undefined): value is number =>
  typeof value === 'number' && Number.isFinite(value) && value > 0;

const filterValidTargets = (list: TargetWord[]): TargetWord[] => list.filter((item) => isValidId(item.id));

function normalizeId(value: any): number | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  const parsed = Number.parseInt(String(value ?? ''), 10);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function mapTarget(detail: any): TargetWord {
  const id = normalizeId(detail.word_id);
  return {
    id: id ?? -1,
    word: detail.word,
    translation: detail.translation ?? undefined,
    familiarity: detail.familiarity ?? undefined,
    hintSentence: detail.hint_sentence ?? undefined,
    hintTranslation: detail.hint_translation ?? undefined,
    isNew: detail.is_new ?? undefined,
  };
}

function mapMessage(item: any): ChatMessage {
  const targets = Array.isArray(item.target_details)
    ? filterValidTargets(item.target_details.map(mapTarget))
    : [];
  return {
    id: item.id,
    role: item.sender === 'user' ? 'user' : 'assistant',
    content: item.content ?? '',
    targets,
    xp: item.xp_earned ?? undefined,
  };
}

export function useLearningSession(sessionId: string) {
  const [session, setSession] = useState<any>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [suggested, setSuggested] = useState<TargetWord[]>([]);
  const ws = useWebSocket(sessionId);

  const mapQueueWord = useCallback((item: any) => ({
    id: normalizeId(item.word_id) ?? -1,
    word: item.word,
    translation: item.english_translation || '',
    familiarity: item.is_new ? 'new' : 'learning',
    isNew: item.is_new,
  }), []);

  const load = useCallback(async () => {
    if (!sessionId) return;
    const sessionResponse = await api.get(`/sessions/${sessionId}`);
    setSession(sessionResponse);

    const response = await api.get(`/sessions/${sessionId}/messages`);
    const items = Array.isArray(response?.items) ? response.items : [];
    const mapped = items.map(mapMessage);
    setMessages(mapped);

    const lastAssistant = [...mapped]
      .reverse()
      .find((message) => message.role === 'assistant' && message.targets && message.targets.length > 0);
    if (lastAssistant?.targets) {
      setSuggested(lastAssistant.targets);
    } else {
      // fallback: fetch queue to populate suggestions when backend delivered none yet
      try {
        const queue = await api.getProgressQueue();
        let fallback = Array.isArray(queue)
          ? queue.map(mapQueueWord).filter((item) => isValidId(item.id))
          : [];

        if (!fallback.length) {
          const vocab = await api.listVocabulary({ limit: 8 });
          const items = Array.isArray(vocab?.items) ? vocab.items : [];
          fallback = items
            .map((item: any) => ({
              id: normalizeId(item.id) ?? -1,
              word: item.word,
              translation: item.english_translation || '',
              familiarity: 'new',
              isNew: true,
            }))
            .filter((item) => isValidId(item.id));
        }

        if (fallback.length) {
          setSuggested(fallback);
        }
      } catch (error) {
        console.debug('Failed to load fallback vocabulary', error);
      }
    }
  }, [sessionId, mapQueueWord]);

  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;

    (async () => {
      if (cancelled) return;
      await load();
      try {
        if (cancelled) return;
        await ws.connect();

        ws.onMessage('session_ready', (data: any) => {
          if (data?.session) {
            setSession(data.session);
          }
        });

        ws.onMessage('turn_result', (data: any) => {
          if (!data) return;
          if (data.session) {
            setSession(data.session);
          }
          const updates: ChatMessage[] = [];

          if (data.user_message) {
            updates.push(mapMessage({ ...data.user_message, sender: 'user' }));
          }

          if (data.assistant_turn?.message) {
            const assistantMessage = mapMessage({
              ...data.assistant_turn.message,
              sender: 'assistant',
              target_details: data.assistant_turn.targets ?? [],
            });
            updates.push(assistantMessage);

            const targets = Array.isArray(data.assistant_turn.targets)
              ? filterValidTargets(data.assistant_turn.targets.map(mapTarget))
              : [];
            const usedIds = new Set<number>(
              Array.isArray(data.word_feedback)
                ? data.word_feedback.filter((wf: any) => wf.was_used).map((wf: any) => wf.word_id)
                : []
            );
            setSuggested((prev) => {
              const keep = prev.filter((w) => isValidId(w.id) && !usedIds.has(w.id));
              const merged = [...keep];
              for (const t of targets) {
                if (!merged.find((m) => m.id === t.id)) merged.push(t);
              }
              return merged;
            });
          }

          if (updates.length) {
            setMessages((prev) => [...prev, ...updates]);
          }
        });
      } catch (error) {
        console.error('Failed to establish WebSocket connection', error);
      }
    })();

    return () => {
      cancelled = true;
      ws.disconnect();
    };
  }, [sessionId, load, ws]);

  const send = useCallback(
    async (text: string, _selectedWordIds?: number[]) => {
      if (!text.trim()) {
        return;
      }

      // Always inform the backend about the full set of currently shown suggestions,
      // so it can exclude them from the next adaptive queue (breaks the "le/de" loop).
      const allSuggestionIds = suggested.filter((w) => isValidId(w.id)).map((w) => w.id);

      if (ws.isConnected()) {
        ws.sendMessage(text, allSuggestionIds);
        return;
      }

      const result = await api.post(`/sessions/${sessionId}/messages`, {
        content: text,
        suggested_word_ids: allSuggestionIds,
      });

      if (result?.session) {
        setSession(result.session);
      }
      const updates: ChatMessage[] = [];
      if (result?.user_message) {
        updates.push(mapMessage({ ...result.user_message, sender: 'user' }));
      }
      if (result?.assistant_turn?.message) {
        const targets = Array.isArray(result.assistant_turn.targets)
          ? filterValidTargets(result.assistant_turn.targets.map(mapTarget))
          : [];
        updates.push(
          mapMessage({
            ...result.assistant_turn.message,
            sender: 'assistant',
            target_details: result.assistant_turn.targets ?? [],
          })
        );
        const usedIds = new Set<number>(
          Array.isArray(result.word_feedback)
            ? result.word_feedback.filter((wf: any) => wf.was_used).map((wf: any) => wf.word_id)
            : []
        );
        setSuggested((prev) => {
          const keep = prev.filter((w) => isValidId(w.id) && !usedIds.has(w.id));
          const merged = [...keep];
          for (const t of targets) {
            if (!merged.find((m) => m.id === t.id)) merged.push(t);
          }
          return merged;
        });
      }

      if (updates.length) {
        setMessages((prev) => [...prev, ...updates]);
      }
    },
    [sessionId, ws, suggested]
  );

  const logExposure = useCallback(
    async (wordId: number, exposureType: 'hint' | 'translation') => {
      if (!sessionId) return;
      try {
        await api.logExposure(sessionId, {
          word_id: wordId,
          exposure_type: exposureType,
        });
      } catch (error) {
        console.debug('Exposure logging failed', error);
      }
    },
    [sessionId]
  );

  const flagWord = useCallback(
    async (wordId: number) => {
      if (!sessionId) return;
      try {
        await api.markWordDifficult(sessionId, { word_id: wordId });
      } catch (error) {
        console.debug('Mark difficult failed', error);
      }
    },
    [sessionId]
  );

  const complete = useCallback(async () => {
    if (!sessionId) return null;
    await api.updateSessionStatus(sessionId, 'completed');
    return api.getSessionSummary(sessionId);
  }, [sessionId]);

  return { session, messages, send, suggested, logExposure, flagWord, complete };
}
