import React from 'react';
import { getSession } from 'next-auth/react';
import api from '@/services/api';

export default function ProgressPage({ summary, statistics, streak, vocabulary }: any) {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Dein Fortschritt</h1>
      <pre className="learning-card overflow-auto p-4">{JSON.stringify({ summary, statistics, streak, vocabulary }, null, 2)}</pre>
    </div>
  );
}

export async function getServerSideProps(ctx: any) {
  const session = await getSession(ctx);
  if (!session) return { redirect: { destination: '/auth/signin', permanent: false } };

  const headers = { Authorization: `Bearer ${session.accessToken}` } as any;
  const base = process.env.API_URL || 'http://localhost:8000/api/v1';

  const [summary, statistics, streak, vocabulary] = await Promise.all([
    fetch(`${base}/analytics/summary`, { headers }).then((r) => r.json()),
    fetch(`${base}/analytics/statistics`, { headers }).then((r) => r.json()),
    fetch(`${base}/analytics/streak`, { headers }).then((r) => r.json()),
    fetch(`${base}/analytics/vocabulary`, { headers }).then((r) => r.json()),
  ]);

  return { props: { summary, statistics, streak, vocabulary } };
}
