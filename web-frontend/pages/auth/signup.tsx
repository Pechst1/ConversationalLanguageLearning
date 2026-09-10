import React from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';
import Link from 'next/link';
import { useForm } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import * as yup from 'yup';
import { ArrowRight, Plus } from 'lucide-react';
import { Action, Chip } from '@/components/atelier-v2/ui';
import {
  AuthChoices,
  AuthEyebrow,
  AuthField,
  AuthFootLink,
  AuthNotice,
  AuthScreen,
  AuthSegments,
  AuthSpacer,
  AuthSteps,
} from '@/components/auth/AuthShell';
import { sanitizeAuthCallbackUrl } from '@/lib/app-auth';
import apiService from '@/services/api';
import toast from 'react-hot-toast';

const schema = yup.object({
  name: yup.string().required('Indiquez votre nom'),
  email: yup.string().email('Adresse e-mail invalide').required('Indiquez votre adresse'),
  password: yup.string().min(8, 'Au moins 8 caractères').required('Choisissez un mot de passe'),
  confirmPassword: yup.string().oneOf([yup.ref('password')], 'Les deux ne correspondent pas').required('Confirmez le mot de passe'),
  nativeLanguage: yup.string().required('Choisissez une langue'),
  targetLanguage: yup.string().required('Choisissez une langue'),
  proficiencyLevel: yup.string().required('Choisissez un niveau'),
  learningMotivation: yup.string().required('Choisissez ce qui vous amène'),
  correctionStyle: yup.string().oneOf(['strict', 'moderate', 'lenient']).required(),
  speakingComfort: yup.string().oneOf(['warming_up', 'ready', 'confident']).required(),
  dailyGoalMinutes: yup.number().oneOf([5, 10, 15, 20]).required(),
});

type FormData = yup.InferType<typeof schema>;

const languageOptions = [
  { value: 'en', label: 'English' },
  { value: 'de', label: 'Deutsch' },
  { value: 'fr', label: 'Français' },
  { value: 'es', label: 'Español' },
  { value: 'it', label: 'Italiano' },
  { value: 'pt', label: 'Português' },
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

// 16px, for the same reason as the Input control: a smaller select zooms the
// WKWebView on focus and never zooms back (WP-20 D-16).
function authErrorMessage(error: any) {
  const detail = error?.response?.data?.detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => String(item?.msg || item?.message || '').trim())
      .filter(Boolean)
      .join(' ');
  }
  if (typeof detail === 'string' && detail.trim()) return detail;
  return 'An error occurred. Please try again.';
}

