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

export interface TargetedError {
  category: string;
  pattern?: string;
  context?: string;
  correction?: string;
  lapses: number;
  reps: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  xp?: number;
  targets?: TargetWord[];
  targetedErrors?: TargetedError[];
  errors?: {
    summary: string;
    errors: Array<{
      code: string;
      message: string;
      span: string;
      suggestion: string;
      category: string;
      severity: string;
      confidence?: number;
      occurrence_count?: number;
      is_recurring?: boolean;
    }>;
    error_stats?: Array<{
      category: string;
      pattern?: string;
      total_occurrences: number;
      occurrences_today: number;
      last_seen?: string;
      next_review?: string;
      state: string;
    }>;
  };
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
  const [latestErrorFeedback, setLatestErrorFeedback] = useState<any | null>(null);
  const [latestWordFeedback, setLatestWordFeedback] = useState<any[] | null>(null);
  const [latestXpAwarded, setLatestXpAwarded] = useState<number | null>(null);
  const [latestComboCount, setLatestComboCount] = useState<number | null>(null);
  const messageIdCounter = useRef(0);

  const {
    connect: connectWebSocket,
    disconnect: disconnectWebSocket,
    sendMessage: rawWebSocketSend,
    onMessage: registerWebSocketHandler,
    setGlobalHandler,
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
        console.log('[useLearningSession] handleTurnResult called with:', JSON.stringify(turnData, null, 2).substring(0, 500));

        if (!turnData?.assistant_turn?.message) {
          console.warn('[useLearningSession] No assistant_turn.message found in turnData');
          return false;
        }

        console.log('[useLearningSession] Processing assistant turn...');
        const assistantMessage = turnData.assistant_turn.message ?? {};
        const assistantTargets = normalizeTargets(
          turnData.assistant_turn.targets ??
          assistantMessage.target_details ??
          assistantMessage.target_words ??
          []
        );
        // Extract targeted errors from assistant turn
        const targetedErrors = Array.isArray(turnData.assistant_turn.targeted_errors)
          ? turnData.assistant_turn.targeted_errors.map((err: any) => ({
            category: err.category,
            pattern: err.pattern,
            context: err.context,
            correction: err.correction,
            lapses: err.lapses ?? 0,
            reps: err.reps ?? 0,
          }))
          : [];
        const assistantChat: ChatMessage = {
          id: String(assistantMessage.id ?? generateMessageId()),
          role: 'assistant',
          content: assistantMessage.content ?? '',
          timestamp: new Date(assistantMessage.created_at ?? Date.now()),
          xp: assistantMessage.xp_earned ?? turnData?.xp_awarded ?? 0,
          targets: assistantTargets,
          targetedErrors,
        };

        console.log('[useLearningSession] Created assistantChat:', { id: assistantChat.id, contentLength: assistantChat.content.length });

        setMessages((prev) => {
          console.log('[useLearningSession] setMessages called, prev length:', prev.length);
          const updated = [...prev];
          const turnUserMessage = turnData.user_message ?? null;
          if (turnUserMessage) {
            const userTargets = normalizeTargets(
              turnUserMessage.target_details ??
              turnUserMessage.target_words ??
              []
            );

            // Merge error_feedback from user message with error_stats from turn result
            let errorData = turnUserMessage.error_feedback;
            if (errorData && turnData.error_feedback?.error_stats) {
              errorData = {
                ...errorData,
                error_stats: turnData.error_feedback.error_stats,
              };
            }

            const normalizedUser: ChatMessage = {
              id: String(turnUserMessage.id ?? generateMessageId()),
              role: 'user',
              content: turnUserMessage.content ?? '',
              timestamp: new Date(turnUserMessage.created_at ?? Date.now()),
              xp: turnUserMessage.xp_earned ?? 0,
              targets: userTargets,
              errors: errorData,
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
          console.log('[useLearningSession] setMessages returning updated array, new length:', updated.length);
          return updated;
        });

        applySessionStats(turnData, assistantTargets);

        // Capture error feedback and word feedback for UI notifications
        // Only set error feedback if there are actual errors to display
        if (turnData.error_feedback) {
          console.log('[useLearningSession] Error feedback received:', turnData.error_feedback);
          const hasErrors = turnData.error_feedback.errors && turnData.error_feedback.errors.length > 0;
          if (hasErrors) {
            setLatestErrorFeedback(turnData.error_feedback);
          }
        }

        if (turnData.word_feedback) {
          console.log('[useLearningSession] Word feedback received:', turnData.word_feedback);
          setLatestWordFeedback(turnData.word_feedback);
        }

        if (typeof turnData.xp_awarded === 'number' && turnData.xp_awarded > 0) {
          console.log('[useLearningSession] XP awarded:', turnData.xp_awarded);
          setLatestXpAwarded(turnData.xp_awarded);
        }

        if (typeof turnData.combo_count === 'number' && turnData.combo_count >= 2) {
          console.log('[useLearningSession] Combo count:', turnData.combo_count);
          setLatestComboCount(turnData.combo_count);
        }

        console.log('[useLearningSession] handleTurnResult completed successfully');
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
    console.log('[useLearningSession] Registering WebSocket listeners...');

    registerWebSocketHandler('turn_result', (payload: any) => {
      console.log('[useLearningSession] turn_result received:', payload);
      latestMessageHandlerRef.current(payload?.data ?? payload);
    });

    registerWebSocketHandler('session_ready', () => {
      console.log('[useLearningSession] session_ready received');
      setIsConnected(true);
    });

    registerWebSocketHandler('error', (payload: any) => {
      console.log('[useLearningSession] error received:', payload);
      const message =
        payload?.data?.message ||
        payload?.message ||
        'Connection error occurred';
      toast.error(message);
    });

    console.log('[useLearningSession] WebSocket listeners registered');
  }, [registerWebSocketHandler]);

  // Set up global message handler - this ensures messages are processed 
  // regardless of handler registration timing issues
  useEffect(() => {
    const globalHandler = (type: string, payload: any) => {
      console.log('[useLearningSession] Global handler received:', type);

      switch (type) {
        case 'turn_result':
          console.log('[useLearningSession] Processing turn_result via global handler');
          latestMessageHandlerRef.current(payload?.data ?? payload);
          break;
        case 'session_ready':
          console.log('[useLearningSession] session_ready via global handler');
          setIsConnected(true);
          break;
        case 'error':
          console.log('[useLearningSession] error via global handler:', payload);
          const message = payload?.data?.message || payload?.message || 'Connection error occurred';
          toast.error(message);
          break;
        default:
          console.log('[useLearningSession] Unhandled message type:', type);
      }
    };

    setGlobalHandler(globalHandler);
    console.log('[useLearningSession] Global handler set');
  }, [setGlobalHandler]);

  useEffect(() => {
    if (!sessionId) {
      return;
    }

    let cancelled = false;

    const establishConnection = async () => {
      console.log('[useLearningSession] Establishing connection for session:', sessionId);
      try {
        // Connect first to ensure wsRef.current is initialized
        await connectWebSocket();
        if (cancelled) {
          return;
        }
        console.log('[useLearningSession] WebSocket connected, isConnected:', isWebSocketConnected());
        setIsConnected(isWebSocketConnected());

        // Register handlers AFTER connecting so wsRef.current exists
        console.log('[useLearningSession] Registering listeners after connect...');
        registerWebSocketListeners();

        // Sync messages after connection to recover any missed during reconnection
        try {
          const messagesResponse = await apiService.getSessionMessages(sessionId) as any;
          const messagesData = messagesResponse?.items || messagesResponse || [];
          console.log('[useLearningSession] Synced', messagesData.length, 'messages from HTTP');
          if (!cancelled && messagesData.length > 0) {
            setMessages(messagesData.map((msg: any) => ({
              id: msg.id,
              role: msg.sender === 'user' ? 'user' : 'assistant',
              content: msg.content,
              timestamp: new Date(msg.created_at),
              xp: msg.xp_earned || 0,
              targets: normalizeTargets(msg.target_details || msg.targets || msg.target_words || []),
              errors: msg.error_feedback,
            })));
          }
        } catch (syncError) {
          console.warn('Message sync failed:', syncError);
        }
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
      // Only disconnect when truly unmounting - the connect function handles session changes
    };
  }, [
    sessionId,
    connectWebSocket,
    registerWebSocketListeners,
    isWebSocketConnected,
  ]);

  // Separate cleanup effect that only runs on unmount
  useEffect(() => {
    return () => {
      console.log('[useLearningSession] Component unmounting, disconnecting WebSocket');
      disconnectWebSocket();
      setIsConnected(false);
    };
  }, [disconnectWebSocket]);

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

      const sessionData = await apiService.createSession(config) as any;

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

      // Fetch the server-calculated summary for accurate stats
      const serverSummary = await apiService.getSessionSummary(session.id) as any;

      // Merge server summary with local session state
      // Spread serverSummary to preserve snake_case fields for SessionSummary component fallbacks
      const completedStats: SessionStats = {
        ...serverSummary,
        totalReviews: serverSummary.words_practiced ?? session.stats.totalReviews,
        correctAnswers: serverSummary.correct_responses ?? session.stats.correctAnswers,
        xpEarned: serverSummary.xp_earned ?? session.stats.xpEarned ?? 0,
        newCards: serverSummary.new_words_introduced ?? session.stats.newCards ?? 0,
        reviewedCards: serverSummary.words_reviewed ?? session.stats.reviewedCards ?? 0,
        // Calculate session duration from start time
        sessionDuration: session.startTime
          ? Math.round((Date.now() - new Date(session.startTime).getTime()) / 1000)
          : undefined,
      };

      setSession(prev => prev ? {
        ...prev,
        status: 'completed',
        endTime: new Date(),
        stats: completedStats,
      } : null);

      // Emit session completion event with server stats
      window.dispatchEvent(new CustomEvent('learningSessionComplete', {
        detail: {
          sessionId: session.id,
          stats: completedStats,
          messages: messages.length,
        }
      }));

      return completedStats;
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

      const sessionData = await apiService.getSession(id) as any;

      // Fetch messages separately
      const messagesResponse = await apiService.getSessionMessages(id) as any;
      const messagesData = messagesResponse?.items || messagesResponse || [];

      const loadedSession: LearningSession = {
        id: sessionData.id,
        status: sessionData.status,
        startTime: new Date(sessionData.started_at || sessionData.created_at),
        endTime: sessionData.completed_at ? new Date(sessionData.completed_at) : undefined,
        stats: {
          totalReviews: sessionData.words_practiced || 0,
          correctAnswers: sessionData.correct_responses || 0,
          xpEarned: sessionData.xp_earned || 0,
        },
        messages: messagesData.map((msg: any) => ({
          id: msg.id,
          role: msg.sender === 'user' ? 'user' : 'assistant',
          content: msg.content,
          timestamp: new Date(msg.created_at),
          xp: msg.xp_earned || 0,
          targets: normalizeTargets(msg.target_details || msg.targets || msg.target_words || []),
          errors: msg.error_feedback,
        })),
        targetWords: [],
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

    // Gamification feedback
    latestErrorFeedback,
    latestWordFeedback,
    latestXpAwarded,
    latestComboCount,
    clearErrorFeedback: () => setLatestErrorFeedback(null),
    clearWordFeedback: () => setLatestWordFeedback(null),
    clearXpAwarded: () => setLatestXpAwarded(null),
    clearComboCount: () => setLatestComboCount(null),
  };
}
