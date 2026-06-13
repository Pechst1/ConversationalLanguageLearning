import React from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';
import Link from 'next/link';
import { useForm } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import * as yup from 'yup';
import { ArrowRight, Plus } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import apiService from '@/services/api';
import toast from 'react-hot-toast';
import { getSession } from 'next-auth/react';

const schema = yup.object({
  name: yup.string().required('Name is required'),
  email: yup.string().email('Invalid email').required('Email is required'),
  password: yup.string().min(6, 'Password must be at least 6 characters').required('Password is required'),
  confirmPassword: yup.string().oneOf([yup.ref('password')], 'Passwords must match').required('Please confirm your password'),
  nativeLanguage: yup.string().required('Native language is required'),
  targetLanguage: yup.string().required('Target language is required'),
  proficiencyLevel: yup.string().required('Current level is required'),
});

type FormData = yup.InferType<typeof schema>;

const languageOptions = [
  { value: 'en', label: 'English' },
  { value: 'de', label: 'Deutsch' },
  { value: 'fr', label: 'Francais' },
  { value: 'es', label: 'Espanol' },
  { value: 'it', label: 'Italiano' },
  { value: 'pt', label: 'Portugues' },
];

const proficiencyOptions = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'];
const interestPresets = [
  'technology',
  'business',
  'travel',
  'sports',
  'politics',
  'science',
  'culture',
  'finance',
  'health',
  'food',
];

const authInputClass =
  'border-[var(--app-ink)] bg-[var(--app-sheet)] text-[var(--app-ink)] placeholder:text-[var(--app-ink-3)] shadow-none focus:translate-x-0 focus:translate-y-0 focus:shadow-none focus-visible:ring-[var(--app-blue)] focus-visible:ring-offset-[var(--app-paper)]';

const selectClass =
  'h-12 w-full rounded-none border-2 border-[var(--app-ink)] bg-[var(--app-sheet)] px-3 py-2 text-sm font-semibold text-[var(--app-ink)] shadow-none focus:border-[var(--app-ink)] focus:outline-none focus:ring-2 focus:ring-[var(--app-blue)] focus:ring-offset-2 focus:ring-offset-[var(--app-paper)]';