export default function SignUpPage() {
  const router = useRouter();
  const [isLoading, setIsLoading] = React.useState(false);
  // Two steps rather than one wall of fields: the essentials, then the answers
  // that actually shape the first edition.
  const [step, setStep] = React.useState<1 | 2>(1);
  const [selectedTopics, setSelectedTopics] = React.useState<string[]>([]);
  const destination = sanitizeAuthCallbackUrl(router.query.callbackUrl);
  const callbackQuery = destination === '/atelier' ? {} : { callbackUrl: destination };

  const {
    register,
    handleSubmit,
    trigger,
    watch,
    setValue,
    formState: { errors },
  } = useForm<FormData>({
    resolver: yupResolver(schema),
    defaultValues: {
      nativeLanguage: 'en',
      targetLanguage: 'fr',
      proficiencyLevel: 'A1',
      learningMotivation: 'travel',
      correctionStyle: 'moderate',
      speakingComfort: 'warming_up',
      dailyGoalMinutes: 10,
    },
  });

  /* Step one may not be left until its own fields are valid — otherwise a
     learner discovers a typo in their email four questions later. */
  const goToSecondStep = async () => {
    const ok = await trigger(['name', 'email', 'password', 'confirmPassword', 'nativeLanguage']);
    if (ok) setStep(2);
  };

  const toggleTopic = (topic: string) => {
    setSelectedTopics((prev) => {
      if (prev.includes(topic)) {
        return prev.filter((value) => value !== topic);
      }
      return [...prev, topic];
    });
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
        learning_motivation: data.learningMotivation,
        speaking_comfort: data.speakingComfort as 'warming_up' | 'ready' | 'confident',
        grammar_correction_level: data.correctionStyle as 'strict' | 'moderate' | 'lenient',
        daily_goal_minutes: data.dailyGoalMinutes,
      });

      toast.success('Compte créé. Connectez-vous pour ouvrir votre première édition.');
      router.push({ pathname: '/auth/signin', query: callbackQuery });
    } catch (error: any) {
      toast.error(authErrorMessage(error));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <>
      <Head>
        <title>Créer un compte · L’Atelier</title>
      </Head>

      <AuthScreen label="Créer un compte">
        <AuthEyebrow>L’Atelier · Quotidien de français</AuthEyebrow>
        <AuthSteps step={step} total={2} />

        {/* Native validation is off: our messages are French and sit under
            the field they belong to. */}
        <form className="auth-form-v2" onSubmit={handleSubmit(onSubmit)} noValidate>
          {step === 1 ? (
            <>
              <h1 className="av2-headline av2-headline--screen">Créer un compte</h1>
              <p className="av2-body av2-body--lg">
                L’essentiel d’abord. La suite façonne votre première édition.
              </p>

              <AuthField
                {...register('name')}
                id="signup-name"
                label="Nom complet"
                placeholder="Votre nom"
                error={errors.name?.message}
                autoComplete="name"
              />
              <AuthField
                {...register('email')}
                id="signup-email"
                type="email"
                label="Adresse e-mail"
                placeholder="vous@exemple.fr"
                error={errors.email?.message}
                autoComplete="email"
                inputMode="email"
              />
              <AuthField
                {...register('password')}
                id="signup-password"
                type="password"
                label="Mot de passe"
                placeholder="Au moins 8 caractères"
                error={errors.password?.message}
                autoComplete="new-password"
              />
              <AuthField
                {...register('confirmPassword')}
                id="signup-confirm"
                type="password"
                label="Confirmer"
                placeholder="Le même, une seconde fois"
                error={errors.confirmPassword?.message}
                autoComplete="new-password"
              />

              <AuthSegments
                legend="Langue de l’interface"
                value={watch('nativeLanguage')}
                onSelect={(next) => setValue('nativeLanguage', next, { shouldValidate: true })}
                options={languageOptions.map((option) => ({
                  value: option.value,
                  label: option.label,
                }))}
              />

              <AuthSpacer />

              <Action tone="primary" type="button" onClick={() => void goToSecondStep()}>
                Continuer
              </Action>

              <AuthFootLink
                href={{ pathname: '/auth/signin', query: callbackQuery }}
                label="Se connecter"
              >
                Déjà inscrit ?
              </AuthFootLink>
            </>
          ) : (
            <>
              <h1 className="av2-headline av2-headline--screen">Votre première édition</h1>
              <p className="av2-body av2-body--lg">
                Ces réponses composent la séance de demain. Tout se change ensuite dans Réglages.
              </p>

              <AuthChoices
                legend="Pourquoi le français ?"
                value={watch('learningMotivation')}
                onSelect={(next) => setValue('learningMotivation', next, { shouldValidate: true })}
                options={[
                  { value: 'travel', label: 'Voyager et me débrouiller' },
                  { value: 'work', label: 'Travailler en français' },
                  { value: 'relationships', label: 'Parler avec mes proches' },
                  { value: 'culture', label: 'Lire, regarder, écouter' },
                ]}
              />

              <AuthSegments
                legend="Niveau actuel"
                compact
                value={watch('proficiencyLevel')}
                onSelect={(next) => setValue('proficiencyLevel', next, { shouldValidate: true })}
                options={proficiencyOptions.map((level) => ({ value: level, label: level }))}
              />

              <AuthSegments
                legend="Minutes par jour"
                compact
                value={String(watch('dailyGoalMinutes'))}
                onSelect={(next) =>
                  setValue('dailyGoalMinutes', Number(next) as 5 | 10 | 15 | 20, {
                    shouldValidate: true,
                  })
                }
                options={[
                  { value: '5', label: '5' },
                  { value: '10', label: '10' },
                  { value: '15', label: '15' },
                  { value: '20', label: '20' },
                ]}
              />

              <AuthSegments
                legend="Corrections"
                value={watch('correctionStyle')}
                onSelect={(next) =>
                  setValue('correctionStyle', next as 'lenient' | 'moderate' | 'strict', {
                    shouldValidate: true,
                  })
                }
                options={[
                  { value: 'lenient', label: 'Légère' },
                  { value: 'moderate', label: 'Équilibrée' },
                  { value: 'strict', label: 'Complète' },
                ]}
              />

              <AuthSegments
                legend="À voix haute"
                value={watch('speakingComfort')}
                onSelect={(next) =>
                  setValue('speakingComfort', next as 'warming_up' | 'ready' | 'confident', {
                    shouldValidate: true,
                  })
                }
                options={[
                  { value: 'warming_up', label: 'Je débute' },
                  { value: 'ready', label: 'Je peux répondre' },
                  { value: 'confident', label: 'Poussez-moi' },
                ]}
              />

              <div className="signup-topics">
                <span className="av2-field__label">Sujets qui vous intéressent</span>
                <div className="signup-topics__row">
                  {interestPresets.map((topic) => (
                    <Chip
                      key={topic}
                      tone={selectedTopics.includes(topic) ? 'story' : 'plain'}
                      aria-pressed={selectedTopics.includes(topic)}
                      onClick={() => toggleTopic(topic)}
                    >
                      {topic}
                    </Chip>
                  ))}
                </div>
              </div>

              {errors.learningMotivation?.message && (
                <AuthNotice>{errors.learningMotivation.message}</AuthNotice>
              )}

              <AuthSpacer />

              <Action
                tone="primary"
                type="submit"
                pending={isLoading}
                pendingLabel="Création…"
              >
                Ouvrir ma première édition
              </Action>

              <button type="button" className="av2-btn av2-btn--quiet" onClick={() => setStep(1)}>
                Revenir à l’essentiel
              </button>
            </>
          )}
        </form>
      </AuthScreen>

      <style jsx global>{`
        .av2 .auth-form-v2 {
          display: flex;
          flex: 1 1 auto;
          flex-direction: column;
          gap: 14px;
          min-width: 0;
        }
        .av2 .signup-topics {
          display: flex;
          flex-direction: column;
          gap: 8px;
          min-width: 0;
        }
        .av2 .signup-topics__row {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
        }
      `}</style>
    </>
  );
}
