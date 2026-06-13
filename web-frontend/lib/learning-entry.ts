import apiService from '@/services/api';

type AuthenticatedSession = {
  accessToken?: string | null;
};

type SessionOverview = {
  id?: string;
  status?: string | null;
};

const ACTIVE_SESSION_STATUSES = new Set(['created', 'in_progress', 'paused']);

const getApiBaseUrl = () => {
  return process.env.API_URL || 'http://localhost:8000';
};

const buildAuthHeaders = (accessToken: string) => {
  return {
    Authorization: `Bearer ${accessToken}`,
    'Content-Type': 'application/json',
  };
};

export async function resolveLearningEntryDestination(
  session: AuthenticatedSession | null,
): Promise<string> {
  const accessToken = session?.accessToken;
  if (!accessToken) {
    return '/auth/signin';
  }

  if (typeof window !== 'undefined') {
    try {
      const sessions = await apiService.getSessions({ limit: 10 });
      const activeSession = Array.isArray(sessions)
        ? sessions.find(
            (item) => item?.id && ACTIVE_SESSION_STATUSES.has(item.status || ''),
          )
        : null;

      if (activeSession?.id) {
        return `/learn/session/${activeSession.id}`;
      }
    } catch (error) {
      console.error('Failed to resolve existing learning session:', error);
    }

    try {
      const payload = await apiService.quickStartSession();
      if (payload?.session?.id) {
        return `/learn/session/${payload.session.id}`;
      }
    } catch (error) {
      console.error('Failed to create quick-start learning session:', error);
    }

    return '/learn/new';
  }

  const baseUrl = getApiBaseUrl();
  const headers = buildAuthHeaders(accessToken);

  try {
    const sessionsResponse = await fetch(`${baseUrl}/api/v1/sessions?limit=10`, {
      headers,
    });

    if (sessionsResponse.ok) {
      const sessions = (await sessionsResponse.json()) as SessionOverview[];
      const activeSession = Array.isArray(sessions)
        ? sessions.find(
            (item) => item?.id && ACTIVE_SESSION_STATUSES.has(item.status || ''),
          )
        : null;

      if (activeSession?.id) {
        return `/learn/session/${activeSession.id}`;
      }
    }
  } catch (error) {
    console.error('Failed to resolve existing learning session:', error);
  }

  try {
    const quickStartResponse = await fetch(`${baseUrl}/api/v1/sessions/quick-start`, {
      method: 'POST',
      headers,
      body: JSON.stringify({}),
    });

    if (quickStartResponse.ok) {
      const payload = (await quickStartResponse.json()) as {
        session?: { id?: string };
      };
      if (payload?.session?.id) {
        return `/learn/session/${payload.session.id}`;
      }
    }
  } catch (error) {
    console.error('Failed to create quick-start learning session:', error);
  }

  return '/learn/new';
}
