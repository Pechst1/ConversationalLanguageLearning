import React from 'react';
import { getSession } from 'next-auth/react';
import { useRouter } from 'next/router';
import { useLearningSession } from '@/hooks/useLearningSession';
import ConversationHistory from '@/components/learning/ConversationHistory';
import VocabularyHelper from '@/components/learning/VocabularyHelper';
import MessageInput from '@/components/learning/MessageInput';
import ProgressIndicator from '@/components/learning/ProgressIndicator';

export default function SessionPage() {
  const router = useRouter();
  const { id } = router.query as { id: string };
  const { session, messages, send } = useLearningSession(id);

  if (!id) return null;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-2 learning-card">
        <div className="h-[70vh] overflow-y-auto pr-2">
          <ConversationHistory messages={messages} />
        </div>
        <div className="mt-4">
          <MessageInput value="" onChange={() => {}} onSubmit={(t) => send(t)} />
        </div>
      </div>
      <div className="space-y-6">
        <VocabularyHelper words={session?.suggestedVocabulary ?? []} />
        <ProgressIndicator xp={session?.xp ?? 0} level={session?.level ?? 1} streak={session?.streak ?? 0} />
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
