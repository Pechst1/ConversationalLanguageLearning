import React from 'react';
import { getSession } from 'next-auth/react';
import Link from 'next/link';
import { BookOpen, MessageCircle, TrendingUp, Trophy, Plus, Book } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';
import apiService from '@/services/api';
import { useCurrentStory } from '@/hooks/useStories';

interface DashboardProps {
  summary: {
    total_xp: number;
    current_streak: number;
    words_mastered: number;
    sessions_completed: number;
  };
  recentSessions: any[];
}

export default function Dashboard({ summary, recentSessions }: DashboardProps) {
  const { currentStory, loading: storyLoading } = useCurrentStory();

  const quickStats = [
    {
      name: 'Total XP',
      value: summary?.total_xp || 0,
      icon: TrendingUp,
      color: 'text-blue-600',
      bgColor: 'bg-blue-100',
    },
    {
      name: 'Current Streak',
      value: `${summary?.current_streak || 0} days`,
      icon: Trophy,
      color: 'text-yellow-600',
      bgColor: 'bg-yellow-100',
    },
    {
      name: 'Words Mastered',
      value: summary?.words_mastered || 0,
      icon: BookOpen,
      color: 'text-green-600',
      bgColor: 'bg-green-100',
    },
    {
      name: 'Sessions Completed',
      value: summary?.sessions_completed || 0,
      icon: MessageCircle,
      color: 'text-purple-600',
      bgColor: 'bg-purple-100',
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-gray-600">Welcome back! Ready to continue learning?</p>
        </div>
        <Link href="/learn/new">
          <Button leftIcon={<Plus className="h-4 w-4" />}>
            Start New Session
          </Button>
        </Link>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {quickStats.map((stat) => (
          <Card key={stat.name}>
            <CardContent className="p-6">
              <div className="flex items-center">
                <div className={`p-2 rounded-lg ${stat.bgColor}`}>
                  <stat.icon className={`h-6 w-6 ${stat.color}`} />
                </div>
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-600">{stat.name}</p>
                  <p className="text-2xl font-bold text-gray-900">{stat.value}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Currently Reading Story */}
      {!storyLoading && currentStory && (
        <Card className="border-2 border-primary-200 bg-gradient-to-br from-primary-50 to-blue-50">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Book className="h-5 w-5 text-primary-600" />
                <CardTitle className="text-primary-900">Currently Reading</CardTitle>
              </div>
              <Link href={`/stories/${currentStory.story.id}`}>
                <Button variant="outline" size="sm">
                  View Story
                </Button>
              </Link>
            </div>
            <CardDescription>Continue your interactive story adventure</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-start gap-4">
              {/* Story Cover */}
              {currentStory.story.cover_image_url ? (
                <div className="flex-shrink-0 w-24 h-32 bg-gray-200 rounded-lg overflow-hidden shadow-md">
                  <img
                    src={currentStory.story.cover_image_url}
                    alt={currentStory.story.title}
                    className="w-full h-full object-cover"
                  />
                </div>
              ) : (
                <div className="flex-shrink-0 w-24 h-32 bg-gradient-to-br from-primary-400 to-blue-500 rounded-lg flex items-center justify-center shadow-md">
                  <Book className="h-12 w-12 text-white" />
                </div>
              )}

              {/* Story Info */}
              <div className="flex-1 min-w-0">
                <h3 className="text-lg font-bold text-gray-900 mb-1">
                  {currentStory.story.title}
                </h3>
                {currentStory.user_progress && (
                  <div className="space-y-2">
                    <p className="text-sm text-gray-600">
                      Chapter {currentStory.user_progress.current_chapter_number || 1}:{' '}
                      <span className="font-medium">{currentStory.user_progress.current_chapter_title || 'Loading...'}</span>
                    </p>

                    {/* Progress Bar */}
                    <div className="space-y-1">
                      <div className="flex items-center justify-between text-xs text-gray-600">
                        <span>{currentStory.user_progress.completion_percentage.toFixed(0)}% complete</span>
                        <span>{currentStory.user_progress.chapters_completed} / {currentStory.story.total_chapters} chapters</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2.5 overflow-hidden">
                        <div
                          className="bg-gradient-to-r from-primary-500 to-blue-600 h-2.5 rounded-full transition-all duration-500"
                          style={{ width: `${currentStory.user_progress.completion_percentage}%` }}
                        />
                      </div>
                    </div>

                    {/* Stats */}
                    <div className="flex items-center gap-4 text-xs text-gray-600 pt-1">
                      <span className="flex items-center gap-1">
                        <Trophy className="h-3 w-3 text-yellow-600" />
                        {currentStory.user_progress.total_xp_earned} XP
                      </span>
                      {currentStory.user_progress.perfect_chapters_count > 0 && (
                        <span className="flex items-center gap-1">
                          ⭐ {currentStory.user_progress.perfect_chapters_count} perfect
                        </span>
                      )}
                    </div>
                  </div>
                )}

                {/* Continue Button */}
                <Link
                  href={`/stories/${currentStory.story.id}`}
                  className="mt-3 inline-block"
                >
                  <Button size="sm" className="w-full sm:w-auto">
                    Continue Story
                  </Button>
                </Link>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Quick Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Quick Actions</CardTitle>
            <CardDescription>Jump into your learning journey</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Link href="/learn/new" className="block">
              <Button variant="outline" className="w-full justify-start">
                <MessageCircle className="mr-2 h-4 w-4" />
                Start Conversation
              </Button>
            </Link>
            <Link href="/stories" className="block">
              <Button variant="outline" className="w-full justify-start">
                <Book className="mr-2 h-4 w-4" />
                Browse Stories
              </Button>
            </Link>
            <Link href="/practice" className="block">
              <Button variant="outline" className="w-full justify-start">
                <BookOpen className="mr-2 h-4 w-4" />
                Practice Vocabulary
              </Button>
            </Link>
            <Link href="/progress" className="block">
              <Button variant="outline" className="w-full justify-start">
                <TrendingUp className="mr-2 h-4 w-4" />
                View Progress
              </Button>
            </Link>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recent Sessions</CardTitle>
            <CardDescription>Your latest learning activities</CardDescription>
          </CardHeader>
          <CardContent>
            {recentSessions?.length > 0 ? (
              <div className="space-y-3">
                {recentSessions.slice(0, 3).map((session: any) => (
                  <div key={session.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <div>
                      <p className="text-sm font-medium">{session.topic || 'General Conversation'}</p>
                      <p className="text-xs text-gray-500">
                        {new Date(session.created_at).toLocaleDateString()}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-semibold text-primary-600">{session.xp_awarded || 0} XP</p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-500 text-center py-4">
                No sessions yet. Start your first conversation!
              </p>
            )}
          </CardContent>
        </Card>
      </div>
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

  try {
    const baseUrl = process.env.API_URL || 'http://localhost:8000';
    const headers = {
      'Authorization': `Bearer ${session.accessToken}`,
      'Content-Type': 'application/json',
    };

    // Fetch dashboard data
    const [summaryRes, sessionsRes] = await Promise.allSettled([
      fetch(`${baseUrl}/api/v1/analytics/summary`, { headers }),
      fetch(`${baseUrl}/api/v1/sessions?limit=5`, { headers }),
    ]);

    const summary = summaryRes.status === 'fulfilled' && summaryRes.value.ok 
      ? await summaryRes.value.json() 
      : { total_xp: 0, current_streak: 0, words_mastered: 0, sessions_completed: 0 };

    const recentSessions = sessionsRes.status === 'fulfilled' && sessionsRes.value.ok 
      ? await sessionsRes.value.json() 
      : [];

    return {
      props: {
        summary,
        recentSessions,
      },
    };
  } catch (error) {
    console.error('Failed to fetch dashboard data:', error);
    return {
      props: {
        summary: { total_xp: 0, current_streak: 0, words_mastered: 0, sessions_completed: 0 },
        recentSessions: [],
      },
    };
  }
}