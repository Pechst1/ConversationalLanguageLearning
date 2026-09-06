import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import { Capacitor } from '@capacitor/core';
import toast from 'react-hot-toast';
import {
    User,
    Globe,
    Target,
    Bell,
    Palette,
    Volume2,
    Shield,
    Save,
    LogOut,
    Trash2,
    Download,
    Moon,
    Sun,
    Mic,
    Languages,
    Lock,
    Mail,
} from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import {
    applyVisualSettings,
    persistVisualSettings,
    type AppFontSize,
    type AppTheme,
} from '@/lib/app-preferences';
import { apiService as api } from '@/services/api';
import { appSignOut, useAppSession } from '@/lib/app-auth';
import { nativePushIsAvailable, registerNativePushToken } from '@/lib/native-push';

interface UserSettings {
    // Profile
    displayName: string;
    email: string;
    nativeLanguage: string;
    targetLanguage: string;
    proficiencyLevel: string;
    cefrTargetLevel: string;
    interests: string[];

    // Learning Goals
    dailyGoalMinutes: number;
    dailyGoalXP: number;
    newWordsPerDay: number;
    defaultVocabDirection: string;

    // Notifications
    practiceReminders: boolean;
    reminderTime: string;
    streakNotifications: boolean;
    weeklyEmailSummary: boolean;
    achievementNotifications: boolean;
    serialEditionNotifications: boolean;

    // Appearance
    theme: 'light' | 'dark' | 'system';
    fontSize: 'small' | 'medium' | 'large';

    // Audio
    voiceInputEnabled: boolean;
    textToSpeechEnabled: boolean;
    ttsSpeed: number;
    autoPlayPronunciation: boolean;

    // Grammar
    grammarCorrectionLevel: 'strict' | 'moderate' | 'lenient';
    showGrammarExplanations: boolean;
}

const defaultSettings: UserSettings = {
    displayName: '',
    email: '',
    nativeLanguage: 'de',
    targetLanguage: 'fr',
    proficiencyLevel: 'A1',
    cefrTargetLevel: 'A1.2',
    interests: [],
    dailyGoalMinutes: 15,
    dailyGoalXP: 50,
    newWordsPerDay: 10,
    defaultVocabDirection: 'fr_to_de',
    practiceReminders: true,
    reminderTime: '09:00',
    streakNotifications: true,
    weeklyEmailSummary: true,
    achievementNotifications: true,
    serialEditionNotifications: true,
    theme: 'system',
    fontSize: 'medium',
    voiceInputEnabled: true,
    textToSpeechEnabled: true,
    ttsSpeed: 1.0,
    autoPlayPronunciation: true,
    grammarCorrectionLevel: 'moderate',
    showGrammarExplanations: true,
};

const proficiencyLevels = [
    { value: 'A1', label: 'A1 · Début', description: 'Phrases et expressions essentielles' },
    { value: 'A2', label: 'A2 · Élémentaire', description: 'Échanges simples du quotidien' },
    { value: 'B1', label: 'B1 · Intermédiaire', description: 'Se débrouiller dans la plupart des situations' },
    { value: 'B2', label: 'B2 · Indépendant', description: 'Échanger avec spontanéité' },
    { value: 'C1', label: 'C1 · Avancé', description: 'Textes et discussions complexes' },
    { value: 'C2', label: 'C2 · Maîtrise', description: 'Aisance proche d’un locuteur natif' },
];

const cefrSublevels = ['A1.1', 'A1.2', 'A2.1', 'A2.2', 'B1.1', 'B1.2', 'B2.1', 'B2.2'];

const languages = [
    { value: 'de', label: 'Allemand' },
    { value: 'en', label: 'Anglais' },
    { value: 'fr', label: 'Français' },
    { value: 'es', label: 'Espagnol' },
    { value: 'it', label: 'Italien' },
];

// The vocabulary table only stores German, English and French glosses, so the
// card direction can only ever pair French with German or English. This list
// used to be hardcoded to the German pair: an English native (the signup
// default) was shown "Français → allemand" and, worse, the save payload then
// carried their stored `fr_to_en` into a schema that rejected it — every save
// on this page returned 422. Options now follow the langue d'appui.
const glossLanguages: Record<string, { label: string; lowercase: string }> = {
    de: { label: 'Allemand', lowercase: 'allemand' },
    en: { label: 'Anglais', lowercase: 'anglais' },
};

function glossLanguageFor(nativeLanguage: string) {
    return nativeLanguage === 'de' ? 'de' : 'en';
}

function vocabDirectionOptions(nativeLanguage: string) {
    const code = glossLanguageFor(nativeLanguage);
    const { label, lowercase } = glossLanguages[code];
    return [
        { value: `fr_to_${code}`, label: `Français → ${lowercase}` },
        { value: `${code}_to_fr`, label: `${label} → français` },
        { value: 'mixed', label: 'Alterné' },
    ];
}

// Keep a stored direction on the pair the langue d'appui actually supports,
// preserving which way round the learner reads their cards.
function normalizeVocabDirection(direction: string, nativeLanguage: string) {
    const code = glossLanguageFor(nativeLanguage);
    if (direction === 'mixed') return 'mixed';
    if (vocabDirectionOptions(nativeLanguage).some((option) => option.value === direction)) {
        return direction;
    }
    return direction.endsWith('_to_fr') ? `${code}_to_fr` : `fr_to_${code}`;
}

const interestTopicPresets = [
    'technologie',
    'travail',
    'voyage',
    'sport',
    'politique',
    'sciences',
    'culture',
    'économie',
    'santé',
    'cuisine',
];

interface SettingsPageProps {
    userEmail?: string;
    userName?: string;
}

type SettingsSection = 'profile' | 'learning' | 'practice' | 'notifications' | 'appearance' | 'audio' | 'privacy';

