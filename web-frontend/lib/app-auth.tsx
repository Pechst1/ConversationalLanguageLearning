import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { SessionProvider, signIn, signOut, useSession, getSession } from 'next-auth/react';

import { isNativePlatform } from '@/lib/native-platform';
import {
  loadNativeAuthSession,
  nativeLogout,
  nativeSignInWithCredentials,
  getNativeAccessToken,
  type NativeAuthSession,
} from '@/lib/native-auth';

type AppAuthStatus = 'loading' | 'authenticated' | 'unauthenticated';
type AppSession = {
  user?: {
    id?: string;
    email?: string | null;
    name?: string | null;
  };
  accessToken?: string | null;
  refreshToken?: string | null;
  error?: string;
} | null;

type SignInResult = {
  ok: boolean;
  error?: string | null;
  url?: string | null;
};

type AppAuthContextValue = {
  data: AppSession;
  status: AppAuthStatus;
  isNative: boolean;
  refresh: () => Promise<AppSession>;
  signInWithCredentials: (email: string, password: string) => Promise<SignInResult>;
  signOut: (options?: { callbackUrl?: string }) => Promise<void>;
};

const AppAuthContext = createContext<AppAuthContextValue | null>(null);

function nativeSessionToAppSession(session: NativeAuthSession | null): AppSession {
  if (!session) return null;
  return {
    user: session.user,
    accessToken: session.accessToken,
    refreshToken: session.refreshToken,
  };
}

function NativeAuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<AppSession>(null);
  const [status, setStatus] = useState<AppAuthStatus>('loading');

  const refresh = useCallback(async () => {
    setStatus('loading');
    const restored = nativeSessionToAppSession(await loadNativeAuthSession());
    setSession(restored);
    setStatus(restored ? 'authenticated' : 'unauthenticated');
    return restored;
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const value = useMemo<AppAuthContextValue>(() => ({
    data: session,
    status,
    isNative: true,
    refresh,
    signInWithCredentials: async (email, password) => {
      try {
        const nextSession = nativeSessionToAppSession(await nativeSignInWithCredentials(email, password));
        setSession(nextSession);
        setStatus('authenticated');
        return { ok: true };
      } catch (error) {
        setSession(null);
        setStatus('unauthenticated');
        return { ok: false, error: error instanceof Error ? error.message : 'Sign in failed.' };
      }
    },
    signOut: async (options) => {
      await nativeLogout();
      setSession(null);
      setStatus('unauthenticated');
      if (options?.callbackUrl && typeof window !== 'undefined') {
        window.location.assign(options.callbackUrl);
      }
    },
  }), [refresh, session, status]);

  return <AppAuthContext.Provider value={value}>{children}</AppAuthContext.Provider>;
}

function WebAuthBridge({ children }: { children: React.ReactNode }) {
  const nextSession = useSession();
  const value = useMemo<AppAuthContextValue>(() => ({
    data: nextSession.data as AppSession,
    status: nextSession.status,
    isNative: false,
    refresh: async () => {
      const updated = await nextSession.update();
      return updated as AppSession;
    },
    signInWithCredentials: async (email, password) => {
      const result = await signIn('credentials', {
        email,
        password,
        redirect: false,
      });
      if (!result?.error) {
        await nextSession.update();
      }
      return {
        ok: !result?.error,
        error: result?.error,
        url: result?.url,
      };
    },
    signOut: async (options) => {
      await signOut({ callbackUrl: options?.callbackUrl });
    },
  }), [nextSession]);

  return <AppAuthContext.Provider value={value}>{children}</AppAuthContext.Provider>;
}

function WebAuthProvider({
  children,
  session,
}: {
  children: React.ReactNode;
  session?: any;
}) {
  return (
    <SessionProvider session={session}>
      <WebAuthBridge>{children}</WebAuthBridge>
    </SessionProvider>
  );
}

export function AppAuthProvider({
  children,
  session,
}: {
  children: React.ReactNode;
  session?: any;
}) {
  const [native] = useState(() => isNativePlatform());
  return native ? (
    <NativeAuthProvider>{children}</NativeAuthProvider>
  ) : (
    <WebAuthProvider session={session}>{children}</WebAuthProvider>
  );
}

export function useAppSession() {
  const value = useContext(AppAuthContext);
  if (!value) {
    throw new Error('useAppSession must be used within AppAuthProvider.');
  }
  return {
    data: value.data,
    status: value.status,
    isNative: value.isNative,
  };
}

export function useAppAuth() {
  const value = useContext(AppAuthContext);
  if (!value) {
    throw new Error('useAppAuth must be used within AppAuthProvider.');
  }
  return value;
}

export async function getAppAccessToken() {
  if (isNativePlatform()) {
    return getNativeAccessToken();
  }
  const session = await getSession();
  return (session as AppSession)?.accessToken || null;
}

export async function appSignOut(options?: { callbackUrl?: string }) {
  if (isNativePlatform()) {
    await nativeLogout();
    if (options?.callbackUrl && typeof window !== 'undefined') {
      window.location.assign(options.callbackUrl);
    }
    return;
  }
  await signOut({ callbackUrl: options?.callbackUrl });
}
