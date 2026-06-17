import React from 'react';
import { useRouter } from 'next/router';
import { useForm } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import * as yup from 'yup';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';
import apiService from '@/services/api';
import toast from 'react-hot-toast';
import ScenarioSelector from '@/components/learning/ScenarioSelector';
import { Globe } from 'lucide-react';
import { ImportStoryModal } from '@/components/stories/ImportStoryModal';

const durationOptions = [10, 15, 20, 30, 45];

const conversationStyles = [
  { value: 'storytelling', label: 'Storytelling', description: 'Continue an evolving narrative.' },
  { value: 'dialogue', label: 'Dialogue', description: 'Simulated back-and-forth conversations.' },
  { value: 'debate', label: 'Debate', description: 'Share opinions and defend a position.' },
  { value: 'tutorial', label: 'Tutorial', description: 'Learn about a topic with guided explanations.' },
];

const focusOptions = [
  { value: 'review', label: 'Review Heavy', description: 'Reinforce familiar vocabulary with gentle practice.' },
  { value: 'balanced', label: 'Balanced', description: 'Mix of new vocabulary and reviews.' },
  { value: 'new', label: 'New Words', description: 'Introduce more fresh vocabulary each turn.' },
];

const directionOptions = [
  { value: 'fr_to_de', label: 'French → German' },
  { value: 'de_to_fr', label: 'German → French' },
];

const schema = yup.object({
  topic: yup.string().optional(),
  conversationStyle: yup.string().oneOf(conversationStyles.map((item) => item.value)).required(),
  focus: yup.string().oneOf(focusOptions.map((item) => item.value)).required(),
  duration: yup
    .number()
    .oneOf(durationOptions, 'Please select a session length.')
    .required('Session length is required'),
  ankiDirection: yup.string().oneOf(directionOptions.map((item) => item.value)).required(),
});

type FormData = yup.InferType<typeof schema>;

