import React from 'react';
import { getSession } from 'next-auth/react';
import Link from 'next/link';
import { BookOpen, MessageCircle, TrendingUp, Trophy, Plus } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';
import apiService from '@/services/api';

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