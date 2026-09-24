import { FormEvent, useMemo, useState } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';
import { Action } from '@/components/atelier-v2/ui';
import {
  AuthEyebrow,
  AuthField,
  AuthFootLink,
  AuthNotice,
  AuthScreen,
  AuthSpacer,
} from '@/components/auth/AuthShell';

import { useOnboardingLanguage } from '@/components/onboarding/LanguageSwitch';
import { sanitizeAuthCallbackUrl } from '@/lib/app-auth';
import { AUTH_EYEBROW, authCopy, authFill } from '@/lib/auth-copy';
import apiService from '@/services/api';

/**
 * Password reset that works on a phone (WP-71).
 *
 * The emailed link pointed at localhost and the native app has no web host, so
 * reset could not be finished on the device. The email now carries a six-digit
 * code: address → code → new password, all inside the app. The old `?token=`
 * link still opens the new-password screen directly.
 */

type Step = 'email' | 'code' | 'password' | 'done';

// bcrypt reads 72 bytes; the server refuses more (accents are two bytes).
const PASSWORD_MAX_BYTES = 72;

function byteLength(value: string) {
  return new TextEncoder().encode(value).length;
}

function httpStatus(error: unknown) {
  return (error as { response?: { status?: number } })?.response?.status;
}

export default function ForgotPasswordPage() {
  const router = useRouter();
  const [language] = useOnboardingLanguage();
  const { reset: copy, signin: shared } = authCopy(language);
  const token = useMemo(() => {
    const value = router.query.token;
    return typeof value === 'string' ? value : '';
  }, [router.query.token]);
  const supportEmail = process.env.NEXT_PUBLIC_SUPPORT_EMAIL?.trim();
  const supportSubject = encodeURIComponent(copy.support_subject);
  const [step, setStep] = useState<Step>('email');
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [devCode, setDevCode] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const destination = sanitizeAuthCallbackUrl(router.query.callbackUrl);
  const callbackQuery = destination === '/atelier' ? {} : { callbackUrl: destination };
  const signInHref = { pathname: '/auth/signin', query: callbackQuery };
  // A link from an older email skips straight to the new password.
  const currentStep: Step = token && step === 'email' ? 'password' : step;

  const sendCode = async () => {
    setError('');
    setNotice('');
    const address = email.trim().toLowerCase();
    if (!address || !address.includes('@')) {
      setError(copy.errors.email_required);
      return false;
    }
    setIsSubmitting(true);
    try {
      const response = await apiService.requestPasswordReset({ email: address });
      setDevCode(response.reset_code || '');
      setCode('');
      setStep('code');
      return true;
    } catch {
      setError(copy.errors.send_failed);
      return false;
    } finally {
      setIsSubmitting(false);
    }
  };

  const requestCode = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await sendCode();
  };

  const resendCode = async () => {
    // The server holds a fresh code back for a minute; say only what we know.
    if (await sendCode()) setNotice(copy.errors.resent);
  };

  const acceptCode = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    setNotice('');
    const digits = code.replace(/\D/g, '');
    if (digits.length !== 6) {
      setError(copy.errors.code_digits);
      return;
    }
    setCode(digits);
    setStep('password');
  };

  const saveNewPassword = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    setNotice('');
    if (newPassword.length < 8) {
      setError(copy.errors.password_short);
      return;
    }
    if (byteLength(newPassword) > PASSWORD_MAX_BYTES) {
      setError(copy.errors.password_long);
      return;
    }
    if (newPassword !== confirmPassword) {
      setError(copy.errors.mismatch);
      return;
    }
    setIsSubmitting(true);
    try {
      if (token) {
        await apiService.confirmPasswordReset({ token, new_password: newPassword });
      } else {
        await apiService.confirmPasswordReset({
          email: email.trim().toLowerCase(),
          code,
          new_password: newPassword,
        });
      }
      setNewPassword('');
      setConfirmPassword('');
      setStep('done');
    } catch (failure) {
      const status = httpStatus(failure);
      if (status === 400 && !token) {
        // Wrong, expired or used up: back to the code, password kept.
        setStep('code');
        setError(copy.errors.code_wrong);
      } else if (status === 400) {
        setError(copy.errors.link_expired);
      } else if (status === 422) {
        setError(copy.errors.password_refused);
      } else {
        setError(copy.errors.send_failed);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const goToSignIn = () => {
    const address = email.trim().toLowerCase();
    void router.push({
      pathname: '/auth/signin',
      query: address ? { ...callbackQuery, email: address } : callbackQuery,
    });
  };

  return (
    <>
      <Head>
        <title>{`${copy.tab_title} · L’Atelier`}</title>
      </Head>

      <AuthScreen label={copy.screen}>
        <AuthEyebrow>{AUTH_EYEBROW}</AuthEyebrow>

        {currentStep === 'email' && (
          <>
            <h1 className="av2-headline av2-headline--screen">{copy.email_title}</h1>
            <p className="av2-body av2-body--lg">{copy.email_lead}</p>

            {error && <AuthNotice>{error}</AuthNotice>}

            <form
              method="post"
              action="/api/auth/pre-hydration"
              className="auth-form-v2"
              onSubmit={requestCode}
              noValidate
            >
              <AuthField
                id="reset-email"
                type="email"
                label={copy.email_label}
                placeholder={shared.email_placeholder}
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                autoComplete="email"
                inputMode="email"
                autoCapitalize="none"
                required
              />

              <AuthSpacer />

              <Action tone="primary" type="submit" pending={isSubmitting} pendingLabel={copy.sending}>
                {copy.send}
              </Action>
            </form>
          </>
        )}

        {currentStep === 'code' && (
          <>
            <h1 className="av2-headline av2-headline--screen">{copy.code_title}</h1>
            <p className="av2-body av2-body--lg">
              {authFill(copy.code_lead, { email: email.trim().toLowerCase() })}
            </p>

            {error && <AuthNotice>{error}</AuthNotice>}
            {notice && <AuthNotice tone="done">{notice}</AuthNotice>}

            <form
              method="post"
              action="/api/auth/pre-hydration"
              className="auth-form-v2"
              onSubmit={acceptCode}
              noValidate
            >
              <AuthField
                id="reset-code"
                type="text"
                label={copy.code_label}
                placeholder="000000"
                value={code}
                onChange={(event) => setCode(event.target.value.replace(/\D/g, '').slice(0, 6))}
                autoComplete="one-time-code"
                inputMode="numeric"
                pattern="[0-9]*"
                maxLength={6}
                required
              />

              <AuthSpacer />

              <Action tone="primary" type="submit">
                {copy.continue}
              </Action>
              <Action tone="quiet" onClick={resendCode} pending={isSubmitting} pendingLabel={copy.sending}>
                {copy.resend}
              </Action>
            </form>
          </>
        )}

        {currentStep === 'password' && (
          <>
            <h1 className="av2-headline av2-headline--screen">{copy.password_title}</h1>

            {error && <AuthNotice>{error}</AuthNotice>}

            <form
              method="post"
              action="/api/auth/pre-hydration"
              className="auth-form-v2"
              onSubmit={saveNewPassword}
              noValidate
            >
              {/* Lets a password manager file the new password under the account. */}
              {!token && (
                <input
                  type="email"
                  name="username"
                  autoComplete="username"
                  value={email.trim().toLowerCase()}
                  readOnly
                  hidden
                />
              )}
              <AuthField
                id="reset-new"
                type="password"
                label={copy.new_password}
                placeholder={copy.new_password_placeholder}
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
                autoComplete="new-password"
                required
              />
              <AuthField
                id="reset-confirm"
                type="password"
                label={copy.confirm}
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
                pendingLabel={copy.saving}
              >
                {copy.save}
              </Action>
            </form>
          </>
        )}

        {currentStep === 'done' && (
          <>
            <h1 className="av2-headline av2-headline--screen">{copy.done_title}</h1>
            <p className="av2-body av2-body--lg">{copy.done_lead}</p>

            <AuthSpacer />

            <Action tone="primary" onClick={goToSignIn}>
              {copy.sign_in}
            </Action>
          </>
        )}

        {/* Development only: the API returns the code when no mailer is wired. */}
        {devCode && currentStep === 'code' && (
          <p className="av2-label reset-dev-link">{authFill(copy.dev_code, { code: devCode })}</p>
        )}

        {supportEmail && currentStep !== 'done' && (
          <p className="av2-label reset-support">
            {copy.stuck}{' '}
            <a className="auth-foot__link" href={`mailto:${supportEmail}?subject=${supportSubject}`}>
              {supportEmail}
            </a>
          </p>
        )}

        {currentStep !== 'done' && <AuthFootLink href={signInHref} label={copy.back_to_sign_in} />}
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
