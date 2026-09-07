/* One chapter of a Bibliothèque text, played as a conversation — on the Claude
 * design (Atelier V2).
 *
 * The data flow is exactly what it was before the WP-20 migration: one learning
 * session over the chapter, goals re-checked against the server after every
 * turn, grammar concepts marked as practised in context on completion. What
 * changed is the chrome and the routes, which now lead to `/bibliotheque/…`.
 *
 * The screen owns its own `AtelierV2Root` because it is rendered directly by
 * the chapter route, not inside another av2 surface.
 */

import React, { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/router';
import useSWR from 'swr';

import {
  Action,
  ArrowLeftIcon,
  AtelierV2Root,
  Chip,
  IconAction,
  SendIcon,
} from '@/components/atelier-v2/ui';
import { useLearningSession } from '@/hooks/useLearningSession';
import { ChapterBase, useCompleteChapter, useCheckGoals } from '@/hooks/useStories';
import NarrativeGoalsPanel from './NarrativeGoalsPanel';
import NarrativeCard from './NarrativeCard';
import ChapterProgressCard from './ChapterProgressCard';
import ChapterCompletionModal from './ChapterCompletionModal';
import ChapterGrammarPreview from './ChapterGrammarPreview';
import apiService from '@/services/api';
import { ChapterGrammarConcept } from '@/types/grammar';

interface StorySessionLayoutProps {
  storyId: string;
  chapterId: string;
  sessionId: string;
  chapter: ChapterBase;
}

export default function StorySessionLayout({
  storyId,
  chapterId,
  sessionId,
  chapter,
}: StorySessionLayoutProps) {
  const router = useRouter();
  const { session, messages, sendMessage, suggested, isConnected, loading } = useLearningSession(sessionId);
  const { completeChapter, loading: completingChapter } = useCompleteChapter();
  const { checkGoals } = useCheckGoals();

  const [draft, setDraft] = useState('');
  const [completedGoals, setCompletedGoals] = useState<string[]>([]);
  const [showCompletionModal, setShowCompletionModal] = useState(false);
  const [completionResult, setCompletionResult] = useState<any>(null);
  const [totalXpEarned, setTotalXpEarned] = useState(0);
  const feedEndRef = useRef<HTMLDivElement>(null);
  const grammarKey = chapterId ? `/grammar/for-chapter/${chapterId}` : null;
  const fetchGrammarForChapter = async (key: string): Promise<ChapterGrammarConcept[]> => {
    const chapterIdFromKey = key.split('/').pop() || '';
    return apiService.getGrammarForChapter(chapterIdFromKey) as Promise<ChapterGrammarConcept[]>;
  };

  // Fetch grammar concepts for this chapter
  const { data: grammarConcepts, isLoading: loadingGrammar } = useSWR<ChapterGrammarConcept[]>(
    grammarKey,
    fetchGrammarForChapter,
  );

  // Calculate total XP from messages
  useEffect(() => {
    const xp = messages.reduce((sum, msg) => sum + (msg.xp || 0), 0);
    setTotalXpEarned(xp);
  }, [messages]);

  // Keep the newest turn in view, the way a conversation is read.
  useEffect(() => {
    feedEndRef.current?.scrollIntoView({ block: 'end' });
  }, [messages.length]);

  // Check goal completion after each message using backend
  useEffect(() => {
    const updateGoals = async () => {
      if (!sessionId || messages.length === 0) return;

      try {
        const result = await checkGoals(storyId, chapterId, sessionId);
        setCompletedGoals(result.goals_completed);
      } catch (error) {
        console.error('Failed to check goals:', error);
        // Silently fail - goal checking is not critical
      }
    };

    updateGoals();
  }, [messages, sessionId, storyId, chapterId, checkGoals]);

  const handleSend = async () => {
    if (!draft.trim() || loading) return;

    try {
      await sendMessage(draft);
      setDraft('');
    } catch (error) {
      console.error('Failed to send message:', error);
    }
  };

  const handleCompleteChapter = async () => {
    try {
      const result = await completeChapter(storyId, chapterId, {
        session_id: sessionId,
        goals_completed: completedGoals,
      });

      // Mark grammar concepts as practiced in context
      if (grammarConcepts && grammarConcepts.length > 0) {
        const conceptIds = grammarConcepts.map(c => c.id);
        try {
          await apiService.markGrammarPracticedInContext(conceptIds);
        } catch (err) {
          console.error('Failed to mark grammar as practiced:', err);
          // Non-critical, continue with completion
        }
      }

      setCompletionResult(result);
      setShowCompletionModal(true);
    } catch (error) {
      console.error('Failed to complete chapter:', error);
    }
  };

  const canCompleteChapter = () => {
    if (!chapter.completion_criteria) return true;

    const minGoals = chapter.completion_criteria.min_goals_completed || 0;
    const minVocab = chapter.completion_criteria.min_vocabulary_used || 0;

    const goalsCompleted = completedGoals.length >= minGoals;
    const vocabularyUsed = (session?.stats.reviewedCards || 0) >= minVocab;

    return goalsCompleted && vocabularyUsed;
  };

  const handleGrammarReviewClick = (conceptId: number) => {
    // Open grammar page with this concept pre-selected for review
    router.push(`/grammar?review=${conceptId}`);
  };

  const chapterNumber = chapter.sequence_order ?? chapter.order_index + 1;

  return (
    <>
      <AtelierV2Root as="main" className="bib-session" aria-label={chapter.title}>
        <header className="bib-session__head">
          <IconAction
            label="Quitter le chapitre"
            onClick={() => router.push(`/bibliotheque/${storyId}`)}
          >
            <ArrowLeftIcon size={18} />
          </IconAction>
          <div className="bib-session__title">
            <p className="av2-label">Chapitre {chapterNumber}</p>
            <h1 className="av2-headline av2-headline--title">{chapter.title}</h1>
          </div>
        </header>

        {messages.length <= 1 && chapter.opening_narrative && (
          <NarrativeCard narrative={chapter.opening_narrative} />
        )}

        <section className="bib-chat" aria-label="La conversation">
          <div className="bib-chat__feed" aria-live="polite">
            {messages.map((message) => (
              <div className="bib-turn" key={message.id} data-role={message.role}>
                <div className="bib-bubble" data-role={message.role}>
                  <p className="av2-body av2-body--lg bib-bubble__text">{message.content}</p>
                  {message.xp && message.xp > 0 ? (
                    <p className="av2-label">+{message.xp} XP</p>
                  ) : null}
                </div>

                {message.role === 'user' && message.errors && message.errors.errors.length > 0 && (
                  <div className="bib-note" data-tone="repair">
                    <p className="av2-label">À reprendre</p>
                    {message.errors.errors.map((error, idx) => (
                      <p className="av2-body" key={idx}>
                        {error.message}
                        {error.suggestion ? ` — ${error.suggestion}` : ''}
                      </p>
                    ))}
                    {message.errors.summary && <p className="av2-label">{message.errors.summary}</p>}
                  </div>
                )}

                {message.role === 'user'
                  && message.errors
                  && message.errors.errors.length === 0
                  && message.xp
                  && message.xp > 0 ? (
                  <div className="bib-note" data-tone="correct">
                    <p className="av2-label">Rien à reprendre.</p>
                  </div>
                ) : null}
              </div>
            ))}

            {loading && (
              <div className="bib-turn" data-role="assistant">
                <div className="bib-bubble" data-role="assistant" aria-busy="true">
                  <p className="av2-label">En train d’écrire…</p>
                </div>
              </div>
            )}
            <div ref={feedEndRef} />
          </div>

          {suggested.length > 0 && (
            <div className="bib-chips" aria-label="Mots suggérés">
              {suggested.map((word) => (
                <Chip
                  key={word.id}
                  onClick={() => setDraft(draft + (draft ? ' ' : '') + word.word)}
                  title={word.translation || undefined}
                >
                  {word.word}
                </Chip>
              ))}
            </div>
          )}

          <div className="av2-composer bib-composer">
            <label className="av2-field">
              <span className="av2-field__label">Votre réponse, en français</span>
              <textarea
                className="av2-field__control"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                placeholder="Écrivez en français…"
                rows={3}
                disabled={!isConnected || loading}
              />
            </label>
            <IconAction
              label="Envoyer"
              tone="action"
              pressable
              onClick={handleSend}
              disabled={!draft.trim() || !isConnected || loading}
            >
              <SendIcon size={18} />
            </IconAction>
          </div>
          <p className="av2-label">{isConnected ? 'En liaison' : 'Liaison en cours…'}</p>
        </section>

        <aside className="bib-session__aside" aria-label="Le suivi du chapitre">
          {(grammarConcepts && grammarConcepts.length > 0) || loadingGrammar ? (
            <ChapterGrammarPreview
              concepts={grammarConcepts || []}
              onReviewClick={handleGrammarReviewClick}
              loading={loadingGrammar}
            />
          ) : null}

          <NarrativeGoalsPanel
            goals={chapter.narrative_goals || []}
            completedGoals={completedGoals}
          />

          <ChapterProgressCard
            goalsCompleted={completedGoals.length}
            totalGoals={chapter.narrative_goals?.length || 0}
            vocabularyUsed={session?.stats.reviewedCards || 0}
            xpEarned={totalXpEarned}
            canComplete={canCompleteChapter()}
            onComplete={handleCompleteChapter}
            loading={completingChapter}
          />
        </aside>

        {showCompletionModal && completionResult && (
          <ChapterCompletionModal
            isOpen={showCompletionModal}
            onClose={() => setShowCompletionModal(false)}
            result={completionResult}
            storyId={storyId}
            storyTitle={chapter.title}
          />
        )}
      </AtelierV2Root>
      <style jsx global>{`
        body { background: var(--app-paper); }
        .av2.bib-session {
          min-height: 100vh;
          max-width: 560px;
          margin: 0 auto;
          padding: 16px 18px 28px;
          display: flex;
          flex-direction: column;
          gap: 16px;
        }
        .av2 .bib-session__head { display: flex; align-items: flex-start; gap: 10px; }
        .av2 .bib-session__title { min-width: 0; }
        .av2 .bib-chat { display: flex; flex-direction: column; gap: 12px; }
        .av2 .bib-chat__feed {
          display: flex;
          flex-direction: column;
          gap: 12px;
          max-height: 58vh;
          overflow-y: auto;
        }
        .av2 .bib-turn { display: flex; flex-direction: column; gap: 6px; align-items: flex-start; }
        .av2 .bib-turn[data-role='user'] { align-items: flex-end; }
        .av2 .bib-bubble {
          max-width: 86%;
          border-radius: var(--av2-r-card, 16px);
          padding: 12px 14px;
          background: var(--av2-card);
        }
        .av2 .bib-bubble[data-role='user'] {
          background: var(--av2-blue);
          color: var(--av2-on-blue);
        }
        .av2 .bib-bubble[data-role='user'] .av2-body,
        .av2 .bib-bubble[data-role='user'] .av2-label { color: inherit; }
        .av2 .bib-bubble__text { white-space: pre-wrap; }
        .av2 .bib-note {
          max-width: 86%;
          border-radius: 14px;
          padding: 10px 12px;
          background: var(--av2-tint-wrong, var(--av2-line));
        }
        .av2 .bib-note[data-tone='correct'] { background: var(--av2-tint-correct, var(--av2-line)); }
        .av2 .bib-composer { align-items: flex-end; }
        .av2 .bib-session__aside { display: flex; flex-direction: column; gap: 12px; }
      `}</style>
    </>
  );
}
