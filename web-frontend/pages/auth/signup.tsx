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
});

type FormData = yup.InferType<typeof schema>;

export default function SignUpPage() {
  const router = useRouter();
  const [isLoading, setIsLoading] = React.useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormData>({
    resolver: yupResolver(schema),
  });

  const onSubmit = async (data: FormData) => {
    setIsLoading(true);
    try {
      await apiService.register({
        name: data.name,
        email: data.email,
        password: data.password,
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
        destination: '/dashboard',
        permanent: false,
      },
    };
  }
  
  return {
    props: {},
  };
}