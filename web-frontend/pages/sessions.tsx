import React from 'react';
import { getSession } from 'next-auth/react';
import Link from 'next/link';
import { MessageCircle, Clock, Trophy } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';
import { formatDateTime } from '@/lib/utils';

interface SessionsProps {
  sessions: {
    id: string;
    topic: string;
    created_at: string;
    completed_at?: string;
    xp_awarded: number;
    message_count: number;
    status: 'active' | 'completed';
  }[];
}

export default function SessionsPage({ sessions }: SessionsProps) {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Learning Sessions</h1>
          <p className="text-gray-600">View your conversation history and progress</p>
        </div>
        <Link href="/learn/new">
          <Button>
            New Session
          </Button>
        </Link>
      </div>

      {sessions?.length > 0 ? (
        <div className="grid gap-6">
          {sessions.map((session) => (
            <Card key={session.id} className="hover:shadow-md transition-shadow">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center space-x-2">
                      <MessageCircle className="h-5 w-5" />
                      <span>{session.topic || 'General Conversation'}</span>
                    </CardTitle>
                    <CardDescription>
                      Started {formatDateTime(session.created_at)}
                      {session.completed_at && ` • Completed ${formatDateTime(session.completed_at)}`}
                    </CardDescription>
                  </div>
                  <div className="flex items-center space-x-4 text-right">
                    <div className="flex items-center text-sm text-gray-600">
                      <Clock className="h-4 w-4 mr-1" />
                      {session.message_count} messages
                    </div>
                    <div className="flex items-center text-sm font-semibold text-primary-600">
                      <Trophy className="h-4 w-4 mr-1" />
                      {session.xp_awarded} XP
                    </div>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      session.status === 'completed' 
                        ? 'bg-green-100 text-green-800' 
                        : 'bg-blue-100 text-blue-800'
                    }`}>
                      {session.status === 'completed' ? 'Completed' : 'Active'}
                    </span>
                  </div>
                  <div className="flex space-x-2">
                    <Link href={`/learn/session/${session.id}`}>
                      <Button variant="outline" size="sm">
                        {session.status === 'completed' ? 'View' : 'Continue'}
                      </Button>
                    </Link>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className="text-center py-12">
            <MessageCircle className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">No sessions yet</h3>
            <p className="text-gray-600 mb-6">
              Start your first conversation to begin learning French!
            </p>
            <Link href="/learn/new">
              <Button>
                Create First Session
              </Button>
            </Link>
          </CardContent>
        </Card>
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

    const response = await fetch(`${baseUrl}/api/v1/sessions?limit=20`, { headers });
    const sessions = response.ok ? await response.json() : [];

    return {
      props: {
        sessions,
      },
    };
  } catch (error) {
    console.error('Failed to fetch sessions:', error);
    return {
      props: {
        sessions: [],
      },
    };
  }
}