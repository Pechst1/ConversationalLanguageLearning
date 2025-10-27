import NextAuth from 'next-auth';

declare module 'next-auth' {
  interface Session {
    accessToken?: string;
    refreshToken?: string;
    user: {
      id: string;
      email: string;
      name: string;
    };
  }

  interface User {
    id: string;
    email: string;
    name: string;
    access_token: string;
    refresh_token: string;
  }
}

declare module 'next-auth/jwt' {
  interface JWT {
    accessToken?: string;
    refreshToken?: string;
    id?: string;
  }
}