import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import useSWR from 'swr';
import { ArrowLeft, BookOpen, AlertCircle, CheckCircle, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { useLearningSession, ChatMessage } from '@/hooks/useLearningSession';
import { ChapterBase, useCompleteChapter, useCheckGoals } from '@/hooks/useStories';
import NarrativeGoalsPanel from './NarrativeGoalsPanel';
import NarrativeCard from './NarrativeCard';
import ChapterProgressCard from './ChapterProgressCard';
import ChapterCompletionModal from './ChapterCompletionModal';
import ChapterGrammarPreview from './ChapterGrammarPreview';
import apiService from '@/services/api';
import { ChapterGrammarConcept } from '@/types/grammar';

interface StorySessionLayoutProps {
  storyId: number;
  chapterId: number;
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

  // Fetch grammar concepts for this chapter
  const { data: grammarConcepts, isLoading: loadingGrammar } = useSWR<ChapterGrammarConcept[]>(
    chapterId ? `/grammar/for-chapter/${chapterId}` : null,
    () => apiService.getGrammarForChapter(String(chapterId))
  );

  // Calculate total XP from messages
  useEffect(() => {
    const xp = messages.reduce((sum, msg) => sum + (msg.xp || 0), 0);
    setTotalXpEarned(xp);
  }, [messages]);

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

  const handleContinueAfterCompletion = () => {
    if (completionResult?.story_completed) {
      // Story completed - go back to story detail
      router.push(`/stories/${storyId}`);
    } else if (completionResult?.next_chapter_id) {
      // Continue to next chapter
      router.push(`/stories/${storyId}/chapter/${completionResult.next_chapter_id}`);
    } else {
      // Fallback - go to story detail
      router.push(`/stories/${storyId}`);
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

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => router.push(`/stories/${storyId}`)}
            >
              <ArrowLeft className="h-4 w-4 mr-2" />
              Exit Chapter
            </Button>
            <div className="flex items-center gap-3">
              <BookOpen className="h-5 w-5 text-primary-600" />
              <div>
                <h2 className="font-bold text-gray-900">{chapter.title}</h2>
                <p className="text-xs text-gray-500">Chapter {chapter.sequence_order}</p>
              </div>
            </div>
            <div className="w-24"></div> {/* Spacer for centering */}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Conversation Area */}
          <div className="lg:col-span-2 space-y-4">
            {/* Opening Narrative (shown once) */}
            {messages.length <= 1 && chapter.opening_narrative && (
              <NarrativeCard narrative={chapter.opening_narrative} />
            )}

            {/* Conversation */}
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 min-h-[500px] flex flex-col">
              {/* Messages */}
              <div className="flex-1 overflow-y-auto space-y-4 mb-4">
                {messages.map((message) => (
                  <div key={message.id} className="space-y-2">
                    <div
                      className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div
                        className={`max-w-[80%] rounded-lg p-4 ${
                          message.role === 'user'
                            ? 'bg-primary-600 text-white'
                            : 'bg-gray-100 text-gray-900'
                        }`}
                      >
                        <p className="whitespace-pre-wrap">{message.content}</p>
                        {message.xp && message.xp > 0 && (
                          <p className="text-xs mt-2 opacity-75 flex items-center gap-1">
                            <Sparkles className="h-3 w-3" />
                            +{message.xp} XP
                          </p>
                        )}
                      </div>
                    </div>

                    {/* Error Feedback for user messages */}
                    {message.role === 'user' && message.errorFeedback && message.errorFeedback.errors.length > 0 && (
                      <div className="flex justify-end">
                        <div className="max-w-[85%] bg-amber-50 border border-amber-200 rounded-lg p-3">
                          <div className="flex items-center gap-2 mb-2">
                            <AlertCircle className="h-4 w-4 text-amber-600" />
                            <span className="text-sm font-medium text-amber-800">Grammar Feedback</span>
                          </div>
                          <div className="space-y-2">
                            {message.errorFeedback.errors.map((error, idx) => (
                              <div key={idx} className="text-sm">
                                <p className="text-amber-900">{error.message}</p>
                                {error.suggestion && (
                                  <p className="text-amber-700 mt-1">
                                    <span className="font-medium">Suggestion:</span> {error.suggestion}
                                  </p>
                                )}
                              </div>
                            ))}
                          </div>
                          {message.errorFeedback.summary && (
                            <p className="text-xs text-amber-600 mt-2 pt-2 border-t border-amber-200">
                              {message.errorFeedback.summary}
                            </p>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Positive feedback when no errors */}
                    {message.role === 'user' && message.errorFeedback && message.errorFeedback.errors.length === 0 && message.xp && message.xp > 0 && (
                      <div className="flex justify-end">
                        <div className="max-w-[85%] bg-green-50 border border-green-200 rounded-lg p-2 flex items-center gap-2">
                          <CheckCircle className="h-4 w-4 text-green-600" />
                          <span className="text-sm text-green-800">Great job! No errors detected.</span>
                        </div>
                      </div>
                    )}
                  </div>
                ))}

                {loading && (
                  <div className="flex justify-start">
                    <div className="bg-gray-100 rounded-lg p-4">
                      <div className="flex gap-2">
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.4s' }}></div>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Input */}
              <div className="border-t border-gray-200 pt-4">
                <div className="flex gap-2">
                  <textarea
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        handleSend();
                      }
                    }}
                    placeholder="Type your message in French..."
                    className="flex-1 resize-none rounded-lg border border-gray-300 p-3 focus:outline-none focus:ring-2 focus:ring-primary-500"
                    rows={3}
                    disabled={!isConnected || loading}
                  />
                  <Button
                    onClick={handleSend}
                    disabled={!draft.trim() || !isConnected || loading}
                    className="self-end"
                  >
                    Send
                  </Button>
                </div>
                <p className="text-xs text-gray-500 mt-2">
                  {isConnected ? 'Connected' : 'Connecting...'}
                </p>
              </div>
            </div>
          </div>

          {/* Sidebar */}
          <div className="space-y-4">
            {/* Grammar Focus for Chapter */}
            {(grammarConcepts && grammarConcepts.length > 0) || loadingGrammar ? (
              <ChapterGrammarPreview
                concepts={grammarConcepts || []}
                onReviewClick={handleGrammarReviewClick}
                loading={loadingGrammar}
              />
            ) : null}

            {/* Narrative Goals */}
            <NarrativeGoalsPanel
              goals={chapter.narrative_goals || []}
              completedGoals={completedGoals}
            />

            {/* Vocabulary Helper */}
            {suggested.length > 0 && (
              <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
                <h3 className="font-bold mb-3 text-sm text-gray-900">Suggested Vocabulary</h3>
                <div className="space-y-2">
                  {suggested.map((word) => (
                    <div
                      key={word.id}
                      className="p-2 bg-gray-50 rounded cursor-pointer hover:bg-gray-100"
                      onClick={() => setDraft(draft + (draft ? ' ' : '') + word.word)}
                    >
                      <p className="font-medium text-sm">{word.word}</p>
                      {word.translation && (
                        <p className="text-xs text-gray-600">{word.translation}</p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Chapter Progress */}
            <ChapterProgressCard
              goalsCompleted={completedGoals.length}
              totalGoals={chapter.narrative_goals?.length || 0}
              vocabularyUsed={session?.stats.reviewedCards || 0}
              xpEarned={totalXpEarned}
              canComplete={canCompleteChapter()}
              onComplete={handleCompleteChapter}
              loading={completingChapter}
            />
          </div>
        </div>
      </div>

      {/* Completion Modal */}
      {showCompletionModal && completionResult && (
        <ChapterCompletionModal
          result={completionResult}
          onContinue={handleContinueAfterCompletion}
          onReturnToStory={() => router.push(`/stories/${storyId}`)}
        />
      )}
    </div>
  );
}
