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

export interface LearningFocusItem {
  kind: 'vocabulary' | 'grammar' | 'error';
  key: string;
  title: string;
  subtitle?: string;
  state?: string;
  priority?: number;
  metadata?: Record<string, unknown>;
}

export interface LearningMomentChoice {
  key: string;
  label: string;
}

export interface LearningMoment {
  id: string;
  kind:
    | 'conversation_turn'
    | 'vocab_boost'
    | 'vocab_check'
    | 'grammar_challenge'
    | 'grammar_repair'
    | 'error_repair';
  sourceType: 'vocabulary' | 'grammar' | 'error';
  title: string;
  body: string;
  inputMode: 'free_text' | 'single_choice' | 'chips';
  choices: LearningMomentChoice[];
  prefillText?: string;
  metadata?: Record<string, unknown>;
  status: 'pending' | 'completed' | 'skipped' | 'expired';
}

export interface LearningMomentResult {
  momentId: string;
  isCorrect?: boolean | null;
  score?: number | null;
  feedbackSummary: string;
  nextStepHint?: string;
}

export interface SessionDetectedError {
  code: string;
  message: string;
  span: string;
  suggestion?: string;
  category: string;
  severity: string;
  confidence?: number;
  occurrence_count?: number;
  is_recurring?: boolean;
}

export interface SessionErrorStat {
  category: string;
  pattern?: string;
  total_occurrences: number;
  occurrences_today: number;
  last_seen?: string;
  next_review?: string;
  state: string;
}

export interface SessionErrorFeedback {
  summary: string;
  errors: SessionDetectedError[];
  error_stats?: SessionErrorStat[];
  review_vocabulary?: string[];
  metadata?: Record<string, unknown>;
}

