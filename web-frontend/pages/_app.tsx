import Head from 'next/head';
import type { AppProps } from 'next/app';
import { useEffect } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import RouteAuthGate from '@/components/auth/RouteAuthGate';
import Layout from '@/components/layout/Layout';
import { AppAuthProvider } from '@/lib/app-auth';
import '@/styles/globals.css';

// Create a client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 3,
      staleTime: 5 * 60 * 1000, // 5 minutes
      refetchOnWindowFocus: false,
    },
  },
});

export default function App({
  Component,
  pageProps: { session, ...pageProps },
}: AppProps) {
  useEffect(() => {
    document.querySelectorAll('[data-next-hide-fouc]').forEach((element) => element.remove());
  }, []);

  return (
    <AppAuthProvider session={session}>
      <QueryClientProvider client={queryClient}>
        <Head>
          <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
          <meta name="theme-color" content="#f1ece1" />
          <meta name="apple-mobile-web-app-capable" content="yes" />
          <meta name="apple-mobile-web-app-title" content="Atelier" />
          <meta name="apple-mobile-web-app-status-bar-style" content="default" />
          <link rel="manifest" href="/manifest.webmanifest" />
          <link rel="apple-touch-icon" href="/icons/atelier-mark.svg" />
        </Head>
        <Layout>
          <RouteAuthGate>
            <Component {...pageProps} />
          </RouteAuthGate>
        </Layout>
      </QueryClientProvider>
    </AppAuthProvider>
  );
}
