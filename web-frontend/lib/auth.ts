import { NextAuthOptions } from 'next-auth';
import CredentialsProvider from 'next-auth/providers/credentials';
import { JWT } from 'next-auth/jwt';

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
  return process.env.API_URL || 'http://localhost:8000';
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

async function refreshAccessToken(token: JWT): Promise<JWT> {
  if (!token.refreshToken) {
    return { ...token, error: 'RefreshAccessTokenError' };
  }

  try {
    const response = await fetch(`${apiBaseUrl()}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        refresh_token: token.refreshToken,
      }),
    });

    if (!response.ok) {
      throw new Error('Refresh token rejected');
    }

    const data = await response.json() as TokenResponse;
    return {
      ...token,
      accessToken: data.access_token,
      refreshToken: data.refresh_token || token.refreshToken,
      accessTokenExpires: getJwtExpiry(data.access_token),
      error: undefined,
    };
  } catch {
    return {
      ...token,
      error: 'RefreshAccessTokenError',
    };
  }
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
