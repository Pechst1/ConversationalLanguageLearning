import React, { useState, useEffect } from 'react';
import { getSession } from 'next-auth/react';
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
import { appSignOut } from '@/lib/app-auth';

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
    preferredSessionLength: number;

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
    preferredSessionLength: 10,
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
    { value: 'A1', label: 'A1 - Beginner', description: 'Basic phrases and expressions' },
    { value: 'A2', label: 'A2 - Elementary', description: 'Simple everyday communication' },
    { value: 'B1', label: 'B1 - Intermediate', description: 'Handle most travel situations' },
    { value: 'B2', label: 'B2 - Upper Intermediate', description: 'Interact with native speakers' },
    { value: 'C1', label: 'C1 - Advanced', description: 'Complex texts and discussions' },
    { value: 'C2', label: 'C2 - Mastery', description: 'Near-native proficiency' },
];

const cefrSublevels = ['A1.1', 'A1.2', 'A2.1', 'A2.2', 'B1.1', 'B1.2', 'B2.1', 'B2.2'];

const languages = [
    { value: 'de', label: 'Deutsch (German)' },
    { value: 'en', label: 'English' },
    { value: 'fr', label: 'Français (French)' },
    { value: 'es', label: 'Español (Spanish)' },
    { value: 'it', label: 'Italiano (Italian)' },
];

