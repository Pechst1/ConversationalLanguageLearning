import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ExternalLink, RefreshCw, Sparkles, X } from 'lucide-react';
import toast from 'react-hot-toast';

import { Button } from '@/components/ui/Button';
import apiService, { LiveStory } from '@/services/api';

interface LiveStoryPickerModalProps {
  isOpen: boolean;
  isStarting?: boolean;
  onClose: () => void;
  onStartImmersiveWithStory: (story: LiveStory) => Promise<void>;
  onStartWithStoryQuick?: (story: LiveStory) => Promise<void>;
  onStartDefault: () => Promise<void>;
}

export default function LiveStoryPickerModal({
  isOpen,
  isStarting = false,
  onClose,
  onStartImmersiveWithStory,
  onStartWithStoryQuick,
  onStartDefault,
}: LiveStoryPickerModalProps) {
  const [stories, setStories] = useState<LiveStory[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [lastRefreshAt, setLastRefreshAt] = useState<Date | null>(null);
  const [topicQuery, setTopicQuery] = useState('');
  const [appliedTopics, setAppliedTopics] = useState<string[]>([]);
  const [topicsUsed, setTopicsUsed] = useState<string[]>([]);

  const selectedStory = useMemo(
    () => stories.find((story) => story.id === selectedId) || null,
    [stories, selectedId]
  );

  const fetchStories = useCallback(async () => {
    try {
      setIsLoading(true);
      const response = await apiService.getLiveStories({
        limit: 6,
        topics: appliedTopics.length > 0 ? appliedTopics.join(',') : undefined,
      });
      const items = response?.items || [];
      setStories(items);
      setTopicsUsed(response?.topics_used || []);
      setSelectedId(items[0]?.id ?? null);
      setLastRefreshAt(new Date());
    } catch (error) {
      console.error('Failed to fetch live articles', error);
      toast.error('Could not load live articles');
      setStories([]);
      setTopicsUsed([]);
      setSelectedId(null);
    } finally {
      setIsLoading(false);
    }
  }, [appliedTopics]);

  const applyTopicFilter = () => {
    const parsed = topicQuery
      .split(',')
      .map((value) => value.trim().toLowerCase())
      .filter(Boolean);
    setAppliedTopics(parsed);
  };

  useEffect(() => {
    if (!isOpen) return;
    void fetchStories();
  }, [isOpen, fetchStories]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-3xl border-4 border-black bg-white shadow-[8px_8px_0px_0px_#000] max-h-[85vh] overflow-hidden"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b-4 border-black bg-bauhaus-blue px-4 py-3 text-white">
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5" />
            <h2 className="text-xl font-black uppercase">Pick A Live Article</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded border-2 border-white p-1 hover:bg-white hover:text-black"
            aria-label="Close live article picker"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-4 overflow-auto p-4">
          <div className="flex items-center justify-between">
            <p className="text-sm font-bold text-gray-700">
              Articles are fetched in your target language and matched to your topics.
            </p>
            <Button
              variant="outline"
              onClick={() => void fetchStories()}
              loading={isLoading}
              leftIcon={<RefreshCw className="h-4 w-4" />}
              className="border-2 border-black"
            >
              Refresh
            </Button>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={topicQuery}
              onChange={(event) => setTopicQuery(event.target.value)}
              placeholder="Focus topics, comma-separated (e.g. ai, startups, climate)"
              className="flex-1 border-2 border-black px-3 py-2 text-sm"
            />
            <Button
              type="button"
              variant="outline"
              onClick={applyTopicFilter}
              className="border-2 border-black"
            >
              Apply Topics
            </Button>
          </div>
          {topicsUsed.length > 0 && (
            <p className="text-xs font-semibold text-gray-600">
              Using topics: {topicsUsed.join(', ')}
            </p>
          )}

          {lastRefreshAt && (
            <p className="text-xs font-semibold text-gray-500">
              Updated: {lastRefreshAt.toLocaleTimeString()}
            </p>
          )}

          {isLoading ? (
            <div className="border-2 border-dashed border-black p-8 text-center font-bold">
              Loading live articles...
            </div>
          ) : stories.length === 0 ? (
            <div className="border-2 border-dashed border-black p-8 text-center">
              <p className="font-bold">No live articles available right now.</p>
              <p className="mt-2 text-sm text-gray-600">You can still start a default quick session.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {stories.map((story) => (
                <div
                  key={story.id}
                  onClick={() => {
                    if (selectedId === story.id) {
                      void onStartImmersiveWithStory(story);
                      return;
                    }
                    setSelectedId(story.id);
                  }}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      setSelectedId(story.id);
                    }
                  }}
                  role="button"
                  tabIndex={0}
                  className={`w-full border-2 p-4 text-left transition-colors ${
                    selectedId === story.id
                      ? 'border-black bg-bauhaus-yellow'
                      : 'border-gray-300 bg-white hover:border-black'
                  }`}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          void onStartImmersiveWithStory(story);
                        }}
                        disabled={isStarting}
                        className="text-left text-lg font-black text-black underline-offset-2 hover:underline disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {story.title}
                      </button>
                      <p className="mt-1 text-sm font-semibold text-gray-700">
                        {story.source} • {story.language.toUpperCase()}
                      </p>
                      {story.summary && (
                        <p className="mt-2 text-sm text-gray-700 line-clamp-3">{story.summary}</p>
                      )}
                      <div className="mt-3 flex flex-wrap items-center gap-2">
                        <Button
                          type="button"
                          onClick={(event) => {
                            event.stopPropagation();
                            void onStartImmersiveWithStory(story);
                          }}
                          loading={isStarting}
                          className="border-2 border-black"
                        >
                          Learn This Article
                        </Button>
                        {onStartWithStoryQuick && (
                          <Button
                            type="button"
                            variant="outline"
                            onClick={(event) => {
                              event.stopPropagation();
                              void onStartWithStoryQuick(story);
                            }}
                            loading={isStarting}
                            className="border-2 border-black"
                          >
                            Quick Chat
                          </Button>
                        )}
                      </div>
                    </div>
                    <a
                      href={story.url}
                      target="_blank"
                      rel="noreferrer"
                      onClick={(event) => event.stopPropagation()}
                      className="inline-flex items-center gap-1 text-sm font-bold underline"
                    >
                      Open
                      <ExternalLink className="h-3 w-3" />
                    </a>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 border-t-4 border-black p-4">
          <p className="text-xs font-semibold text-gray-600">
            Immersive mode imports the article and turns it into a guided discussion session.
          </p>
          <Button
            variant="outline"
            onClick={() => void onStartDefault()}
            loading={isStarting}
            className="border-2 border-black"
          >
            Start Without Article
          </Button>
          <div className="flex items-center gap-2">
            {onStartWithStoryQuick && (
              <Button
                variant="outline"
                onClick={() => selectedStory && void onStartWithStoryQuick(selectedStory)}
                loading={isStarting}
                disabled={!selectedStory}
                className="border-2 border-black"
              >
                Quick Chat
              </Button>
            )}
            <Button
              onClick={() => selectedStory && void onStartImmersiveWithStory(selectedStory)}
              loading={isStarting}
              disabled={!selectedStory}
              className="border-2 border-black"
            >
              Start Immersive Lesson
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
