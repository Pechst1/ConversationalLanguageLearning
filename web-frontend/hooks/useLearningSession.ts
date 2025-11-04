import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useWebSocket as useWebSocketClient } from '@/services/websocket';
import apiService from '@/services/api';
import toast from 'react-hot-toast';

export interface TargetWord {
  id: number;
  word: string;
  text: string;
  translation?: string;
  hintTranslation?: string;
  familiarity?: 'new' | 'learning' | 'familiar';
  difficulty?: number;
  exposureCount?: number;
  position?: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  xp?: number;
  targets?: TargetWord[];
}

export interface SessionStats {
  totalReviews: number;
  correctAnswers: number;
  sessionDuration?: number;
  xpEarned?: number;
  newCards?: number;
  reviewedCards?: number;
  averageResponseTime?: number;
  difficultyBreakdown?: {
    easy: number;
    good: number;
    hard: number;
    again: number;
  };
  wordsLearned?: string[];
  sessionStartTime?: string;
  sessionEndTime?: string;
}

export interface LearningSession {
  id: string;
  status: 'active' | 'completed' | 'paused' | 'abandoned';
  startTime: Date;
  endTime?: Date;
  stats: SessionStats;
  messages: ChatMessage[];
  targetWords: TargetWord[];
}

const parseNumericId = (value: unknown): number | null => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }

  if (typeof value === 'string') {
    const parsed = Number.parseInt(value, 10);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }

  return null;
};

const normalizeTargetWord = (target: any): TargetWord | null => {
  if (!target) {
    return null;
  }

  const id =
    parseNumericId(target.id) ??
    parseNumericId(target.word_id) ??
    parseNumericId(target.wordId) ??
    parseNumericId(target.target_word_id);

  if (id === null) {
    return null;
  }

  const rawText = target.text ?? target.word ?? '';
  const textValue = typeof rawText === 'string' ? rawText.trim() : '';

  return {
    id,
    word: typeof target.word === 'string' ? target.word : textValue,
    text: textValue || (typeof target.word === 'string' ? target.word : ''),
    translation: target.translation ?? target.hintTranslation ?? target.hint_translation ?? undefined,
    hintTranslation: target.hintTranslation ?? target.hint_translation ?? undefined,
    familiarity:
      target.familiarity ?? (typeof target.is_new === 'boolean' ? (target.is_new ? 'new' : undefined) : undefined),
    difficulty: target.difficulty ?? target.difficulty_rating ?? undefined,
    exposureCount: target.exposure_count ?? target.exposures ?? undefined,
    position:
      typeof target.position === 'number'
        ? target.position
        : typeof target.start === 'number'
        ? target.start
        : typeof target.start_index === 'number'
        ? target.start_index
        : undefined,
  };
};

const normalizeTargets = (targets: any): TargetWord[] => {
  if (!Array.isArray(targets)) {
    return [];
  }

  return targets
    .map((target) => normalizeTargetWord(target))
    .filter((target): target is TargetWord => target !== null);
};