const interestTopicPresets = [
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

interface SettingsPageProps {
    userEmail: string;
    userName: string;
}

type SettingsSection = 'profile' | 'learning' | 'practice' | 'notifications' | 'appearance' | 'audio' | 'privacy';

export default function SettingsPage({ userEmail, userName }: SettingsPageProps) {
    const [settings, setSettings] = useState<UserSettings>({
        ...defaultSettings,
        displayName: userName || '',
        email: userEmail || '',
    });
    const [activeSection, setActiveSection] = useState<SettingsSection>('profile');
    const [isSaving, setIsSaving] = useState(false);
    const [saveMessage, setSaveMessage] = useState<string | null>(null);
    const [hasChanges, setHasChanges] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [customInterestTopic, setCustomInterestTopic] = useState('');
    const [privacyAction, setPrivacyAction] = useState<'export' | 'signout' | 'delete' | null>(null);
    const [passwordForm, setPasswordForm] = useState({ currentPassword: '', newPassword: '' });
    const [emailForm, setEmailForm] = useState({ currentPassword: '', newEmail: '' });

    // Load settings from API on mount
    useEffect(() => {
        const fetchSettings = async () => {
            try {
                const user: any = await api.getSettings();
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
                    defaultVocabDirection: user.default_vocab_direction || prev.defaultVocabDirection,
                    preferredSessionLength: user.preferred_session_time ? 15 : prev.preferredSessionLength, // Approx mapping

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
                // Fallback to defaults or show error
            } finally {
                setIsLoading(false);
            }
        };

        fetchSettings();
    }, []);

    useEffect(() => {
        applyVisualSettings(settings.theme, settings.fontSize);
    }, [settings.fontSize, settings.theme]);

    const updateSetting = <K extends keyof UserSettings>(key: K, value: UserSettings[K]) => {
        setSettings(prev => ({ ...prev, [key]: value }));
        setHasChanges(true);
    };

    const saveSettings = async () => {
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

            setSaveMessage('Settings saved successfully!');
            setHasChanges(false);
            setTimeout(() => setSaveMessage(null), 3000);
        } catch (error) {
            console.error('Failed to save settings:', error);
            setSaveMessage('Failed to save settings');
        } finally {
            setIsSaving(false);
        }
    };

    const handleDeleteAccount = async () => {
        if (!confirm('Are you ABSOLUTELY sure? This action cannot be undone and will permanently delete your account and all data.')) {
            return;
        }

        setPrivacyAction('delete');
        setIsSaving(true);
        try {
            await api.deleteAccount();
            await appSignOut({ callbackUrl: '/' });
        } catch (error) {
            console.error('Failed to delete account:', error);
            setSaveMessage('Failed to delete account. Please try again.');
            setIsSaving(false);
            setPrivacyAction(null);
        }
    };

    const handlePasswordChange = async () => {
        if (!passwordForm.currentPassword || passwordForm.newPassword.length < 8) {
            toast.error('Enter your current password and a new password with at least 8 characters.');
            return;
        }
        setIsSaving(true);
        try {
            await api.changePassword({
                current_password: passwordForm.currentPassword,
                new_password: passwordForm.newPassword,
            });
            setPasswordForm({ currentPassword: '', newPassword: '' });
            toast.success('Password changed. Please sign in again.');
            await appSignOut({ callbackUrl: '/auth/signin' });
        } catch (error) {
            console.error('Failed to change password:', error);
            toast.error('Could not change password.');
        } finally {
            setIsSaving(false);
        }
    };

    const handleEmailChange = async () => {
        if (!emailForm.currentPassword || !emailForm.newEmail) {
            toast.error('Enter a new email and your current password.');
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
            toast.success('Email changed. Please sign in again.');
            await appSignOut({ callbackUrl: '/auth/signin' });
        } catch (error) {
            console.error('Failed to change email:', error);
            toast.error('Could not change email.');
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
            toast.success('Export ready.');
        } catch (error) {
            console.error('Failed to export user data:', error);
            toast.error('Could not export your data.');
        } finally {
            setPrivacyAction(null);
        }
    };

    const handleSignOutAllDevices = async () => {
        if (!confirm('Sign out from every device, including this one?')) return;
        setPrivacyAction('signout');
        try {
            await api.signOutAllDevices();
            toast.success('Signed out everywhere.');
            await appSignOut({ callbackUrl: '/auth/signin' });
        } catch (error) {
            console.error('Failed to sign out all devices:', error);
            toast.error('Could not sign out all devices.');
            setPrivacyAction(null);
        }
    };

    const handleNotificationToggle = async (key: keyof UserSettings, value: boolean) => {
        if ((key === 'practiceReminders' || key === 'serialEditionNotifications') && value === true) {
            // Request permission & subscribe
            if ('serviceWorker' in navigator && 'PushManager' in window) {
                try {
                    const permission = await Notification.requestPermission();
                    if (permission === 'granted') {
                        const loadingToast = toast.loading('Enabling notifications...');

                        const reg = await navigator.serviceWorker.register('/sw.js');
                        // Wait for SW to be ready
                        await navigator.serviceWorker.ready;

                        const { publicKey } = await api.getVapidPublicKey();

                        const sub = await reg.pushManager.subscribe({
                            userVisibleOnly: true,
                            applicationServerKey: urlBase64ToUint8Array(publicKey)
                        });

                        await api.subscribeToNotifications(sub.toJSON());
                        toast.success("Notifications enabled!", { id: loadingToast });
                    } else {
                        toast.error("Permission denied. check browser settings.");
                        return;
                    }
                } catch (e: any) {
                    console.error(e);
                    toast.error("Failed to enable notifications: " + e.message);
                    return;
                }
            } else {
                toast.error("Push notifications not supported in this browser.");
            }
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
        { id: 'profile' as const, label: 'Profile', icon: User },
        { id: 'learning' as const, label: 'Learning', icon: Languages },
        { id: 'practice' as const, label: 'Practice Goals', icon: Target },
        { id: 'notifications' as const, label: 'Notifications', icon: Bell },
        { id: 'appearance' as const, label: 'Appearance', icon: Palette },
        { id: 'audio' as const, label: 'Audio & Voice', icon: Volume2 },
        { id: 'privacy' as const, label: 'Privacy & Data', icon: Shield },
    ];

    if (isLoading) {
        return (
            <div className="settings-page min-h-screen bg-[var(--app-paper)] px-5 py-6 pb-24 sm:p-6">
                <div className="mx-auto max-w-6xl border border-[var(--app-ink)] bg-[var(--app-sheet)] p-6">
                    <div className="text-xs font-black uppercase tracking-[0.16em] text-[var(--app-ink-3)]">Settings</div>
                    <h1 className="mt-2 font-serif text-3xl italic">Loading your account controls...</h1>
                </div>
            </div>
        );
    }

    return (
        <div className="settings-page min-h-screen bg-[var(--app-paper)] px-5 py-6 pb-24 sm:p-6">
            <div className="max-w-6xl mx-auto">
                {/* Header */}
                <div className="mb-8 border-b border-[var(--app-ink)] pb-5">
                    <div className="text-xs font-black uppercase tracking-[0.16em] text-[var(--app-ink-3)]">Administration Layer</div>
                    <h1 className="mt-1 font-serif text-5xl italic leading-none">Settings</h1>
                    <p className="mt-3 max-w-2xl text-[var(--app-ink-2)]">Customize your learning account, appearance, language preferences, notifications, and privacy controls.</p>
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
                                        {saveMessage || 'You have unsaved changes'}
                                    </span>
                                    {!saveMessage && (
                                        <Button
                                            onClick={saveSettings}
                                            disabled={isSaving}
                                            leftIcon={isSaving ? undefined : <Save className="w-4 h-4" />}
                                        >
                                            {isSaving ? 'Saving...' : 'Save Changes'}
                                        </Button>
                                    )}
                                </div>
                            </div>
                        )}

                        {/* Profile Section */}
                        {activeSection === 'profile' && (
                            <Card className="border-4 border-black shadow-[6px_6px_0px_0px_#000]">
                                <CardHeader className="bg-gray-100 border-b-4 border-black">
                                    <CardTitle className="flex items-center gap-2">
                                        <User className="w-6 h-6" /> Profile Settings
                                    </CardTitle>
                                    <CardDescription>Manage your account information</CardDescription>
                                </CardHeader>
                                <CardContent className="p-6 space-y-6">
                                    <div>
                                        <label className="block text-sm font-bold uppercase mb-2">Display Name</label>
                                        <input
                                            type="text"
                                            value={settings.displayName}
                                            onChange={(e) => updateSetting('displayName', e.target.value)}
                                            className="w-full p-3 border-2 border-black shadow-[4px_4px_0px_0px_#000] focus:outline-none focus:shadow-[6px_6px_0px_0px_#000]"
                                            placeholder="Your name"
                                        />
                                    </div>

                                    <div>
                                        <label className="block text-sm font-bold uppercase mb-2">Email</label>
                                        <input
                                            type="email"
                                            value={settings.email}
                                            disabled
                                            className="w-full p-3 border-2 border-gray-300 bg-gray-100 text-gray-500"
                                        />
                                        <p className="text-xs text-gray-500 mt-1">Use the secure form below to change your sign-in email.</p>
                                    </div>

                                    <div className="grid gap-4 border-2 border-black bg-white p-4">
                                        <h3 className="flex items-center gap-2 font-black uppercase">
                                            <Mail className="w-5 h-5" /> Change Email
                                        </h3>
                                        <input
                                            type="email"
                                            value={emailForm.newEmail}
                                            onChange={(event) => setEmailForm((prev) => ({ ...prev, newEmail: event.target.value }))}
                                            className="w-full p-3 border-2 border-black shadow-[4px_4px_0px_0px_#000]"
                                            placeholder="new@email.com"
                                        />
                                        <input
                                            type="password"
                                            value={emailForm.currentPassword}
                                            onChange={(event) => setEmailForm((prev) => ({ ...prev, currentPassword: event.target.value }))}
                                            className="w-full p-3 border-2 border-black shadow-[4px_4px_0px_0px_#000]"
                                            placeholder="Current password"
                                        />
                                        <Button
                                            type="button"
                                            variant="outline"
                                            leftIcon={<Mail className="w-4 h-4" />}
                                            onClick={handleEmailChange}
                                            disabled={isSaving || !emailForm.newEmail || !emailForm.currentPassword}
                                        >
                                            Change Email
                                        </Button>
                                    </div>

                                    <div className="grid gap-4 border-2 border-black bg-white p-4">
                                        <h3 className="flex items-center gap-2 font-black uppercase">
                                            <Lock className="w-5 h-5" /> Change Password
                                        </h3>
                                        <input
                                            type="password"
                                            value={passwordForm.currentPassword}
                                            onChange={(event) => setPasswordForm((prev) => ({ ...prev, currentPassword: event.target.value }))}
                                            className="w-full p-3 border-2 border-black shadow-[4px_4px_0px_0px_#000]"
                                            placeholder="Current password"
                                        />
                                        <input
                                            type="password"
                                            value={passwordForm.newPassword}
                                            onChange={(event) => setPasswordForm((prev) => ({ ...prev, newPassword: event.target.value }))}
                                            className="w-full p-3 border-2 border-black shadow-[4px_4px_0px_0px_#000]"
                                            placeholder="New password"
                                        />
                                        <Button
                                            type="button"
                                            variant="outline"
                                            leftIcon={<Lock className="w-4 h-4" />}
                                            onClick={handlePasswordChange}
                                            disabled={isSaving || !passwordForm.currentPassword || passwordForm.newPassword.length < 8}
                                        >
                                            Change Password
                                        </Button>
                                    </div>
                                </CardContent>
                            </Card>
                        )}

                        {/* Learning Section */}
                        {activeSection === 'learning' && (
                            <Card className="border-4 border-black shadow-[6px_6px_0px_0px_#000]">
                                <CardHeader className="bg-bauhaus-blue text-white border-b-4 border-black">
                                    <CardTitle className="flex items-center gap-2">
                                        <Languages className="w-6 h-6" /> Language Preferences
                                    </CardTitle>
                                    <CardDescription className="text-white/80">Configure your language learning settings</CardDescription>
                                </CardHeader>
                                <CardContent className="p-6 space-y-6">
                                    <div className="grid grid-cols-2 gap-6">
                                        <div>
                                            <label className="block text-sm font-bold uppercase mb-2">Native Language</label>
                                            <select
                                                value={settings.nativeLanguage}
                                                onChange={(e) => updateSetting('nativeLanguage', e.target.value)}
                                                className="w-full p-3 border-2 border-black shadow-[4px_4px_0px_0px_#000] bg-white"
                                            >
                                                {languages.map(lang => (
                                                    <option key={lang.value} value={lang.value}>{lang.label}</option>
                                                ))}
                                            </select>
                                        </div>

                                        <div>
                                            <label className="block text-sm font-bold uppercase mb-2">Learning Language</label>
                                            <select
                                                value={settings.targetLanguage}
                                                onChange={(e) => updateSetting('targetLanguage', e.target.value)}
                                                className="w-full p-3 border-2 border-black shadow-[4px_4px_0px_0px_#000] bg-white"
                                            >
                                                {languages.map(lang => (
                                                    <option key={lang.value} value={lang.value}>{lang.label}</option>
                                                ))}
                                            </select>
                                        </div>
                                    </div>

                                    <div>
                                        <label className="block text-sm font-bold uppercase mb-3">Proficiency Level</label>
                                        <div className="grid grid-cols-2 gap-3">
                                            {proficiencyLevels.map(level => (
                                                <button
                                                    key={level.value}
                                                    onClick={() => updateSetting('proficiencyLevel', level.value)}
                                                    className={`p-4 border-2 border-black text-left transition-all ${settings.proficiencyLevel === level.value
                                                        ? 'bg-bauhaus-blue text-white shadow-[4px_4px_0px_0px_#000]'
                                                        : 'bg-white hover:bg-gray-50'
                                                        }`}
                                                >
                                                    <div className="font-bold">{level.label}</div>
                                                    <div className={`text-xs mt-1 ${settings.proficiencyLevel === level.value ? 'text-white/80' : 'text-gray-500'}`}>
                                                        {level.description}
                                                    </div>
                                                </button>
                                            ))}
                                        </div>
                                    </div>

                                    <div>
                                        <label className="block text-sm font-bold uppercase mb-2">
                                            Live Article Topics
                                        </label>
                                        <p className="text-xs text-gray-500 mb-3">
                                            These topics steer which live article seeds appear in your pre-session picker.
                                        </p>
                                        <div className="flex flex-wrap gap-2 mb-3">
                                            {interestTopicPresets.map((topic) => (
                                                <button
                                                    key={topic}
                                                    type="button"
                                                    onClick={() => toggleInterestTopic(topic)}
                                                    className={`px-3 py-1 border-2 border-black text-sm font-bold ${
                                                        settings.interests.includes(topic)
                                                            ? 'bg-bauhaus-yellow shadow-[2px_2px_0px_0px_#000]'
                                                            : 'bg-white'
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
                                                placeholder="Add custom topic"
                                                className="flex-1 p-3 border-2 border-black shadow-[4px_4px_0px_0px_#000]"
                                            />
                                            <Button
                                                type="button"
                                                variant="outline"
                                                onClick={addCustomInterestTopic}
                                                className="border-2 border-black"
                                            >
                                                Add
                                            </Button>
                                        </div>
                                        {settings.interests.length > 0 && (
                                            <p className="text-xs text-gray-600 mt-2">
                                                Selected: {settings.interests.join(', ')}
                                            </p>
                                        )}
                                    </div>

                                    <div>
                                        <label className="block text-sm font-bold uppercase mb-2">Grammar Correction Level</label>
                                        <div className="flex gap-4">
                                            {(['lenient', 'moderate', 'strict'] as const).map(level => (
                                                <button
                                                    key={level}
                                                    onClick={() => updateSetting('grammarCorrectionLevel', level)}
                                                    className={`flex-1 p-3 border-2 border-black font-bold capitalize ${settings.grammarCorrectionLevel === level
                                                        ? 'bg-bauhaus-yellow shadow-[4px_4px_0px_0px_#000]'
                                                        : 'bg-white'
                                                        }`}
                                                >
                                                    {level}
                                                </button>
                                            ))}
                                        </div>
                                        <p className="text-xs text-gray-500 mt-2">
                                            {settings.grammarCorrectionLevel === 'strict' && 'All errors will be corrected'}
                                            {settings.grammarCorrectionLevel === 'moderate' && 'Major errors will be corrected'}
                                            {settings.grammarCorrectionLevel === 'lenient' && 'Only critical errors will be corrected'}
                                        </p>
                                    </div>

                                    <div className="flex items-center justify-between p-4 bg-gray-50 border-2 border-black">
                                        <div>
                                            <div className="font-bold">Show Grammar Explanations</div>
                                            <div className="text-sm text-gray-500">Display detailed explanations for corrections</div>
                                        </div>
                                        <button
                                            onClick={() => updateSetting('showGrammarExplanations', !settings.showGrammarExplanations)}
                                            className={`w-14 h-8 rounded-full border-2 border-black transition-colors ${settings.showGrammarExplanations ? 'bg-green-500' : 'bg-gray-300'
                                                }`}
                                        >
                                            <div className={`w-6 h-6 bg-white border-2 border-black rounded-full transition-transform ${settings.showGrammarExplanations ? 'translate-x-6' : 'translate-x-0'
                                                }`} />
                                        </button>
                                    </div>
                                </CardContent>
                            </Card>
                        )}

                        {/* Practice Goals Section */}
                        {activeSection === 'practice' && (
                            <Card className="border-4 border-black shadow-[6px_6px_0px_0px_#000]">
                                <CardHeader className="bg-bauhaus-yellow border-b-4 border-black">
                                    <CardTitle className="flex items-center gap-2">
                                        <Target className="w-6 h-6" /> Practice Goals
                                    </CardTitle>
                                    <CardDescription>Set your daily learning targets</CardDescription>
                                </CardHeader>
                                <CardContent className="p-6 space-y-6">
                                    <div className="grid grid-cols-2 gap-6">
                                        <div>
                                            <label className="block text-sm font-bold uppercase mb-2">
                                                Daily Goal (Minutes)
                                            </label>
                                            <input
                                                type="number"
                                                min="5"
                                                max="120"
                                                value={settings.dailyGoalMinutes}
                                                onChange={(e) => updateSetting('dailyGoalMinutes', parseInt(e.target.value) || 15)}
                                                className="w-full p-3 border-2 border-black shadow-[4px_4px_0px_0px_#000]"
                                            />
                                            <div className="flex gap-2 mt-2">
                                                {[5, 10, 15, 30, 60].map(mins => (
                                                    <button
                                                        key={mins}
                                                        onClick={() => updateSetting('dailyGoalMinutes', mins)}
                                                        className={`px-3 py-1 text-sm font-bold border-2 border-black ${settings.dailyGoalMinutes === mins ? 'bg-bauhaus-blue text-white' : 'bg-white'
                                                            }`}
                                                    >
                                                        {mins}m
                                                    </button>
                                                ))}
                                            </div>
                                        </div>

                                        <div>
                                            <label className="block text-sm font-bold uppercase mb-2">
                                                CEFR Target
                                            </label>
                                            <select
                                                value={settings.cefrTargetLevel}
                                                onChange={(e) => updateSetting('cefrTargetLevel', e.target.value)}
                                                className="w-full p-3 border-2 border-black shadow-[4px_4px_0px_0px_#000] bg-white"
                                            >
                                                {cefrSublevels.map((level) => (
                                                    <option key={level} value={level}>{level}</option>
                                                ))}
                                            </select>
                                            <p className="mt-2 text-sm text-gray-600">
                                                The Atelier meter forecasts this target from your daily pace.
                                            </p>
                                        </div>
                                    </div>

                                    <div className="grid grid-cols-2 gap-6">
                                        <div>
                                            <label className="block text-sm font-bold uppercase mb-2">
                                                Daily XP Goal
                                            </label>
                                            <input
                                                type="number"
                                                min="10"
                                                max="500"
                                                step="10"
                                                value={settings.dailyGoalXP}
                                                onChange={(e) => updateSetting('dailyGoalXP', parseInt(e.target.value) || 50)}
                                                className="w-full p-3 border-2 border-black shadow-[4px_4px_0px_0px_#000]"
                                            />
                                            <div className="flex gap-2 mt-2">
                                                {[20, 50, 100, 150, 200].map(xp => (
                                                    <button
                                                        key={xp}
                                                        onClick={() => updateSetting('dailyGoalXP', xp)}
                                                        className={`px-3 py-1 text-sm font-bold border-2 border-black ${settings.dailyGoalXP === xp ? 'bg-bauhaus-blue text-white' : 'bg-white'
                                                            }`}
                                                    >
                                                        {xp}
                                                    </button>
                                                ))}
                                            </div>
                                        </div>

                                        <div>
                                            <label className="block text-sm font-bold uppercase mb-2">
                                                New Words Per Day
                                            </label>
                                            <input
                                                type="number"
                                                min="1"
                                                max="50"
                                                value={settings.newWordsPerDay}
                                                onChange={(e) => updateSetting('newWordsPerDay', parseInt(e.target.value) || 10)}
                                                className="w-full p-3 border-2 border-black shadow-[4px_4px_0px_0px_#000]"
                                            />
                                        </div>

                                        <div>
                                            <label className="block text-sm font-bold uppercase mb-2">
                                                Default Vocabulary Direction
                                            </label>
                                            <select
                                                value={settings.defaultVocabDirection}
                                                onChange={(e) => updateSetting('defaultVocabDirection', e.target.value)}
                                                className="w-full p-3 border-2 border-black shadow-[4px_4px_0px_0px_#000] bg-white"
                                            >
                                                <option value="fr_to_de">French → German</option>
                                                <option value="de_to_fr">German → French</option>
                                                <option value="mixed">Mixed (Both)</option>
                                            </select>
                                        </div>
                                    </div>

                                    <div>
                                        <label className="block text-sm font-bold uppercase mb-2">
                                            Preferred Session Length (Minutes)
                                        </label>
                                        <div className="flex items-center gap-4">
                                            <input
                                                type="range"
                                                min="5"
                                                max="30"
                                                step="5"
                                                value={settings.preferredSessionLength}
                                                onChange={(e) => updateSetting('preferredSessionLength', parseInt(e.target.value))}
                                                className="flex-1 h-3 bg-gray-200 rounded-full appearance-none cursor-pointer"
                                            />
                                            <span className="font-bold text-xl w-16 text-center">
                                                {settings.preferredSessionLength}m
                                            </span>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        )}

                        {/* Notifications Section */}
                        {activeSection === 'notifications' && (
                            <Card className="border-4 border-black shadow-[6px_6px_0px_0px_#000]">
                                <CardHeader className="bg-bauhaus-red text-white border-b-4 border-black">
                                    <CardTitle className="flex items-center gap-2">
                                        <Bell className="w-6 h-6" /> Notifications
                                    </CardTitle>
                                    <CardDescription className="text-white/80">Manage your notification preferences</CardDescription>
                                </CardHeader>
                                <CardContent className="p-6 space-y-4">
                                    {[
                                        { key: 'practiceReminders' as const, label: 'Practice Reminders', desc: 'Get reminded to practice daily' },
                                        { key: 'streakNotifications' as const, label: 'Streak Alerts', desc: 'Notifications about your streak status' },
                                        { key: 'weeklyEmailSummary' as const, label: 'Weekly Email Summary', desc: 'Receive weekly progress reports' },
                                        { key: 'achievementNotifications' as const, label: 'Achievement Alerts', desc: 'Get notified when you earn achievements' },
                                        { key: 'serialEditionNotifications' as const, label: 'Serial Edition Alerts', desc: 'Get tomorrow’s serial edition when it is ready' },
                                    ].map(item => (
                                        <div key={item.key} className="flex items-center justify-between p-4 bg-gray-50 border-2 border-black">
                                            <div>
                                                <div className="font-bold">{item.label}</div>
                                                <div className="text-sm text-gray-500">{item.desc}</div>
                                            </div>
                                            <button
                                                onClick={() => handleNotificationToggle(item.key, !settings[item.key])}
                                                className={`w-14 h-8 rounded-full border-2 border-black transition-colors ${settings[item.key] ? 'bg-green-500' : 'bg-gray-300'
                                                    }`}
                                            >
                                                <div className={`w-6 h-6 bg-white border-2 border-black rounded-full transition-transform ${settings[item.key] ? 'translate-x-6' : 'translate-x-0'
                                                    }`} />
                                            </button>
                                        </div>
                                    ))}

                                    {settings.practiceReminders && (
                                        <div className="p-4 bg-white border-2 border-black">
                                            <label className="block text-sm font-bold uppercase mb-2">Reminder Time</label>
                                            <input
                                                type="time"
                                                value={settings.reminderTime}
                                                onChange={(e) => updateSetting('reminderTime', e.target.value)}
                                                className="p-3 border-2 border-black"
                                            />
                                        </div>
                                    )}
                                </CardContent>
                            </Card>
                        )}

                        {/* Appearance Section */}
                        {activeSection === 'appearance' && (
                            <Card className="border-4 border-black shadow-[6px_6px_0px_0px_#000]">
                                <CardHeader className="bg-purple-600 text-white border-b-4 border-black">
                                    <CardTitle className="flex items-center gap-2">
                                        <Palette className="w-6 h-6" /> Appearance
                                    </CardTitle>
                                    <CardDescription className="text-white/80">Customize how the app looks</CardDescription>
                                </CardHeader>
                                <CardContent className="p-6 space-y-6">
                                    <div>
                                        <label className="block text-sm font-bold uppercase mb-3">Theme</label>
                                        <div className="grid grid-cols-3 gap-4">
                                            {[
                                                { value: 'light' as const, label: 'Light', icon: Sun },
                                                { value: 'dark' as const, label: 'Dark', icon: Moon },
                                                { value: 'system' as const, label: 'System', icon: Palette },
                                            ].map(theme => (
                                                <button
                                                    key={theme.value}
                                                    onClick={() => updateSetting('theme', theme.value)}
                                                    className={`p-4 border-2 border-black flex flex-col items-center gap-2 ${settings.theme === theme.value
                                                        ? 'bg-bauhaus-blue text-white shadow-[4px_4px_0px_0px_#000]'
                                                        : 'bg-white'
                                                        }`}
                                                >
                                                    <theme.icon className="w-8 h-8" />
                                                    <span className="font-bold">{theme.label}</span>
                                                </button>
                                            ))}
                                        </div>
                                    </div>

                                    <div>
                                        <label className="block text-sm font-bold uppercase mb-3">Font Size</label>
                                        <div className="grid grid-cols-3 gap-4">
                                            {[
                                                { value: 'small' as const, label: 'Small', size: 'text-sm' },
                                                { value: 'medium' as const, label: 'Medium', size: 'text-base' },
                                                { value: 'large' as const, label: 'Large', size: 'text-lg' },
                                            ].map(size => (
                                                <button
                                                    key={size.value}
                                                    onClick={() => updateSetting('fontSize', size.value)}
                                                    className={`p-4 border-2 border-black ${size.size} ${settings.fontSize === size.value
                                                        ? 'bg-bauhaus-yellow shadow-[4px_4px_0px_0px_#000]'
                                                        : 'bg-white'
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
                            <Card className="border-4 border-black shadow-[6px_6px_0px_0px_#000]">
                                <CardHeader className="bg-green-600 text-white border-b-4 border-black">
                                    <CardTitle className="flex items-center gap-2">
                                        <Volume2 className="w-6 h-6" /> Audio & Voice
                                    </CardTitle>
                                    <CardDescription className="text-white/80">Configure voice and audio settings</CardDescription>
                                </CardHeader>
                                <CardContent className="p-6 space-y-4">
                                    {[
                                        { key: 'voiceInputEnabled' as const, label: 'Voice Input', desc: 'Enable microphone for speaking practice', icon: Mic },
                                        { key: 'textToSpeechEnabled' as const, label: 'Text-to-Speech', desc: 'Hear pronunciations of words', icon: Volume2 },
                                        { key: 'autoPlayPronunciation' as const, label: 'Auto-play Pronunciation', desc: 'Automatically play word audio' },
                                    ].map(item => (
                                        <div key={item.key} className="flex items-center justify-between p-4 bg-gray-50 border-2 border-black">
                                            <div className="flex items-center gap-3">
                                                {item.icon && <item.icon className="w-5 h-5 text-gray-600" />}
                                                <div>
                                                    <div className="font-bold">{item.label}</div>
                                                    <div className="text-sm text-gray-500">{item.desc}</div>
                                                </div>
                                            </div>
                                            <button
                                                onClick={() => updateSetting(item.key, !settings[item.key])}
                                                className={`w-14 h-8 rounded-full border-2 border-black transition-colors ${settings[item.key] ? 'bg-green-500' : 'bg-gray-300'
                                                    }`}
                                            >
                                                <div className={`w-6 h-6 bg-white border-2 border-black rounded-full transition-transform ${settings[item.key] ? 'translate-x-6' : 'translate-x-0'
                                                    }`} />
                                            </button>
                                        </div>
                                    ))}

                                    <div className="p-4 bg-white border-2 border-black">
                                        <label className="block text-sm font-bold uppercase mb-3">Speech Speed</label>
                                        <div className="flex items-center gap-4">
                                            <span className="text-sm font-bold">Slow</span>
                                            <input
                                                type="range"
                                                min="0.5"
                                                max="1.5"
                                                step="0.1"
                                                value={settings.ttsSpeed}
                                                onChange={(e) => updateSetting('ttsSpeed', parseFloat(e.target.value))}
                                                className="flex-1 h-3 bg-gray-200 rounded-full appearance-none cursor-pointer"
                                            />
                                            <span className="text-sm font-bold">Fast</span>
                                            <span className="font-bold text-lg w-12 text-center">{settings.ttsSpeed}x</span>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        )}

                        {/* Privacy Section */}
                        {activeSection === 'privacy' && (
                            <Card className="border-4 border-black shadow-[6px_6px_0px_0px_#000]">
                                <CardHeader className="bg-gray-800 text-white border-b-4 border-black">
                                    <CardTitle className="flex items-center gap-2">
                                        <Shield className="w-6 h-6" /> Privacy & Data
                                    </CardTitle>
                                    <CardDescription className="text-white/80">Manage your data and privacy settings</CardDescription>
                                </CardHeader>
                                <CardContent className="p-6 space-y-6">
                                    <div className="p-4 bg-blue-50 border-2 border-blue-300">
                                        <h3 className="font-bold mb-2 flex items-center gap-2">
                                            <Download className="w-5 h-5" /> Export Your Data
                                        </h3>
                                        <p className="text-sm text-gray-600 mb-4">
                                            Download all your learning data including vocabulary, progress, and achievements.
                                        </p>
                                        <Button
                                            variant="outline"
                                            leftIcon={<Download className="w-4 h-4" />}
                                            className="border-2 border-black"
                                            onClick={handleExportData}
                                            loading={privacyAction === 'export'}
                                        >
                                            Export Data (JSON)
                                        </Button>
                                    </div>

                                    <div className="p-4 bg-yellow-50 border-2 border-yellow-400">
                                        <h3 className="font-bold mb-2 flex items-center gap-2">
                                            <LogOut className="w-5 h-5" /> Sign Out Everywhere
                                        </h3>
                                        <p className="text-sm text-gray-600 mb-4">
                                            Sign out from all devices and sessions.
                                        </p>
                                        <Button
                                            variant="outline"
                                            className="border-2 border-black"
                                            onClick={handleSignOutAllDevices}
                                            loading={privacyAction === 'signout'}
                                        >
                                            Sign Out All Devices
                                        </Button>
                                    </div>

                                    <div className="p-4 bg-red-50 border-2 border-red-400">
                                        <h3 className="font-bold mb-2 text-red-700 flex items-center gap-2">
                                            <Trash2 className="w-5 h-5" /> Danger Zone
                                        </h3>
                                        <p className="text-sm text-gray-600 mb-4">
                                            Permanently delete your account and all associated data. This action cannot be undone.
                                        </p>
                                        <Button
                                            variant="outline"
                                            className="border-2 border-red-500 text-red-600 hover:bg-red-100"
                                            onClick={handleDeleteAccount}
                                            loading={privacyAction === 'delete'}
                                            disabled={isSaving && privacyAction !== 'delete'}
                                        >
                                            Delete Account
                                        </Button>
                                    </div>
                                </CardContent>
                            </Card>
                        )}
                    </div>
                </div>
            </div>
            <style jsx global>{`
                .settings-page .learning-card {
                    border-width: 1px !important;
                    box-shadow: none !important;
                    background: var(--app-sheet);
                }
                .settings-page .border-4,
                .settings-page .border-2 {
                    border-width: 1px !important;
                }
                .settings-page [class*="shadow-"] {
                    box-shadow: none !important;
                }
                .settings-page input,
                .settings-page select,
                .settings-page textarea {
                    background: var(--app-sheet) !important;
                    color: var(--app-ink);
                }
                .settings-page .bg-white,
                .settings-page .bg-gray-50,
                .settings-page .bg-gray-100 {
                    background: var(--app-sheet) !important;
                }
                .settings-page .text-black,
                .settings-page h1,
                .settings-page h2,
                .settings-page h3 {
                    color: var(--app-ink) !important;
                }
                .settings-page .text-gray-500,
                .settings-page .text-gray-600 {
                    color: var(--app-ink-3) !important;
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

export async function getServerSideProps(context: any) {
    const session = await getSession(context);

    if (!session) {
        return {
            redirect: {
                destination: '/auth/signin',
                permanent: false,
            },
        };
    }

    return {
        props: {
            userEmail: session.user?.email || '',
            userName: session.user?.name || '',
        },
    };
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
