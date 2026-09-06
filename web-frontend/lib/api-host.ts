/**
 * The backend host for server-side calls that carry a learner's credentials.
 *
 * This used to default to `http://localhost:8000`. On a developer machine that
 * port frequently belongs to a *different* application, so a bare `npm run dev`
 * would POST an email and password to whatever happened to be listening. The
 * value is now required: an unset `API_URL` is a configuration error, not
 * something to guess.
 *
 * Deliberately throws at CALL time, never at module load, so `next build` — which
 * compiles these modules but never invokes them — is unaffected. CI builds
 * without `API_URL` and must keep working.
 */
export function requireApiHost(context: string): string {
  const configured = (process.env.API_URL || '').trim();
  if (!configured) {
    throw new Error(
      `API_URL is not set, so ${context} has no backend to talk to. Set it to the ` +
        'API origin (for example http://localhost:8010) before starting the app. ' +
        'It is deliberately not defaulted: guessing a port risks sending ' +
        'credentials to an unrelated service.',
    );
  }
  return configured.replace(/\/+$/, '');
}
