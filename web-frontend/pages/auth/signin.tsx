import React from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';
import Link from 'next/link';
import { useForm } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import * as yup from 'yup';
import { ArrowRight } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { sanitizeAuthCallbackUrl, useAppAuth } from '@/lib/app-auth';
import toast from 'react-hot-toast';

const schema = yup.object({
  email: yup.string().email('Invalid email').required('Email is required'),
  password: yup.string().min(6, 'Password must be at least 6 characters').required('Password is required'),
});

type FormData = yup.InferType<typeof schema>;

const authInputClass =
  'border-[var(--app-ink)] bg-[var(--app-sheet)] text-[var(--app-ink)] placeholder:text-[var(--app-ink-3)] shadow-none focus:translate-x-0 focus:translate-y-0 focus:shadow-none focus-visible:ring-[var(--app-blue)] focus-visible:ring-offset-[var(--app-paper)]';

export default function SignInPage() {
  const router = useRouter();
  const auth = useAppAuth();
  const [isLoading, setIsLoading] = React.useState(false);
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
    try {
      const result = await auth.signInWithCredentials(data.email, data.password);

      if (result?.error) {
        toast.error('Invalid credentials. Please try again.');
      } else {
        toast.success('Welcome back!');
        router.push(destination);
      }
    } catch (error) {
      toast.error('An error occurred. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <>
      <Head>
        <title>Sign in - Atelier</title>
      </Head>

      <main className="auth-page">
        <section className="auth-shell" aria-labelledby="signin-title">
          <div className="auth-brand-panel">
            <Link className="auth-brand" href="/" aria-label="Open Atelier home">
              <AtelierMark />
              <span>Atelier</span>
            </Link>

            <div className="auth-copy">
              <p className="auth-kicker">Mobile language atelier</p>
              <h1>Pick up the thread.</h1>
              <p>
                Return to the paper trail of drills, repairs, and speaking practice waiting in your atelier.
              </p>
            </div>

            <div className="auth-strip" aria-hidden="true">
              <span>Daily</span>
              <span>Notebook</span>
              <span>Voice</span>
            </div>
          </div>

          <div className="auth-form-panel">
            <div className="auth-form-heading">
              <p className="auth-kicker">Welcome back</p>
              <h2 id="signin-title">Sign in</h2>
              <p>
                New here?{' '}
                <Link href={{ pathname: '/auth/signup', query: callbackQuery }} className="auth-inline-link">
                  Create account
                </Link>
              </p>
            </div>

            <form onSubmit={handleSubmit(onSubmit)} className="auth-form">
              <Input
                {...register('email')}
                type="email"
                label="Email address"
                placeholder="Enter your email"
                error={errors.email?.message}
                autoComplete="email"
                className={authInputClass}
              />

              <Input
                {...register('password')}
                type="password"
                label="Password"
                placeholder="Enter your password"
                error={errors.password?.message}
                autoComplete="current-password"
                className={authInputClass}
              />

              <div className="auth-form-meta">
                <Link href={forgotPasswordHref} className="auth-inline-link">
                  Forgot your password?
                </Link>
              </div>

              <Button
                type="submit"
                className="auth-submit w-full"
                loading={isLoading}
                rightIcon={<ArrowRight className="h-4 w-4" aria-hidden="true" />}
                size="lg"
              >
                Sign in
              </Button>
            </form>
          </div>
        </section>

        <style jsx>{`
          .auth-page {
            min-height: 100dvh;
            display: grid;
            align-items: start;
            justify-items: center;
            padding: calc(max(18px, env(safe-area-inset-top)) + 12px) 16px calc(max(22px, env(safe-area-inset-bottom)) + 10px);
            background:
              linear-gradient(rgba(20, 17, 13, .035) 1px, transparent 1px),
              linear-gradient(90deg, rgba(20, 17, 13, .025) 1px, transparent 1px),
              var(--app-paper);
            background-size: 100% 34px, 34px 100%, auto;
            color: var(--app-ink);
          }

          .auth-shell {
            width: min(100%, 1040px);
            display: grid;
            overflow: hidden;
            border: 1px solid var(--app-ink);
            background: var(--app-sheet);
            box-shadow: 7px 7px 0 var(--app-ink);
          }

          .auth-brand-panel,
          .auth-form-panel {
            padding: 22px 20px;
          }

          .auth-brand-panel {
            display: grid;
            gap: 22px;
            border-bottom: 1px solid var(--app-ink);
            background: var(--app-paper-2);
          }

          .auth-brand {
            display: inline-flex;
            width: max-content;
            align-items: center;
            gap: 12px;
            color: var(--app-ink);
            text-decoration: none;
            font-size: 21px;
            font-weight: 900;
          }

          .auth-copy {
            display: grid;
            gap: 10px;
          }

          .auth-kicker {
            margin: 0;
            color: var(--app-ink-3);
            font-size: 10px;
            font-weight: 900;
            letter-spacing: .14em;
            text-transform: uppercase;
          }

          .auth-copy h1,
          .auth-form-heading h2 {
            margin: 0;
            color: var(--app-ink);
            font-family: var(--app-serif);
            font-style: italic;
            font-weight: 500;
            letter-spacing: 0;
            line-height: .96;
          }

          .auth-copy h1 {
            max-width: 11ch;
            font-size: clamp(36px, 12vw, 54px);
          }

          .auth-copy p,
          .auth-form-heading p {
            margin: 0;
            color: var(--app-ink-2);
            line-height: 1.45;
          }

          .auth-strip {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            border: 1px solid var(--app-ink);
            background: var(--app-paper);
          }

          .auth-strip span {
            min-width: 0;
            padding: 10px 8px;
            overflow: hidden;
            border-right: 1px solid var(--app-ink);
            text-overflow: ellipsis;
            white-space: nowrap;
            text-align: center;
            color: var(--app-ink-2);
            font-size: 10px;
            font-weight: 900;
            letter-spacing: .1em;
            text-transform: uppercase;
          }

          .auth-strip span:last-child {
            border-right: 0;
          }

          .auth-form-panel,
          .auth-form,
          .auth-form-heading {
            display: grid;
          }

          .auth-form-panel {
            gap: 22px;
            background: var(--app-sheet);
          }

          .auth-form-heading {
            gap: 8px;
          }

          .auth-form-heading h2 {
            font-size: clamp(32px, 10vw, 44px);
          }

          .auth-form {
            gap: 18px;
          }

          .auth-form-meta {
            display: flex;
            justify-content: flex-end;
            margin-top: -4px;
          }

          .auth-inline-link {
            color: var(--app-blue);
            font-weight: 900;
            text-decoration: underline;
            text-decoration-thickness: 1px;
            text-underline-offset: 4px;
          }

          :global(.auth-submit) {
            min-height: 54px;
          }

          @media (min-width: 780px) {
            .auth-page {
              padding: 40px;
              place-items: center;
            }

            .auth-shell {
              grid-template-columns: minmax(320px, .82fr) minmax(380px, 1fr);
              box-shadow: 10px 10px 0 var(--app-ink);
            }

            .auth-brand-panel {
              min-height: 620px;
              align-content: space-between;
              border-right: 1px solid var(--app-ink);
              border-bottom: 0;
              padding: 34px;
            }

            .auth-form-panel {
              align-content: center;
              padding: 46px 44px;
            }

            .auth-copy h1 {
              font-size: clamp(60px, 7vw, 88px);
            }
          }
        `}</style>
      </main>
    </>
  );
}

function AtelierMark() {
  return (
    <svg width="30" height="30" viewBox="0 0 28 28" aria-hidden="true">
      <rect x="0" y="0" width="11" height="11" fill="var(--app-ink)" />
      <circle cx="22" cy="6" r="6" fill="var(--app-blue)" />
      <rect x="0" y="17" width="11" height="11" fill="var(--app-yellow)" />
      <path d="M17 28L23 16L28 28H17Z" fill="var(--app-red)" />
    </svg>
  );
}
