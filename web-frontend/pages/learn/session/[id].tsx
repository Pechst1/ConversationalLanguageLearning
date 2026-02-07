import React from 'react';
import type { GetServerSidePropsContext, GetServerSidePropsResult } from 'next';
import { getSession } from 'next-auth/react';
import { useRouter } from 'next/router';
import toast from 'react-hot-toast';

import ConversationHistory from '@/components/learning/ConversationHistory';
import MessageInput from '@/components/learning/MessageInput';
import ProgressIndicator from '@/components/learning/ProgressIndicator';
import SessionSummary from '@/components/learning/SessionSummary';
import VocabularyHelper from '@/components/learning/VocabularyHelper';
import XPNotification from '@/components/learning/XPNotification';
import ErrorFeedbackModal from '@/components/learning/ErrorFeedbackModal';
import VoiceModeToggle from '@/components/learning/VoiceModeToggle';
import { Button } from '@/components/ui/Button';
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
    sendMessage,
    suggested,
    logWordExposure,
    markWordDifficult,
    completeSession,
    activeSessionId,
    latestErrorFeedback,
    clearErrorFeedback,
    latestXpAwarded,
    latestComboCount,
    clearXpAwarded,
    clearComboCount,
  } = useLearningSession(sessionId);

  const [draft, setDraft] = React.useState('');
  const [selectedWordIds, setSelectedWordIds] = React.useState<number[]>([]);
  const [summary, setSummary] = React.useState<SummarySessionStats | null>(null);
  const [isCompleting, setIsCompleting] = React.useState(false);
  const { isSpeakingMode, speakText } = useSpeakingMode();

  // Track words sent in the last message to calculate XP breakdown correctly
  const lastSentWordsRef = React.useRef<any[]>([]);

  const handleSend = React.useCallback(
    async (text: string) => {
      if (!text.trim() || summary) {
        return;
      }

      // Store selected words before clearing them
      lastSentWordsRef.current = suggested.filter(w => selectedWordIds.includes(w.id));
      console.log('Sending message with words:', lastSentWordsRef.current);

      await sendMessage(text, selectedWordIds);
      setSelectedWordIds([]);
    },
    [sendMessage, selectedWordIds, summary, suggested],
  );

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

  const handleReturnToDashboard = React.useCallback(() => {
    router.push('/dashboard').catch((error) => {
      console.error('Failed to navigate to dashboard:', error);
      toast.error('Unable to navigate to dashboard.');
    });
  }, [router]);

  const handleStartNewSession = React.useCallback(() => {
    router.push('/learn/new').catch((error) => {
      console.error('Failed to start a new session:', error);
      toast.error('Unable to start a new session right now.');
    });
  }, [router]);

  const xp = session?.stats?.xpEarned ?? 0;
  const level = (session as unknown as { level?: number } | undefined)?.level ?? 1;
  const streak = (session as unknown as { streak?: number } | undefined)?.streak ?? 0;

  // Debug: Track error feedback changes
  React.useEffect(() => {
    console.log('[SessionPage] latestErrorFeedback changed:', latestErrorFeedback);
  }, [latestErrorFeedback]);

  // Track previous XP to show detailed notifications
  const prevXpRef = React.useRef(xp);
  const [xpNotifications, setXPNotifications] = React.useState<Array<{ id: string; xp: number; breakdown?: any; comboCount?: number }>>([]);

  // Use latestXpAwarded and latestComboCount from hook for accurate notifications
  React.useEffect(() => {
    if (latestXpAwarded && latestXpAwarded > 0) {
      console.log('[SessionPage] XP Awarded from WebSocket:', latestXpAwarded, 'Combo:', latestComboCount);

      // Use the words that were selected when the message was sent
      const wordsUsed = lastSentWordsRef.current;
      console.log('XP Breakdown Calculation - Words Used:', wordsUsed);

      // Identify hard words (new words or those marked as learning)
      const hardWords = wordsUsed
        .filter(w => w.familiarity === 'new' || w.is_new)
        .map(w => ({
          word: w.word,
          bonus: 5,
          reason: w.familiarity === 'new' ? 'Neues Vokabel gemeistert!' : 'Schwieriges Wort verwendet!',
        }));

      // Use combo count from backend if available
      const comboCount = latestComboCount || 0;
      const comboBonus = comboCount >= 2 ? (comboCount - 1) * 10 : 0;

      const wordBonus = wordsUsed.length * 10;
      const difficultyBonus = hardWords.length * 5;
      const calculatedTotal = wordBonus + difficultyBonus + comboBonus;
      const baseXP = Math.max(5, latestXpAwarded - calculatedTotal);

      const breakdown = {
        baseXP,
        wordBonus,
        difficultyBonus,
        comboBonus,
        perfectBonus: latestXpAwarded >= 50 ? 10 : 0,
        total: latestXpAwarded,
        words: wordsUsed.map(w => w.word),
        difficulty: hardWords.length > 0 ? ('hard' as const) : wordsUsed.length > 0 ? ('medium' as const) : ('easy' as const),
        hardWords,
      };

      console.log('[SessionPage] XP Breakdown Result:', breakdown);

      const notification = {
        id: `xp-${Date.now()}`,
        xp: latestXpAwarded,
        breakdown,
        comboCount,
      };

      setXPNotifications(prev => [...prev, notification]);

      // Reset tracked words
      lastSentWordsRef.current = [];

      // Show combo toast if combo count is significant
      if (comboCount >= 2) {
        toast.success(`${comboCount}x Combo! +${comboBonus} XP Bonus`, {
          icon: '🔥',
          duration: 3000,
          style: {
            borderRadius: '10px',
            background: 'linear-gradient(135deg, #ff6b35, #f72585)',
            color: '#fff',
            fontWeight: 'bold',
          },
        });
      } else if (latestXpAwarded >= 15) {
        toast.success(`+${latestXpAwarded} XP`, {
          icon: '⭐',
          style: {
            borderRadius: '10px',
            background: '#333',
            color: '#fff',
          },
        });
      }

      // Clear the latest values to avoid re-triggering
      clearXpAwarded();
      if (latestComboCount) clearComboCount();
    }
  }, [latestXpAwarded, latestComboCount, clearXpAwarded, clearComboCount, suggested]);

  if (!sessionId) {
    return null;
  }

  return (
    <>
      {/* XP Notifications */}
      {xpNotifications.map((notif) => (
        <XPNotification
          key={notif.id}
          xpGained={notif.xp}
          breakdown={notif.breakdown}
          onComplete={() => setXPNotifications(prev => prev.filter(n => n.id !== notif.id))}
        />
      ))}

      {/* Error Feedback Modal */}
      {latestErrorFeedback && (
        <ErrorFeedbackModal
          errorFeedback={latestErrorFeedback}
          onClose={clearErrorFeedback}
        />
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          {!summary && (
            <>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-black uppercase tracking-wider">Mission Control</h2>
                <VoiceModeToggle />
              </div>
              <VocabularyHelper
                className="learning-card"
                words={suggested}
                onInsertWord={handleInsertWord}
                onToggleWord={handleToggleSuggestion}
              />
            </>
          )}

          <div className="learning-card">
            {summary ? (
              <SessionSummary
                stats={summary}
                onStartNewSession={handleStartNewSession}
                onReturnToDashboard={handleReturnToDashboard}
              />
            ) : (
              <>
                <div className="conversation-window">
                  <ConversationHistory
                    messages={messages}
                    onWordInteract={handleWordInteract}
                    onWordFlag={markWordDifficult}
                    activeSessionId={activeSessionId}
                  />
                </div>
                <div className="mt-4 space-y-3">
                  <MessageInput value={draft} onChange={setDraft} onSubmit={handleSend} />
                  <div className="flex justify-end">
                    <Button variant="outline" onClick={handleCompleteSession} loading={isCompleting}>
                      Complete Session
                    </Button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>

        <div className="space-y-6">
          <ProgressIndicator xp={xp} level={level} streak={streak} />
          {summary && (
            <Button className="w-full" onClick={() => router.push('/sessions')}>
              Back to Sessions
            </Button>
          )}
        </div>
      </div>
    </>
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
