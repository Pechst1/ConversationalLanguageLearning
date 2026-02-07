import React, { useState, useEffect } from 'react';
import { getSession, signOut } from 'next-auth/react';
import { useRouter } from 'next/router';
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
    Check,
    ChevronRight,
    LogOut,
    Trash2,
    Download,
    Moon,
    Sun,
    Mic,
    Languages,
} from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';

interface UserSettings {
    // Profile
    displayName: string;
    email: string;
    nativeLanguage: string;
    targetLanguage: string;
    proficiencyLevel: string;

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

const languages = [
    { value: 'de', label: 'Deutsch (German)' },
    { value: 'en', label: 'English' },
    { value: 'fr', label: 'Français (French)' },
    { value: 'es', label: 'Español (Spanish)' },
    { value: 'it', label: 'Italiano (Italian)' },
];

interface SettingsPageProps {
    userEmail: string;
    userName: string;
}

type SettingsSection = 'profile' | 'learning' | 'practice' | 'notifications' | 'appearance' | 'audio' | 'privacy';

import { apiService as api } from '@/services/api';

// ... (previous imports)

export default function SettingsPage({ userEmail, userName }: SettingsPageProps) {
    const [settings, setSettings] = useState<UserSettings>({
        ...defaultSettings,
        displayName: userName || '',
        email: userEmail || '',
    });
    const router = useRouter();
    const [activeSection, setActiveSection] = useState<SettingsSection>('profile');
    const [isSaving, setIsSaving] = useState(false);
    const [saveMessage, setSaveMessage] = useState<string | null>(null);
    const [hasChanges, setHasChanges] = useState(false);
    const [isLoading, setIsLoading] = useState(true);

    // Load settings from API on mount
    useEffect(() => {
        const fetchSettings = async () => {
            try {
                const user: any = await api.getCurrentUser();
                setSettings(prev => ({
                    ...prev,
                    displayName: user.full_name || prev.displayName,
                    email: user.email || prev.email,
                    nativeLanguage: user.native_language || prev.nativeLanguage,
                    targetLanguage: user.target_language || prev.targetLanguage,
                    proficiencyLevel: user.proficiency_level || prev.proficiencyLevel,

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

                    theme: (user.theme as any) || prev.theme,
                    fontSize: (user.font_size as any) || prev.fontSize,

                    voiceInputEnabled: user.voice_input_enabled ?? prev.voiceInputEnabled,
                    textToSpeechEnabled: user.text_to_speech_enabled ?? prev.textToSpeechEnabled,
                    ttsSpeed: user.tts_speed ? parseFloat(user.tts_speed) : prev.ttsSpeed,
                    autoPlayPronunciation: user.auto_play_pronunciation ?? prev.autoPlayPronunciation,

                    grammarCorrectionLevel: (user.grammar_correction_level as any) || prev.grammarCorrectionLevel,
                    showGrammarExplanations: user.show_grammar_explanations ?? prev.showGrammarExplanations,
                }));
            } catch (error) {
                console.error('Failed to load user settings:', error);
                // Fallback to defaults or show error
            } finally {
                setIsLoading(false);
            }
        };

        fetchSettings();
    }, []);

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

                theme: settings.theme,
                font_size: settings.fontSize,

                voice_input_enabled: settings.voiceInputEnabled,
                text_to_speech_enabled: settings.textToSpeechEnabled,
                tts_speed: settings.ttsSpeed.toString(),
                auto_play_pronunciation: settings.autoPlayPronunciation,

                grammar_correction_level: settings.grammarCorrectionLevel,
                show_grammar_explanations: settings.showGrammarExplanations,
            };

            await api.updateProfile(payload);

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

        setIsSaving(true);
        try {
            await api.deleteAccount();
            await signOut({ callbackUrl: '/' });
        } catch (error) {
            console.error('Failed to delete account:', error);
            setSaveMessage('Failed to delete account. Please try again.');
            setIsSaving(false);
        }
    };

    const handleNotificationToggle = async (key: keyof UserSettings, value: boolean) => {
        if (key === 'practiceReminders' && value === true) {
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

    const sections = [
        { id: 'profile' as const, label: 'Profile', icon: User },
        { id: 'learning' as const, label: 'Learning', icon: Languages },
        { id: 'practice' as const, label: 'Practice Goals', icon: Target },
        { id: 'notifications' as const, label: 'Notifications', icon: Bell },
        { id: 'appearance' as const, label: 'Appearance', icon: Palette },
        { id: 'audio' as const, label: 'Audio & Voice', icon: Volume2 },
        { id: 'privacy' as const, label: 'Privacy & Data', icon: Shield },
    ];

    return (
        <div className="min-h-screen bg-gray-50 p-6">
            <div className="max-w-6xl mx-auto">
                {/* Header */}
                <div className="mb-8">
                    <h1 className="text-4xl font-black uppercase tracking-tight">Settings</h1>
                    <p className="text-gray-600 mt-2">Customize your learning experience</p>
                </div>

                <div className="flex gap-8">
                    {/* Sidebar Navigation */}
                    <div className="w-64 flex-shrink-0">
                        <Card className="border-4 border-black shadow-[6px_6px_0px_0px_#000] sticky top-6">
                            <CardContent className="p-2">
                                {sections.map((section) => (
                                    <button
                                        key={section.id}
                                        onClick={() => setActiveSection(section.id)}
                                        className={`w-full flex items-center gap-3 px-4 py-3 text-left font-bold transition-all ${activeSection === section.id
                                            ? 'bg-bauhaus-blue text-white'
                                            : 'hover:bg-gray-100'
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
                    <div className="flex-1">
                        {/* Save Banner */}
                        {(hasChanges || saveMessage) && (
                            <div className={`mb-6 p-4 border-4 border-black shadow-[4px_4px_0px_0px_#000] ${saveMessage ? 'bg-green-100' : 'bg-bauhaus-yellow'
                                }`}>
                                <div className="flex items-center justify-between">
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
                                        <p className="text-xs text-gray-500 mt-1">Email cannot be changed</p>
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
                                    </div>

                                    <div className="grid grid-cols-2 gap-6">
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
                                            disabled={isSaving}
                                        >
                                            {isSaving && activeSection === 'privacy' ? 'Deleting...' : 'Delete Account'}
                                        </Button>
                                    </div>
                                </CardContent>
                            </Card>
                        )}
                    </div>
                </div>
            </div>
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
