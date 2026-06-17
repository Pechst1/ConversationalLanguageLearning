import Head from 'next/head';
import Link from 'next/link';
import { ArrowLeft, Mail } from 'lucide-react';

export default function ForgotPasswordPage() {
  const supportEmail = process.env.NEXT_PUBLIC_SUPPORT_EMAIL?.trim();
  const supportSubject = encodeURIComponent('Atelier password help');

  return (
    <>
      <Head>
        <title>Password help - Atelier</title>
      </Head>

      <main className="auth-page">
        <section className="auth-card" aria-labelledby="password-help-title">
          <Link className="auth-back" href="/auth/signin">
            <ArrowLeft size={15} aria-hidden="true" /> Sign in
          </Link>
          <div className="auth-icon" aria-hidden="true">
            <Mail size={24} />
          </div>
          <p className="auth-kicker">Account help</p>
          <h1 id="password-help-title">Password reset is handled by support for now.</h1>
          <p>
            Send us the email address on your account and we will help you restore access.
            The automated reset flow is not enabled in this release yet.
          </p>
          {supportEmail ? (
            <a className="support-link" href={`mailto:${supportEmail}?subject=${supportSubject}`}>
              Email support
            </a>
          ) : (
            <p className="support-note">Contact support through your account team.</p>
          )}
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

        .auth-back {
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

        .support-note {
          font-size: 13px;
          font-weight: 800;
        }
      `}</style>
    </>
  );
}
