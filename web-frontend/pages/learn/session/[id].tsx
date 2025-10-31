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
  const { session, messages, send, suggested, logExposure, flagWord, complete } = useLearningSession(id);
  const [draft, setDraft] = React.useState('');
  const [summary, setSummary] = React.useState<any>(null);
  const [isCompleting, setIsCompleting] = React.useState(false);

  const handleSend = React.useCallback(
    async (text: string) => {
      if (summary) return;
      // The hook ignores selectedWordIds and sends the full suggestion list.
      // Keep API usage clear by omitting the unused param here.
      await send(text);
    },
    [send, summary]
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

  if (!id) return null;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-2 space-y-4">
        {!summary && (
          <VocabularyHelper className="learning-card" words={suggested} onInsertWord={handleInsertWord} />
        )}
        <div className="learning-card">
          {summary ? (
            <SessionSummary summary={summary} />
          ) : (
            <>
              <div className="conversation-window">
                <ConversationHistory
                  messages={messages}
                  onWordInteract={handleWordInteract}
                  onWordFlag={flagWord}
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
