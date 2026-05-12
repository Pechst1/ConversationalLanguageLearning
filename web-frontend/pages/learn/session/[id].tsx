import React from 'react';
import type { GetServerSidePropsContext, GetServerSidePropsResult } from 'next';
import { getSession } from 'next-auth/react';
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
    <div className="min-h-screen bg-[#f6f1e7] text-stone-900">
      <div className="mx-auto flex min-h-screen max-w-5xl flex-col px-4 py-6 sm:px-6 lg:px-8">
        <header className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-2">
            <div className="text-[11px] font-medium uppercase tracking-[0.22em] text-stone-400">
              {summary ? 'Session review' : 'Learning stream'}
            </div>
            <h1 className="text-2xl font-semibold tracking-tight text-stone-900 sm:text-3xl">
              {summary ? 'Review this session' : 'Continue learning'}
            </h1>
            <p className="max-w-2xl text-sm leading-6 text-stone-500">
              {summary
                ? 'Your recap stays in one place so you can decide what to revisit next.'
                : 'The session chooses the next prompt. Your job is just to respond.'}
            </p>
          </div>
          <VoiceModeToggle className="lg:justify-end" />
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
            <div className="rounded-[32px] border border-stone-200 bg-white/90 p-6 shadow-sm">
              <SessionSummary
                stats={summary}
                onStartNewSession={handleContinueLearning}
                onReturnToLearning={handleReturnToLearningStream}
              />
              <div className="mt-6 flex justify-end">
                <button
                  type="button"
                  onClick={() => router.push('/sessions')}
                  className="inline-flex items-center justify-center rounded-full border border-stone-200 bg-stone-900 px-5 py-2.5 text-sm font-medium text-stone-50 transition-colors hover:bg-stone-800"
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
              <div className="sticky bottom-4 mt-4 space-y-3 rounded-[32px] border border-stone-200 bg-[#f6f1e7]/95 p-3 shadow-lg backdrop-blur">
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
                <div className="flex flex-col gap-3 text-xs text-stone-500 sm:flex-row sm:items-center sm:justify-between">
                  <span>Double-click a highlighted word in the transcript to mark it difficult.</span>
                  <button
                    type="button"
                    onClick={handleCompleteSession}
                    disabled={isCompleting}
                    className="inline-flex items-center justify-center rounded-full border border-stone-200 bg-white px-4 py-2 text-sm font-medium text-stone-700 transition-colors hover:bg-stone-50 disabled:cursor-not-allowed disabled:opacity-60"
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

export async function getServerSideProps(
  ctx: GetServerSidePropsContext,
): Promise<GetServerSidePropsResult<Record<string, never>>> {
  const session = await getSession(ctx);

  if (!session) {
    return {
      redirect: {
        destination: '/auth/signin',
        permanent: false,
      },
    };
  }

  return { props: {} };
}
