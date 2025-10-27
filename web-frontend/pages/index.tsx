import { useSession } from 'next-auth/react';
import { useRouter } from 'next/router';
import { useEffect } from 'react';
import Link from 'next/link';
import { BookOpen, MessageCircle, TrendingUp, Users } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';

const features = [
  {
    name: 'Interactive Conversations',
    description: 'Practice French through AI-powered conversations that adapt to your level.',
    icon: MessageCircle,
  },
  {
    name: 'Vocabulary Learning',
    description: 'Master new words with our spaced repetition system.',
    icon: BookOpen,
  },
  {
    name: 'Progress Tracking',
    description: 'Monitor your learning journey with detailed analytics.',
    icon: TrendingUp,
  },
  {
    name: 'Achievement System',
    description: 'Stay motivated with badges and streak rewards.',
    icon: Users,
  },
];

export default function HomePage() {
  const { data: session, status } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (status === 'authenticated') {
      router.push('/dashboard');
    }
  }, [status, router]);

  if (status === 'loading') {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-50 to-secondary-50">
      {/* Hero Section */}
      <div className="relative isolate px-6 pt-14 lg:px-8">
        <div className="mx-auto max-w-2xl py-32 sm:py-48 lg:py-56">
          <div className="text-center">
            <h1 className="text-4xl font-bold tracking-tight text-gray-900 sm:text-6xl">
              Learn French Through{' '}
              <span className="text-primary-600">Conversation</span>
            </h1>
            <p className="mt-6 text-lg leading-8 text-gray-600">
              Master French naturally with AI-powered conversations, personalized vocabulary training, 
              and intelligent progress tracking. Start your journey today!
            </p>
            <div className="mt-10 flex items-center justify-center gap-x-6">
              <Link href="/auth/signup">
                <Button size="lg">Get Started</Button>
              </Link>
              <Link href="/auth/signin">
                <Button variant="outline" size="lg">Sign In</Button>
              </Link>
            </div>
          </div>
        </div>
      </div>

      {/* Features Section */}
      <div className="py-24 sm:py-32">
        <div className="mx-auto max-w-7xl px-6 lg:px-8">
          <div className="mx-auto max-w-2xl lg:text-center">
            <h2 className="text-base font-semibold leading-7 text-primary-600">Learn Smarter</h2>
            <p className="mt-2 text-3xl font-bold tracking-tight text-gray-900 sm:text-4xl">
              Everything you need to master French
            </p>
            <p className="mt-6 text-lg leading-8 text-gray-600">
              Our platform combines cutting-edge AI technology with proven language learning 
              methodologies to create the most effective learning experience.
            </p>
          </div>
          <div className="mx-auto mt-16 max-w-2xl sm:mt-20 lg:mt-24 lg:max-w-none">
            <dl className="grid max-w-xl grid-cols-1 gap-x-8 gap-y-16 lg:max-w-none lg:grid-cols-2">
              {features.map((feature) => (
                <Card key={feature.name} className="hover:shadow-lg transition-shadow">
                  <CardHeader>
                    <div className="flex items-center space-x-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary-600">
                        <feature.icon className="h-6 w-6 text-white" aria-hidden="true" />
                      </div>
                      <CardTitle className="text-xl">{feature.name}</CardTitle>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <CardDescription className="text-base">{feature.description}</CardDescription>
                  </CardContent>
                </Card>
              ))}
            </dl>
          </div>
        </div>
      </div>

      {/* CTA Section */}
      <div className="bg-primary-600">
        <div className="px-6 py-24 sm:px-6 sm:py-32 lg:px-8">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
              Ready to start learning?
            </h2>
            <p className="mx-auto mt-6 max-w-xl text-lg leading-8 text-primary-100">
              Join thousands of learners who are improving their French skills every day.
            </p>
            <div className="mt-10 flex items-center justify-center gap-x-6">
              <Link href="/auth/signup">
                <Button variant="secondary" size="lg">
                  Start Free Trial
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}