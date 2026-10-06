import React from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';
import Link from 'next/link';
import { useForm } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import * as yup from 'yup';
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
import { sanitizeAuthCallbackUrl, useAppAuth } from '@/lib/app-auth';
import { AUTH_EYEBROW, authCopy, signInErrorText } from '@/lib/auth-copy';

// Messages are keys into the copy table, so the schema never fixes a language.
const schema = yup.object({
  email: yup.string().email('email_invalid').required('email_required'),
  password: yup.string().min(6, 'password_short').required('password_required'),
});

type FormData = yup.InferType<typeof schema>;

export default function SignInPage() {
  const router = useRouter();
  const auth = useAppAuth();
  const [language] = useOnboardingLanguage();
  const copy = authCopy(language).signin;
  const [isLoading, setIsLoading] = React.useState(false);
  // Stated on the screen rather than only in a toast the learner may miss, and
  // never disclosing whether the address is registered.
  const [failure, setFailure] = React.useState<string | null>(null);
  const destination = sanitizeAuthCallbackUrl(router.query.callbackUrl);
  const callbackQuery = destination === '/atelier' ? {} : { callbackUrl: destination };
  const forgotPasswordHref = { pathname: '/auth/forgot-password', query: callbackQuery };

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors },
  } = useForm<FormData>({
    resolver: yupResolver(schema),
  });

  // A learner sent here straight after sign-up keeps the address they typed.
  React.useEffect(() => {
    if (!router.isReady) return;
    const prefilled = Array.isArray(router.query.email) ? router.query.email[0] : router.query.email;
    if (prefilled) setValue('email', prefilled);
  }, [router.isReady, router.query.email, setValue]);

  const onSubmit = async (data: FormData) => {
    setIsLoading(true);
    setFailure(null);
    try {
      const result = await auth.signInWithCredentials(data.email, data.password);

      if (result?.error) {
        setFailure(copy.wrong_credentials);
      } else {
        router.push(destination);
      }
    } catch (error) {
      setFailure(copy.failed);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <>
      <Head>
        <title>{`${copy.screen} · L’Atelier`}</title>
      </Head>

      <AuthScreen label={copy.screen}>
        <AuthEyebrow>{AUTH_EYEBROW}</AuthEyebrow>

        <h1 className="av2-headline av2-headline--screen" id="signin-title">
          {copy.screen}
        </h1>

        {failure && <AuthNotice>{failure}</AuthNotice>}

        {/* `action` keeps the pre-hydration post working: a learner who submits
            before React has hydrated still reaches the server. */}
        <form
          method="post"
          action="/api/auth/pre-hydration"
          onSubmit={handleSubmit(onSubmit)}
          className="auth-form-v2"
          /* Our own validation speaks the learner's language and renders under the field; the
             browser's built-in bubble speaks the device's language and covers
             the layout. Ours wins. */
          noValidate
        >
          <AuthField
            {...register('email')}
            id="signin-email"
            type="email"
            label={copy.email}
            placeholder={copy.email_placeholder}
            error={signInErrorText(copy, errors.email?.message)}
            autoComplete="email"
            inputMode="email"
          />

          <AuthField
            {...register('password')}
            id="signin-password"
            type="password"
            label={copy.password}
            placeholder={copy.password_placeholder}
            error={signInErrorText(copy, errors.password?.message)}
            autoComplete="current-password"
          />

          <div className="auth-form-v2__meta">
            <Link className="auth-foot__link" href={forgotPasswordHref}>
              {copy.forgot}
            </Link>
          </div>

          <AuthSpacer />

          <Action tone="primary" type="submit" pending={isLoading} pendingLabel={copy.pending}>
            {copy.submit}
          </Action>
        </form>

        <AuthFootLink href={{ pathname: '/auth/signup', query: callbackQuery }} label={copy.create_account}>
          {copy.new_here}
        </AuthFootLink>
      </AuthScreen>

      <style jsx global>{`
        .av2 .auth-form-v2 {
          display: flex;
          flex: 1 1 auto;
          flex-direction: column;
          gap: 14px;
          min-width: 0;
        }
        .av2 .auth-form-v2__meta {
          display: flex;
          justify-content: flex-end;
          min-height: var(--av2-tap);
          align-items: center;
        }
      `}</style>
    </>
  );
}
