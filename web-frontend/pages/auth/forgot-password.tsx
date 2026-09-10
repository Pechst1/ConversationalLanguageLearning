import { FormEvent, useMemo, useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { ArrowLeft, KeyRound, Mail } from 'lucide-react';
import { Action } from '@/components/atelier-v2/ui';
import {
  AuthEyebrow,
  AuthField,
  AuthFootLink,
  AuthNotice,
  AuthScreen,
  AuthSpacer,
} from '@/components/auth/AuthShell';

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
      setError('Indiquez l’adresse de votre compte.');
      return;
    }
    setIsSubmitting(true);
    try {
      const response = await apiService.requestPasswordReset({ email: email.trim() });
      setMessage(response.message);
      setDevResetUrl(response.reset_url || '');
    } catch {
      setError('L’envoi n’a pas abouti. Réessayez dans un instant.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const confirmReset = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    setMessage('');
    if (newPassword.length < 8) {
      setError('Au moins 8 caractères pour le nouveau mot de passe.');
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('Les deux mots de passe ne correspondent pas.');
      return;
    }
    setIsSubmitting(true);
    try {
      await apiService.confirmPasswordReset({ token, new_password: newPassword });
      setMessage('Votre mot de passe est changé. Vous pouvez vous connecter.');
      setNewPassword('');
      setConfirmPassword('');
    } catch {
      setError('Ce lien est invalide ou a expiré. Demandez-en un nouveau.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <Head>
        <title>Mot de passe · L’Atelier</title>
      </Head>

      <AuthScreen label="Mot de passe oublié">
        <AuthEyebrow>L’Atelier · Quotidien de français</AuthEyebrow>

        {resetMode ? (
          <>
            <h1 className="av2-headline av2-headline--screen">Nouveau mot de passe</h1>
            <p className="av2-body av2-body--lg">
              Choisissez-en un que vous n’utilisez pas ailleurs.
            </p>

            {error && <AuthNotice>{error}</AuthNotice>}
            {message && <AuthNotice tone="done">{message}</AuthNotice>}

            <form
              method="post"
              action="/api/auth/pre-hydration"
              className="auth-form-v2"
              onSubmit={confirmReset}
              noValidate
            >
              <AuthField
                id="reset-new"
                type="password"
                label="Nouveau mot de passe"
                placeholder="Au moins 8 caractères"
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
                autoComplete="new-password"
                required
              />
              <AuthField
                id="reset-confirm"
                type="password"
                label="Confirmer"
                placeholder="Le même, une seconde fois"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                autoComplete="new-password"
                required
              />

              <AuthSpacer />

              <Action
                tone="primary"
                type="submit"
                pending={isSubmitting}
                pendingLabel="Enregistrement…"
              >
                Enregistrer
              </Action>
            </form>
          </>
        ) : (
          <>
            <h1 className="av2-headline av2-headline--screen">
              {message ? 'Vérifiez votre boîte' : 'Mot de passe oublié'}
            </h1>
            <p className="av2-body av2-body--lg">
              {message
                ? 'Rien reçu au bout de quelques minutes ? Regardez les indésirables, puis redemandez un lien.'
                : 'Indiquez votre adresse : nous envoyons un lien pour en choisir un nouveau.'}
            </p>

            {error && <AuthNotice>{error}</AuthNotice>}
            {/* The server's own wording, which deliberately does not say whether
                the address is registered. */}
            {message && <AuthNotice tone="done">{message}</AuthNotice>}

            <form
              method="post"
              action="/api/auth/pre-hydration"
              className="auth-form-v2"
              onSubmit={requestReset}
              noValidate
            >
              <AuthField
                id="reset-email"
                type="email"
                label="Adresse e-mail"
                placeholder="vous@exemple.fr"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                autoComplete="email"
                inputMode="email"
                required
              />

              <AuthSpacer />

              <Action tone="primary" type="submit" pending={isSubmitting} pendingLabel="Envoi…">
                {message ? 'Renvoyer le lien' : 'Envoyer le lien'}
              </Action>
            </form>
          </>
        )}

        {/* Development only: the API returns the link when no mailer is wired. */}
        {devResetUrl && (
          <p className="av2-label reset-dev-link">
            Lien de test :{' '}
            <a className="auth-foot__link" href={devResetUrl}>
              {devResetUrl}
            </a>
          </p>
        )}

        {supportEmail && (
          <p className="av2-label reset-support">
            Toujours bloqué ?{' '}
            <a className="auth-foot__link" href={`mailto:${supportEmail}?subject=${supportSubject}`}>
              {supportEmail}
            </a>
          </p>
        )}

        <AuthFootLink href={signInHref} label="Retour à la connexion" />
      </AuthScreen>

      <style jsx global>{`
        .av2 .auth-form-v2 {
          display: flex;
          flex: 1 1 auto;
          flex-direction: column;
          gap: 14px;
          min-width: 0;
        }
        .av2 .reset-dev-link,
        .av2 .reset-support {
          margin: 0;
          font-weight: 400;
          overflow-wrap: anywhere;
        }
      `}</style>
    </>
  );
}
