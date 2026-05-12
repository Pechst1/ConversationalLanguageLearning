import React from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import { useForm } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import * as yup from 'yup';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';
import apiService from '@/services/api';
import toast from 'react-hot-toast';
import { getSession } from 'next-auth/react';

const schema = yup.object({
  name: yup.string().required('Name is required'),
  email: yup.string().email('Invalid email').required('Email is required'),
  password: yup.string().min(6, 'Password must be at least 6 characters').required('Password is required'),
  confirmPassword: yup.string().oneOf([yup.ref('password')], 'Passwords must match').required('Please confirm your password'),
  nativeLanguage: yup.string().required('Native language is required'),
  targetLanguage: yup.string().required('Target language is required'),
  proficiencyLevel: yup.string().required('Current level is required'),
});

type FormData = yup.InferType<typeof schema>;

const languageOptions = [
  { value: 'en', label: 'English' },
  { value: 'de', label: 'Deutsch' },
  { value: 'fr', label: 'Francais' },
  { value: 'es', label: 'Espanol' },
  { value: 'it', label: 'Italiano' },
  { value: 'pt', label: 'Portugues' },
];

const proficiencyOptions = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'];
const interestPresets = [
  'technology',
  'business',
  'travel',
  'sports',
  'politics',
  'science',
  'culture',
  'finance',
  'health',
  'food',
];

export default function SignUpPage() {
  const router = useRouter();
  const [isLoading, setIsLoading] = React.useState(false);
  const [selectedTopics, setSelectedTopics] = React.useState<string[]>([]);
  const [customTopic, setCustomTopic] = React.useState('');

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormData>({
    resolver: yupResolver(schema),
    defaultValues: {
      nativeLanguage: 'en',
      targetLanguage: 'fr',
      proficiencyLevel: 'A1',
    },
  });

  const toggleTopic = (topic: string) => {
    setSelectedTopics((prev) => {
      if (prev.includes(topic)) {
        return prev.filter((value) => value !== topic);
      }
      return [...prev, topic];
    });
  };

  const addCustomTopic = () => {
    const normalized = customTopic.trim().toLowerCase();
    if (!normalized) {
      return;
    }
    if (!selectedTopics.includes(normalized)) {
      setSelectedTopics((prev) => [...prev, normalized]);
    }
    setCustomTopic('');
  };

  const onSubmit = async (data: FormData) => {
    setIsLoading(true);
    try {
      await apiService.register({
        full_name: data.name,
        email: data.email,
        password: data.password,
        native_language: data.nativeLanguage,
        target_language: data.targetLanguage,
        proficiency_level: data.proficiencyLevel,
        interests: selectedTopics.join(','),
      });

      toast.success('Account created successfully! Please sign in.');
      router.push('/auth/signin');
    } catch (error: any) {
      const message = error.response?.data?.detail || 'An error occurred. Please try again.';
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <div className="mx-auto h-12 w-12 bg-primary-600 rounded-lg flex items-center justify-center">
            <span className="text-white font-bold text-lg">CL</span>
          </div>
          <h2 className="mt-6 text-3xl font-bold text-gray-900">Create your account</h2>
          <p className="mt-2 text-sm text-gray-600">
            Or{' '}
            <Link href="/auth/signin" className="font-medium text-primary-600 hover:text-primary-500">
              sign in to your existing account
            </Link>
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Get started</CardTitle>
            <CardDescription>Create your account to begin learning French</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
              <Input
                {...register('name')}
                type="text"
                label="Full name"
                placeholder="Enter your full name"
                error={errors.name?.message}
                autoComplete="name"
              />

              <Input
                {...register('email')}
                type="email"
                label="Email address"
                placeholder="Enter your email"
                error={errors.email?.message}
                autoComplete="email"
              />

              <Input
                {...register('password')}
                type="password"
                label="Password"
                placeholder="Create a password"
                error={errors.password?.message}
                autoComplete="new-password"
              />

              <Input
                {...register('confirmPassword')}
                type="password"
                label="Confirm password"
                placeholder="Confirm your password"
                error={errors.confirmPassword?.message}
                autoComplete="new-password"
              />

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-sm font-medium text-gray-700">Native language</label>
                  <select
                    {...register('nativeLanguage')}
                    className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                  >
                    {languageOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                  {errors.nativeLanguage?.message && (
                    <p className="mt-1 text-sm text-red-600">{errors.nativeLanguage.message}</p>
                  )}
                </div>

                <div>
                  <label className="mb-1 block text-sm font-medium text-gray-700">Target language</label>
                  <select
                    {...register('targetLanguage')}
                    className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                  >
                    {languageOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                  {errors.targetLanguage?.message && (
                    <p className="mt-1 text-sm text-red-600">{errors.targetLanguage.message}</p>
                  )}
                </div>
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Current CEFR level</label>
                <select
                  {...register('proficiencyLevel')}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                >
                  {proficiencyOptions.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
                {errors.proficiencyLevel?.message && (
                  <p className="mt-1 text-sm text-red-600">{errors.proficiencyLevel.message}</p>
                )}
              </div>

              <div className="space-y-3">
                <div>
                  <label className="mb-1 block text-sm font-medium text-gray-700">
                    Topics for live stories (onboarding)
                  </label>
                  <p className="text-xs text-gray-500">
                    Pick topics you want to discuss. You can change this later in settings.
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {interestPresets.map((topic) => (
                    <button
                      key={topic}
                      type="button"
                      onClick={() => toggleTopic(topic)}
                      className={`rounded-full border px-3 py-1 text-sm ${
                        selectedTopics.includes(topic)
                          ? 'border-primary-600 bg-primary-600 text-white'
                          : 'border-gray-300 text-gray-700'
                      }`}
                    >
                      {topic}
                    </button>
                  ))}
                </div>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={customTopic}
                    onChange={(event) => setCustomTopic(event.target.value)}
                    placeholder="Add custom topic"
                    className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm"
                  />
                  <Button type="button" variant="outline" onClick={addCustomTopic}>
                    Add
                  </Button>
                </div>
                {selectedTopics.length > 0 && (
                  <p className="text-xs text-gray-600">Selected: {selectedTopics.join(', ')}</p>
                )}
              </div>

              <Button type="submit" className="w-full" loading={isLoading}>
                Create account
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

// Prevent access if already authenticated
export async function getServerSideProps(context: any) {
  const session = await getSession(context);
  
  if (session) {
    return {
      redirect: {
        destination: '/atelier',
        permanent: false,
      },
    };
  }
  
  return {
    props: {},
  };
}