export default function SettingsPage({ userEmail, userName }: SettingsPageProps) {
    const router = useRouter();
    const { data: session } = useAppSession();
    const [settings, setSettings] = useState<UserSettings>({
        ...defaultSettings,
        displayName: userName || session?.user?.name || '',
        email: userEmail || session?.user?.email || '',
    });
    const [activeSection, setActiveSection] = useState<SettingsSection>('profile');
    const [isSaving, setIsSaving] = useState(false);
    const [saveMessage, setSaveMessage] = useState<string | null>(null);
    const [hasChanges, setHasChanges] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [settingsLoadError, setSettingsLoadError] = useState<string | null>(null);
    const [settingsReloadKey, setSettingsReloadKey] = useState(0);
    const [customInterestTopic, setCustomInterestTopic] = useState('');
    const [privacyAction, setPrivacyAction] = useState<'export' | 'signout' | 'delete' | null>(null);
    const [passwordForm, setPasswordForm] = useState({ currentPassword: '', newPassword: '' });
    const [emailForm, setEmailForm] = useState({ currentPassword: '', newEmail: '' });
    const [isAdmin, setIsAdmin] = useState(false);

    useEffect(() => {
        if (!router.isReady) return;
        const requested = String(router.query.section || '');
        if (['profile', 'learning', 'practice', 'notifications', 'appearance', 'audio', 'privacy'].includes(requested)) {
            setActiveSection(requested as SettingsSection);
        }
    }, [router.isReady, router.query.section]);

    useEffect(() => {
        setSettings((prev) => ({
            ...prev,
            displayName: prev.displayName || session?.user?.name || '',
            email: prev.email || session?.user?.email || '',
        }));
    }, [session?.user?.email, session?.user?.name]);

    // Load settings from API on mount
    useEffect(() => {
        const fetchSettings = async () => {
            setIsLoading(true);
            setSettingsLoadError(null);
            try {
                const user: any = await api.getSettings();
                setIsAdmin(user.role === 'admin');
                const loadedTheme = (user.theme || 'system') as AppTheme;
                const loadedFontSize = (user.font_size || 'medium') as AppFontSize;
                setSettings(prev => ({
                    ...prev,
                    displayName: user.full_name || prev.displayName,
                    email: user.email || prev.email,
                    nativeLanguage: user.native_language || prev.nativeLanguage,
                    targetLanguage: user.target_language || prev.targetLanguage,
                    proficiencyLevel: user.proficiency_level || prev.proficiencyLevel,
                    cefrTargetLevel: user.cefr_target_level || prev.cefrTargetLevel,
                    interests: (user.interests || '')
                        .split(',')
                        .map((value: string) => value.trim())
                        .filter(Boolean),

                    dailyGoalMinutes: user.daily_goal_minutes || prev.dailyGoalMinutes,
                    dailyGoalXP: user.daily_goal_xp || prev.dailyGoalXP,
                    newWordsPerDay: user.new_words_per_day || prev.newWordsPerDay,
                    defaultVocabDirection: normalizeVocabDirection(
                        user.default_vocab_direction || prev.defaultVocabDirection,
                        user.native_language || prev.nativeLanguage,
                    ),

                    practiceReminders: user.practice_reminders ?? prev.practiceReminders,
                    reminderTime: user.reminder_time || prev.reminderTime,
                    streakNotifications: user.streak_notifications ?? prev.streakNotifications,
                    weeklyEmailSummary: user.weekly_email_summary ?? prev.weeklyEmailSummary,
                    achievementNotifications: user.achievement_notifications ?? prev.achievementNotifications,
                    serialEditionNotifications: user.serial_edition_notifications ?? prev.serialEditionNotifications,

                    theme: loadedTheme,
                    fontSize: loadedFontSize,

                    voiceInputEnabled: user.voice_input_enabled ?? prev.voiceInputEnabled,
                    textToSpeechEnabled: user.text_to_speech_enabled ?? prev.textToSpeechEnabled,
                    ttsSpeed: user.tts_speed ? parseFloat(user.tts_speed) : prev.ttsSpeed,
                    autoPlayPronunciation: user.auto_play_pronunciation ?? prev.autoPlayPronunciation,

                    grammarCorrectionLevel: (user.grammar_correction_level as any) || prev.grammarCorrectionLevel,
                    showGrammarExplanations: user.show_grammar_explanations ?? prev.showGrammarExplanations,
                }));
                persistVisualSettings(loadedTheme, loadedFontSize);
            } catch (error) {
                console.error('Failed to load user settings:', error);
                setSettingsLoadError('Votre dossier n’a pas pu être chargé. Réessayez avant de modifier vos préférences.');
            } finally {
                setIsLoading(false);
            }
        };

        fetchSettings();
    }, [settingsReloadKey]);

    useEffect(() => {
        applyVisualSettings(settings.theme, settings.fontSize);
    }, [settings.fontSize, settings.theme]);

    const updateSetting = <K extends keyof UserSettings>(key: K, value: UserSettings[K]) => {
        setSettings(prev => ({ ...prev, [key]: value }));
        setHasChanges(true);
    };

    // Changing the langue d'appui changes which gloss pair exists, so carry the
    // card direction across instead of leaving a value no option can match.
    const updateNativeLanguage = (nativeLanguage: string) => {
        setSettings(prev => ({
            ...prev,
            nativeLanguage,
            defaultVocabDirection: normalizeVocabDirection(prev.defaultVocabDirection, nativeLanguage),
        }));
        setHasChanges(true);
    };

    const saveSettings = async () => {
        if (settingsLoadError) {
            toast.error('Rechargez le dossier avant de classer les modifications.');
            return;
        }
        setIsSaving(true);
        try {
            // Map frontend settings to backend payload
            const payload = {
                full_name: settings.displayName,
                native_language: settings.nativeLanguage,
                target_language: settings.targetLanguage,
                proficiency_level: settings.proficiencyLevel,
                cefr_target_level: settings.cefrTargetLevel,
                interests: settings.interests.join(','),

                daily_goal_minutes: settings.dailyGoalMinutes,
                daily_goal_xp: settings.dailyGoalXP,
                new_words_per_day: settings.newWordsPerDay,
                default_vocab_direction: settings.defaultVocabDirection,

                notifications_enabled: true, // Master switch implicitly true if specific ones are used
                practice_reminders: settings.practiceReminders,
                reminder_time: settings.reminderTime,
                streak_notifications: settings.streakNotifications,
                weekly_email_summary: settings.weeklyEmailSummary,
                achievement_notifications: settings.achievementNotifications,
                serial_edition_notifications: settings.serialEditionNotifications,

                theme: settings.theme,
                font_size: settings.fontSize,

                voice_input_enabled: settings.voiceInputEnabled,
                text_to_speech_enabled: settings.textToSpeechEnabled,
                tts_speed: settings.ttsSpeed.toString(),
                auto_play_pronunciation: settings.autoPlayPronunciation,

                grammar_correction_level: settings.grammarCorrectionLevel,
                show_grammar_explanations: settings.showGrammarExplanations,
            };

            await api.updateSettings(payload);
            persistVisualSettings(settings.theme, settings.fontSize);

            setSaveMessage('Modifications classées.');
            setHasChanges(false);
            setTimeout(() => setSaveMessage(null), 3000);
        } catch (error: any) {
            console.error('Failed to save settings:', error);
            // A rejected field used to vanish behind one generic line, which is
            // how an unsavable direction went unnoticed. Name the field.
            const detail = error?.response?.data?.detail;
            const rejected = Array.isArray(detail)
                ? Array.from(new Set(detail.map((item: any) => String(item?.loc?.[1] || '')).filter(Boolean)))
                : [];
            setSaveMessage(
                rejected.length
                    ? `Les modifications n’ont pas pu être classées : ${rejected.join(', ')}.`
                    : 'Les modifications n’ont pas pu être classées.',
            );
        } finally {
            setIsSaving(false);
        }
    };

    const handleDeleteAccount = async () => {
        if (!confirm('Supprimer définitivement ce compte et toutes ses données ? Cette action est irréversible.')) {
            return;
        }

        setPrivacyAction('delete');
        setIsSaving(true);
        try {
            await api.deleteAccount();
            await appSignOut({ callbackUrl: '/' });
        } catch (error) {
            console.error('Failed to delete account:', error);
            setSaveMessage('Le compte n’a pas pu être supprimé. Réessayez.');
            setIsSaving(false);
            setPrivacyAction(null);
        }
    };

    const handlePasswordChange = async () => {
        if (!passwordForm.currentPassword || passwordForm.newPassword.length < 8) {
            toast.error('Saisissez votre mot de passe actuel et un nouveau mot de passe d’au moins 8 caractères.');
            return;
        }
        setIsSaving(true);
        try {
            await api.changePassword({
                current_password: passwordForm.currentPassword,
                new_password: passwordForm.newPassword,
            });
            setPasswordForm({ currentPassword: '', newPassword: '' });
            toast.success('Mot de passe modifié. Reconnectez-vous.');
            await appSignOut({ callbackUrl: '/auth/signin' });
        } catch (error) {
            console.error('Failed to change password:', error);
            toast.error('Le mot de passe n’a pas pu être modifié.');
        } finally {
            setIsSaving(false);
        }
    };

    const handleEmailChange = async () => {
        if (!emailForm.currentPassword || !emailForm.newEmail) {
            toast.error('Saisissez la nouvelle adresse et votre mot de passe actuel.');
            return;
        }
        setIsSaving(true);
        try {
            const updated: any = await api.changeEmail({
                current_password: emailForm.currentPassword,
                new_email: emailForm.newEmail,
            });
            setSettings((prev) => ({ ...prev, email: updated.email || emailForm.newEmail }));
            setEmailForm({ currentPassword: '', newEmail: '' });
            toast.success('Adresse modifiée. Reconnectez-vous.');
            await appSignOut({ callbackUrl: '/auth/signin' });
        } catch (error) {
            console.error('Failed to change email:', error);
            toast.error('L’adresse n’a pas pu être modifiée.');
        } finally {
            setIsSaving(false);
        }
    };

    const handleExportData = async () => {
        setPrivacyAction('export');
        try {
            const data = await api.exportUserData();
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = `atelier-export-${new Date().toISOString().slice(0, 10)}.json`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(url);
            toast.success('Archive prête.');
        } catch (error) {
            console.error('Failed to export user data:', error);
            toast.error('L’archive n’a pas pu être préparée.');
        } finally {
            setPrivacyAction(null);
        }
    };

    const handleSignOutAllDevices = async () => {
        if (!confirm('Fermer toutes les sessions, y compris celle-ci ?')) return;
        setPrivacyAction('signout');
        try {
            await api.signOutAllDevices();
            toast.success('Toutes les sessions sont fermées.');
            await appSignOut({ callbackUrl: '/auth/signin' });
        } catch (error) {
            console.error('Failed to sign out all devices:', error);
            toast.error('Les sessions n’ont pas pu être fermées.');
            setPrivacyAction(null);
        }
    };

    const enableDeviceNotifications = async (): Promise<boolean> => {
        if (Capacitor.isNativePlatform()) {
            if (!nativePushIsAvailable()) {
                toast.error('Les notifications ne sont pas disponibles dans cette version iPhone.');
                return false;
            }
            const loadingToast = toast.loading('Connexion des notifications iPhone…');
            try {
                const token = await registerNativePushToken();
                await api.subscribeToNativeNotifications(token);
                toast.success('Notifications iPhone reliées.', { id: loadingToast });
                return true;
            } catch (error: any) {
                console.error(error);
                toast.error(error?.message || 'Les notifications iPhone n’ont pas pu être reliées.', { id: loadingToast });
                return false;
            }
        }
        if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
            toast.error('Ce navigateur ne prend pas en charge les notifications.');
            return false;
        }
        const loadingToast = toast.loading('Connexion des notifications…');
        try {
            const permission = await Notification.requestPermission();
            if (permission !== 'granted') {
                toast.error('Permission refusée. Vérifiez les réglages de cet appareil.', { id: loadingToast });
                return false;
            }
            const reg = await navigator.serviceWorker.register('/sw.js');
            await navigator.serviceWorker.ready;
            const { publicKey } = await api.getVapidPublicKey();
            if (!publicKey?.trim()) {
                toast.error('Les notifications ne sont pas encore configurées.', { id: loadingToast });
                return false;
            }
            const sub = await reg.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: urlBase64ToUint8Array(publicKey),
            });
            await api.subscribeToNotifications(sub.toJSON());
            toast.success('Notifications reliées.', { id: loadingToast });
            return true;
        } catch (error: any) {
            console.error(error);
            toast.error(`Connexion impossible : ${error?.message || 'erreur inconnue'}`, { id: loadingToast });
            return false;
        }
    };

    const handleNotificationToggle = async (key: keyof UserSettings, value: boolean) => {
        if (
            (key === 'practiceReminders' || key === 'serialEditionNotifications')
            && value === true
            && !(await enableDeviceNotifications())
        ) {
            return;
        }
        updateSetting(key, value);
    };

    const toggleInterestTopic = (topic: string) => {
        const normalized = topic.trim().toLowerCase();
        if (!normalized) return;
        const next = settings.interests.includes(normalized)
            ? settings.interests.filter((item) => item !== normalized)
            : [...settings.interests, normalized];
        updateSetting('interests', next);
    };

    const addCustomInterestTopic = () => {
        const normalized = customInterestTopic.trim().toLowerCase();
        if (!normalized) return;
        if (settings.interests.includes(normalized)) {
            setCustomInterestTopic('');
            return;
        }
        updateSetting('interests', [...settings.interests, normalized]);
        setCustomInterestTopic('');
    };

    const sections = [
        { id: 'profile' as const, label: 'Dossier', icon: User },
        { id: 'learning' as const, label: 'Langues', icon: Languages },
        { id: 'practice' as const, label: 'Rythme', icon: Target },
        { id: 'notifications' as const, label: 'Notifications', icon: Bell },
        { id: 'appearance' as const, label: 'Apparence', icon: Palette },
        { id: 'audio' as const, label: 'Voix', icon: Volume2 },
        { id: 'privacy' as const, label: 'Données', icon: Shield },
    ];

    if (isLoading) {
        return (
            <div className="settings-page min-h-screen bg-[var(--app-paper)] px-5 py-6 pb-24 sm:p-6">
                <div className="mx-auto max-w-6xl border border-[var(--app-ink)] bg-[var(--app-sheet)] p-6">
                    <div className="text-xs font-black uppercase tracking-[0.16em] text-[var(--app-ink-3)]">L’administration</div>
                    <h1 className="mt-2 font-serif text-3xl italic">Ouverture de votre dossier…</h1>
                </div>
            </div>
        );
    }

    if (settingsLoadError) {
        return (
            <div className="settings-page min-h-screen bg-[var(--app-paper)] px-5 py-6 pb-24 sm:p-6">
                <div className="mx-auto max-w-2xl border border-[var(--app-ink)] bg-[var(--app-sheet)] p-6">
                    <div className="text-xs font-black uppercase tracking-[0.16em] text-[var(--app-blue)]">Dossier indisponible</div>
                    <h1 className="mt-2 font-serif text-3xl italic leading-tight">Vos réglages n’ont pas pu être chargés.</h1>
                    <p className="mt-3 text-sm font-semibold leading-6 text-[var(--app-ink-2)]">{settingsLoadError}</p>
                    <Button className="mt-5" onClick={() => setSettingsReloadKey((value) => value + 1)}>
                        Réessayer
                    </Button>
                </div>
            </div>
        );
    }

    return (
        <div className="settings-page min-h-screen bg-[var(--app-paper)] px-5 py-6 pb-24 sm:p-6">
            <div className="max-w-6xl mx-auto">
                {/* Header */}
                <div className="mb-8 border-b border-[var(--app-ink)] pb-5">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                        <div className="text-xs font-black uppercase tracking-[0.16em] text-[var(--app-ink-3)]">DOSSIER DU LECTEUR</div>
                        {isAdmin && (
                            <button
                                type="button"
                                onClick={() => void router.push('/pilot-ops')}
                                className="border border-[var(--app-ink)] bg-[var(--app-sheet)] px-3 py-2 text-[10px] font-black uppercase tracking-[0.14em]"
                            >
                                Pilotage · coût & qualité
                            </button>
                        )}
                    </div>
                    <h1 className="mt-1 font-serif text-5xl italic leading-none">L’administration</h1>
                    <p className="mt-3 max-w-2xl text-[var(--app-ink-2)]">Votre langue, votre rythme, la livraison de l’édition et les archives du compte.</p>
                </div>

                <div className="flex flex-col gap-6 lg:flex-row lg:gap-8">
                    {/* Sidebar Navigation */}
                    <div className="w-full flex-shrink-0 lg:w-64">
                        <Card className="sticky top-20">
                            <CardContent className="flex gap-2 overflow-x-auto p-2 lg:block lg:space-y-1 lg:overflow-visible">
                                {sections.map((section) => (
                                    <button
                                        key={section.id}
                                        onClick={() => setActiveSection(section.id)}
                                        className={`flex min-w-[156px] items-center gap-3 border border-transparent px-4 py-3 text-left text-xs font-black uppercase tracking-[0.08em] transition-colors lg:w-full ${activeSection === section.id
                                            ? 'border-[var(--app-ink)] bg-[var(--app-ink)] text-[var(--app-paper)]'
                                            : 'text-[var(--app-ink-2)] hover:border-[var(--app-ink)] hover:bg-[var(--app-paper-2)]'
                                            }`}
                                    >
                                        <section.icon className="w-5 h-5" />
                                        {section.label}
                                    </button>
                                ))}
                            </CardContent>
                        </Card>
                    </div>

                    {/* Main Content */}
                    <div className="min-w-0 flex-1">
                        {/* Save Banner */}
                        {(hasChanges || saveMessage) && (
                            <div className={`mb-6 border border-[var(--app-ink)] p-4 ${saveMessage ? 'bg-[var(--app-sheet)]' : 'bg-[var(--app-yellow)]'
                                }`}>
                                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                                    <span className="font-bold">
                                        {saveMessage || 'Des modifications attendent d’être classées'}
                                    </span>
                                    {!saveMessage && (
                                        <Button
                                            onClick={saveSettings}
                                            disabled={isSaving}
                                            leftIcon={isSaving ? undefined : <Save className="w-4 h-4" />}
                                        >
                                            {isSaving ? 'Classement…' : 'Classer les modifications'}
                                        </Button>
                                    )}
                                </div>
                            </div>
                        )}

                        {/* Profile Section */}
                        {activeSection === 'profile' && (
                            <Card className="border border-[var(--app-ink)]">
                                <CardHeader className="bg-[var(--app-paper-2)] border-b border-[var(--app-ink)]">
                                    <CardTitle className="flex items-center gap-2">
                                        <User className="w-6 h-6" /> Votre dossier
                                    </CardTitle>
                                    <CardDescription>Identité et accès à votre édition</CardDescription>
                                </CardHeader>
                                <CardContent className="p-6 space-y-6">
                                    <div>
                                        <label className="block text-sm font-bold uppercase mb-2">Nom affiché</label>
                                        <input
                                            type="text"
                                            value={settings.displayName}
                                            onChange={(e) => updateSetting('displayName', e.target.value)}
                                            className="w-full p-3 border border-[var(--app-ink)] bg-[var(--app-sheet)] focus:outline-none focus:border-[var(--app-blue)]"
                                            placeholder="Votre nom"
                                        />
                                    </div>

                                    <div>
                                        <label className="block text-sm font-bold uppercase mb-2">Email</label>
                                        <div
                                            className="w-full min-h-[52px] p-3 border border-[var(--app-paper-3)] bg-[var(--app-paper-2)] text-[var(--app-ink-2)] break-all"
                                            title={settings.email}
                                        >
                                            {settings.email}
                                        </div>
                                        <p className="text-xs text-[var(--app-ink-3)] mt-1">Utilisez le formulaire sécurisé pour modifier votre adresse de connexion.</p>
                                    </div>

                                    <div className="grid gap-4 border border-[var(--app-ink)] bg-[var(--app-sheet)] p-4">
                                        <h3 className="flex items-center gap-2 font-black uppercase">
                                            <Mail className="w-5 h-5" /> Modifier l’adresse
                                        </h3>
                                        <input
                                            type="email"
                                            value={emailForm.newEmail}
                                            onChange={(event) => setEmailForm((prev) => ({ ...prev, newEmail: event.target.value }))}
                                            className="w-full p-3 border border-[var(--app-ink)]"
                                            placeholder="new@email.com"
                                        />
                                        <input
                                            type="password"
                                            value={emailForm.currentPassword}
                                            onChange={(event) => setEmailForm((prev) => ({ ...prev, currentPassword: event.target.value }))}
                                            className="w-full p-3 border border-[var(--app-ink)]"
                                            placeholder="Mot de passe actuel"
                                        />
                                        <Button
                                            type="button"
                                            variant="outline"
                                            leftIcon={<Mail className="w-4 h-4" />}
                                            onClick={handleEmailChange}
                                            disabled={isSaving || !emailForm.newEmail || !emailForm.currentPassword}
                                        >
                                            Enregistrer la nouvelle adresse
                                        </Button>
                                    </div>

                                    <div className="grid gap-4 border border-[var(--app-ink)] bg-[var(--app-sheet)] p-4">
                                        <h3 className="flex items-center gap-2 font-black uppercase">
                                            <Lock className="w-5 h-5" /> Modifier le mot de passe
                                        </h3>
                                        <input
                                            type="password"
                                            value={passwordForm.currentPassword}
                                            onChange={(event) => setPasswordForm((prev) => ({ ...prev, currentPassword: event.target.value }))}
                                            className="w-full p-3 border border-[var(--app-ink)]"
                                            placeholder="Mot de passe actuel"
                                        />
                                        <input
                                            type="password"
                                            value={passwordForm.newPassword}
                                            onChange={(event) => setPasswordForm((prev) => ({ ...prev, newPassword: event.target.value }))}
                                            className="w-full p-3 border border-[var(--app-ink)]"
                                            placeholder="Nouveau mot de passe"
                                        />
                                        <Button
                                            type="button"
                                            variant="outline"
                                            leftIcon={<Lock className="w-4 h-4" />}
                                            onClick={handlePasswordChange}
                                            disabled={isSaving || !passwordForm.currentPassword || passwordForm.newPassword.length < 8}
                                        >
                                            Enregistrer le nouveau mot de passe
                                        </Button>
                                    </div>
                                </CardContent>
                            </Card>
                        )}

                        {/* Learning Section */}
                        {activeSection === 'learning' && (
                            <Card className="border border-[var(--app-ink)]">
                                <CardHeader className="bg-[var(--app-blue)] text-[var(--app-paper)] border-b border-[var(--app-ink)]">
                                    <CardTitle className="flex items-center gap-2">
                                        <Languages className="w-6 h-6" /> Langues de travail
                                    </CardTitle>
                                    <CardDescription>Le français appris et votre langue d’appui</CardDescription>
                                </CardHeader>
                                <CardContent className="p-6 space-y-6">
                                    <div className="grid grid-cols-2 gap-6">
                                        <div>
                                            <label className="block text-sm font-bold uppercase mb-2">Langue d’appui</label>
                                            <select
                                                value={settings.nativeLanguage}
                                                onChange={(e) => updateNativeLanguage(e.target.value)}
                                                className="w-full p-3 border border-[var(--app-ink)] bg-[var(--app-sheet)]"
                                            >
                                                {languages.map(lang => (
                                                    <option key={lang.value} value={lang.value}>{lang.label}</option>
                                                ))}
                                            </select>
                                        </div>

                                        <div>
                                            <label className="block text-sm font-bold uppercase mb-2">Langue apprise</label>
                                            <select
                                                value={settings.targetLanguage}
                                                onChange={(e) => updateSetting('targetLanguage', e.target.value)}
                                                className="w-full p-3 border border-[var(--app-ink)] bg-[var(--app-sheet)]"
                                            >
                                                {languages.map(lang => (
                                                    <option key={lang.value} value={lang.value}>{lang.label}</option>
                                                ))}
                                            </select>
                                        </div>
                                    </div>

                                    <div>
                                        <label className="block text-sm font-bold uppercase mb-3">Niveau actuel</label>
                                        <div className="grid grid-cols-2 gap-3">
                                            {proficiencyLevels.map(level => (
                                                <button
                                                    key={level.value}
                                                    onClick={() => updateSetting('proficiencyLevel', level.value)}
                                                    className={`p-4 border border-[var(--app-ink)] text-left transition-all ${settings.proficiencyLevel === level.value
                                                        ? 'bg-[var(--app-blue)] text-[var(--app-paper)]'
                                                        : 'bg-[var(--app-sheet)] hover:bg-[var(--app-paper-2)]'
                                                        }`}
                                                >
                                                    <div className="font-bold">{level.label}</div>
                                                    <div className={`text-xs mt-1 ${settings.proficiencyLevel === level.value ? 'text-[var(--app-paper)]/80' : 'text-[var(--app-ink-3)]'}`}>
                                                        {level.description}
                                                    </div>
                                                </button>
                                            ))}
                                        </div>
                                    </div>

                                    <div>
                                        <label className="block text-sm font-bold uppercase mb-2">
                                            Sujets de la rédaction
                                        </label>
                                        <p className="text-xs text-[var(--app-ink-3)] mb-3">
                                            Ces sujets orientent les articles proposés avant une séance.
                                        </p>
                                        <div className="flex flex-wrap gap-2 mb-3">
                                            {interestTopicPresets.map((topic) => (
                                                <button
                                                    key={topic}
                                                    type="button"
                                                    onClick={() => toggleInterestTopic(topic)}
                                                    className={`px-3 py-1 border border-[var(--app-ink)] text-sm font-bold ${
                                                        settings.interests.includes(topic)
                                                            ? 'bg-[var(--app-yellow)]'
                                                            : 'bg-[var(--app-sheet)]'
                                                    }`}
                                                >
                                                    {topic}
                                                </button>
                                            ))}
                                        </div>
                                        <div className="flex gap-2">
                                            <input
                                                type="text"
                                                value={customInterestTopic}
                                                onChange={(event) => setCustomInterestTopic(event.target.value)}
                                                placeholder="Ajouter un sujet"
                                                className="flex-1 p-3 border border-[var(--app-ink)]"
                                            />
                                            <Button
                                                type="button"
                                                variant="outline"
                                                onClick={addCustomInterestTopic}
                                                className="border border-[var(--app-ink)]"
                                            >
                                                Ajouter
                                            </Button>
                                        </div>
                                        {settings.interests.length > 0 && (
                                            <p className="text-xs text-[var(--app-ink-2)] mt-2">
                                                Retenus : {settings.interests.join(', ')}
                                            </p>
                                        )}
                                    </div>

                                    <div>
                                        <label className="block text-sm font-bold uppercase mb-2">Intensité des corrections</label>
                                        <div className="flex gap-4">
                                            {(['lenient', 'moderate', 'strict'] as const).map(level => (
                                                <button
                                                    key={level}
                                                    onClick={() => updateSetting('grammarCorrectionLevel', level)}
                                                    className={`flex-1 p-3 border border-[var(--app-ink)] font-bold capitalize ${settings.grammarCorrectionLevel === level
                                                        ? 'bg-[var(--app-yellow)]'
                                                        : 'bg-[var(--app-sheet)]'
                                                        }`}
                                                >
                                                    {{ lenient: 'Légère', moderate: 'Équilibrée', strict: 'Complète' }[level]}
                                                </button>
                                            ))}
                                        </div>
                                        <p className="text-xs text-[var(--app-ink-3)] mt-2">
                                            {settings.grammarCorrectionLevel === 'strict' && 'Toutes les formes seront corrigées.'}
                                            {settings.grammarCorrectionLevel === 'moderate' && 'Les erreurs importantes seront corrigées.'}
                                            {settings.grammarCorrectionLevel === 'lenient' && 'Seules les erreurs qui gênent le sens seront corrigées.'}
                                        </p>
                                    </div>

                                    <div className="flex items-center justify-between p-4 bg-[var(--app-paper-2)] border border-[var(--app-ink)]">
                                        <div>
                                            <div className="font-bold">Afficher les explications</div>
                                            <div className="text-sm text-[var(--app-ink-3)]">Joindre une note détaillée à chaque correction</div>
                                        </div>
                                        <button
                                            onClick={() => updateSetting('showGrammarExplanations', !settings.showGrammarExplanations)}
                                            className={`w-14 h-8 rounded-full border border-[var(--app-ink)] transition-colors ${settings.showGrammarExplanations ? 'bg-[var(--app-green)]' : 'bg-[var(--app-paper-3)]'
                                                }`}
                                        >
                                            <div className={`w-6 h-6 bg-[var(--app-sheet)] border border-[var(--app-ink)] rounded-full transition-transform ${settings.showGrammarExplanations ? 'translate-x-6' : 'translate-x-0'
                                                }`} />
                                        </button>
                                    </div>
                                </CardContent>
                            </Card>
                        )}

                        {/* Practice Goals Section */}
                        {activeSection === 'practice' && (
                            <Card className="border border-[var(--app-ink)]">
                                <CardHeader className="bg-[var(--app-yellow)] border-b border-[var(--app-ink)]">
                                    <CardTitle className="flex items-center gap-2">
                                        <Target className="w-6 h-6" /> Rythme de l’édition
                                    </CardTitle>
                                    <CardDescription>Réglez le format de votre rendez-vous quotidien</CardDescription>
                                </CardHeader>
                                <CardContent className="p-6 space-y-6">
                                    <div className="grid grid-cols-2 gap-6">
                                        <div>
                                            <label className="block text-sm font-bold uppercase mb-2">
                                                Temps quotidien
                                            </label>
                                            <input
                                                type="number"
                                                min="5"
                                                max="120"
                                                value={settings.dailyGoalMinutes}
                                                onChange={(e) => updateSetting('dailyGoalMinutes', parseInt(e.target.value) || 15)}
                                                className="w-full p-3 border border-[var(--app-ink)]"
                                            />
                                            <div className="flex gap-2 mt-2">
                                                {[5, 10, 15, 30, 60].map(mins => (
                                                    <button
                                                        key={mins}
                                                        onClick={() => updateSetting('dailyGoalMinutes', mins)}
                                                        className={`px-3 py-1 text-sm font-bold border border-[var(--app-ink)] ${settings.dailyGoalMinutes === mins ? 'bg-[var(--app-blue)] text-[var(--app-paper)]' : 'bg-[var(--app-sheet)]'
                                                            }`}
                                                    >
                                                        {mins}m
                                                    </button>
                                                ))}
                                            </div>
                                        </div>

                                        <div>
                                            <label className="block text-sm font-bold uppercase mb-2">
                                                Objectif CECRL
                                            </label>
                                            <select
                                                value={settings.cefrTargetLevel}
                                                onChange={(e) => updateSetting('cefrTargetLevel', e.target.value)}
                                                className="w-full p-3 border border-[var(--app-ink)] bg-[var(--app-sheet)]"
                                            >
                                                {cefrSublevels.map((level) => (
                                                    <option key={level} value={level}>{level}</option>
                                                ))}
                                            </select>
                                            <p className="mt-2 text-sm text-[var(--app-ink-2)]">
                                                L’Atelier estime l’échéance selon votre rythme réel.
                                            </p>
                                        </div>
                                    </div>

                                    <div className="grid grid-cols-2 gap-6">
                                        <div>
                                            <label className="block text-sm font-bold uppercase mb-2">
                                                Repère XP quotidien
                                            </label>
                                            <input
                                                type="number"
                                                min="10"
                                                max="500"
                                                step="10"
                                                value={settings.dailyGoalXP}
                                                onChange={(e) => updateSetting('dailyGoalXP', parseInt(e.target.value) || 50)}
                                                className="w-full p-3 border border-[var(--app-ink)]"
                                            />
                                            <div className="flex gap-2 mt-2">
                                                {[20, 50, 100, 150, 200].map(xp => (
                                                    <button
                                                        key={xp}
                                                        onClick={() => updateSetting('dailyGoalXP', xp)}
                                                        className={`px-3 py-1 text-sm font-bold border border-[var(--app-ink)] ${settings.dailyGoalXP === xp ? 'bg-[var(--app-blue)] text-[var(--app-paper)]' : 'bg-[var(--app-sheet)]'
                                                            }`}
                                                    >
                                                        {xp}
                                                    </button>
                                                ))}
                                            </div>
                                        </div>

                                        <div>
                                            <label className="block text-sm font-bold uppercase mb-2">
                                                Nouveaux mots par jour
                                            </label>
                                            <input
                                                type="number"
                                                min="1"
                                                max="50"
                                                value={settings.newWordsPerDay}
                                                onChange={(e) => updateSetting('newWordsPerDay', parseInt(e.target.value) || 10)}
                                                className="w-full p-3 border border-[var(--app-ink)]"
                                            />
                                        </div>

                                        <div>
                                            <label className="block text-sm font-bold uppercase mb-2">
                                                Sens des cartes
                                            </label>
                                            <select
                                                value={settings.defaultVocabDirection}
                                                onChange={(e) => updateSetting('defaultVocabDirection', e.target.value)}
                                                className="w-full p-3 border border-[var(--app-ink)] bg-[var(--app-sheet)]"
                                            >
                                                {vocabDirectionOptions(settings.nativeLanguage).map((option) => (
                                                    <option key={option.value} value={option.value}>{option.label}</option>
                                                ))}
                                            </select>
                                            {!glossLanguages[settings.nativeLanguage] && (
                                                <p className="mt-2 text-xs text-[var(--app-ink-3)]">
                                                    Les traductions du lexique n’existent qu’en allemand et en anglais ;
                                                    l’anglais sert d’appui pour les autres langues.
                                                </p>
                                            )}
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        )}

                        {/* Notifications Section */}
                        {activeSection === 'notifications' && (
                            <Card className="border border-[var(--app-ink)]">
                                <CardHeader className="bg-[var(--app-red)] text-[var(--app-paper)] border-b border-[var(--app-ink)]">
                                    <CardTitle className="flex items-center gap-2">
                                        <Bell className="w-6 h-6" /> Livraison de l’édition
                                    </CardTitle>
                                    <CardDescription>Choisissez quand la rédaction peut vous prévenir</CardDescription>
                                </CardHeader>
                                <CardContent className="p-6 space-y-4">
                                    <div className="border-2 border-[var(--app-ink)] bg-[var(--app-yellow)] p-4">
                                        <div className="font-serif text-2xl italic">Recevoir l’édition sur cet appareil</div>
                                        <p className="mt-1 text-sm text-[var(--app-ink-2)]">
                                            Reliez cet iPhone ou ce navigateur une seule fois, même si vos préférences sont déjà actives.
                                        </p>
                                        <Button
                                            type="button"
                                            className="mt-4"
                                            leftIcon={<Bell className="h-4 w-4" />}
                                            onClick={() => void enableDeviceNotifications()}
                                        >
                                            Relier cet appareil
                                        </Button>
                                    </div>
                                    {[
                                        { key: 'practiceReminders' as const, label: 'Rappel de l’édition', desc: 'Un rappel quotidien à l’heure choisie' },
                                        { key: 'streakNotifications' as const, label: 'Série en cours', desc: 'Un signal quand votre série peut être prolongée' },
                                        { key: 'weeklyEmailSummary' as const, label: 'Relevé hebdomadaire', desc: 'Un bilan de progression chaque semaine' },
                                        { key: 'achievementNotifications' as const, label: 'Distinctions', desc: 'Un avis lorsqu’une distinction est classée' },
                                        { key: 'serialEditionNotifications' as const, label: 'Feuilleton', desc: 'La prochaine parution dès qu’elle est prête' },
                                    ].map(item => (
                                        <div key={item.key} className="flex items-center justify-between p-4 bg-[var(--app-paper-2)] border border-[var(--app-ink)]">
                                            <div>
                                                <div className="font-bold">{item.label}</div>
                                                <div className="text-sm text-[var(--app-ink-3)]">{item.desc}</div>
                                            </div>
                                            <button
                                                onClick={() => handleNotificationToggle(item.key, !settings[item.key])}
                                                className={`w-14 h-8 rounded-full border border-[var(--app-ink)] transition-colors ${settings[item.key] ? 'bg-[var(--app-green)]' : 'bg-[var(--app-paper-3)]'
                                                    }`}
                                            >
                                                <div className={`w-6 h-6 bg-[var(--app-sheet)] border border-[var(--app-ink)] rounded-full transition-transform ${settings[item.key] ? 'translate-x-6' : 'translate-x-0'
                                                    }`} />
                                            </button>
                                        </div>
                                    ))}

                                    {settings.practiceReminders && (
                                        <div className="p-4 bg-[var(--app-sheet)] border border-[var(--app-ink)]">
                                            <label className="block text-sm font-bold uppercase mb-2">Heure de livraison</label>
                                            <input
                                                type="time"
                                                value={settings.reminderTime}
                                                onChange={(e) => updateSetting('reminderTime', e.target.value)}
                                                className="p-3 border border-[var(--app-ink)]"
                                            />
                                        </div>
                                    )}
                                </CardContent>
                            </Card>
                        )}

                        {/* Appearance Section */}
                        {activeSection === 'appearance' && (
                            <Card className="border border-[var(--app-ink)]">
                                <CardHeader className="bg-[var(--app-ink)] text-[var(--app-paper)] border-b border-[var(--app-ink)]">
                                    <CardTitle className="flex items-center gap-2">
                                        <Palette className="w-6 h-6" /> Apparence de la publication
                                    </CardTitle>
                                    <CardDescription>Papier, encre et taille de lecture</CardDescription>
                                </CardHeader>
                                <CardContent className="p-6 space-y-6">
                                    <div>
                                        <label className="block text-sm font-bold uppercase mb-3">Papier</label>
                                        <div className="grid grid-cols-3 gap-4">
                                            {[
                                                { value: 'light' as const, label: 'Clair', icon: Sun },
                                                { value: 'dark' as const, label: 'Sombre', icon: Moon },
                                                { value: 'system' as const, label: 'Système', icon: Palette },
                                            ].map(theme => (
                                                <button
                                                    key={theme.value}
                                                    onClick={() => updateSetting('theme', theme.value)}
                                                    className={`p-4 border border-[var(--app-ink)] flex flex-col items-center gap-2 ${settings.theme === theme.value
                                                        ? 'bg-[var(--app-blue)] text-[var(--app-paper)]'
                                                        : 'bg-[var(--app-sheet)]'
                                                        }`}
                                                >
                                                    <theme.icon className="w-8 h-8" />
                                                    <span className="font-bold">{theme.label}</span>
                                                </button>
                                            ))}
                                        </div>
                                    </div>

                                    <div>
                                        <label className="block text-sm font-bold uppercase mb-3">Corps du texte</label>
                                        <div className="grid grid-cols-3 gap-4">
                                            {[
                                                { value: 'small' as const, label: 'Petit', size: 'text-sm' },
                                                { value: 'medium' as const, label: 'Moyen', size: 'text-base' },
                                                { value: 'large' as const, label: 'Grand', size: 'text-lg' },
                                            ].map(size => (
                                                <button
                                                    key={size.value}
                                                    onClick={() => updateSetting('fontSize', size.value)}
                                                    className={`p-4 border border-[var(--app-ink)] ${size.size} ${settings.fontSize === size.value
                                                        ? 'bg-[var(--app-yellow)]'
                                                        : 'bg-[var(--app-sheet)]'
                                                        }`}
                                                >
                                                    <span className="font-bold">{size.label}</span>
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        )}

                        {/* Audio Section */}
                        {activeSection === 'audio' && (
                            <Card className="border border-[var(--app-ink)]">
                                <CardHeader className="bg-green-600 text-[var(--app-paper)] border-b border-[var(--app-ink)]">
                                    <CardTitle className="flex items-center gap-2">
                                        <Volume2 className="w-6 h-6" /> Le Studio
                                    </CardTitle>
                                    <CardDescription>Micro, lecture et vitesse de la voix</CardDescription>
                                </CardHeader>
                                <CardContent className="p-6 space-y-4">
                                    {[
                                        { key: 'voiceInputEnabled' as const, label: 'Micro', desc: 'Autoriser la pratique parlée', icon: Mic },
                                        { key: 'textToSpeechEnabled' as const, label: 'Lecture à voix haute', desc: 'Écouter la prononciation des mots', icon: Volume2 },
                                        { key: 'autoPlayPronunciation' as const, label: 'Lecture automatique', desc: 'Lancer le son du mot sans geste supplémentaire' },
                                    ].map(item => (
                                        <div key={item.key} className="flex items-center justify-between p-4 bg-[var(--app-paper-2)] border border-[var(--app-ink)]">
                                            <div className="flex items-center gap-3">
                                                {item.icon && <item.icon className="w-5 h-5 text-[var(--app-ink-2)]" />}
                                                <div>
                                                    <div className="font-bold">{item.label}</div>
                                                    <div className="text-sm text-[var(--app-ink-3)]">{item.desc}</div>
                                                </div>
                                            </div>
                                            <button
                                                onClick={() => updateSetting(item.key, !settings[item.key])}
                                                className={`w-14 h-8 rounded-full border border-[var(--app-ink)] transition-colors ${settings[item.key] ? 'bg-[var(--app-green)]' : 'bg-[var(--app-paper-3)]'
                                                    }`}
                                            >
                                                <div className={`w-6 h-6 bg-[var(--app-sheet)] border border-[var(--app-ink)] rounded-full transition-transform ${settings[item.key] ? 'translate-x-6' : 'translate-x-0'
                                                    }`} />
                                            </button>
                                        </div>
                                    ))}

                                    <div className="p-4 bg-[var(--app-sheet)] border border-[var(--app-ink)]">
                                        <label className="block text-sm font-bold uppercase mb-3">Vitesse de lecture</label>
                                        <div className="flex items-center gap-4">
                                            <span className="text-sm font-bold">Lente</span>
                                            <input
                                                type="range"
                                                min="0.5"
                                                max="1.5"
                                                step="0.1"
                                                value={settings.ttsSpeed}
                                                onChange={(e) => updateSetting('ttsSpeed', parseFloat(e.target.value))}
                                                className="flex-1 h-3 bg-[var(--app-paper-3)] rounded-full appearance-none cursor-pointer"
                                            />
                                            <span className="text-sm font-bold">Rapide</span>
                                            <span className="font-bold text-lg w-12 text-center">{settings.ttsSpeed}x</span>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        )}

                        {/* Privacy Section */}
                        {activeSection === 'privacy' && (
                            <Card className="border border-[var(--app-ink)]">
                                <CardHeader className="bg-[var(--app-ink)] text-[var(--app-paper)] border-b border-[var(--app-ink)]">
                                    <CardTitle className="flex items-center gap-2">
                                        <Shield className="w-6 h-6" /> Archives & données
                                    </CardTitle>
                                    <CardDescription>Exporter, fermer les sessions ou supprimer le dossier</CardDescription>
                                </CardHeader>
                                <CardContent className="p-6 space-y-6">
                                    <div className="p-4 border-2 border-[var(--app-blue)]" style={{ background: 'rgb(var(--app-blue-rgb) / 0.10)' }}>
                                        <h3 className="font-bold mb-2 flex items-center gap-2">
                                            <Download className="w-5 h-5" /> Exporter vos archives
                                        </h3>
                                        <p className="text-sm text-[var(--app-ink-2)] mb-4">
                                            Téléchargez votre vocabulaire, votre progression et vos distinctions.
                                        </p>
                                        <Button
                                            variant="outline"
                                            leftIcon={<Download className="w-4 h-4" />}
                                            className="border border-[var(--app-ink)]"
                                            onClick={handleExportData}
                                            loading={privacyAction === 'export'}
                                        >
                                            Préparer l’archive JSON
                                        </Button>
                                    </div>

                                    <div className="p-4 border-2 border-[var(--app-yellow)]" style={{ background: 'rgb(var(--app-yellow-rgb) / 0.15)' }}>
                                        <h3 className="font-bold mb-2 flex items-center gap-2">
                                            <LogOut className="w-5 h-5" /> Fermer toutes les sessions
                                        </h3>
                                        <p className="text-sm text-[var(--app-ink-2)] mb-4">
                                            Déconnectez tous les appareils reliés à votre dossier.
                                        </p>
                                        <Button
                                            variant="outline"
                                            className="border border-[var(--app-ink)]"
                                            onClick={handleSignOutAllDevices}
                                            loading={privacyAction === 'signout'}
                                        >
                                            Tout déconnecter
                                        </Button>
                                    </div>

                                    <div className="p-4 border-2 border-[var(--app-red)]" style={{ background: 'rgb(var(--app-red-rgb) / 0.10)' }}>
                                        <h3 className="font-bold mb-2 text-[var(--app-red)] flex items-center gap-2">
                                            <Trash2 className="w-5 h-5" /> Suppression définitive
                                        </h3>
                                        <p className="text-sm text-[var(--app-ink-2)] mb-4">
                                            Supprimez le compte et toutes ses données. Cette action est irréversible.
                                        </p>
                                        <Button
                                            variant="outline"
                                            className="border-2 border-[var(--app-red)] text-[var(--app-red)]"
                                            onClick={handleDeleteAccount}
                                            loading={privacyAction === 'delete'}
                                            disabled={isSaving && privacyAction !== 'delete'}
                                        >
                                            Supprimer le compte
                                        </Button>
                                    </div>
                                </CardContent>
                            </Card>
                        )}
                    </div>
                </div>
            </div>
            <style jsx global>{`
                /* What survives of the old override block: everything else in
                   it existed only to beat hardcoded neo-brutalist utilities
                   (bg-white, border-black, #000 offset shadows) with
                   !important. Those utilities are theme tokens now, so the
                   overrides had nothing left to fight — and several of their
                   selectors had become meaningless after the rename. */
                .settings-page input,
                .settings-page select,
                .settings-page textarea {
                    background: var(--app-sheet);
                    color: var(--app-ink);
                }
                .settings-page .learning-card > div:first-child {
                    font-family: var(--app-serif);
                }
                @media (max-width: 760px) {
                    .settings-page {
                        padding-top: 22px;
                    }
                    .settings-page .learning-card {
                        padding: 0;
                    }
                }
            `}</style>
        </div>
    );
}

function urlBase64ToUint8Array(base64String: string) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding)
        .replace(/-/g, '+')
        .replace(/_/g, '/');

    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);

    for (let i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
}
