/**
 * WP-75 — sign-up on one screen, in the learner's own language.
 *
 * Email, a password shown or hidden (never typed twice), an optional first
 * name, one question — «Votre français ?» — and the interface language, guessed
 * from the browser. Everything the old second step asked gets a server-side
 * default and lives in Réglages.
 *
 * On success the learner is signed in with what they just typed and lands in
 * today's scene (`/atelier?start=today`), never on the placement: «Nouveau»
 * skips it entirely, and the placement is offered after day three instead.
 */

import React from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';
import { Action, BottomSheet } from '@/components/atelier-v2/ui';
import {
  AuthEyebrow,
  AuthField,
  AuthFootLink,
  AuthNotice,
  AuthScreen,
  AuthSegments,
  AuthSpacer,
} from '@/components/auth/AuthShell';
import { LegalDocumentView } from '@/components/legal/LegalDocumentView';
import { LanguageSwitch, useOnboardingLanguage } from '@/components/onboarding/LanguageSwitch';
import { sanitizeAuthCallbackUrl, useAppAuth } from '@/lib/app-auth';
import {
  LEGAL_VERSION,
  SIGNUP_CONSENT,
  legalDocument,
  resolveLegalLanguage,
  type LegalDocumentKind,
} from '@/lib/legal';
import {
  SIGNUP_COPY,
  SIGNUP_NAV,
  STARTING_POINTS,
  afterSignUpDestination,
  buildRegisterPayload,
  validateSignUp,
  type SignUpErrors,
  type SignUpForm,
  type StartingPoint,
} from '@/lib/onboarding-signup';
import apiService from '@/services/api';
import toast from 'react-hot-toast';

function authErrorMessage(error: any, fallback: string) {
  const detail = error?.response?.data?.detail;
  if (Array.isArray(detail)) {
    const joined = detail
      .map((item) => String(item?.msg || item?.message || '').trim())
      .filter(Boolean)
      .join(' ');
    if (joined) return joined;
  }
  if (typeof detail === 'string' && detail.trim()) return detail;
  return fallback;
}

