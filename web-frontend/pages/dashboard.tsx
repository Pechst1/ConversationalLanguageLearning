import React from 'react';
import { getSession } from 'next-auth/react';
import Link from 'next/link';
import { BookOpen, MessageCircle, TrendingUp, Trophy, Plus, Clock, Globe } from 'lucide-react';
import { useState } from 'react';
import { ImportStoryModal } from '@/components/stories/ImportStoryModal';
import { Button } from '@/components/ui/Button';
import apiService from '@/services/api';
import InsightsCard from '@/components/learning/InsightsCard';

// Safe date formatting helper
function formatDate(dateString: string | undefined | null): string {
  if (!dateString) return 'No date';
  const date = new Date(dateString);
  if (isNaN(date.getTime())) return 'No date';
  return date.toLocaleDateString();
}

interface DashboardProps {
  summary: {
    total_xp: number;
    current_streak: number;
    words_mastered: number;
    sessions_completed: number;
  };
  recentSessions: any[];
}

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';

export default function Dashboard({ summary, recentSessions }: DashboardProps) {
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const quickStats = [
    {
      name: 'Total XP',
      value: summary?.total_xp || 0,
      icon: TrendingUp,
      color: 'text-black',
      bgColor: 'bg-bauhaus-blue',
      borderColor: 'border-black'
    },
    {
      name: 'Current Streak',
      value: `${summary?.current_streak || 0} days`,
      icon: Trophy,
      color: 'text-black',
      bgColor: 'bg-bauhaus-yellow',
      borderColor: 'border-black'
    },
    {
      name: 'Words Mastered',
      value: summary?.words_mastered || 0,
      icon: BookOpen,
      color: 'text-white',
      bgColor: 'bg-green-600',
      borderColor: 'border-black'
    },
    {
      name: 'Sessions Completed',
      value: summary?.sessions_completed || 0,
      icon: MessageCircle,
      color: 'text-white',
      bgColor: 'bg-bauhaus-red',
      borderColor: 'border-black'
    },
  ];

  return (
    <div className="space-y-8 p-4">
      <div className="flex items-center justify-between border-b-4 border-black pb-6 bg-white p-4 shadow-[4px_4px_0px_0px_#000]">
        <div>
          <h1 className="text-4xl font-extrabold text-black uppercase tracking-tight">Dashboard</h1>
          <p className="text-gray-600 font-bold mt-1">Welcome back! Ready to continue learning?</p>
        </div>
        <Link href="/learn/new">
          <Button leftIcon={<Plus className="h-5 w-5" />} className="shadow-[4px_4px_0px_0px_#000] border-2 border-black">
            Start New Session
          </Button>
        </Link>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {quickStats.map((stat) => (
          <Card key={stat.name} className={`border-4 border-black shadow-[8px_8px_0px_0px_#000] hover:translate-y-[-4px] transition-transform`}>
            <CardContent className="p-6">
              <div className="flex items-center">
                <div className={`p-3 border-2 border-black shadow-[2px_2px_0px_0px_#000] ${stat.bgColor}`}>
                  <stat.icon className={`h-6 w-6 ${stat.color}`} />
                </div>
                <div className="ml-4">
                  <p className="text-sm font-bold text-gray-600 uppercase tracking-widest">{stat.name}</p>
                  <p className="text-3xl font-black text-black">{stat.value}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <Card className="border-4 border-black shadow-[8px_8px_0px_0px_#000]">
          <CardHeader className="bg-bauhaus-yellow border-b-4 border-black p-4">
            <CardTitle className="text-2xl font-black uppercase">Quick Actions</CardTitle>
            <CardDescription className="text-black font-bold">Jump into your learning journey</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 p-6">
            <Link href="/learn/new" className="block group">
              <Button variant="outline" className="w-full justify-start text-lg h-14 border-2 border-black shadow-[4px_4px_0px_0px_#000] group-hover:bg-bauhaus-blue group-hover:text-white transition-all">
                <MessageCircle className="mr-3 h-5 w-5" />
                Start Conversation
              </Button>
            </Link>
            <Link href="/practice" className="block group">
              <Button variant="outline" className="w-full justify-start text-lg h-14 border-2 border-black shadow-[4px_4px_0px_0px_#000] group-hover:bg-bauhaus-yellow group-hover:text-black transition-all">
                <BookOpen className="mr-3 h-5 w-5" />
                Practice Vocabulary
              </Button>
            </Link>
            <Link href="/audio-session" className="block group">
              <Button variant="outline" className="w-full justify-start text-lg h-14 border-2 border-black shadow-[4px_4px_0px_0px_#000] group-hover:bg-purple-600 group-hover:text-white transition-all">
                <Clock className="mr-3 h-5 w-5" />
                Quick Audio Session (5 min)
              </Button>
            </Link>

            <Link href="/progress" className="block group">
              <Button variant="outline" className="w-full justify-start text-lg h-14 border-2 border-black shadow-[4px_4px_0px_0px_#000] group-hover:bg-bauhaus-red group-hover:text-white transition-all">
                <TrendingUp className="mr-3 h-5 w-5" />
                View Progress
              </Button>
            </Link>

            <Button
              onClick={() => setIsImportModalOpen(true)}
              variant="outline"
              className="w-full justify-start text-lg h-14 border-2 border-black shadow-[4px_4px_0px_0px_#000] hover:bg-green-600 hover:text-white transition-all"
            >
              <Globe className="mr-3 h-5 w-5" />
              Import Web Content
            </Button>
          </CardContent>
        </Card>

        <Card className="border-4 border-black shadow-[8px_8px_0px_0px_#000]">
          <CardHeader className="bg-bauhaus-blue border-b-4 border-black p-4">
            <CardTitle className="text-2xl font-black uppercase text-white">Recent Sessions</CardTitle>
            <CardDescription className="text-white font-bold opacity-90">Your latest learning activities</CardDescription>
          </CardHeader>
          <CardContent className="p-6">
            {recentSessions?.length > 0 ? (
              <div className="space-y-4">
                {recentSessions.slice(0, 3).map((session: any) => (
                  <div key={session.id} className="flex items-center justify-between p-4 bg-white border-2 border-black shadow-[4px_4px_0px_0px_#000] hover:translate-x-1 transition-transform">
                    <div>
                      <p className="text-lg font-bold text-black">{session.topic || 'General Conversation'}</p>
                      <p className="text-xs font-bold text-gray-500 uppercase">
                        {formatDate(session.created_at)}
                      </p>
                    </div>
                    <div className="text-right">
                      <span className="inline-block px-3 py-1 bg-bauhaus-yellow border-2 border-black font-black text-sm shadow-[2px_2px_0px_0px_#000]">
                        {session.xp_awarded || 0} XP
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 border-2 border-dashed border-gray-300">
                <p className="text-lg font-bold text-gray-500">
                  No sessions yet. Start your first conversation!
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* AI Insights Section */}
      <div className="mt-8">
        <InsightsCard />
      </div>

      {isImportModalOpen && (
        <ImportStoryModal onClose={() => setIsImportModalOpen(false)} />
      )}
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