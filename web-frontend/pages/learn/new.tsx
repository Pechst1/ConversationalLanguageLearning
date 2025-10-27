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

const schema = yup.object({
  topic: yup.string().optional(),
  difficulty: yup.string().oneOf(['beginner', 'intermediate', 'advanced']).optional(),
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
      difficulty: 'intermediate',
    },
  });

  const onSubmit = async (data: FormData) => {
    setIsLoading(true);
    try {
      const session = await apiService.createSession(data);
      toast.success('Session created successfully!');
      router.push(`/learn/session/${session.id}`);
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
            Customize your learning experience by selecting a topic and difficulty level.
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
                Difficulty Level
              </label>
              <div className="grid grid-cols-3 gap-3">
                {['beginner', 'intermediate', 'advanced'].map((level) => (
                  <label key={level} className="relative">
                    <input
                      {...register('difficulty')}
                      type="radio"
                      value={level}
                      className="sr-only peer"
                    />
                    <div className="p-4 border-2 border-gray-200 rounded-lg cursor-pointer peer-checked:border-primary-500 peer-checked:bg-primary-50 hover:border-gray-300 transition-colors">
                      <div className="text-center">
                        <p className="font-medium capitalize">{level}</p>
                      </div>
                    </div>
                  </label>
                ))}
              </div>
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