export default function SignUpPage() {
  const router = useRouter();
  const auth = useAppAuth();
  const [language, setLanguage] = useOnboardingLanguage();
  const copy = SIGNUP_COPY[language];
  const nav = SIGNUP_NAV[language];
  const [isLoading, setIsLoading] = React.useState(false);
  const [showPassword, setShowPassword] = React.useState(false);
  const [email, setEmail] = React.useState('');
  const [password, setPassword] = React.useState('');
  const [firstName, setFirstName] = React.useState('');
  const [startingPoint, setStartingPoint] = React.useState<StartingPoint | null>(null);
  const [errors, setErrors] = React.useState<SignUpErrors>({});
  // WP-72: the terms and the privacy policy open in a sheet, so reading them
  // never costs the learner what they already typed.
  const [legalSheet, setLegalSheet] = React.useState<LegalDocumentKind | null>(null);

  const destination = sanitizeAuthCallbackUrl(router.query.callbackUrl);
  const callbackQuery = destination === '/atelier' ? {} : { callbackUrl: destination };
  /* A learner who arrived from a deep link keeps their destination; everyone
     else lands in the day-1 scene, not on Home and not on the placement. */
  const landing = afterSignUpDestination(destination);

  const legalLanguage = resolveLegalLanguage(language);
  const consent = SIGNUP_CONSENT[legalLanguage];

  const form: SignUpForm = { email, password, firstName, startingPoint, language };

  /* The same shape react-hook-form gave this page, so the pre-hydration
     contract (`onSubmit={handleSubmit(onSubmit)}`) stays exactly as it was. */
  const handleSubmit =
    (submit: (data: SignUpForm) => Promise<void>) => (event: React.FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      const found = validateSignUp(form);
      setErrors(found);
      if (Object.keys(found).length > 0) return;
      void submit(form);
    };

  const onSubmit = async (data: SignUpForm) => {
    setIsLoading(true);
    try {
      const payload = buildRegisterPayload(data);
      await apiService.post('/auth/register', payload);

      /* The account exists; the learner has just typed the address and the
         password, so sign them in with those and open the first scene. Only
         when that fails does the sign-in form appear — with the address kept,
         so nothing is retyped. */
      const signedIn = await auth.signInWithCredentials(payload.email, data.password).catch(() => null);
      if (signedIn?.ok) {
        /* WP-72: the consent line was on screen when the account was created;
           record which version it named. Best effort. */
        await apiService
          .post('/legal/consent', { version: LEGAL_VERSION, surface: 'signup', language: legalLanguage })
          .catch(() => undefined);
        void router.replace(landing);
        return;
      }
      toast.success(copy.created_sign_in);
      void router.push({ pathname: '/auth/signin', query: { callbackUrl: landing, email: payload.email } });
    } catch (error: any) {
      toast.error(authErrorMessage(error, copy.failed));
    } finally {
      setIsLoading(false);
    }
  };

  const errorText = (key: keyof SignUpErrors) => {
    const code = errors[key];
    return code ? copy.errors[code] : undefined;
  };

  return (
    <>
      <Head>
        <title>{`${nav.screen} · L’Atelier`}</title>
      </Head>

      <AuthScreen label={nav.screen}>
        <div className="signup-top">
          <AuthEyebrow>L’Atelier</AuthEyebrow>
          <LanguageSwitch value={language} onChange={setLanguage} label={copy.language} />
        </div>

        {/* `method`/`action`: a submit that beats hydration — a password
            manager, a fast typist — must POST to a route that reads nothing,
            never fall back to a GET that puts the password in the URL.
            Native validation is off so our messages sit under their field. */}
        <form
          method="post"
          action="/api/auth/pre-hydration"
          className="auth-form-v2"
          onSubmit={handleSubmit(onSubmit)}
          noValidate
          lang={language}
        >
          <h1 className="av2-headline av2-headline--screen">{copy.title}</h1>

          <AuthField
            id="signup-email"
            name="email"
            type="email"
            label={copy.email}
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            error={errorText('email')}
            autoComplete="email"
            inputMode="email"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
          />

          <div className="signup-password">
            <AuthField
              id="signup-password"
              name="password"
              type={showPassword ? 'text' : 'password'}
              label={copy.password}
              placeholder={copy.password_hint}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              error={errorText('password')}
              autoComplete="new-password"
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
            />
            <button
              type="button"
              className="signup-password__toggle"
              aria-controls="signup-password"
              aria-pressed={showPassword}
              onClick={() => setShowPassword((value) => !value)}
            >
              {showPassword ? copy.hide : copy.show}
            </button>
          </div>

          <AuthField
            id="signup-name"
            name="given-name"
            label={`${copy.first_name} (${copy.optional})`}
            value={firstName}
            onChange={(event) => setFirstName(event.target.value)}
            autoComplete="given-name"
          />

          <AuthSegments
            legend={copy.level_question}
            value={startingPoint ?? ''}
            onSelect={(next) => {
              setStartingPoint(next as StartingPoint);
              setErrors((current) => ({ ...current, startingPoint: undefined }));
            }}
            options={STARTING_POINTS.map((point) => ({ value: point, label: copy.levels[point] }))}
          />
          {errors.startingPoint && <AuthNotice>{errorText('startingPoint')}</AuthNotice>}

          <AuthSpacer />

          {/* WP-72 (Apple 5.1.1 / 5.1.2): one line, in the learner's own
              language, naming the AI provider and the two documents. */}
          <p className="signup-consent" lang={legalLanguage} data-signup-consent>
            {consent.ai} {consent.accept}{' '}
            <button type="button" className="signup-consent__link" onClick={() => setLegalSheet('terms')}>
              {consent.terms}
            </button>{' '}
            {consent.and}{' '}
            <button type="button" className="signup-consent__link" onClick={() => setLegalSheet('privacy')}>
              {consent.privacy}
            </button>
            {consent.end}
          </p>

          <Action tone="primary" type="submit" pending={isLoading} pendingLabel={nav.pending}>
            {nav.submit}
          </Action>

          <AuthFootLink href={{ pathname: '/auth/signin', query: callbackQuery }} label={nav.have_account} />
        </form>

        <BottomSheet
          open={legalSheet !== null}
          title={legalSheet ? legalDocument(legalSheet, legalLanguage).title : ''}
          onClose={() => setLegalSheet(null)}
        >
          {legalSheet && <LegalDocumentView kind={legalSheet} language={legalLanguage} showTitle={false} />}
        </BottomSheet>
      </AuthScreen>

      <style jsx global>{`
        .av2 .auth-form-v2 {
          display: flex;
          flex: 1 1 auto;
          flex-direction: column;
          gap: 14px;
          min-width: 0;
        }
        .av2 .signup-top {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
        }
        .av2 .signup-password {
          position: relative;
        }
        .av2 .signup-password__toggle {
          position: absolute;
          top: 0;
          right: 0;
          min-height: 28px;
          padding: 0 4px;
          border: 0;
          background: none;
          font: inherit;
          font-size: var(--av2-t-meta);
          font-weight: 700;
          color: var(--av2-blue);
          cursor: pointer;
        }
        .av2 .signup-consent {
          margin: 0;
          font-size: 0.875rem;
          line-height: 1.45;
          color: var(--av2-muted);
        }
        .av2 .signup-consent__link {
          display: inline;
          padding: 0;
          border: 0;
          background: none;
          font: inherit;
          color: var(--av2-blue);
          text-decoration: underline;
          text-underline-offset: 2px;
          cursor: pointer;
        }
      `}</style>
    </>
  );
}