export default function SignUpPage() {
  const router = useRouter();
  const [isLoading, setIsLoading] = React.useState(false);
  const [selectedTopics, setSelectedTopics] = React.useState<string[]>([]);
  const [customTopic, setCustomTopic] = React.useState('');

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormData>({
    resolver: yupResolver(schema),
    defaultValues: {
      nativeLanguage: 'en',
      targetLanguage: 'fr',
      proficiencyLevel: 'A1',
    },
  });

  const toggleTopic = (topic: string) => {
    setSelectedTopics((prev) => {
      if (prev.includes(topic)) {
        return prev.filter((value) => value !== topic);
      }
      return [...prev, topic];
    });
  };

  const addCustomTopic = () => {
    const normalized = customTopic.trim().toLowerCase();
    if (!normalized) {
      return;
    }
    if (!selectedTopics.includes(normalized)) {
      setSelectedTopics((prev) => [...prev, normalized]);
    }
    setCustomTopic('');
  };

  const onSubmit = async (data: FormData) => {
    setIsLoading(true);
    try {
      await apiService.register({
        full_name: data.name,
        email: data.email,
        password: data.password,
        native_language: data.nativeLanguage,
        target_language: data.targetLanguage,
        proficiency_level: data.proficiencyLevel,
        interests: selectedTopics.join(','),
      });

      toast.success('Account created successfully! Please sign in.');
      router.push('/auth/signin');
    } catch (error: any) {
      const message = error.response?.data?.detail || 'An error occurred. Please try again.';
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <>
      <Head>
        <title>Create account - Atelier</title>
      </Head>

      <main className="auth-page">
        <section className="auth-shell" aria-labelledby="signup-title">
          <div className="auth-brand-panel">
            <Link className="auth-brand" href="/" aria-label="Open Atelier home">
              <AtelierMark />
              <span>Atelier</span>
            </Link>

            <div className="auth-copy">
              <p className="auth-kicker">Onboarding entry</p>
              <h1>Start with the essentials.</h1>
              <p>
                Make an account now; tune the language profile when you want the first session to feel precise.
              </p>
            </div>

            <div className="profile-ticket" aria-hidden="true">
              <span>English</span>
              <strong>to</strong>
              <span>French</span>
              <strong>A1</strong>
            </div>
          </div>

          <div className="auth-form-panel">
            <div className="auth-form-heading">
              <p className="auth-kicker">Create account</p>
              <h2 id="signup-title">Join Atelier</h2>
              <p>
                Already have an account?{' '}
                <Link href="/auth/signin" className="auth-inline-link">
                  Sign in
                </Link>
              </p>
            </div>

            <form onSubmit={handleSubmit(onSubmit)} className="auth-form">
              <Input
                {...register('name')}
                type="text"
                label="Full name"
                placeholder="Enter your full name"
                error={errors.name?.message}
                autoComplete="name"
                className={authInputClass}
              />

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
                placeholder="Create a password"
                error={errors.password?.message}
                autoComplete="new-password"
                className={authInputClass}
              />

              <Input
                {...register('confirmPassword')}
                type="password"
                label="Confirm password"
                placeholder="Confirm your password"
                error={errors.confirmPassword?.message}
                autoComplete="new-password"
                className={authInputClass}
              />

              <details className="profile-details">
                <summary>
                  <span className="summary-copy">
                    <strong>Learning profile</strong>
                    <small>English to French, A1 by default</small>
                  </span>
                </summary>

                <div className="profile-body">
                  <div className="select-grid">
                    <div className="field-group">
                      <label htmlFor="nativeLanguage">Native language</label>
                      <select id="nativeLanguage" {...register('nativeLanguage')} className={selectClass}>
                        {languageOptions.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                      {errors.nativeLanguage?.message && (
                        <p className="field-error">{errors.nativeLanguage.message}</p>
                      )}
                    </div>

                    <div className="field-group">
                      <label htmlFor="targetLanguage">Target language</label>
                      <select id="targetLanguage" {...register('targetLanguage')} className={selectClass}>
                        {languageOptions.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                      {errors.targetLanguage?.message && (
                        <p className="field-error">{errors.targetLanguage.message}</p>
                      )}
                    </div>
                  </div>

                  <div className="field-group">
                    <label htmlFor="proficiencyLevel">Current CEFR level</label>
                    <select id="proficiencyLevel" {...register('proficiencyLevel')} className={selectClass}>
                      {proficiencyOptions.map((option) => (
                        <option key={option} value={option}>
                          {option}
                        </option>
                      ))}
                    </select>
                    {errors.proficiencyLevel?.message && (
                      <p className="field-error">{errors.proficiencyLevel.message}</p>
                    )}
                  </div>

                  <div className="topic-panel">
                    <label>Topics for live article seeds</label>
                    <div className="topic-grid">
                      {interestPresets.map((topic) => (
                        <button
                          key={topic}
                          type="button"
                          onClick={() => toggleTopic(topic)}
                          aria-pressed={selectedTopics.includes(topic)}
                          className={selectedTopics.includes(topic) ? 'topic-chip selected' : 'topic-chip'}
                        >
                          {topic}
                        </button>
                      ))}
                    </div>

                    <div className="custom-topic-row">
                      <input
                        type="text"
                        value={customTopic}
                        onChange={(event) => setCustomTopic(event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key === 'Enter') {
                            event.preventDefault();
                            addCustomTopic();
                          }
                        }}
                        placeholder="Add custom topic"
                        className={`h-12 w-full rounded-none border-2 px-3 py-2 text-sm focus:outline-none ${authInputClass}`}
                      />
                      <Button
                        type="button"
                        variant="outline"
                        onClick={addCustomTopic}
                        leftIcon={<Plus className="h-4 w-4" aria-hidden="true" />}
                      >
                        Add
                      </Button>
                    </div>

                    {selectedTopics.length > 0 && (
                      <p className="selected-topics">Selected: {selectedTopics.join(', ')}</p>
                    )}
                  </div>
                </div>
              </details>

              <Button
                type="submit"
                className="auth-submit w-full"
                loading={isLoading}
                rightIcon={<ArrowRight className="h-4 w-4" aria-hidden="true" />}
                size="lg"
              >
                Create account
              </Button>
            </form>
          </div>
        </section>

        <style jsx>{`
          .auth-page {
            min-height: 100dvh;
            display: grid;
            place-items: center;
            padding: max(18px, env(safe-area-inset-top)) 16px max(22px, env(safe-area-inset-bottom));
            background:
              linear-gradient(rgba(20, 17, 13, .035) 1px, transparent 1px),
              linear-gradient(90deg, rgba(20, 17, 13, .025) 1px, transparent 1px),
              var(--app-paper);
            background-size: 100% 34px, 34px 100%, auto;
            color: var(--app-ink);
          }

          .auth-shell {
            width: min(100%, 1100px);
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
            max-width: 12ch;
            font-size: clamp(40px, 15vw, 62px);
          }

          .auth-copy p,
          .auth-form-heading p {
            margin: 0;
            color: var(--app-ink-2);
            line-height: 1.45;
          }

          .profile-ticket {
            display: grid;
            grid-template-columns: 1fr auto 1fr auto;
            align-items: center;
            border: 1px solid var(--app-ink);
            background: var(--app-paper);
          }

          .profile-ticket span,
          .profile-ticket strong {
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

          .profile-ticket strong:last-child {
            border-right: 0;
            background: var(--app-yellow);
            color: var(--app-ink);
          }

          .auth-form-panel,
          .auth-form,
          .auth-form-heading,
          .profile-body,
          .topic-panel {
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
            font-size: clamp(34px, 12vw, 48px);
          }

          .auth-form {
            gap: 18px;
          }

          .auth-inline-link {
            color: var(--app-blue);
            font-weight: 900;
            text-decoration: underline;
            text-decoration-thickness: 1px;
            text-underline-offset: 4px;
          }

          .profile-details {
            border: 1px solid var(--app-ink);
            background: var(--app-paper);
          }

          .profile-details summary {
            display: grid;
            grid-template-columns: 1fr auto;
            gap: 12px;
            align-items: center;
            min-height: 54px;
            padding: 0 14px;
            cursor: pointer;
            list-style: none;
          }

          .profile-details summary::-webkit-details-marker {
            display: none;
          }

          .profile-details summary::after {
            content: '+';
            display: grid;
            width: 28px;
            height: 28px;
            place-items: center;
            border: 1px solid var(--app-ink);
            background: var(--app-sheet);
            color: var(--app-ink);
            font-weight: 900;
            line-height: 1;
          }

          .profile-details[open] summary {
            border-bottom: 1px solid var(--app-ink);
          }

          .profile-details[open] summary::after {
            content: '-';
            background: var(--app-ink);
            color: var(--app-paper);
          }

          .summary-copy {
            display: grid;
            min-width: 0;
            gap: 3px;
          }

          .summary-copy strong {
            color: var(--app-ink);
            font-size: 12px;
            font-weight: 900;
            letter-spacing: .11em;
            text-transform: uppercase;
          }

          .summary-copy small {
            display: none;
            color: var(--app-ink-3);
            font-size: 11px;
            font-weight: 800;
          }

          .profile-body {
            gap: 16px;
            padding: 16px 14px 18px;
            background: var(--app-paper-2);
          }

          .select-grid {
            display: grid;
            gap: 14px;
          }

          .field-group {
            display: grid;
            gap: 8px;
          }

          .field-group label,
          .topic-panel label {
            color: var(--app-ink);
            font-size: 13px;
            font-weight: 800;
          }

          .field-error {
            margin: 0;
            color: var(--app-red);
            font-size: 13px;
            font-weight: 700;
          }

          .topic-panel {
            gap: 12px;
          }

          .topic-grid {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
          }

          .topic-chip {
            min-height: 34px;
            border: 1px solid var(--app-ink);
            background: var(--app-sheet);
            padding: 0 11px;
            color: var(--app-ink);
            font-size: 12px;
            font-weight: 900;
            text-transform: capitalize;
            transition: background .12s ease, color .12s ease;
          }

          .topic-chip.selected {
            background: var(--app-blue);
            color: white;
          }

          .custom-topic-row {
            display: grid;
            grid-template-columns: minmax(0, 1fr) auto;
            gap: 8px;
            align-items: start;
          }

          .selected-topics {
            margin: 0;
            color: var(--app-ink-2);
            font-size: 12px;
            font-weight: 700;
            line-height: 1.35;
          }

          :global(.auth-submit) {
            min-height: 54px;
          }

          @media (min-width: 560px) {
            .summary-copy small {
              display: block;
            }

            .select-grid {
              grid-template-columns: repeat(2, minmax(0, 1fr));
            }
          }

          @media (min-width: 860px) {
            .auth-page {
              padding: 40px;
            }

            .auth-shell {
              grid-template-columns: minmax(320px, .78fr) minmax(460px, 1fr);
              box-shadow: 10px 10px 0 var(--app-ink);
            }

            .auth-brand-panel {
              min-height: 720px;
              align-content: space-between;
              border-right: 1px solid var(--app-ink);
              border-bottom: 0;
              padding: 34px;
            }

            .auth-form-panel {
              align-content: center;
              padding: 42px 44px;
            }

            .auth-copy h1 {
              font-size: clamp(58px, 6.7vw, 84px);
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

// Prevent access if already authenticated
export async function getServerSideProps(context: any) {
  const session = await getSession(context);
  
  if (session) {
    return {
      redirect: {
        destination: '/atelier',
        permanent: false,
      },
    };
  }
  
  return {
    props: {},
  };
}
