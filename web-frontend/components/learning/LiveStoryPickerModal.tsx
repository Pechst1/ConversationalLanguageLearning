import React, { useEffect, useMemo, useState } from 'react';
import { ExternalLink, RefreshCw, Sparkles, X } from 'lucide-react';
import toast from 'react-hot-toast';

import { Button } from '@/components/ui/Button';
import apiService, { LiveStory } from '@/services/api';

interface LiveStoryPickerModalProps {
  isOpen: boolean;
  isStarting?: boolean;
  onClose: () => void;
  onStartWithStory: (story: LiveStory) => Promise<void>;
  onStartDefault: () => Promise<void>;
}

export default function LiveStoryPickerModal({
  isOpen,
  isStarting = false,
  onClose,
  onStartWithStory,
  onStartDefault,
}: LiveStoryPickerModalProps) {
  const [stories, setStories] = useState<LiveStory[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [lastRefreshAt, setLastRefreshAt] = useState<Date | null>(null);

  const selectedStory = useMemo(
    () => stories.find((story) => story.id === selectedId) || null,
    [stories, selectedId]
  );

  const fetchStories = async () => {
    try {
      setIsLoading(true);
      const response = await apiService.getLiveStories({ limit: 6 });
      const items = response?.items || [];
      setStories(items);
      setSelectedId(items[0]?.id ?? null);
      setLastRefreshAt(new Date());
    } catch (error) {
      console.error('Failed to fetch live stories', error);
      toast.error('Could not load live stories');
      setStories([]);
      setSelectedId(null);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (!isOpen) return;
    void fetchStories();
  }, [isOpen]);

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
            <h2 className="text-xl font-black uppercase">Pick A Live Story</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded border-2 border-white p-1 hover:bg-white hover:text-black"
            aria-label="Close live story picker"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-4 overflow-auto p-4">
          <div className="flex items-center justify-between">
            <p className="text-sm font-bold text-gray-700">
              Stories are fetched in your target language.
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

          {lastRefreshAt && (
            <p className="text-xs font-semibold text-gray-500">
              Updated: {lastRefreshAt.toLocaleTimeString()}
            </p>
          )}

          {isLoading ? (
            <div className="border-2 border-dashed border-black p-8 text-center font-bold">
              Loading live stories...
            </div>
          ) : stories.length === 0 ? (
            <div className="border-2 border-dashed border-black p-8 text-center">
              <p className="font-bold">No live stories available right now.</p>
              <p className="mt-2 text-sm text-gray-600">You can still start a default quick session.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {stories.map((story) => (
                <button
                  key={story.id}
                  type="button"
                  onClick={() => setSelectedId(story.id)}
                  className={`w-full border-2 p-4 text-left transition-colors ${
                    selectedId === story.id
                      ? 'border-black bg-bauhaus-yellow'
                      : 'border-gray-300 bg-white hover:border-black'
                  }`}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="text-lg font-black text-black">{story.title}</p>
                      <p className="mt-1 text-sm font-semibold text-gray-700">
                        {story.source} • {story.language.toUpperCase()}
                      </p>
                      {story.summary && (
                        <p className="mt-2 text-sm text-gray-700 line-clamp-3">{story.summary}</p>
                      )}
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
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="flex items-center justify-between border-t-4 border-black p-4">
          <Button
            variant="outline"
            onClick={() => void onStartDefault()}
            loading={isStarting}
            className="border-2 border-black"
          >
            Start Without Story
          </Button>
          <Button
            onClick={() => selectedStory && void onStartWithStory(selectedStory)}
            loading={isStarting}
            disabled={!selectedStory}
            className="border-2 border-black"
          >
            Start With Selected Story
          </Button>
        </div>
      </div>
    </div>
  );
}
