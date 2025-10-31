import React from 'react';
import { getSession } from 'next-auth/react';
import { useRouter } from 'next/router';
import { useForm } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import * as yup from 'yup';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';
import apiService from '@/services/api';
import toast from 'react-hot-toast';

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

const schema = yup.object({
  topic: yup.string().optional(),
  conversationStyle: yup.string().oneOf(conversationStyles.map((item) => item.value)).required(),
  focus: yup.string().oneOf(focusOptions.map((item) => item.value)).required(),
  duration: yup
    .number()
    .oneOf(durationOptions, 'Please select a session length.')
    .required('Session length is required'),
});

type FormData = yup.InferType<typeof schema>;

export default function NewSessionPage() {
  const router = useRouter();
  const [isLoading, setIsLoading] = React.useState(false);

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
      } as const;
      const response = await apiService.createSession(payload);
      const sessionId = response?.session?.id;
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
    <div className="max-w-2xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Start New Learning Session</h1>
        <p className="text-gray-600 mt-2">
          Create a personalized conversation session to practice your French skills.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Session Settings</CardTitle>
          <CardDescription>
            Pick a topic, session style, and focus so the tutor can weave vocabulary into a natural conversation.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
            <Input
              {...register('topic')}
              label="Topic (Optional)"
              placeholder="e.g., Travel, Food, Business"
              error={errors.topic?.message}
            />

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Conversation Style
              </label>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {conversationStyles.map((style) => (
                  <label key={style.value} className="relative cursor-pointer">
                    <input
                      {...register('conversationStyle')}
                      type="radio"
                      value={style.value}
                      className="sr-only peer"
                    />
                    <div className="p-4 border-2 border-gray-200 rounded-lg peer-checked:border-primary-500 peer-checked:bg-primary-50 hover:border-gray-300 transition-colors">
                      <p className="font-semibold">{style.label}</p>
                      <p className="text-sm text-gray-600">{style.description}</p>
                    </div>
                  </label>
                ))}
              </div>
              {errors.conversationStyle && (
                <p className="mt-2 text-sm text-red-600">{errors.conversationStyle.message}</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Vocabulary Focus
              </label>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {focusOptions.map((option) => (
                  <label key={option.value} className="relative cursor-pointer">
                    <input
                      {...register('focus')}
                      type="radio"
                      value={option.value}
                      className="sr-only peer"
                    />
                    <div className="p-4 border-2 border-gray-200 rounded-lg peer-checked:border-primary-500 peer-checked:bg-primary-50 hover:border-gray-300 transition-colors">
                      <p className="font-semibold">{option.label}</p>
                      <p className="text-sm text-gray-600">{option.description}</p>
                    </div>
                  </label>
                ))}
              </div>
              {errors.focus && <p className="mt-2 text-sm text-red-600">{errors.focus.message}</p>}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Session Length
              </label>
              <div className="grid grid-cols-3 gap-3">
                {durationOptions.map((minutes) => (
                  <label key={minutes} className="relative">
                    <input
                      {...register('duration', { valueAsNumber: true })}
                      type="radio"
                      value={minutes}
                      className="sr-only peer"
                    />
                    <div className="p-4 border-2 border-gray-200 rounded-lg cursor-pointer peer-checked:border-primary-500 peer-checked:bg-primary-50 hover:border-gray-300 transition-colors text-center">
                      <p className="font-medium">{minutes} min</p>
                    </div>
                  </label>
                ))}
              </div>
              {errors.duration && (
                <p className="mt-2 text-sm text-red-600">{errors.duration.message}</p>
              )}
            </div>

            <Button type="submit" className="w-full" loading={isLoading}>
              Start Session
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

export async function getServerSideProps(context: any) {
  const session = await getSession(context);
  
  if (!session) {
    return {
      redirect: {
        destination: '/auth/signin',
        permanent: false,
      },
    };
  }
  
  return {
    props: {},
  };
}
