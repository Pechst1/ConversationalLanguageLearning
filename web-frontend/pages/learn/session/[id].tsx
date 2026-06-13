import React from 'react';
import { useRouter } from 'next/router';
import toast from 'react-hot-toast';

import ConversationHistory from '@/components/learning/ConversationHistory';
import MessageInput from '@/components/learning/MessageInput';
import ProgressIndicator from '@/components/learning/ProgressIndicator';
import SessionSummary from '@/components/learning/SessionSummary';
import LearningFocusPanel from '@/components/learning/LearningFocusPanel';
import LearningMomentCard from '@/components/learning/LearningMomentCard';
import MomentResultInline from '@/components/learning/MomentResultInline';
import SessionTurnFeedback from '@/components/learning/SessionTurnFeedback';
import VoiceModeToggle from '@/components/learning/VoiceModeToggle';
import { useLearningSession } from '@/hooks/useLearningSession';
import { SpeakingModeProvider, useSpeakingMode } from '@/contexts/SpeakingModeContext';
import type { SessionStats as SummarySessionStats } from '@/types/learning';

const SessionPageContent: React.FC = () => {
  const router = useRouter();
  const rawId = router.query.id;
  const sessionId = Array.isArray(rawId) ? rawId[0] : rawId;

  const {
    session,
    messages,
    loading,
    sendMessage,
    submitMoment,
    skipMoment,
    suggested,
    learningFocus,
    pendingMoment,
    logWordExposure,
    markWordDifficult,
    completeSession,
    activeSessionId,
    latestErrorFeedback,
    latestWordFeedback,
    latestXpAwarded,
    latestComboCount,
    latestMomentResult,
    clearTurnFeedback,
    clearMomentResult,
  } = useLearningSession(sessionId);

  const [draft, setDraft] = React.useState('');
  const [selectedWordIds, setSelectedWordIds] = React.useState<number[]>([]);
  const [summary, setSummary] = React.useState<SummarySessionStats | null>(null);
  const [isCompleting, setIsCompleting] = React.useState(false);
  const { isSpeakingMode, speakText } = useSpeakingMode();

  const handleSend = React.useCallback(
    async (text: string) => {
      if (!text.trim() || summary) {
        return;
      }

      if (
        pendingMoment &&
        pendingMoment.kind !== 'vocab_boost' &&
        pendingMoment.kind !== 'conversation_turn'
      ) {
        toast.error('Complete the exercise above before sending a new reply.');
        return;
      }

      await sendMessage(text, selectedWordIds);
      setSelectedWordIds([]);
    },
    [pendingMoment, sendMessage, selectedWordIds, summary],
  );

  const handleMomentSubmit = React.useCallback(
    async (payload: { answerText?: string; selectedChoice?: string }) => {
      if (!pendingMoment) {
        return;
      }
      await submitMoment(pendingMoment.id, payload);
    },
    [pendingMoment, submitMoment],
  );

  const handleMomentSkip = React.useCallback(async () => {
    if (!pendingMoment) {
      return;
    }
    await skipMoment(pendingMoment.id);
  }, [pendingMoment, skipMoment]);

  const handleInsertWord = React.useCallback((word: string) => {
    setDraft((existing) => {
      if (!word) {
        return existing;
      }

      const alreadyIncluded = existing
        .toLowerCase()
        .split(/\s+/)
        .filter(Boolean)
        .includes(word.toLowerCase());

      if (alreadyIncluded) {
        return existing;
      }

      return existing ? `${existing} ${word}` : word;
    });
  }, []);

  const handleToggleSuggestion = React.useCallback((word: { id: number }, isSelected: boolean) => {
    setSelectedWordIds((prev) => {
      if (isSelected) {
        if (prev.includes(word.id)) {
          return prev;
        }
        return [...prev, word.id];
      }

      return prev.filter((value) => value !== word.id);
    });
  }, []);

  const handleWordInteract = React.useCallback(
    (wordId: number, exposureType: 'hint' | 'translation') => {
      if (!Number.isFinite(wordId)) {
        return;
      }
      logWordExposure(wordId, exposureType);
    },
    [logWordExposure],
  );

  const handleCompleteSession = React.useCallback(async () => {
    if (!sessionId || summary) {
      return;
    }

    try {
      setIsCompleting(true);
      const result = await completeSession();
      if (result) {
        setSummary(result as unknown as SummarySessionStats);
        toast.success('Session completed! Review your highlights below.');
        setDraft('');
        setSelectedWordIds([]);
      }
    } catch (error) {
      console.error('Unable to complete session:', error);
      toast.error('Unable to complete session right now.');
    } finally {
      setIsCompleting(false);
    }
  }, [completeSession, sessionId, summary]);

  React.useEffect(() => {
    setSelectedWordIds((prev) => prev.filter((wordId) => suggested.some((item) => item.id === wordId)));
  }, [suggested]);

  // Auto-speak assistant messages when speaking mode is enabled
  const lastMessageIdRef = React.useRef<string | null>(null);
  React.useEffect(() => {
    if (!isSpeakingMode || messages.length === 0) return;

    const lastMessage = messages[messages.length - 1];
    if (
      lastMessage.role === 'assistant' &&
      lastMessage.content &&
      lastMessage.id !== lastMessageIdRef.current
    ) {
      lastMessageIdRef.current = lastMessage.id;
      speakText(lastMessage.content);
    }
  }, [messages, isSpeakingMode, speakText]);

  const handleReturnToLearningStream = React.useCallback(() => {
    router.push('/learn').catch((error) => {
      console.error('Failed to navigate to the learning stream:', error);
      toast.error('Unable to navigate back to learning right now.');
    });
  }, [router]);

  const handleContinueLearning = React.useCallback(() => {
    router.push('/learn').catch((error) => {
      console.error('Failed to continue learning:', error);
      toast.error('Unable to continue learning right now.');
    });
  }, [router]);

  const xp = session?.stats?.xpEarned ?? 0;
  const level = (session as unknown as { level?: number } | undefined)?.level ?? 1;
  const streak = (session as unknown as { streak?: number } | undefined)?.streak ?? 0;
  const isBlockingMoment =
    pendingMoment != null &&
    pendingMoment.kind !== 'vocab_boost' &&
    pendingMoment.kind !== 'conversation_turn';

  if (!sessionId) {
    return null;
  }

  return (
    <div className="min-h-screen bg-[var(--app-paper)] text-[var(--app-ink)]">
      <div className="mx-auto flex min-h-screen max-w-5xl flex-col px-4 py-6 sm:px-6 lg:px-8">
        <header className="mb-8 border-b border-[var(--app-ink)] pb-5">
          <div className="text-xs font-black uppercase tracking-[0.16em] text-[var(--app-ink-3)]">
            {summary ? 'Session review' : 'Learning stream'}
          </div>
          <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4 mt-1">
            <h1 className="font-serif text-5xl italic leading-none text-[var(--app-ink)]">
              {summary ? 'Review this session' : 'Continue learning'}
            </h1>
            <VoiceModeToggle className="md:justify-end" />
          </div>
          <p className="mt-3 max-w-2xl text-[var(--app-ink-2)] text-sm">
            {summary
              ? 'Your recap stays in one place so you can decide what to revisit next.'
              : 'The session chooses the next prompt. Your job is just to respond.'}
          </p>
        </header>

        <div className="mb-4">
          <ProgressIndicator xp={xp} level={level} streak={streak} />
        </div>

        {!summary ? (
          <div className="mb-4">
            <LearningFocusPanel
              items={learningFocus}
              selectedWordIds={selectedWordIds}
              currentMoment={pendingMoment}
              onInsertWord={handleInsertWord}
              onToggleWord={handleToggleSuggestion}
            />
          </div>
        ) : null}

        <div className="flex-1">
          {summary ? (
            <div className="rounded-none border-4 border-black bg-[var(--app-sheet)] p-6 shadow-[8px_8px_0px_0px_#000]">
              <SessionSummary
                stats={summary}
                onStartNewSession={handleContinueLearning}
                onReturnToLearning={handleReturnToLearningStream}
              />
              <div className="mt-6 flex justify-end">
                <button
                  type="button"
                  onClick={() => router.push('/sessions')}
                  className="inline-flex items-center justify-center rounded-none border-2 border-black bg-black px-5 py-2.5 text-sm font-bold text-white transition-all hover:-translate-y-0.5 hover:shadow-[3px_3px_0px_0px_#000]"
                >
                  Back to sessions
                </button>
              </div>
            </div>
          ) : (
            <div className="flex h-full flex-col">
              <ConversationHistory
                messages={messages}
                onWordInteract={handleWordInteract}
                onWordFlag={markWordDifficult}
                activeSessionId={activeSessionId}
              />
              <div className="sticky bottom-4 mt-4 space-y-3 rounded-none border-4 border-black bg-[var(--app-paper)]/95 p-4 shadow-[6px_6px_0px_0px_#000] backdrop-blur">
                <MomentResultInline
                  result={latestMomentResult}
                  onDismiss={clearMomentResult}
                />
                <SessionTurnFeedback
                  xpAwarded={latestXpAwarded}
                  comboCount={latestComboCount}
                  errorFeedback={latestErrorFeedback}
                  wordFeedback={latestWordFeedback}
                  onDismiss={clearTurnFeedback}
                />
                <LearningMomentCard
                  moment={pendingMoment}
                  loading={loading}
                  onSubmit={handleMomentSubmit}
                  onSkip={handleMomentSkip}
                />
                <MessageInput
                  value={draft}
                  onChange={setDraft}
                  onSubmit={handleSend}
                  disabled={isBlockingMoment || loading}
                  placeholder={
                    isBlockingMoment
                      ? 'Complete the prompt above first...'
                      : undefined
                  }
                  helperText={
                    isBlockingMoment
                      ? 'This quick exercise needs one answer before the conversation continues.'
                      : undefined
                  }
                />
                <div className="flex flex-col gap-3 text-xs text-[var(--app-ink-2)] sm:flex-row sm:items-center sm:justify-between">
                  <span>Double-click a highlighted word in the transcript to mark it difficult.</span>
                  <button
                    type="button"
                    onClick={handleCompleteSession}
                    disabled={isCompleting}
                    className="inline-flex items-center justify-center rounded-none border-2 border-black bg-white px-4 py-2 text-sm font-bold text-black transition-all hover:-translate-y-0.5 hover:shadow-[3px_3px_0px_0px_#000] disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {isCompleting ? 'Ending session...' : 'End session'}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

const SessionPage: React.FC = () => {
  return (
    <SpeakingModeProvider>
      <SessionPageContent />
    </SpeakingModeProvider>
  );
};

export default SessionPage;
