mkdir -p web-frontend/pages/learn/session
cat > web-frontend/pages/learn/session/[id].tsx <<'TSX'
import React from 'react';
import { getSession } from 'next-auth/react';
import { useRouter } from 'next/router';
import toast from 'react-hot-toast';
import { Button } from '@/components/ui/Button';
import { useLearningSession } from '@/hooks/useLearningSession';
import ConversationHistory from '@/components/learning/ConversationHistory';
import VocabularyHelper from '@/components/learning/VocabularyHelper';
import MessageInput from '@/components/learning/MessageInput';
import ProgressIndicator from '@/components/learning/ProgressIndicator';
import SessionSummary from '@/components/learning/SessionSummary';

export default function SessionPage() {
  const router = useRouter();
  const { id } = router.query as { id: string };
  const { session, messages, send, suggested, logExposure, flagWord, complete, activeSessionId } = useLearningSession(id);
  const [draft, setDraft] = React.useState('');
  const [selectedWordIds, setSelectedWordIds] = React.useState<number[]>([]);
  const [summary, setSummary] = React.useState<any>(null);
  const [isCompleting, setIsCompleting] = React.useState(false);

  const handleSend = React.useCallback(
    async (text: string) => {
      if (summary) return;
      await send(text, selectedWordIds);
      setSelectedWordIds([]);
    },
    [send, selectedWordIds, summary]
  );

  const handleInsertWord = React.useCallback(
    (word: string) => {
      setDraft((existing) => {
        const lowered = existing.toLowerCase();
        if (lowered.includes(word.toLowerCase())) {
          return existing;
        }
        return existing ? `${existing} ${word}` : word;
      });
    },
    []
  );

  const handleToggleSuggestion = React.useCallback((word: { id: number }, isSelected: boolean) => {
    setSelectedWordIds((prev) => {
      if (isSelected) {
        if (prev.includes(word.id)) {
          return prev;
        }
        return [...prev, word.id];
      }
      return prev.filter((id) => id !== word.id);
    });
  }, []);

  const handleWordInteract = React.useCallback(
    (wordId: number, exposureType: 'hint' | 'translation') => {
      logExposure(wordId, exposureType);
    },
    [logExposure]
  );

  const handleCompleteSession = React.useCallback(async () => {
    if (!id || summary) return;
    try {
      setIsCompleting(true);
      const result = await complete();
      if (result) {
        setSummary(result);
        toast.success('Session completed! Review your highlights below.');
        setDraft('');
        setSelectedWordIds([]);
      }
    } catch (error) {
      toast.error('Unable to complete session right now.');
    } finally {
      setIsCompleting(false);
    }
  }, [complete, id, summary]);

  React.useEffect(() => {
    setSelectedWordIds((prev) => prev.filter((wordId) => suggested.some((item) => item.id === wordId)));
  }, [suggested]);

  if (!id) return null;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-2 space-y-4">
        {!summary && (
          <VocabularyHelper
            className="learning-card"
            words={suggested}
            onInsertWord={handleInsertWord}
            onToggleWord={handleToggleSuggestion}
          />
        )}
        <div className="learning-card">
          {summary ? (
            <SessionSummary
              stats={summary}
              onStartNewSession={() => router.push('/learn/new')}
              onReturnToDashboard={() => router.push('/dashboard')}
            />
          ) : (
            <>
              <div className="conversation-window">
                <ConversationHistory
                  messages={messages}
                  onWordInteract={handleWordInteract}
                  onWordFlag={flagWord}
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
        <ProgressIndicator xp={session?.xp_earned ?? 0} level={session?.level ?? 1} streak={session?.streak ?? 0} />
        {summary && (
          <Button className="w-full" onClick={() => router.push('/sessions')}>
            Back to Sessions
          </Button>
        )}
      </div>
    </div>
  );
}

export async function getServerSideProps(ctx: any) {
  const session = await getSession(ctx);
  if (!session) {
    return { redirect: { destination: '/auth/signin', permanent: false } };
  }
  return { props: {} };
}
TSX
