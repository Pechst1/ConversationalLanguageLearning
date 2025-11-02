import { useState, useEffect, useCallback, useRef } from 'react';
import { useWebSocket } from './useWebSocket';
import apiService from '@/services/api';
import toast from 'react-hot-toast';

export interface TargetWord {
  id: number | string;
  word: string;
  translation: string;
  hintTranslation?: string;
  familiarity?: 'new' | 'learning' | 'familiar';
  difficulty?: number;
  exposureCount?: number;
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

export function useLearningSession(sessionId?: string) {
  const [session, setSession] = useState<LearningSession | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const messageIdCounter = useRef(0);
  
  const { sendMessage: sendWebSocketMessage, isConnected: wsConnected } = useWebSocket(
    sessionId || '',
    {
      onMessage: handleWebSocketMessage,
      onConnect: () => setIsConnected(true),
      onDisconnect: () => setIsConnected(false),
      onError: (error) => {
        console.error('WebSocket error:', error);
        toast.error('Connection error occurred');
      }
    }
  );

  const generateMessageId = useCallback(() => {
    return `msg-${Date.now()}-${++messageIdCounter.current}`;
  }, []);

  function handleWebSocketMessage(data: any) {
    try {
      const message: ChatMessage = {
        id: generateMessageId(),
        role: data.role || 'assistant',
        content: data.content || '',
        timestamp: new Date(data.timestamp || Date.now()),
        xp: data.xp || 0,
        targets: data.targets || data.target_words || []
      };
      
      setMessages(prev => [...prev, message]);
      
      // Update session stats if provided
      if (data.session_stats && session) {
        setSession(prev => prev ? {
          ...prev,
          stats: { ...prev.stats, ...data.session_stats }
        } : null);
      }
    } catch (error) {
      console.error('Error processing WebSocket message:', error);
    }
  }

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
          targets: sessionData.greeting_targets || []
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
      if (wsConnected && sendWebSocketMessage) {
        sendWebSocketMessage({
          content,
          suggested_word_ids: suggestedWordIds,
        });
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
  }, [session, wsConnected, sendWebSocketMessage, generateMessageId]);

  const logWordExposure = useCallback(async (wordId: number, exposureType: 'hint' | 'translation') => {
    if (!session) return;
    
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
    if (!session) return;
    
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
          targets: msg.targets || msg.target_words || [],
        })) || [],
        targetWords: sessionData.target_words || [],
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

  return {
    session,
    messages,
    loading,
    error,
    isConnected: isConnected && wsConnected,
    createSession,
    sendMessage,
    logWordExposure,
    markWordDifficult,
    completeSession,
    loadSession,
    
    // Helper to get active session ID for components
    activeSessionId: session?.id,
  };
}
