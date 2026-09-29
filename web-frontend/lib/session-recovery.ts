/** WP-107: concurrent 401s share one session read; each request replays once. */
type Session = { accessToken?: string | null; error?: string } | null;

export function webSessionRecovery(readSession: () => Promise<Session>) {
  let pending: Promise<string | null> | null = null;
  return () => {
    if (!pending) {
      pending = readSession()
        .then((session) => session?.error ? null : session?.accessToken || null)
        .catch(() => null)
        .finally(() => { pending = null; });
    }
    return pending;
  };
}

export const SESSION_EXPIRED_EVENT = 'atelier:session-expired';

/** Remove the unusable web cookie before opening sign-in, so the guest gate
 * cannot send a still-authenticated session straight back to this screen. */
export async function reconnectWebSession(callbackUrl: string) {
  const { signOut } = await import('next-auth/react');
  await signOut({ callbackUrl: `/auth/signin?callbackUrl=${encodeURIComponent(callbackUrl)}` });
}

export const sessionExpiredCopy = {
  fr: { message: 'Votre session a expiré — reconnectez-vous.', action: 'Se reconnecter' },
  en: { message: 'Your session has expired — sign in again.', action: 'Sign in again' },
  de: { message: 'Deine Sitzung ist abgelaufen — melde dich erneut an.', action: 'Erneut anmelden' },
};
