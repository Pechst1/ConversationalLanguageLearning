import { useEffect } from 'react';
import { useRouter } from 'next/router';

import SerialEpisodeReplayPage from './episode/[index]';

function queryIndex(rawIndex: string | string[] | undefined): string | null {
  const direct = Array.isArray(rawIndex) ? rawIndex[0] : rawIndex;
  const browserValue = typeof window === 'undefined'
    ? null
    : new URLSearchParams(window.location.search).get('index');
  const value = String(direct ?? browserValue ?? '').trim();
  return /^\d+$/.test(value) ? value : null;
}

export default function SerialEpisodeQueryAliasPage() {
  const router = useRouter();

  useEffect(() => {
    if (!router.isReady) return;
    const index = queryIndex(router.query.index);
    if (index) {
      void router.replace(`/serial/episode/${index}`);
    }
  }, [router]);

  return <SerialEpisodeReplayPage />;
}