export function useLearningSession(sessionId?: string) {
  const [session, setSession] = useState<LearningSession | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const messageIdCounter = useRef(0);

  const {
    connect: connectWebSocket,
    disconnect: disconnectWebSocket,
    sendMessage: rawWebSocketSend,
    onMessage: registerWebSocketHandler,
    isConnected: isWebSocketConnected,
  } = useWebSocketClient(sessionId || '');

  const generateMessageId = useCallback(() => {
    return `msg-${Date.now()}-${++messageIdCounter.current}`;
  }, []);

  const handleWebSocketMessage = useCallback((data: any) => {
    try {
      const payload = data?.data ?? data;

      const applySessionStats = (turnData: any, normalizedTargets?: TargetWord[]) => {
        const sessionOverview = turnData?.session ?? {};
        const wordFeedback: Array<{ rating?: number | null }> = Array.isArray(turnData?.word_feedback)
          ? turnData.word_feedback
          : [];
        const correctAnswers = wordFeedback.filter((item) => (item?.rating ?? 0) >= 2).length;
        const statsUpdate: Partial<SessionStats> = {
          totalReviews: wordFeedback.length,
          correctAnswers,
        };
        if (typeof sessionOverview?.xp_earned === 'number') {
          statsUpdate.xpEarned = sessionOverview.xp_earned;
        }
        if (typeof sessionOverview?.words_practiced === 'number') {
          statsUpdate.reviewedCards = sessionOverview.words_practiced;
        }

        setSession((prev) => {
          if (!prev) {
            if (!turnData?.session) {
              return prev;
            }
            return {
              id: String(sessionOverview?.id ?? ''),
              status: sessionOverview?.status ?? 'active',
              startTime: new Date(sessionOverview?.started_at ?? Date.now()),
              endTime: sessionOverview?.completed_at
                ? new Date(sessionOverview.completed_at)
                : undefined,
              stats: {
                totalReviews: statsUpdate.totalReviews ?? 0,
                correctAnswers: statsUpdate.correctAnswers ?? 0,
                xpEarned: statsUpdate.xpEarned ?? 0,
                reviewedCards: statsUpdate.reviewedCards,
              },
              messages: [],
              targetWords: normalizedTargets ?? [],
            };
          }

          return {
            ...prev,
            status: sessionOverview?.status ?? prev.status,
            endTime: sessionOverview?.completed_at
              ? new Date(sessionOverview.completed_at)
              : prev.endTime,
            stats: {
              ...prev.stats,
              ...(statsUpdate.xpEarned !== undefined
                ? { xpEarned: statsUpdate.xpEarned }
                : {}),
              ...(statsUpdate.reviewedCards !== undefined
                ? { reviewedCards: statsUpdate.reviewedCards }
                : {}),
              totalReviews: statsUpdate.totalReviews ?? prev.stats.totalReviews,
              correctAnswers: statsUpdate.correctAnswers ?? prev.stats.correctAnswers,
            },
            targetWords: normalizedTargets ?? prev.targetWords,
          };
        });
      };

      const handleTurnResult = (turnData: any) => {
        if (!turnData?.assistant_turn?.message) {
          return false;
        }

        const assistantMessage = turnData.assistant_turn.message ?? {};
        const assistantTargets = normalizeTargets(
          turnData.assistant_turn.targets ??
            assistantMessage.target_details ??
            assistantMessage.target_words ??
            []
        );
        const assistantChat: ChatMessage = {
          id: String(assistantMessage.id ?? generateMessageId()),
          role: 'assistant',
          content: assistantMessage.content ?? '',
          timestamp: new Date(assistantMessage.created_at ?? Date.now()),
          xp: assistantMessage.xp_earned ?? turnData?.xp_awarded ?? 0,
          targets: assistantTargets,
        };

        setMessages((prev) => {
          const updated = [...prev];
          const turnUserMessage = turnData.user_message ?? null;
          if (turnUserMessage) {
            const userTargets = normalizeTargets(
              turnUserMessage.target_details ??
                turnUserMessage.target_words ??
                []
            );
            const normalizedUser: ChatMessage = {
              id: String(turnUserMessage.id ?? generateMessageId()),
              role: 'user',
              content: turnUserMessage.content ?? '',
              timestamp: new Date(turnUserMessage.created_at ?? Date.now()),
              xp: turnUserMessage.xp_earned ?? 0,
              targets: userTargets,
            };

            let replaced = false;
            for (let index = updated.length - 1; index >= 0; index -= 1) {
              if (updated[index].role === 'user') {
                updated[index] = {
                  ...updated[index],
                  ...normalizedUser,
                };
                replaced = true;
                break;
              }
            }

            if (!replaced) {
              updated.push(normalizedUser);
            }
          }

          updated.push(assistantChat);
          return updated;
        });

        applySessionStats(turnData, assistantTargets);
        return true;
      };

      if (handleTurnResult(payload)) {
        return;
      }

      const message: ChatMessage = {
        id: generateMessageId(),
        role: payload.role || 'assistant',
        content: payload.content || '',
        timestamp: new Date(payload.timestamp || Date.now()),
        xp: payload.xp || 0,
        targets: normalizeTargets(
          payload.targets ||
            payload.target_words ||
            payload.target_details ||
            payload.targetDetails ||
            []
        ),
      };

      setMessages((prev) => [...prev, message]);

      if (payload.session_stats) {
        const statsData = payload.session_stats;
        setSession((prev) => (prev ? {
          ...prev,
          stats: {
            ...prev.stats,
            ...statsData,
          },
        } : prev));
      }
    } catch (error) {
      console.error('Error processing WebSocket message:', error);
    }
  }, [generateMessageId]);

  const latestMessageHandlerRef = useRef<(data: any) => void>(handleWebSocketMessage);

  useEffect(() => {
    latestMessageHandlerRef.current = handleWebSocketMessage;
  }, [handleWebSocketMessage]);

  const registerWebSocketListeners = useCallback(() => {
    registerWebSocketHandler('turn_result', (payload: any) => {
      latestMessageHandlerRef.current(payload?.data ?? payload);
    });

    registerWebSocketHandler('session_ready', () => {
      setIsConnected(true);
    });

    registerWebSocketHandler('error', (payload: any) => {
      const message =
        payload?.data?.message ||
        payload?.message ||
        'Connection error occurred';
      toast.error(message);
    });
  }, [registerWebSocketHandler]);

  useEffect(() => {
    if (!sessionId) {
      return;
    }

    let cancelled = false;

    const establishConnection = async () => {
      try {
        await connectWebSocket();
        if (cancelled) {
          return;
        }
        setIsConnected(isWebSocketConnected());
        registerWebSocketListeners();
      } catch (connectionError) {
        if (!cancelled) {
          console.error('WebSocket connection failed:', connectionError);
          toast.error('Connection error occurred');
          setIsConnected(false);
        }
      }
    };

    establishConnection();

    return () => {
      cancelled = true;
      disconnectWebSocket();
      setIsConnected(false);
    };
  }, [
    sessionId,
    connectWebSocket,
    disconnectWebSocket,
    registerWebSocketListeners,
    isWebSocketConnected,
  ]);

  // Derive vocabulary suggestions from the latest assistant message
  const suggested = useMemo(() => {
    const lastWithTargets = [...messages]
      .reverse()
      .find((m) => m.role === 'assistant' && Array.isArray(m.targets) && m.targets.length > 0);
    if (!lastWithTargets) return [] as { id: number; word: string; translation?: string; is_new?: boolean; familiarity?: 'new' | 'learning' | 'familiar' }[];

    const seen = new Set<number>();
    const mapped = (lastWithTargets.targets || []).map((t) => ({
      id: t.id,
      word: t.word || t.text,
      translation: t.hintTranslation || t.translation || undefined,
      is_new: t.familiarity ? t.familiarity === 'new' : undefined,
      familiarity: (t.familiarity as 'new' | 'learning' | 'familiar' | undefined) || undefined,
    }));
    const unique = mapped.filter((w) => {
      if (!w.id || seen.has(w.id)) return false;
      seen.add(w.id);
      return true;
    });
    return unique;
  }, [messages]);

  const createSession = useCallback(async (config: {
    topic?: string;
    planned_duration_minutes: number;
    conversation_style?: string;
    difficulty_preference?: string;
    generate_greeting?: boolean;
  }) => {
    try {
      setLoading(true);
      setError(null);
      
      const sessionData = await apiService.createSession(config);
      
      const newSession: LearningSession = {
        id: sessionData.id,
        status: 'active',
        startTime: new Date(sessionData.created_at || Date.now()),
        stats: {
          totalReviews: 0,
          correctAnswers: 0,
          xpEarned: 0,
        },
        messages: [],
        targetWords: [],
      };
      
      setSession(newSession);
      setMessages([]);
      
      // If there's a greeting message, add it
      if (sessionData.greeting) {
        const greetingMessage: ChatMessage = {
          id: generateMessageId(),
          role: 'assistant',
          content: sessionData.greeting,
          timestamp: new Date(),
          targets: normalizeTargets(sessionData.greeting_targets || sessionData.greetingTargets || []),
        };
        setMessages([greetingMessage]);
      }
      
      return newSession;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to create session';
      setError(errorMessage);
      toast.error(errorMessage);
      throw error;
    } finally {
      setLoading(false);
    }
  }, [generateMessageId]);

  const sendMessage = useCallback(async (content: string, suggestedWordIds?: number[]) => {
    if (!session) {
      throw new Error('No active session');
    }

    try {
      setLoading(true);
      
      // Add user message immediately
      const userMessage: ChatMessage = {
        id: generateMessageId(),
        role: 'user',
        content,
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, userMessage]);
      
      // Send via WebSocket if connected, otherwise fallback to HTTP
      if (isWebSocketConnected()) {
        rawWebSocketSend(content, suggestedWordIds);
      } else {
        // HTTP fallback
        const response = await apiService.sendMessage(session.id, {
          content,
          suggested_word_ids: suggestedWordIds,
        });
        
        // Process HTTP response
        if (response) {
          handleWebSocketMessage(response);
        }
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to send message';
      setError(errorMessage);
      toast.error(errorMessage);
      throw error;
    } finally {
      setLoading(false);
    }
  }, [session, generateMessageId, isWebSocketConnected, rawWebSocketSend, handleWebSocketMessage]);

  const logWordExposure = useCallback(async (wordId: number, exposureType: 'hint' | 'translation') => {
    if (!session || !Number.isFinite(wordId)) return;
    
    try {
      await apiService.logExposure(session.id, {
        word_id: wordId,
        exposure_type: exposureType,
      });
    } catch (error) {
      console.error('Failed to log word exposure:', error);
    }
  }, [session]);

  const markWordDifficult = useCallback(async (wordId: number) => {
    if (!session || !Number.isFinite(wordId)) {
      toast.error('Unable to mark this word as difficult');
      return;
    }

    try {
      await apiService.markWordDifficult(session.id, { word_id: wordId });
      toast.success('Word marked as difficult', { duration: 2000 });
    } catch (error) {
      console.error('Failed to mark word as difficult:', error);
      toast.error('Failed to mark word as difficult');
    }
  }, [session]);

  const completeSession = useCallback(async () => {
    if (!session) return;
    
    try {
      await apiService.updateSessionStatus(session.id, 'completed');
      
      setSession(prev => prev ? {
        ...prev,
        status: 'completed',
        endTime: new Date(),
      } : null);
      
      // Emit session completion event
      window.dispatchEvent(new CustomEvent('learningSessionComplete', {
        detail: {
          sessionId: session.id,
          stats: session.stats,
          messages: messages.length,
        }
      }));
      
      return session.stats;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to complete session';
      setError(errorMessage);
      toast.error(errorMessage);
      throw error;
    }
  }, [session, messages]);

  const loadSession = useCallback(async (id: string) => {
    try {
      setLoading(true);
      setError(null);
      
      const sessionData = await apiService.getSession(id);
      
      const loadedSession: LearningSession = {
        id: sessionData.id,
        status: sessionData.status,
        startTime: new Date(sessionData.created_at),
        endTime: sessionData.ended_at ? new Date(sessionData.ended_at) : undefined,
        stats: sessionData.stats || {
          totalReviews: 0,
          correctAnswers: 0,
          xpEarned: 0,
        },
        messages: sessionData.messages?.map((msg: any) => ({
          id: msg.id,
          role: msg.role,
          content: msg.content,
          timestamp: new Date(msg.timestamp),
          xp: msg.xp,
          targets: normalizeTargets(
            msg.targets || msg.target_words || msg.target_details || msg.targetDetails || []
          ),
        })) || [],
        targetWords: normalizeTargets(
          sessionData.target_words || sessionData.targetWords || sessionData.target_details || []
        ),
      };
      
      setSession(loadedSession);
      setMessages(loadedSession.messages);
      
      return loadedSession;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to load session';
      setError(errorMessage);
      toast.error(errorMessage);
      throw error;
    } finally {
      setLoading(false);
    }
  }, []);

  // Load session on mount if sessionId provided
  useEffect(() => {
    if (sessionId && !session) {
      loadSession(sessionId).catch(console.error);
    }
  }, [sessionId, session, loadSession]);

  const connectionReady = isConnected && isWebSocketConnected();

  return {
    session,
    messages,
    loading,
    error,
    isConnected: connectionReady,
    createSession,
    // aliases for compatibility with consumers
    sendMessage,
    send: sendMessage,
    logWordExposure,
    logExposure: logWordExposure,
    markWordDifficult,
    flagWord: markWordDifficult,
    completeSession,
    complete: completeSession,
    loadSession,
    
    // Helper to get active session ID for components
    activeSessionId: session?.id,

    // Derived suggestions for helper widget
    suggested,
  };
}
