import { NextAuthOptions } from 'next-auth';
import CredentialsProvider from 'next-auth/providers/credentials';
import { JWT } from 'next-auth/jwt';

import { requireApiHost } from '@/lib/api-host';

interface User {
  id: string;
  email: string;
  name: string;
  access_token: string;
  refresh_token: string;
}

interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

function apiBaseUrl() {
  // No fallback: see lib/api-host.ts. These calls carry the learner's email,
  // password and tokens, so a guessed host is a credential-disclosure risk.
  return requireApiHost('authentication');
}

function getJwtExpiry(token?: string): number {
  if (!token) return 0;

  try {
    const [, payload] = token.split('.');
    const decoded = JSON.parse(Buffer.from(payload, 'base64url').toString('utf8'));
    return typeof decoded.exp === 'number' ? decoded.exp * 1000 : 0;
  } catch {
    return 0;
  }
}

type RefreshOutcome =
  | { status: 'refreshed'; data: TokenResponse }
  | { status: 'rejected' }
  | { status: 'unreachable' };

/**
 * One refresh per refresh token in this server process (WP-71).
 *
 * Parallel `/api/auth/session` calls each run the jwt callback with the same
 * cookie, so an expired access token used to fire several refreshes with one
 * rotating refresh token. They now share one request; across processes the
 * backend's grace window hands late racers the same successor.
 */
const refreshesInFlight = new Map<string, Promise<RefreshOutcome>>();

async function requestRefresh(refreshToken: string): Promise<RefreshOutcome> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        refresh_token: refreshToken,
      }),
    });
  } catch {
    return { status: 'unreachable' };
  }
  // Only the server refusing the token ends the session; a 5xx or a proxy
  // hiccup is not a verdict on it.
  if (response.status === 401 || response.status === 403) return { status: 'rejected' };
  if (!response.ok) return { status: 'unreachable' };
  try {
    return { status: 'refreshed', data: await response.json() as TokenResponse };
  } catch {
    return { status: 'unreachable' };
  }
}

function sharedRefresh(refreshToken: string): Promise<RefreshOutcome> {
  let pending = refreshesInFlight.get(refreshToken);
  if (!pending) {
    pending = requestRefresh(refreshToken).finally(() => {
      refreshesInFlight.delete(refreshToken);
    });
    refreshesInFlight.set(refreshToken, pending);
  }
  return pending;
}

async function refreshAccessToken(token: JWT): Promise<JWT> {
  if (!token.refreshToken) {
    return { ...token, error: 'RefreshAccessTokenError' };
  }

  const outcome = await sharedRefresh(String(token.refreshToken));
  if (outcome.status === 'rejected') {
    return { ...token, error: 'RefreshAccessTokenError' };
  }
  if (outcome.status === 'unreachable') {
    // Keep the session; the next session read tries again.
    return { ...token, error: undefined };
  }
  const { data } = outcome;
  return {
    ...token,
    accessToken: data.access_token,
    refreshToken: data.refresh_token || token.refreshToken,
    accessTokenExpires: getJwtExpiry(data.access_token),
    error: undefined,
  };
}

export const authOptions: NextAuthOptions = {
  providers: [
    CredentialsProvider({
      name: 'credentials',
      credentials: {
        email: { label: 'Email', type: 'email' },
        password: { label: 'Password', type: 'password' },
      },
      async authorize(credentials): Promise<User | null> {
        if (!credentials?.email || !credentials?.password) {
          return null;
        }

        try {
          const response = await fetch(`${apiBaseUrl()}/api/v1/auth/login`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              email: credentials.email,
              password: credentials.password,
            }),
          });

          if (!response.ok) {
            return null;
          }

          const data = await response.json();

          // Fetch user profile
          const userResponse = await fetch(`${apiBaseUrl()}/api/v1/users/me`, {
            headers: {
              'Authorization': `Bearer ${data.access_token}`,
            },
          });

          if (!userResponse.ok) {
            return null;
          }

          const userData = await userResponse.json();

          return {
            id: userData.id,
            email: userData.email,
            name: userData.full_name || userData.email,
            access_token: data.access_token,
            refresh_token: data.refresh_token,
          };
        } catch (error) {
          console.error('Authentication error:', error);
          return null;
        }
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.accessToken = user.access_token;
        token.refreshToken = user.refresh_token;
        token.accessTokenExpires = getJwtExpiry(user.access_token);
        token.id = user.id;
        token.error = undefined;
        return token;
      }

      if (token.accessToken && token.accessTokenExpires && Date.now() < token.accessTokenExpires - 30_000) {
        return token;
      }

      return refreshAccessToken(token);
    },
    async session({ session, token }) {
      if (token) {
        session.user.id = token.id as string;
        session.accessToken = token.accessToken as string;
        session.refreshToken = token.refreshToken as string;
        session.error = token.error;
      }
      return session;
    },
  },
  events: {
    async signOut({ token }) {
      if (!token?.refreshToken) return;

      try {
        await fetch(`${apiBaseUrl()}/api/v1/auth/logout`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            refresh_token: token.refreshToken,
          }),
        });
      } catch {
        // The local session should still be cleared even if backend revocation fails.
      }
    },
  },
  pages: {
    signIn: '/auth/signin',
  },
  session: {
    strategy: 'jwt',
  },
  secret: process.env.NEXTAUTH_SECRET,
};