export interface SessionWordFeedback {
  wordId: number;
  word: string;
  translation?: string;
  isNew: boolean;
  wasUsed: boolean;
  rating?: number | null;
  hadError: boolean;
  error?: SessionDetectedError;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  xp?: number;
  targets?: TargetWord[];
  learningFocus?: LearningFocusItem[];
  errors?: SessionErrorFeedback;
  pendingMoment?: LearningMoment | null;
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

type SuggestedWord = {
  id: number;
  word: string;
  translation?: string;
  is_new?: boolean;
  familiarity?: 'new' | 'learning' | 'familiar';
};

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

const normalizeLearningFocus = (items: any): LearningFocusItem[] => {
  if (!Array.isArray(items)) {
    return [];
  }

  return items
    .map((item) => {
      if (!item || typeof item !== 'object') {
        return null;
      }

      const kind = item.kind;
      const key = typeof item.key === 'string' ? item.key : '';
      const title = typeof item.title === 'string' ? item.title : '';

      if (!key || !title || !['vocabulary', 'grammar', 'error'].includes(kind)) {
        return null;
      }

      return {
        kind,
        key,
        title,
        subtitle: typeof item.subtitle === 'string' ? item.subtitle : undefined,
        state: typeof item.state === 'string' ? item.state : undefined,
        priority: typeof item.priority === 'number' ? item.priority : undefined,
        metadata: item.metadata && typeof item.metadata === 'object' ? item.metadata : undefined,
      } as LearningFocusItem;
    })
    .filter((item): item is LearningFocusItem => item !== null);
};

const normalizeLearningMoment = (item: any): LearningMoment | null => {
  if (!item || typeof item !== 'object') {
    return null;
  }

  const id = typeof item.id === 'string' ? item.id : '';
  const kind = typeof item.kind === 'string' ? item.kind : '';
  const sourceType = typeof item.source_type === 'string' ? item.source_type : '';
  const title = typeof item.title === 'string' ? item.title : '';
  const body = typeof item.body === 'string' ? item.body : '';
  const inputMode = typeof item.input_mode === 'string' ? item.input_mode : 'free_text';
  const status = typeof item.status === 'string' ? item.status : 'pending';

  if (
    !id ||
    !title ||
    !body ||
    !['conversation_turn', 'vocab_boost', 'vocab_check', 'grammar_challenge', 'grammar_repair', 'error_repair'].includes(kind) ||
    !['vocabulary', 'grammar', 'error'].includes(sourceType) ||
    !['free_text', 'single_choice', 'chips'].includes(inputMode) ||
    !['pending', 'completed', 'skipped', 'expired'].includes(status)
  ) {
    return null;
  }

  const choices = Array.isArray(item.choices)
    ? item.choices
        .map((choice: unknown) => {
          if (!choice || typeof choice !== 'object') {
            return null;
          }

          const choiceRecord = choice as Record<string, unknown>;
          const key = typeof choiceRecord.key === 'string' ? choiceRecord.key : '';
          const label = typeof choiceRecord.label === 'string' ? choiceRecord.label : '';
          if (!key || !label) {
            return null;
          }
          return { key, label } as LearningMomentChoice;
        })
        .filter((choice: LearningMomentChoice | null): choice is LearningMomentChoice => choice !== null)
    : [];

  return {
    id,
    kind: kind as LearningMoment['kind'],
    sourceType: sourceType as LearningMoment['sourceType'],
    title,
    body,
    inputMode: inputMode as LearningMoment['inputMode'],
    choices,
    prefillText: typeof item.prefill_text === 'string' ? item.prefill_text : undefined,
    metadata: item.metadata && typeof item.metadata === 'object' ? item.metadata : undefined,
    status: status as LearningMoment['status'],
  };
};

const normalizeLearningMomentResult = (item: any): LearningMomentResult | null => {
  if (!item || typeof item !== 'object') {
    return null;
  }

  const momentId = typeof item.moment_id === 'string' ? item.moment_id : '';
  const feedbackSummary =
    typeof item.feedback_summary === 'string' ? item.feedback_summary : '';

  if (!momentId || !feedbackSummary) {
    return null;
  }

  return {
    momentId,
    isCorrect:
      typeof item.is_correct === 'boolean' || item.is_correct === null
        ? item.is_correct
        : undefined,
    score:
      typeof item.score_0_10 === 'number' || item.score_0_10 === null
        ? item.score_0_10
        : undefined,
    feedbackSummary,
    nextStepHint:
      typeof item.next_step_hint === 'string' ? item.next_step_hint : undefined,
  };
};

const extractMomentResultFromFeedback = (
  feedback: SessionErrorFeedback | null,
): LearningMomentResult | null => {
  if (!feedback?.metadata || typeof feedback.metadata !== 'object') {
    return null;
  }

  return normalizeLearningMomentResult(
    (feedback.metadata as Record<string, unknown>).moment_result,
  );
};

const normalizeDetectedError = (item: any): SessionDetectedError | null => {
  if (!item || typeof item !== 'object') {
    return null;
  }

  const code = typeof item.code === 'string' ? item.code : '';
  const message = typeof item.message === 'string' ? item.message : '';
  const span = typeof item.span === 'string' ? item.span : '';
  const category = typeof item.category === 'string' ? item.category : '';
  const severity = typeof item.severity === 'string' ? item.severity : '';

  if (!code || !message || !span || !category || !severity) {
    return null;
  }

  return {
    code,
    message,
    span,
    suggestion: typeof item.suggestion === 'string' ? item.suggestion : undefined,
    category,
    severity,
    confidence: typeof item.confidence === 'number' ? item.confidence : undefined,
    occurrence_count:
      typeof item.occurrence_count === 'number' ? item.occurrence_count : undefined,
    is_recurring:
      typeof item.is_recurring === 'boolean' ? item.is_recurring : undefined,
  };
};

const normalizeErrorFeedback = (item: any): SessionErrorFeedback | null => {
  if (!item || typeof item !== 'object') {
    return null;
  }

  const errors = Array.isArray(item.errors)
    ? item.errors
        .map((error: unknown) => normalizeDetectedError(error))
        .filter((error: SessionDetectedError | null): error is SessionDetectedError => error !== null)
    : [];

  const errorStats = Array.isArray(item.error_stats)
    ? item.error_stats
        .map((stat: unknown) => {
          if (!stat || typeof stat !== 'object') {
            return null;
          }

          const statRecord = stat as Record<string, unknown>;

          const category =
            typeof statRecord.category === 'string' ? statRecord.category : '';
          const totalOccurrences =
            typeof statRecord.total_occurrences === 'number'
              ? statRecord.total_occurrences
              : null;
          const occurrencesToday =
            typeof statRecord.occurrences_today === 'number'
              ? statRecord.occurrences_today
              : 0;
          const state =
            typeof statRecord.state === 'string' ? statRecord.state : '';

          if (!category || totalOccurrences === null || !state) {
            return null;
          }

          return {
            category,
            pattern:
              typeof statRecord.pattern === 'string' ? statRecord.pattern : undefined,
            total_occurrences: totalOccurrences,
            occurrences_today: occurrencesToday,
            last_seen:
              typeof statRecord.last_seen === 'string'
                ? statRecord.last_seen
                : undefined,
            next_review:
              typeof statRecord.next_review === 'string'
                ? statRecord.next_review
                : undefined,
            state,
          } as SessionErrorStat;
        })
        .filter((stat: SessionErrorStat | null): stat is SessionErrorStat => stat !== null)
    : [];

  const summary = typeof item.summary === 'string' ? item.summary : '';
  const metadata =
    item.metadata && typeof item.metadata === 'object' ? item.metadata : undefined;

  if (
    !summary &&
    errors.length === 0 &&
    errorStats.length === 0 &&
    (!metadata || Object.keys(metadata).length === 0)
  ) {
    return null;
  }

  return {
    summary,
    errors,
    error_stats: errorStats.length > 0 ? errorStats : undefined,
    review_vocabulary: Array.isArray(item.review_vocabulary)
      ? item.review_vocabulary.filter((value: unknown): value is string => typeof value === 'string')
      : undefined,
    metadata,
  };
};

const normalizeWordFeedback = (items: any): SessionWordFeedback[] => {
  if (!Array.isArray(items)) {
    return [];
  }

  return items
    .map((item) => {
      if (!item || typeof item !== 'object') {
        return null;
      }

      const wordId = parseNumericId(item.word_id ?? item.wordId);
      const word = typeof item.word === 'string' ? item.word : '';

      if (wordId === null || !word) {
        return null;
      }

      return {
        wordId,
        word,
        translation: typeof item.translation === 'string' ? item.translation : undefined,
        isNew: Boolean(item.is_new ?? item.isNew),
        wasUsed: Boolean(item.was_used ?? item.wasUsed),
        rating:
          typeof item.rating === 'number' || item.rating === null ? item.rating : undefined,
        hadError: Boolean(item.had_error ?? item.hadError),
        error: normalizeDetectedError(item.error) || undefined,
      } as SessionWordFeedback;
    })
    .filter((item): item is SessionWordFeedback => item !== null);
};

export function useLearningSession(sessionId?: string) {
  const [session, setSession] = useState<LearningSession | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [latestErrorFeedback, setLatestErrorFeedback] = useState<SessionErrorFeedback | null>(null);
  const [latestWordFeedback, setLatestWordFeedback] = useState<SessionWordFeedback[] | null>(null);
  const [latestXpAwarded, setLatestXpAwarded] = useState<number | null>(null);
  const [latestComboCount, setLatestComboCount] = useState<number | null>(null);
  const [latestMomentResult, setLatestMomentResult] = useState<LearningMomentResult | null>(null);
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
        const wordFeedback = normalizeWordFeedback(turnData?.word_feedback);
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
        const learningFocus = normalizeLearningFocus(
          turnData.assistant_turn.learning_focus ??
          assistantMessage.learning_focus ??
          [],
        );
        const assistantChat: ChatMessage = {
          id: String(assistantMessage.id ?? generateMessageId()),
          role: 'assistant',
          content: assistantMessage.content ?? '',
          timestamp: new Date(assistantMessage.created_at ?? Date.now()),
          xp: assistantMessage.xp_earned ?? turnData?.xp_awarded ?? 0,
          targets: assistantTargets,
          learningFocus,
          pendingMoment: normalizeLearningMoment(
            turnData.assistant_turn.pending_moment ?? assistantMessage.pending_moment,
          ),
        };

        console.log('[useLearningSession] Created assistantChat:', { id: assistantChat.id, contentLength: assistantChat.content.length });

        setMessages((prev) => {
          console.log('[useLearningSession] setMessages called, prev length:', prev.length);
          const updated = [...prev];
          for (let index = updated.length - 1; index >= 0; index -= 1) {
            if (updated[index].role === 'assistant' && updated[index].pendingMoment) {
              updated[index] = {
                ...updated[index],
                pendingMoment: null,
              };
              break;
            }
          }
          const turnUserMessage = turnData.user_message ?? null;
          if (turnUserMessage) {
            const userTargets = normalizeTargets(
              turnUserMessage.target_details ??
              turnUserMessage.target_words ??
              []
            );

            // Merge error_feedback from user message with error_stats from turn result
            let errorData = normalizeErrorFeedback(turnUserMessage.error_feedback);
            const turnErrorFeedback = normalizeErrorFeedback(turnData.error_feedback);
            if (errorData && turnErrorFeedback?.error_stats) {
              errorData = {
                ...errorData,
                error_stats: turnErrorFeedback.error_stats,
              };
            }

            const normalizedUser: ChatMessage = {
              id: String(turnUserMessage.id ?? generateMessageId()),
              role: 'user',
              content: turnUserMessage.content ?? '',
              timestamp: new Date(turnUserMessage.created_at ?? Date.now()),
              xp: turnUserMessage.xp_earned ?? 0,
              targets: userTargets,
              errors: errorData || undefined,
              pendingMoment: normalizeLearningMoment(turnUserMessage.pending_moment),
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

        const normalizedErrorFeedback = normalizeErrorFeedback(turnData.error_feedback);
        if (normalizedErrorFeedback) {
          console.log('[useLearningSession] Error feedback received:', normalizedErrorFeedback);
          setLatestErrorFeedback(normalizedErrorFeedback);
          const normalizedMomentResult = extractMomentResultFromFeedback(normalizedErrorFeedback);
          if (normalizedMomentResult) {
            setLatestMomentResult(normalizedMomentResult);
          }
        }

        const normalizedWordFeedback = normalizeWordFeedback(turnData.word_feedback);
        if (normalizedWordFeedback.length > 0) {
          console.log('[useLearningSession] Word feedback received:', normalizedWordFeedback);
          setLatestWordFeedback(normalizedWordFeedback);
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
        learningFocus: normalizeLearningFocus(
          payload.learning_focus ||
          payload.learningFocus ||
          [],
        ),
        pendingMoment: normalizeLearningMoment(
          payload.pending_moment ||
          payload.pendingMoment,
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
      const syncMessages = async () => {
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
              learningFocus: normalizeLearningFocus(msg.learning_focus || []),
              errors: normalizeErrorFeedback(msg.error_feedback) || undefined,
              pendingMoment: normalizeLearningMoment(msg.pending_moment),
            })));
          }
        } catch (syncError) {
          console.warn('Message sync failed:', syncError);
        }
      };

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
      } catch (connectionError) {
        if (!cancelled) {
          console.warn('WebSocket connection failed, falling back to HTTP sync:', connectionError);
          setIsConnected(false);
        }
      } finally {
        await syncMessages();
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
    if (!lastWithTargets) {
      const lastWithFocus = [...messages]
        .reverse()
        .find((m) => m.role === 'assistant' && Array.isArray(m.learningFocus) && m.learningFocus.length > 0);

      if (!lastWithFocus) {
        return [] as SuggestedWord[];
      }

      const seen = new Set<number>();
      return (lastWithFocus.learningFocus || []).reduce<SuggestedWord[]>((words, item) => {
        if (item.kind !== 'vocabulary') {
          return words;
        }

        const wordId = typeof item.metadata?.word_id === 'number' ? item.metadata.word_id : null;
        if (wordId === null || seen.has(wordId)) {
          return words;
        }

        seen.add(wordId);
        words.push({
          id: wordId,
          word: item.title,
          translation:
            typeof item.metadata?.translation === 'string'
              ? item.metadata.translation
              : item.subtitle,
          is_new: Boolean(item.metadata?.is_new),
          familiarity: item.state as 'new' | 'learning' | 'familiar' | undefined,
        });
        return words;
      }, []);
    }

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
    return unique as SuggestedWord[];
  }, [messages]);

  const learningFocus = useMemo(() => {
    const lastWithFocus = [...messages]
      .reverse()
      .find((message) => message.role === 'assistant' && Array.isArray(message.learningFocus) && message.learningFocus.length > 0);

    return lastWithFocus?.learningFocus || [];
  }, [messages]);

  const pendingMoment = useMemo(() => {
    const lastWithMoment = [...messages]
      .reverse()
      .find(
        (message) =>
          message.role === 'assistant' &&
          message.pendingMoment &&
          message.pendingMoment.status === 'pending',
      );

    return lastWithMoment?.pendingMoment || null;
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
      const sessionPayload = sessionData?.session ?? sessionData;
      const greetingTurn = sessionData?.assistant_turn;
      if (!sessionPayload?.id) {
        throw new Error('Session creation response missing id');
      }

      const newSession: LearningSession = {
        id: String(sessionPayload.id),
        status: 'active',
        startTime: new Date(sessionPayload.started_at || sessionPayload.created_at || Date.now()),
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
      if (greetingTurn?.message?.content) {
        const greetingMessage: ChatMessage = {
          id: String(greetingTurn.message.id ?? generateMessageId()),
          role: 'assistant',
          content: greetingTurn.message.content,
          timestamp: new Date(greetingTurn.message.created_at || Date.now()),
          targets: normalizeTargets(greetingTurn.targets || greetingTurn.message.target_details || []),
          learningFocus: normalizeLearningFocus(
            greetingTurn.learning_focus || greetingTurn.message.learning_focus || [],
          ),
          pendingMoment: normalizeLearningMoment(
            greetingTurn.pending_moment || greetingTurn.message.pending_moment,
          ),
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

  const applyMomentResponse = useCallback((response: any, resolvedMomentId: string) => {
    const nextMoment = normalizeLearningMoment(response?.next_moment);
    const momentResult = normalizeLearningMomentResult(response?.moment_result);

    setMessages((prev) => {
      const updated = [...prev];
      let targetIndex = -1;

      for (let index = updated.length - 1; index >= 0; index -= 1) {
        if (
          updated[index].role === 'assistant' &&
          updated[index].pendingMoment?.id === resolvedMomentId
        ) {
          targetIndex = index;
          break;
        }
      }

      if (targetIndex === -1) {
        for (let index = updated.length - 1; index >= 0; index -= 1) {
          if (updated[index].role === 'assistant' && updated[index].pendingMoment) {
            targetIndex = index;
            break;
          }
        }
      }

      if (targetIndex >= 0) {
        updated[targetIndex] = {
          ...updated[targetIndex],
          pendingMoment: nextMoment,
        };
      }

      const assistantTurn = response?.assistant_turn?.message;
      if (assistantTurn?.content) {
        updated.push({
          id: String(assistantTurn.id ?? generateMessageId()),
          role: 'assistant',
          content: assistantTurn.content,
          timestamp: new Date(assistantTurn.created_at ?? Date.now()),
          xp: assistantTurn.xp_earned ?? 0,
          targets: normalizeTargets(
            response?.assistant_turn?.targets ??
            assistantTurn.target_details ??
            [],
          ),
          learningFocus: normalizeLearningFocus(
            response?.assistant_turn?.learning_focus ??
            assistantTurn.learning_focus ??
            [],
          ),
          pendingMoment: normalizeLearningMoment(
            response?.assistant_turn?.pending_moment ??
            assistantTurn.pending_moment,
          ),
        });
      }

      return updated;
    });

    if (response?.session) {
      const sessionOverview = response.session;
      setSession((prev) => (prev ? {
        ...prev,
        status: sessionOverview.status ?? prev.status,
        endTime: sessionOverview.completed_at ? new Date(sessionOverview.completed_at) : prev.endTime,
        stats: {
          ...prev.stats,
          xpEarned:
            typeof sessionOverview.xp_earned === 'number'
              ? sessionOverview.xp_earned
              : prev.stats.xpEarned,
          reviewedCards:
            typeof sessionOverview.words_practiced === 'number'
              ? sessionOverview.words_practiced
              : prev.stats.reviewedCards,
        },
      } : prev));
    }

    setLatestMomentResult(momentResult);
  }, [generateMessageId]);

  const submitMoment = useCallback(async (
    momentId: string,
    payload: { answerText?: string; selectedChoice?: string },
  ) => {
    if (!session) {
      throw new Error('No active session');
    }

    try {
      setLoading(true);
      const response = await apiService.submitSessionMoment(session.id, momentId, {
        answer_text: payload.answerText,
        selected_choice: payload.selectedChoice,
      });
      applyMomentResponse(response, momentId);
      return response;
    } catch (requestError) {
      const errorMessage =
        requestError instanceof Error ? requestError.message : 'Failed to submit moment';
      setError(errorMessage);
      toast.error(errorMessage);
      throw requestError;
    } finally {
      setLoading(false);
    }
  }, [applyMomentResponse, session]);

  const skipMoment = useCallback(async (momentId: string) => {
    if (!session) {
      throw new Error('No active session');
    }

    try {
      setLoading(true);
      const response = await apiService.skipSessionMoment(session.id, momentId);
      applyMomentResponse(response, momentId);
      return response;
    } catch (requestError) {
      const errorMessage =
        requestError instanceof Error ? requestError.message : 'Failed to skip moment';
      setError(errorMessage);
      toast.error(errorMessage);
      throw requestError;
    } finally {
      setLoading(false);
    }
  }, [applyMomentResponse, session]);

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
          learningFocus: normalizeLearningFocus(msg.learning_focus || []),
          errors: normalizeErrorFeedback(msg.error_feedback) || undefined,
          pendingMoment: normalizeLearningMoment(msg.pending_moment),
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
  const clearTurnFeedback = useCallback(() => {
    setLatestErrorFeedback(null);
    setLatestWordFeedback(null);
    setLatestXpAwarded(null);
    setLatestComboCount(null);
    setLatestMomentResult(null);
  }, []);

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
    submitMoment,
    skipMoment,
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
    learningFocus,
    pendingMoment,

    // Gamification feedback
    latestErrorFeedback,
    latestWordFeedback,
    latestXpAwarded,
    latestComboCount,
    latestMomentResult,
    clearTurnFeedback,
    clearErrorFeedback: () => setLatestErrorFeedback(null),
    clearWordFeedback: () => setLatestWordFeedback(null),
    clearXpAwarded: () => setLatestXpAwarded(null),
    clearComboCount: () => setLatestComboCount(null),
    clearMomentResult: () => setLatestMomentResult(null),
  };
}
