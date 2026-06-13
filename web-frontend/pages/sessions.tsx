import React from 'react';
import Link from 'next/link';
import { MessageCircle, Clock, Trophy } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';
import { formatDateTime } from '@/lib/utils';
import apiService from '@/services/api';

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

function mapSessionItem(item: any): SessionsProps['sessions'][number] {
  return {
    id: item.id,
    topic: item.topic || 'General Conversation',
    created_at: item.started_at || item.created_at || new Date().toISOString(),
    completed_at: item.completed_at || null,
    xp_awarded: item.xp_earned || item.xp_awarded || 0,
    message_count: item.words_practiced || item.message_count || 0,
    status: item.status === 'completed' ? 'completed' : 'active',
  };
}

export default function SessionsPage({ sessions = [] }: SessionsProps) {
  const [sessionList, setSessionList] = React.useState(sessions);

  React.useEffect(() => {
    let cancelled = false;
    apiService.getSessions({ limit: 20 })
      .then((rows) => {
        if (!cancelled) {
          setSessionList(Array.isArray(rows) ? rows.map(mapSessionItem) : []);
        }
      })
      .catch((error) => {
        console.error('Failed to fetch sessions:', error);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="space-y-6">
      <div className="mb-8 border-b border-[var(--app-ink)] pb-5">
        <div className="text-xs font-black uppercase tracking-[0.16em] text-[var(--app-ink-3)]">
          History
        </div>
        <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4 mt-1">
          <h1 className="font-serif text-5xl italic leading-none text-[var(--app-ink)]">
            Sessions
          </h1>
          <div>
            <Link href="/learn/new">
              <button className="border border-black px-4 py-2 text-xs font-black uppercase tracking-[0.13em] transition-all bg-[var(--app-sheet)] text-[var(--app-ink)] hover:bg-[var(--app-paper-2)]">
                New Session
              </button>
            </Link>
          </div>
        </div>
        <p className="mt-3 max-w-2xl text-[var(--app-ink-2)]">
          View your conversation history, progress tracking, and achievements.
        </p>
      </div>

      {sessionList?.length > 0 ? (
        <div className="grid gap-6">
          {sessionList.map((session) => (
            <div
              key={session.id}
              className="border-4 border-black bg-white p-6 shadow-[6px_6px_0px_0px_#000] hover:-translate-y-1 hover:shadow-[8px_8px_0px_0px_#000] transition-all"
            >
              <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4 border-b-2 border-black pb-4 mb-4">
                <div>
                  <h3 className="text-xl font-black uppercase tracking-tight flex items-center gap-2">
                    <MessageCircle className="h-5 w-5" />
                    <span>{session.topic || 'General Conversation'}</span>
                  </h3>
                  <p className="text-xs text-gray-500 font-bold mt-1 uppercase tracking-wider">
                    Started {formatDateTime(session.created_at)}
                    {session.completed_at && ` • Completed ${formatDateTime(session.completed_at)}`}
                  </p>
                </div>
                <div className="flex items-center gap-4 text-sm font-bold uppercase">
                  <span className="flex items-center text-gray-600">
                    <Clock className="h-4 w-4 mr-1 text-black" />
                    {session.message_count} messages
                  </span>
                  <span className="flex items-center text-purple-600">
                    <Trophy className="h-4 w-4 mr-1 text-purple-600" />
                    {session.xp_awarded} XP
                  </span>
                </div>
              </div>

              <div className="flex items-center justify-between">
                <span className={`px-2.5 py-1 border-2 border-black text-xs font-black uppercase tracking-wider shadow-[2px_2px_0px_0px_#000] ${
                  session.status === 'completed'
                    ? 'bg-bauhaus-yellow text-black'
                    : 'bg-bauhaus-blue text-white'
                }`}>
                  {session.status === 'completed' ? 'Completed' : 'Active'}
                </span>

                <Link href={`/learn/session/${session.id}`}>
                  <button className={`border-2 border-black px-4 py-2 text-xs font-black uppercase tracking-[0.13em] transition-all shadow-[3px_3px_0px_0px_#000] hover:-translate-y-0.5 hover:shadow-[4px_4px_0px_0px_#000] active:translate-y-0 active:shadow-[1px_1px_0px_0px_#000] ${
                    session.status === 'completed'
                      ? 'bg-white text-black hover:bg-gray-100'
                      : 'bg-bauhaus-red text-white hover:bg-red-700'
                  }`}>
                    {session.status === 'completed' ? 'View' : 'Continue'}
                  </button>
                </Link>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="border-4 border-black bg-white p-12 shadow-[8px_8px_0px_0px_#000] text-center">
          <MessageCircle className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-2xl font-black uppercase mb-2">No sessions yet</h3>
          <p className="text-gray-600 font-bold mb-8">
            Start your first conversation to begin learning French!
          </p>
          <Link href="/learn/new">
            <button className="border-4 border-black bg-bauhaus-blue text-white font-black text-lg px-8 py-4 uppercase tracking-widest hover:-translate-y-1 hover:shadow-[6px_6px_0px_0px_#000] transition-all">
              Create First Session
            </button>
          </Link>
        </div>
      )}
    </div>
  );
}