export default function NewSessionPage() {
  const router = useRouter();
  const [isLoading, setIsLoading] = React.useState(false);

  const [selectedScenario, setSelectedScenario] = React.useState<string | null>(null);
  const [isImportModalOpen, setIsImportModalOpen] = React.useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormData>({
    resolver: yupResolver(schema),
    defaultValues: {
      conversationStyle: 'storytelling',
      focus: 'balanced',
      duration: 15,
      ankiDirection: 'fr_to_de',
    },
  });

  const onSubmit = async (data: FormData) => {
    setIsLoading(true);
    try {
      const duration = Number(data.duration);
      if (!Number.isFinite(duration)) {
        throw new Error('Invalid session length');
      }
      const payload = {
        topic: data.topic?.trim() || undefined,
        difficulty_preference: data.focus,
        planned_duration_minutes: duration,
        conversation_style: data.conversationStyle,
        generate_greeting: true,
        anki_direction: data.ankiDirection,
        scenario: selectedScenario || undefined,
      } as const;
      const response = await apiService.createSession(payload);
      const sessionId = (response as any)?.session?.id;
      if (!sessionId) {
        throw new Error('Session creation response missing identifier');
      }
      toast.success('Session created successfully!');
      const path = { pathname: '/learn/session/[id]', query: { id: sessionId } };
      await router.push(path);
    } catch (error) {
      toast.error('Failed to create session');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[var(--app-paper)] text-[var(--app-ink)] p-4 sm:p-6 lg:p-8">
      <div className="max-w-2xl mx-auto">
        <header className="mb-8 border-b border-[var(--app-ink)] pb-5">
          <div className="text-xs font-black uppercase tracking-[0.16em] text-[var(--app-ink-3)]">
            New Session
          </div>
          <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4 mt-1">
            <h1 className="font-serif text-5xl italic leading-none text-[var(--app-ink)]">
              Start Learning
            </h1>
          </div>
          <p className="mt-3 max-w-2xl text-[var(--app-ink-2)] text-sm">
            Create a personalized conversation session to practice your French skills.
          </p>
        </header>

        <Card className="mb-8 border-4 border-black bg-[var(--app-sheet)] shadow-[6px_6px_0px_0px_#000] rounded-none">
          <CardHeader className="bg-purple-100/50 border-b-4 border-black py-4 px-6">
            <CardTitle className="flex items-center gap-2 text-purple-900 font-bold uppercase text-lg">
              <Globe className="h-5 w-5 text-purple-700" />
              Import Content
            </CardTitle>
            <CardDescription className="text-purple-800 text-xs font-medium">
              Turn any French YouTube video or web article into an interactive lesson.
            </CardDescription>
          </CardHeader>
          <CardContent className="p-6">
            <Button
              onClick={() => setIsImportModalOpen(true)}
              variant="outline"
              className="w-full h-12 border-2 border-black bg-white hover:bg-purple-50 text-purple-700 font-bold rounded-none shadow-[4px_4px_0px_0px_#000] hover:-translate-y-0.5 hover:shadow-[5px_5px_0px_0px_#000] transition-all"
              leftIcon={<Globe className="h-4 w-4" />}
            >
              Paste Link (YouTube / Web)
            </Button>
          </CardContent>
        </Card>

        {isImportModalOpen && <ImportStoryModal onClose={() => setIsImportModalOpen(false)} />}

        <Card className="border-4 border-black bg-[var(--app-sheet)] shadow-[8px_8px_0px_0px_#000] rounded-none">
          <CardHeader className="border-b-4 border-black py-4 px-6 bg-[var(--app-paper-2)]">
            <CardTitle className="font-serif italic text-3xl text-[var(--app-ink)]">Session Settings</CardTitle>
            <CardDescription className="text-[var(--app-ink-2)] text-sm">
              Pick a topic, session style, and focus so the tutor can weave vocabulary into a natural conversation.
            </CardDescription>
          </CardHeader>
          <CardContent className="p-6">
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-8">
              <div>
                <label className="block text-sm font-bold uppercase text-[var(--app-ink)] mb-3">
                  Roleplay Scenario (Optional)
                </label>
                <ScenarioSelector selectedId={selectedScenario} onSelect={setSelectedScenario} />
                <p className="text-xs text-[var(--app-ink-3)] mt-2">
                  Select a scenario to act out a specific situation. This overrides the conversation style.
                </p>
              </div>

              <div className="border-t border-stone-200 pt-6">
                <Input
                  {...register('topic')}
                  label="Custom Topic (Optional)"
                  placeholder="e.g., Travel, Food, Business"
                  error={errors.topic?.message}
                  className="rounded-none border-2 border-black bg-white focus:ring-0 focus:border-black"
                />
              </div>

              <div>
                <label className="block text-sm font-bold uppercase text-[var(--app-ink)] mb-2">
                  Conversation Style
                </label>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {conversationStyles.map((style) => (
                    <label key={style.value} className="relative cursor-pointer block">
                      <input
                        {...register('conversationStyle')}
                        type="radio"
                        value={style.value}
                        className="sr-only custom-radio"
                        disabled={!!selectedScenario}
                      />
                      <div className={`p-4 border border-stone-300 bg-white transition-all rounded-none flex items-start gap-3 radio-card ${
                        selectedScenario ? 'opacity-50 cursor-not-allowed' : 'hover:border-stone-400'
                      }`}>
                        <div className="w-4 h-4 rounded-full border border-stone-400 flex items-center justify-center bg-white shrink-0 mt-0.5">
                          <div className="w-2.5 h-2.5 rounded-full bg-transparent radio-dot transition-colors" />
                        </div>
                        <div>
                          <p className="font-bold text-[var(--app-ink)]">{style.label}</p>
                          <p className="text-xs text-[var(--app-ink-2)] mt-0.5">{style.description}</p>
                        </div>
                      </div>
                    </label>
                  ))}
                </div>
                {errors.conversationStyle && (
                  <p className="mt-2 text-sm text-red-600">{errors.conversationStyle.message}</p>
                )}
              </div>

              <div>
                <label className="block text-sm font-bold uppercase text-[var(--app-ink)] mb-2">
                  Vocabulary Focus
                </label>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  {focusOptions.map((option) => (
                    <label key={option.value} className="relative cursor-pointer block">
                      <input
                        {...register('focus')}
                        type="radio"
                        value={option.value}
                        className="sr-only custom-radio"
                      />
                      <div className="p-4 border border-stone-300 bg-white transition-all rounded-none flex items-start gap-3 radio-card hover:border-stone-400">
                        <div className="w-4 h-4 rounded-full border border-stone-400 flex items-center justify-center bg-white shrink-0 mt-0.5">
                          <div className="w-2.5 h-2.5 rounded-full bg-transparent radio-dot transition-colors" />
                        </div>
                        <div>
                          <p className="font-bold text-[var(--app-ink)]">{option.label}</p>
                          <p className="text-xs text-[var(--app-ink-2)] mt-0.5">{option.description}</p>
                        </div>
                      </div>
                    </label>
                  ))}
                </div>
                {errors.focus && <p className="mt-2 text-sm text-red-600">{errors.focus.message}</p>}
              </div>

              <div>
                <label className="block text-sm font-bold uppercase text-[var(--app-ink)] mb-2">Card Orientation</label>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {directionOptions.map((option) => (
                    <label key={option.value} className="relative cursor-pointer block">
                      <input
                        {...register('ankiDirection')}
                        type="radio"
                        value={option.value}
                        className="sr-only custom-radio"
                      />
                      <div className="p-4 border border-stone-300 bg-white transition-all rounded-none flex items-start gap-3 radio-card hover:border-stone-400">
                        <div className="w-4 h-4 rounded-full border border-stone-400 flex items-center justify-center bg-white shrink-0 mt-0.5">
                          <div className="w-2.5 h-2.5 rounded-full bg-transparent radio-dot transition-colors" />
                        </div>
                        <div>
                          <p className="font-bold text-[var(--app-ink)]">{option.label}</p>
                        </div>
                      </div>
                    </label>
                  ))}
                </div>
                {errors.ankiDirection && (
                  <p className="mt-2 text-sm text-red-600">{errors.ankiDirection.message}</p>
                )}
              </div>

              <div>
                <label className="block text-sm font-bold uppercase text-[var(--app-ink)] mb-2">
                  Session Length
                </label>
                <div className="grid grid-cols-5 gap-3">
                  {durationOptions.map((minutes) => (
                    <label key={minutes} className="relative cursor-pointer block">
                      <input
                        {...register('duration', { valueAsNumber: true })}
                        type="radio"
                        value={minutes}
                        className="sr-only custom-radio"
                      />
                      <div className="p-3 border border-stone-300 bg-white transition-all rounded-none flex flex-col items-center justify-center gap-1 radio-card hover:border-stone-400 text-center">
                        <p className="font-bold text-[var(--app-ink)]">{minutes} min</p>
                      </div>
                    </label>
                  ))}
                </div>
                {errors.duration && (
                  <p className="mt-2 text-sm text-red-600">{errors.duration.message}</p>
                )}
              </div>

              <Button
                type="submit"
                className="w-full h-14 text-lg font-bold border-2 border-black bg-black text-white hover:bg-black/90 rounded-none shadow-[4px_4px_0px_0px_#000] hover:-translate-y-0.5 hover:shadow-[5px_5px_0px_0px_#000] transition-all"
                loading={isLoading}
              >
                Start Session
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>

      <style jsx global>{`
        .custom-radio:checked + .radio-card {
          border-color: #000 !important;
          background-color: var(--app-paper-2) !important;
        }
        .custom-radio:checked + .radio-card .radio-dot {
          background-color: #000 !important;
        }
      `}</style>
    </div>
  );
}
