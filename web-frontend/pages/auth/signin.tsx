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
import { sanitizeAuthCallbackUrl, useAppAuth } from '@/lib/app-auth';

const schema = yup.object({
  email: yup.string().email('Adresse e-mail invalide').required('Indiquez votre adresse'),
  password: yup.string().min(6, 'Au moins 6 caractères').required('Indiquez votre mot de passe'),
});

type FormData = yup.InferType<typeof schema>;

export default function SignInPage() {
  const router = useRouter();
  const auth = useAppAuth();
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
    formState: { errors },
  } = useForm<FormData>({
    resolver: yupResolver(schema),
  });

  const onSubmit = async (data: FormData) => {
    setIsLoading(true);
    setFailure(null);
    try {
      const result = await auth.signInWithCredentials(data.email, data.password);

      if (result?.error) {
        setFailure('Identifiants incorrects. Vérifiez l’adresse et le mot de passe.');
      } else {
        router.push(destination);
      }
    } catch (error) {
      setFailure('La connexion n’a pas abouti. Réessayez dans un instant.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <>
      <Head>
        <title>Se connecter · L’Atelier</title>
      </Head>

      <AuthScreen label="Se connecter">
        <AuthEyebrow>L’Atelier · Quotidien de français</AuthEyebrow>

        <h1 className="av2-headline av2-headline--screen" id="signin-title">
          Se connecter
        </h1>

        {failure && <AuthNotice>{failure}</AuthNotice>}

        {/* `action` keeps the pre-hydration post working: a learner who submits
            before React has hydrated still reaches the server. */}
        <form
          method="post"
          action="/api/auth/pre-hydration"
          onSubmit={handleSubmit(onSubmit)}
          className="auth-form-v2"
          /* Our own validation speaks French and renders under the field; the
             browser's built-in bubble speaks the device's language and covers
             the layout. Ours wins. */
          noValidate
        >
          <AuthField
            {...register('email')}
            id="signin-email"
            type="email"
            label="Adresse e-mail"
            placeholder="vous@exemple.fr"
            error={errors.email?.message}
            autoComplete="email"
            inputMode="email"
          />

          <AuthField
            {...register('password')}
            id="signin-password"
            type="password"
            label="Mot de passe"
            placeholder="Votre mot de passe"
            error={errors.password?.message}
            autoComplete="current-password"
          />

          <div className="auth-form-v2__meta">
            <Link className="auth-foot__link" href={forgotPasswordHref}>
              Mot de passe oublié ?
            </Link>
          </div>

          <AuthSpacer />

          <Action tone="primary" type="submit" pending={isLoading} pendingLabel="Connexion…">
            Se connecter
          </Action>
        </form>

        <AuthFootLink href={{ pathname: '/auth/signup', query: callbackQuery }} label="Créer un compte">
          Nouveau ici ?
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
