import { FormEvent, useMemo, useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { ArrowLeft, KeyRound, Mail } from 'lucide-react';

import { sanitizeAuthCallbackUrl } from '@/lib/app-auth';
import apiService from '@/services/api';

export default function ForgotPasswordPage() {
  const router = useRouter();
  const token = useMemo(() => {
    const value = router.query.token;
    return typeof value === 'string' ? value : '';
  }, [router.query.token]);
  const supportEmail = process.env.NEXT_PUBLIC_SUPPORT_EMAIL?.trim();
  const supportSubject = encodeURIComponent('Atelier password help');
  const [email, setEmail] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [devResetUrl, setDevResetUrl] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const resetMode = Boolean(token);
  const destination = sanitizeAuthCallbackUrl(router.query.callbackUrl);
  const callbackQuery = destination === '/atelier' ? {} : { callbackUrl: destination };
  const signInHref = { pathname: '/auth/signin', query: callbackQuery };

  const requestReset = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    setMessage('');
    setDevResetUrl('');
    if (!email.trim()) {
      setError('Enter the email address for your account.');
      return;
    }
    setIsSubmitting(true);
    try {
      const response = await apiService.requestPasswordReset({ email: email.trim() });
      setMessage(response.message);
      setDevResetUrl(response.reset_url || '');
    } catch {
      setError('We could not start the reset flow. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const confirmReset = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    setMessage('');
    if (newPassword.length < 8) {
      setError('Use at least 8 characters for the new password.');
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('The passwords do not match.');
      return;
    }
    setIsSubmitting(true);
    try {
      await apiService.confirmPasswordReset({ token, new_password: newPassword });
      setMessage('Your password has been reset. You can sign in now.');
      setNewPassword('');
      setConfirmPassword('');
    } catch {
      setError('That reset link is invalid or expired. Request a fresh link.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <Head>
        <title>Password help - Atelier</title>
      </Head>

      <main className="auth-page">
        <section className="auth-card" aria-labelledby="password-help-title">
          <Link className="auth-back" href={signInHref}>
            <ArrowLeft size={15} aria-hidden="true" /> Sign in
          </Link>
          <div className="auth-icon" aria-hidden="true">
            {resetMode ? <KeyRound size={24} /> : <Mail size={24} />}
          </div>
          <p className="auth-kicker">Account help</p>
          <h1 id="password-help-title">{resetMode ? 'Choose a new password.' : 'Reset your password.'}</h1>
          <p>
            {resetMode
              ? 'Enter a new password for your Atelier account. Reset links expire after a short window.'
              : 'Enter your account email. If it exists, we will send a one-time reset link.'}
          </p>

          {resetMode ? (
            <form className="auth-form" onSubmit={confirmReset}>
              <label>
                <span>New password</span>
                <input
                  value={newPassword}
                  onChange={(event) => setNewPassword(event.target.value)}
                  type="password"
                  autoComplete="new-password"
                  minLength={8}
                  required
                />
              </label>
              <label>
                <span>Confirm password</span>
                <input
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  type="password"
                  autoComplete="new-password"
                  minLength={8}
                  required
                />
              </label>
              <button className="support-link" type="submit" disabled={isSubmitting}>
                {isSubmitting ? 'Saving...' : 'Reset password'}
              </button>
            </form>
          ) : (
            <form className="auth-form" onSubmit={requestReset}>
              <label>
                <span>Email</span>
                <input
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  type="email"
                  autoComplete="email"
                  required
                />
              </label>
              <button className="support-link" type="submit" disabled={isSubmitting}>
                {isSubmitting ? 'Sending...' : 'Send reset link'}
              </button>
            </form>
          )}

          {message && <p className="status-message">{message}</p>}
          {resetMode && message ? (
            <Link className="plain-link" href={signInHref}>
              Continue to sign in
            </Link>
          ) : null}
          {error && <p className="error-message">{error}</p>}
          {devResetUrl && (
            <p className="dev-note">
              Dev reset link: <a href={devResetUrl}>open reset</a>
            </p>
          )}
          {!resetMode && supportEmail ? (
            <a className="plain-link" href={`mailto:${supportEmail}?subject=${supportSubject}`}>
              Still need help?
            </a>
          ) : null}
        </section>
      </main>

      <style jsx>{`
        .auth-page {
          min-height: 100dvh;
          display: grid;
          place-items: center;
          padding: calc(max(18px, env(safe-area-inset-top)) + 12px) 16px calc(max(22px, env(safe-area-inset-bottom)) + 10px);
          background:
            linear-gradient(rgba(20, 17, 13, .035) 1px, transparent 1px),
            linear-gradient(90deg, rgba(20, 17, 13, .025) 1px, transparent 1px),
            var(--app-paper);
          background-size: 100% 34px, 34px 100%, auto;
          color: var(--app-ink);
        }

        .auth-card {
          width: min(100%, 480px);
          display: grid;
          gap: 16px;
          border: 1px solid var(--app-ink);
          background: var(--app-sheet);
          padding: 24px 20px;
          box-shadow: 7px 7px 0 var(--app-ink);
        }

        .auth-back,
        .plain-link {
          width: max-content;
          display: inline-flex;
          align-items: center;
          gap: 8px;
          color: var(--app-blue);
          font-size: 12px;
          font-weight: 900;
          letter-spacing: .08em;
          text-decoration: none;
          text-transform: uppercase;
        }

        .auth-icon {
          width: 54px;
          height: 54px;
          display: grid;
          place-items: center;
          border: 1px solid var(--app-ink);
          background: var(--app-yellow);
          box-shadow: 4px 4px 0 var(--app-ink);
        }

        .auth-kicker {
          margin: 0;
          color: var(--app-ink-3);
          font-size: 10px;
          font-weight: 900;
          letter-spacing: .14em;
          text-transform: uppercase;
        }

        h1 {
          margin: 0;
          color: var(--app-ink);
          font-family: var(--app-serif);
          font-size: clamp(34px, 10vw, 50px);
          font-style: italic;
          font-weight: 500;
          letter-spacing: 0;
          line-height: .98;
        }

        p {
          margin: 0;
          color: var(--app-ink-2);
          line-height: 1.45;
        }

        .auth-form {
          display: grid;
          gap: 14px;
        }

        label {
          display: grid;
          gap: 7px;
        }

        label span {
          color: var(--app-ink-3);
          font-size: 11px;
          font-weight: 900;
          letter-spacing: .1em;
          text-transform: uppercase;
        }

        input {
          min-height: 46px;
          border: 2px solid var(--app-ink);
          background: var(--app-paper);
          color: var(--app-ink);
          padding: 10px 12px;
          font-size: 16px;
          outline: none;
        }

        input:focus {
          border-color: var(--app-blue);
        }

        .support-link {
          min-height: 44px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          border: 1px solid var(--app-ink);
          background: var(--accent-action);
          color: white;
          padding: 12px 18px;
          text-decoration: none;
          font-size: 12px;
          font-weight: 900;
          letter-spacing: .08em;
          text-transform: uppercase;
          box-shadow: var(--ink-block-shadow);
        }

        .support-link:disabled {
          cursor: not-allowed;
          opacity: .68;
          transform: none;
        }

        .status-message,
        .error-message,
        .dev-note {
          border: 1px solid var(--app-ink);
          padding: 10px 12px;
          font-size: 13px;
          font-weight: 800;
        }

        .status-message {
          background: rgba(59, 130, 246, .08);
        }

        .error-message {
          background: rgba(239, 68, 68, .1);
          color: var(--app-ink);
        }

        .dev-note {
          background: rgba(245, 158, 11, .12);
        }
      `}</style>
    </>
  );
}
