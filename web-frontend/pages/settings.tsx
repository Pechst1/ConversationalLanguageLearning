/* Réglages — the design's SETTINGS SHEET artboard (Atelier App.dc.html,
 * `data-screen-label="Réglages"`), composed as a page because the app reaches
 * it from the masthead gear rather than as an overlay.
 *
 * Verbatim from the artboard: the kicker "Prénom · A2" over the one Garamond
 * italic headline; a card "Temps par édition · n min" with a segmented control
 * of 40px buttons (active = ink face, paper label, 3px press; inactive = paper
 * face, line-2 press); cards of list rows separated by hairlines with a 48×28
 * pill toggle (blue on, line-2 off, 22px paper knob), "Rappel" and "Compte"
 * rows. The design prints a streak headline and seven week squares; neither
 * exists in the settings payload, so the headline is "Réglages" and the week
 * row is not drawn.
 *
 * Everything the page did before is still here — every section, control,
 * dialog and `?section=` anchor — only the presentation moved. The two
 * confirmations use the system `Dialog` through a promise helper that keeps
 * the literal `confirm('…')` call sites, because that is what the safety guard
 * in tests/test_core_mobile_edge_flows.py reads.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';
import { Capacitor } from '@capacitor/core';
import toast from 'react-hot-toast';
import {
    Action,
    AtelierV2Root,
    Chip,
    Dialog,
    Notice,
    ShapeToken,
    Skeleton,
    StateBlock,
} from '@/components/atelier-v2/ui';
import {
    readListenFirst,
    writeListenFirst,
} from '@/components/atelier-v2/journey/story-episode-model';
import {
    applyVisualSettings,
    persistVisualSettings,
    type AppFontSize,
    type AppTheme,
} from '@/lib/app-preferences';
import { resolveSettingsLanguage, settingsCopy, type SettingsCopy } from '@/lib/settings-copy';
import { INTEREST_TOPICS, interestTopicKey, interestTopicLabel } from '@/lib/interest-topics';
import { apiService as api, type AddressPreference } from '@/services/api';
import { appSignOut, useAppSession } from '@/lib/app-auth';
import { nativePushIsAvailable, registerNativePushToken } from '@/lib/native-push';
import { FEEDBACK_OPEN_EVENT } from '@/components/feedback/FeedbackWidget';

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

    // How the feuilleton addresses the reader
    addressPreference: AddressPreference;
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
    addressPreference: 'neutral',
};

// The récit has to agree with the reader in French. Rather than guess, the reader
// says so once here; 'neutral' asks the story to avoid gendered forms entirely.
// The *choice* is French grammar; the words that offer it are the learner's.
function addressOptions(copy: SettingsCopy): { value: AddressPreference; label: string }[] {
    return [
        { value: 'feminine', label: copy.address_feminine },
        { value: 'masculine', label: copy.address_masculine },
        { value: 'neutral', label: copy.address_neutral },
    ];
}

function addressHint(copy: SettingsCopy, preference: AddressPreference): string {
    if (preference === 'feminine') return copy.address_feminine_hint;
    if (preference === 'masculine') return copy.address_masculine_hint;
    return copy.address_neutral_hint;
}

// The CEFR code is data — it is printed exactly as the account holds it. Only
// the word beside it, and the line under it, belong to the learner's language.
function proficiencyLevels(copy: SettingsCopy) {
    return [
        { value: 'A1', label: `A1 · ${copy.level_a1_name}`, description: copy.level_a1_hint },
        { value: 'A2', label: `A2 · ${copy.level_a2_name}`, description: copy.level_a2_hint },
        { value: 'B1', label: `B1 · ${copy.level_b1_name}`, description: copy.level_b1_hint },
        { value: 'B2', label: `B2 · ${copy.level_b2_name}`, description: copy.level_b2_hint },
        { value: 'C1', label: `C1 · ${copy.level_c1_name}`, description: copy.level_c1_hint },
        { value: 'C2', label: `C2 · ${copy.level_c2_name}`, description: copy.level_c2_hint },
    ];
}

const cefrSublevels = ['A1.1', 'A1.2', 'A2.1', 'A2.2', 'B1.1', 'B1.2', 'B2.1', 'B2.2'];

function languageOptions(copy: SettingsCopy) {
    return [
        { value: 'de', label: copy.language_de },
        { value: 'en', label: copy.language_en },
        { value: 'fr', label: copy.language_fr },
        { value: 'es', label: copy.language_es },
        { value: 'it', label: copy.language_it },
    ];
}

// The vocabulary table only stores German, English and French glosses, so the
// card direction can only ever pair French with German or English. This list
// used to be hardcoded to the German pair: an English native (the signup
// default) was shown "Français → allemand" and, worse, the save payload then
// carried their stored `fr_to_en` into a schema that rejected it — every save
// on this page returned 422. Options now follow the langue d'appui.
const GLOSS_LANGUAGES = ['de', 'en'];

function glossLanguageFor(nativeLanguage: string) {
    return nativeLanguage === 'de' ? 'de' : 'en';
}

/** The values the schema accepts — labels are a separate, translated concern. */
function vocabDirectionValues(nativeLanguage: string) {
    const code = glossLanguageFor(nativeLanguage);
    return [`fr_to_${code}`, `${code}_to_fr`, 'mixed'];
}

function vocabDirectionOptions(nativeLanguage: string, copy: SettingsCopy) {
    const code = glossLanguageFor(nativeLanguage);
    const gloss = code === 'de' ? copy.language_de : copy.language_en;
    return [
        { value: `fr_to_${code}`, label: `${copy.language_fr} → ${gloss}` },
        { value: `${code}_to_fr`, label: `${gloss} → ${copy.language_fr}` },
        { value: 'mixed', label: copy.direction_mixed },
    ];
}

// Keep a stored direction on the pair the langue d'appui actually supports,
// preserving which way round the learner reads their cards.
function normalizeVocabDirection(direction: string, nativeLanguage: string) {
    const code = glossLanguageFor(nativeLanguage);
    if (direction === 'mixed') return 'mixed';
    if (vocabDirectionValues(nativeLanguage).includes(direction)) {
        return direction;
    }
    return direction.endsWith('_to_fr') ? `${code}_to_fr` : `fr_to_${code}`;
}

const interestTopicPresets = INTEREST_TOPICS;

// The design draws 5 / 8 / 15 min. The app's presets predate it and the free
// field accepts 5–120, so the existing values are rendered as the same control.
const minutePresets = [5, 10, 15, 30, 60];
const xpPresets = [20, 50, 100, 150, 200];

interface SettingsPageProps {
    userEmail?: string;
    userName?: string;
}

type SettingsSection = 'profile' | 'learning' | 'practice' | 'notifications' | 'appearance' | 'audio' | 'privacy';

const SECTION_LABEL_KEYS: Record<SettingsSection, keyof SettingsCopy> = {
    profile: 'section_profile',
    learning: 'section_learning',
    practice: 'section_practice',
    notifications: 'section_notifications',
    appearance: 'section_appearance',
    audio: 'section_audio',
    privacy: 'section_privacy',
};

const sectionIds = Object.keys(SECTION_LABEL_KEYS) as SettingsSection[];

// ---------------------------------------------------------------------------
// Local controls — the artboard's toggle and segmented control, and the row
// anatomy its two cards share. Presentation only; every value is a token.
// ---------------------------------------------------------------------------

function Switch({
    checked,
    onChange,
    labelledBy,
    disabled,
    copy,
}: {
    checked: boolean;
    onChange: (next: boolean) => void;
    labelledBy: string;
    disabled?: boolean;
    /** The screen-reader state word; a toggle whose state is unreadable is not a control. */
    copy: SettingsCopy;
}) {
    return (
        <button
            type="button"
            role="switch"
            aria-checked={checked}
            aria-labelledby={labelledBy}
            className="st-switch"
            disabled={disabled}
            onClick={() => onChange(!checked)}
        >
            <span className="st-switch__pill" aria-hidden="true">
                <span className="st-switch__knob" />
            </span>
            <span className="av2-sr">{checked ? copy.switch_on : copy.switch_off}</span>
        </button>
    );
}

function Segmented<T extends string | number>({
    label,
    options,
    value,
    onChange,
}: {
    label: string;
    options: { value: T; label: string }[];
    value: T;
    onChange: (next: T) => void;
}) {
    return (
        <div className="st-seg" role="radiogroup" aria-label={label}>
            {options.map((option) => {
                const active = option.value === value;
                return (
                    <button
                        key={String(option.value)}
                        type="button"
                        role="radio"
                        aria-checked={active}
                        className="st-seg__btn"
                        data-active={active ? 'true' : undefined}
                        onClick={() => onChange(option.value)}
                    >
                        {option.label}
                    </button>
                );
            })}
        </div>
    );
}

function Row({
    id,
    label,
    hint,
    value,
    children,
    stacked,
}: {
    id?: string;
    label: React.ReactNode;
    hint?: React.ReactNode;
    /** Trailing muted text — the artboard's "19:30" / "vincent@…". */
    value?: React.ReactNode;
    children?: React.ReactNode;
    /** Control sits under the label instead of beside it. */
    stacked?: boolean;
}) {
    return (
        <div className={`st-row${stacked ? ' st-row--stacked' : ''}`}>
            <div className="st-row__text">
                <span className="st-row__label" id={id}>{label}</span>
                {hint && <span className="st-row__hint">{hint}</span>}
            </div>
            {value !== undefined && <span className="st-row__value">{value}</span>}
            {children && <div className="st-row__control">{children}</div>}
        </div>
    );
}

function Field({
    label,
    children,
}: {
    label: string;
    children: React.ReactNode;
}) {
    return (
        <label className="av2-field st-field">
            <span className="av2-field__label">{label}</span>
            {children}
        </label>
    );
}

/**
 * A promise-shaped confirmation over the system `Dialog`, so a handler still
 * reads `if (!(await confirm('…'))) return;`. The sentence up to its question
 * mark is the dialog's headline; anything after it is the body.
 */
type ConfirmOptions = { confirmLabel?: string };

function useConfirmDialog(copy: SettingsCopy) {
    const [request, setRequest] = useState<{ message: string; options: ConfirmOptions } | null>(null);
    const resolver = useRef<((value: boolean) => void) | null>(null);

    const confirm = useCallback((message: string, options: ConfirmOptions = {}) => {
        return new Promise<boolean>((resolve) => {
            // A second question while one is open answers the first with "no".
            resolver.current?.(false);
            resolver.current = resolve;
            setRequest({ message, options });
        });
    }, []);

    const settle = useCallback((value: boolean) => {
        const resolve = resolver.current;
        resolver.current = null;
        setRequest(null);
        resolve?.(value);
    }, []);

    const onClose = useCallback(() => settle(false), [settle]);

    let title = request?.message ?? '';
    let body: string | undefined;
    const cut = title.indexOf('?');
    if (cut >= 0 && cut < title.length - 1) {
        body = title.slice(cut + 1).trim();
        title = title.slice(0, cut + 1);
    }

    const dialog = (
        <Dialog
            open={request !== null}
            title={title}
            body={body}
            onClose={onClose}
            actions={
                <>
                    <Action tone="secondary" onClick={() => settle(false)}>
                        {copy.action_cancel}
                    </Action>
                    <Action tone="primary" onClick={() => settle(true)}>
                        {request?.options.confirmLabel ?? copy.action_confirm}
                    </Action>
                </>
            }
        />
    );

    return { confirm, dialog };
}

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
    const [saveFailed, setSaveFailed] = useState(false);
    const [hasChanges, setHasChanges] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [settingsLoadError, setSettingsLoadError] = useState<string | null>(null);
    const [settingsReloadKey, setSettingsReloadKey] = useState(0);
    const [customInterestTopic, setCustomInterestTopic] = useState('');
    const [privacyAction, setPrivacyAction] = useState<'export' | 'signout' | 'delete' | null>(null);
    const [passwordForm, setPasswordForm] = useState({ currentPassword: '', newPassword: '' });
    const [emailForm, setEmailForm] = useState({ currentPassword: '', newEmail: '' });
    const [isAdmin, setIsAdmin] = useState(false);
    /**
     * WP-32's «Écouter d’abord» preference (WP-37 hook). It lives in
     * `localStorage`, not in the settings payload, so it is read *after* mount:
     * seeding it from storage during render would make the server's HTML and
     * the client's first paint disagree. The default, here as everywhere, is
     * off.
     */
    const [listenFirst, setListenFirst] = useState(false);
    useEffect(() => { setListenFirst(readListenFirst()); }, []);
    // WP-49: the row exists only where the server can read an episode aloud.
    const [episodeAudioEnabled, setEpisodeAudioEnabled] = useState(false);

    /**
     * WP-46 — the one screen that does not speak the publication's French.
     *
     * Réglages is administrative: a learner has to understand what they are
     * about to change *before* they change it, and «suppression définitive» is
     * not the sentence to learn that on. So the whole screen follows the
     * account's `native_language`.
     *
     * `nativeLanguageKnown` is what keeps it from flickering. Until the account
     * answers, the honest value is "we do not know", and `resolveSettingsLanguage`
     * answers English for it — so the first paint is never French that a German
     * or English learner then watches swap. The declared default in
     * `defaultSettings` is a payload default, not a claim about this learner.
     */
    const [nativeLanguageKnown, setNativeLanguageKnown] = useState(false);
    const copyLanguage = resolveSettingsLanguage(
        nativeLanguageKnown ? settings.nativeLanguage : null,
    );
    const copy = settingsCopy(copyLanguage);

    const { confirm, dialog: confirmDialog } = useConfirmDialog(copy);
    const pendingScroll = useRef<SettingsSection | null>(null);

    useEffect(() => {
        if (!router.isReady) return;
        const requested = String(router.query.section || '');
        if ((sectionIds as string[]).includes(requested)) {
            setActiveSection(requested as SettingsSection);
            pendingScroll.current = requested as SettingsSection;
        }
    }, [router.isReady, router.query.section]);

    // The anchors only exist once the sheet has rendered, so the scroll waits
    // for the load to finish rather than firing at an empty skeleton.
    useEffect(() => {
        if (isLoading || settingsLoadError || !pendingScroll.current) return;
        const target = document.getElementById(`settings-${pendingScroll.current}`);
        pendingScroll.current = null;
        target?.scrollIntoView({ block: 'start', behavior: 'smooth' });
    }, [isLoading, settingsLoadError]);

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
                setEpisodeAudioEnabled(Boolean(user.episode_audio_enabled));
                // From here the screen knows whose language it is in.
                setNativeLanguageKnown(true);
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

                    addressPreference: (user.address_preference as AddressPreference) || prev.addressPreference,
                }));
                persistVisualSettings(loadedTheme, loadedFontSize);
            } catch (error) {
                console.error('Failed to load user settings:', error);
                // The account never answered, so its language is unknown: English.
                setSettingsLoadError(settingsCopy(resolveSettingsLanguage(null)).load_error_body);
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
            toast.error(copy.save_blocked);
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

                address_preference: settings.addressPreference,
            };

            await api.updateSettings(payload);
            persistVisualSettings(settings.theme, settings.fontSize);

            setSaveFailed(false);
            setSaveMessage(copy.save_done);
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
            setSaveFailed(true);
            setSaveMessage(
                rejected.length
                    ? `${copy.save_failed_fields} ${rejected.join(', ')}.`
                    : copy.save_failed,
            );
        } finally {
            setIsSaving(false);
        }
    };

    const handleDeleteAccount = async () => {
        if (!(await confirm(copy.confirm_delete_account, { confirmLabel: copy.confirm_delete_account_label }))) {
            return;
        }

        setPrivacyAction('delete');
        setIsSaving(true);
        try {
            await api.deleteAccount();
            await appSignOut({ callbackUrl: '/' });
        } catch (error) {
            console.error('Failed to delete account:', error);
            setSaveFailed(true);
            setSaveMessage(copy.delete_account_failed);
            setIsSaving(false);
            setPrivacyAction(null);
        }
    };

    const handlePasswordChange = async () => {
        if (!passwordForm.currentPassword || passwordForm.newPassword.length < 8) {
            toast.error(copy.password_incomplete);
            return;
        }
        setIsSaving(true);
        try {
            await api.changePassword({
                current_password: passwordForm.currentPassword,
                new_password: passwordForm.newPassword,
            });
            setPasswordForm({ currentPassword: '', newPassword: '' });
            toast.success(copy.password_changed);
            await appSignOut({ callbackUrl: '/auth/signin' });
        } catch (error) {
            console.error('Failed to change password:', error);
            toast.error(copy.password_failed);
        } finally {
            setIsSaving(false);
        }
    };

    const handleEmailChange = async () => {
        if (!emailForm.currentPassword || !emailForm.newEmail) {
            toast.error(copy.email_incomplete);
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
            toast.success(copy.email_changed);
            await appSignOut({ callbackUrl: '/auth/signin' });
        } catch (error) {
            console.error('Failed to change email:', error);
            toast.error(copy.email_failed);
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
            toast.success(copy.export_ready);
        } catch (error) {
            console.error('Failed to export user data:', error);
            toast.error(copy.export_failed);
        } finally {
            setPrivacyAction(null);
        }
    };

    const handleSignOutAllDevices = async () => {
        if (!(await confirm(copy.confirm_signout_all))) return;
        setPrivacyAction('signout');
        try {
            await api.signOutAllDevices();
            toast.success(copy.signout_all_done);
            await appSignOut({ callbackUrl: '/auth/signin' });
        } catch (error) {
            console.error('Failed to sign out all devices:', error);
            toast.error(copy.signout_all_failed);
            setPrivacyAction(null);
        }
    };

    const enableDeviceNotifications = async (): Promise<boolean> => {
        if (Capacitor.isNativePlatform()) {
            if (!nativePushIsAvailable()) {
                toast.error(copy.push_ios_unavailable);
                return false;
            }
            const loadingToast = toast.loading(copy.push_ios_connecting);
            try {
                const token = await registerNativePushToken();
                await api.subscribeToNativeNotifications(token);
                toast.success(copy.push_ios_linked, { id: loadingToast });
                return true;
            } catch (error: any) {
                console.error(error);
                toast.error(error?.message || copy.push_ios_failed, { id: loadingToast });
                return false;
            }
        }
        if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
            toast.error(copy.push_unsupported);
            return false;
        }
        const loadingToast = toast.loading(copy.push_connecting);
        try {
            const permission = await Notification.requestPermission();
            if (permission !== 'granted') {
                toast.error(copy.push_denied, { id: loadingToast });
                return false;
            }
            const reg = await navigator.serviceWorker.register('/sw.js');
            await navigator.serviceWorker.ready;
            const { publicKey } = await api.getVapidPublicKey();
            if (!publicKey?.trim()) {
                toast.error(copy.push_not_configured, { id: loadingToast });
                return false;
            }
            const sub = await reg.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: urlBase64ToUint8Array(publicKey),
            });
            await api.subscribeToNotifications(sub.toJSON());
            toast.success(copy.push_linked, { id: loadingToast });
            return true;
        } catch (error: any) {
            console.error(error);
            toast.error(`${copy.push_failed} ${error?.message || copy.push_unknown_error}`, { id: loadingToast });
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
        const normalized = interestTopicKey(topic);
        if (!normalized) return;
        const next = settings.interests.includes(normalized)
            ? settings.interests.filter((item) => item !== normalized)
            : [...settings.interests, normalized];
        updateSetting('interests', next);
    };

    const addCustomInterestTopic = () => {
        const normalized = interestTopicKey(customInterestTopic);
        if (!normalized) return;
        if (settings.interests.includes(normalized)) {
            setCustomInterestTopic('');
            return;
        }
        updateSetting('interests', [...settings.interests, normalized]);
        setCustomInterestTopic('');
    };

    const jumpToSection = (id: SettingsSection) => {
        setActiveSection(id);
        document.getElementById(`settings-${id}`)?.scrollIntoView({ block: 'start', behavior: 'smooth' });
    };

    // The name and the level are data: printed as the account holds them.
    const firstName = settings.displayName.trim().split(/\s+/)[0] || '';
    const kicker = `${firstName || copy.kicker_fallback} · ${settings.proficiencyLevel}`;

    const head = (
        <Head>
            <title>{copy.page_title}</title>
        </Head>
    );

    if (isLoading) {
        return (
            <>
                {head}
                <AtelierV2Root as="main" className="st-page" language={copyLanguage} aria-busy="true" aria-label={copy.page_label}>
                    <header className="st-head">
                        <div style={{ width: '40%' }}><Skeleton height={14} radius={7} /></div>
                        <div style={{ marginTop: 8, width: '55%' }}><Skeleton height={30} radius={8} /></div>
                    </header>
                    <div className="st-stack">
                        <Skeleton height={112} radius={18} />
                        <Skeleton height={168} radius={18} />
                        <Skeleton height={168} radius={18} />
                    </div>
                    <span className="av2-sr" role="status">{copy.loading_status}</span>
                </AtelierV2Root>
                <SettingsStyles />
            </>
        );
    }

    if (settingsLoadError) {
        return (
            <>
                {head}
                <AtelierV2Root as="main" className="st-page" language={copyLanguage} aria-label={copy.page_label}>
                    <header className="st-head">
                        <p className="st-kicker">{copy.load_error_kicker}</p>
                        <h1 className="av2-headline">{copy.load_error_headline}</h1>
                    </header>
                    <div className="st-stack">
                        <StateBlock
                            tone="error"
                            title={copy.load_error_title}
                            body={settingsLoadError}
                            action={{ label: copy.action_retry, onSelect: () => setSettingsReloadKey((value) => value + 1) }}
                        />
                    </div>
                </AtelierV2Root>
                <SettingsStyles />
            </>
        );
    }

    return (
        <>
            {head}
            <AtelierV2Root as="main" className="st-page" language={copyLanguage} aria-label={copy.page_label}>
                <header className="st-head">
                    <p className="st-kicker">{kicker}</p>
                    {/* the one Garamond italic headline on this screen */}
                    <h1 className="av2-headline">{copy.headline}</h1>
                </header>

                <nav className="st-jump" aria-label={copy.jump_label}>
                    {sectionIds.map((id) => (
                        <Chip
                            key={id}
                            tone={activeSection === id ? 'story' : 'plain'}
                            aria-current={activeSection === id ? 'true' : undefined}
                            onClick={() => jumpToSection(id)}
                        >
                            {copy[SECTION_LABEL_KEYS[id]]}
                        </Chip>
                    ))}
                </nav>

                <div className="st-stack">
                    {/* ---------------- Dossier ---------------- */}
                    <section id="settings-profile" className="st-section" aria-labelledby="st-profile-label">
                        <p className="av2-label st-section__label" id="st-profile-label">{copy.section_profile}</p>
                        <div className="st-card">
                            <Row label={copy.row_account} value={<span className="st-email" title={settings.email}>{settings.email}</span>} />
                            <Row label={copy.row_display_name} stacked>
                                <input
                                    type="text"
                                    className="av2-field__control"
                                    value={settings.displayName}
                                    onChange={(e) => updateSetting('displayName', e.target.value)}
                                    placeholder={copy.display_name_placeholder}
                                    aria-label={copy.row_display_name}
                                />
                            </Row>
                            {isAdmin && (
                                <button type="button" className="st-row st-row--link" onClick={() => void router.push('/pilot-ops')}>
                                    <span className="st-row__text">
                                        <span className="st-row__label">{copy.row_admin}</span>
                                        <span className="st-row__hint">{copy.row_admin_hint}</span>
                                    </span>
                                    <span className="st-row__value" aria-hidden="true">→</span>
                                </button>
                            )}
                        </div>

                        <div className="st-card">
                            <Row label={copy.row_change_email} hint={copy.row_change_email_hint} stacked>
                                <div className="st-form">
                                    <Field label={copy.field_new_email}>
                                        <input
                                            type="email"
                                            className="av2-field__control"
                                            value={emailForm.newEmail}
                                            onChange={(event) => setEmailForm((prev) => ({ ...prev, newEmail: event.target.value }))}
                                            placeholder="new@email.com"
                                            autoComplete="email"
                                        />
                                    </Field>
                                    <Field label={copy.field_current_password}>
                                        <input
                                            type="password"
                                            className="av2-field__control"
                                            value={emailForm.currentPassword}
                                            onChange={(event) => setEmailForm((prev) => ({ ...prev, currentPassword: event.target.value }))}
                                            autoComplete="current-password"
                                        />
                                    </Field>
                                    <Action
                                        tone="secondary"
                                        inline
                                        onClick={handleEmailChange}
                                        disabled={isSaving || !emailForm.newEmail || !emailForm.currentPassword}
                                    >
                                        {copy.action_save_email}
                                    </Action>
                                </div>
                            </Row>
                            <Row label={copy.row_change_password} hint={copy.row_change_password_hint} stacked>
                                <div className="st-form">
                                    <Field label={copy.field_current_password}>
                                        <input
                                            type="password"
                                            className="av2-field__control"
                                            value={passwordForm.currentPassword}
                                            onChange={(event) => setPasswordForm((prev) => ({ ...prev, currentPassword: event.target.value }))}
                                            autoComplete="current-password"
                                        />
                                    </Field>
                                    <Field label={copy.field_new_password}>
                                        <input
                                            type="password"
                                            className="av2-field__control"
                                            value={passwordForm.newPassword}
                                            onChange={(event) => setPasswordForm((prev) => ({ ...prev, newPassword: event.target.value }))}
                                            autoComplete="new-password"
                                        />
                                    </Field>
                                    <Action
                                        tone="secondary"
                                        inline
                                        onClick={handlePasswordChange}
                                        disabled={isSaving || !passwordForm.currentPassword || passwordForm.newPassword.length < 8}
                                    >
                                        {copy.action_save_password}
                                    </Action>
                                </div>
                            </Row>
                        </div>
                    </section>

                    {/* ---------------- Langues ---------------- */}
                    <section id="settings-learning" className="st-section" aria-labelledby="st-learning-label">
                        <p className="av2-label st-section__label" id="st-learning-label">{copy.section_learning}</p>
                        <div className="st-card">
                            <Row label={copy.row_native_language} id="st-native-label">
                                <select
                                    className="av2-field__control st-select"
                                    aria-labelledby="st-native-label"
                                    value={settings.nativeLanguage}
                                    onChange={(e) => updateNativeLanguage(e.target.value)}
                                >
                                    {languageOptions(copy).map(lang => (
                                        <option key={lang.value} value={lang.value}>{lang.label}</option>
                                    ))}
                                </select>
                            </Row>
                            <Row label={copy.row_target_language} id="st-target-label">
                                <select
                                    className="av2-field__control st-select"
                                    aria-labelledby="st-target-label"
                                    value={settings.targetLanguage}
                                    onChange={(e) => updateSetting('targetLanguage', e.target.value)}
                                >
                                    {languageOptions(copy).map(lang => (
                                        <option key={lang.value} value={lang.value}>{lang.label}</option>
                                    ))}
                                </select>
                            </Row>
                        </div>

                        {/* WP-25 — the re-run. The level below is what the learner
                            *said*; the bilan is what the app can *measure*, and a
                            learner whose French has moved should be able to ask
                            again rather than edit a dropdown. */}
                        <div className="st-card">
                            <Row
                                label={copy.row_placement}
                                hint={copy.row_placement_hint}
                            >
                                <button
                                    type="button"
                                    className="av2-btn av2-btn--quiet av2-btn--inline"
                                    onClick={() => { void router.push('/placement?rerun=1'); }}
                                >
                                    {copy.action_placement}
                                </button>
                            </Row>
                        </div>

                        {/* WP-31 — «Répétition». The one entry point into the
                            rehearsal flow: the learner declares a real thing that
                            is about to happen, rehearses it once, and reports back
                            afterwards. The Home entry is owed by another owner. */}
                        <div className="st-card">
                            <Row
                                label={copy.row_rehearsal}
                                hint={copy.row_rehearsal_hint}
                            >
                                <button
                                    type="button"
                                    className="av2-btn av2-btn--quiet av2-btn--inline"
                                    onClick={() => { void router.push('/repetition'); }}
                                >
                                    {copy.action_open}
                                </button>
                            </Row>
                        </div>

                        {/* WP-35 — «Votre dossier». What the application believes
                            about the learner, with the evidence behind each
                            number, and the two-question check that lets them
                            disagree with it. The Home entry is owed by another
                            owner. */}
                        <div className="st-card">
                            <Row
                                label={copy.row_dossier}
                                hint={copy.row_dossier_hint}
                            >
                                <button
                                    type="button"
                                    className="av2-btn av2-btn--quiet av2-btn--inline"
                                    onClick={() => { void router.push('/dossier'); }}
                                >
                                    {copy.action_open}
                                </button>
                            </Row>
                        </div>

                        {/* WP-43 — the feedback panel's phone entry. The floating
                            launcher is hidden on phone widths (it floated over
                            the reading column); this row opens the same panel. */}
                        <div className="st-card">
                            <Row
                                label={copy.row_feedback}
                                hint={copy.row_feedback_hint}
                            >
                                <button
                                    type="button"
                                    className="av2-btn av2-btn--quiet av2-btn--inline"
                                    onClick={() => { window.dispatchEvent(new Event(FEEDBACK_OPEN_EVENT)); }}
                                >
                                    {copy.action_feedback}
                                </button>
                            </Row>
                        </div>

                        <div className="st-card" role="radiogroup" aria-label={copy.row_level}>
                            <Row label={copy.row_level} value={settings.proficiencyLevel} />
                            {proficiencyLevels(copy).map(level => {
                                const active = settings.proficiencyLevel === level.value;
                                return (
                                    <button
                                        key={level.value}
                                        type="button"
                                        role="radio"
                                        aria-checked={active}
                                        className="st-row st-row--option"
                                        onClick={() => updateSetting('proficiencyLevel', level.value)}
                                    >
                                        <span className="st-row__text">
                                            <span className="st-row__label">{level.label}</span>
                                            <span className="st-row__hint">{level.description}</span>
                                        </span>
                                        <span className="st-row__value st-option__state">
                                            {active ? <><ShapeToken kind="story" size="sm" /> {copy.level_current}</> : null}
                                        </span>
                                    </button>
                                );
                            })}
                        </div>

                        <div className="st-card">
                            <Row label={copy.row_topics} hint={copy.row_topics_hint} stacked>
                                <div className="st-topics">
                                    {interestTopicPresets.map((topic) => {
                                        const selected = settings.interests.includes(topic.key);
                                        return (
                                            <Chip
                                                key={topic.key}
                                                tone={selected ? 'reward' : 'plain'}
                                                aria-pressed={selected}
                                                onClick={() => toggleInterestTopic(topic.key)}
                                            >
                                                {topic.label}
                                            </Chip>
                                        );
                                    })}
                                </div>
                                <div className="st-inline">
                                    <input
                                        type="text"
                                        className="av2-field__control"
                                        value={customInterestTopic}
                                        onChange={(event) => setCustomInterestTopic(event.target.value)}
                                        onKeyDown={(event) => {
                                            if (event.key === 'Enter') {
                                                event.preventDefault();
                                                addCustomInterestTopic();
                                            }
                                        }}
                                        placeholder={copy.topic_placeholder}
                                        aria-label={copy.topic_placeholder}
                                    />
                                    <Action tone="secondary" inline onClick={addCustomInterestTopic}>
                                        {copy.action_add_topic}
                                    </Action>
                                </div>
                                {settings.interests.length > 0 && (
                                    <p className="st-row__hint">{copy.topics_selected} {settings.interests.map(interestTopicLabel).join(', ')}</p>
                                )}
                            </Row>
                        </div>

                        <div className="st-card">
                            <Row
                                label={copy.row_correction}
                                hint={
                                    settings.grammarCorrectionLevel === 'strict'
                                        ? copy.correction_strict_hint
                                        : settings.grammarCorrectionLevel === 'moderate'
                                            ? copy.correction_moderate_hint
                                            : copy.correction_lenient_hint
                                }
                                stacked
                            >
                                <Segmented
                                    label={copy.row_correction}
                                    options={[
                                        { value: 'lenient' as const, label: copy.correction_lenient },
                                        { value: 'moderate' as const, label: copy.correction_moderate },
                                        { value: 'strict' as const, label: copy.correction_strict },
                                    ]}
                                    value={settings.grammarCorrectionLevel}
                                    onChange={(value) => updateSetting('grammarCorrectionLevel', value)}
                                />
                            </Row>
                            <Row id="st-explanations-label" label={copy.row_explanations} hint={copy.row_explanations_hint}>
                                <Switch
                                    copy={copy}
                                    labelledBy="st-explanations-label"
                                    checked={settings.showGrammarExplanations}
                                    onChange={(next) => updateSetting('showGrammarExplanations', next)}
                                />
                            </Row>
                        </div>

                        <div className="st-card">
                            <Row
                                label={copy.row_address}
                                hint={addressHint(copy, settings.addressPreference)}
                                stacked
                            >
                                <Segmented
                                    label={copy.row_address}
                                    options={addressOptions(copy)}
                                    value={settings.addressPreference}
                                    onChange={(value) => updateSetting('addressPreference', value)}
                                />
                            </Row>
                        </div>
                    </section>

                    {/* ---------------- Rythme ---------------- */}
                    <section id="settings-practice" className="st-section" aria-labelledby="st-practice-label">
                        <p className="av2-label st-section__label" id="st-practice-label">{copy.section_practice}</p>
                        {/* The artboard's "Temps par édition" card, verbatim. */}
                        <div className="st-card st-card--padded">
                            <div className="st-card__title">
                                <span>{copy.card_time_title}</span>
                                <span className="st-row__value">{settings.dailyGoalMinutes} {copy.minutes_short}</span>
                            </div>
                            <Segmented
                                label={copy.card_time_title}
                                options={minutePresets.map((mins) => ({ value: mins, label: `${mins} ${copy.minutes_short}` }))}
                                value={settings.dailyGoalMinutes}
                                onChange={(mins) => updateSetting('dailyGoalMinutes', mins)}
                            />
                            <Field label={copy.field_other_duration}>
                                <input
                                    type="number"
                                    className="av2-field__control st-number"
                                    min="5"
                                    max="120"
                                    value={settings.dailyGoalMinutes}
                                    onChange={(e) => updateSetting('dailyGoalMinutes', parseInt(e.target.value) || 15)}
                                />
                            </Field>
                        </div>

                        <div className="st-card">
                            <Row label={copy.row_cefr} hint={copy.row_cefr_hint} id="st-cefr-label">
                                <select
                                    className="av2-field__control st-select"
                                    aria-labelledby="st-cefr-label"
                                    value={settings.cefrTargetLevel}
                                    onChange={(e) => updateSetting('cefrTargetLevel', e.target.value)}
                                >
                                    {cefrSublevels.map((level) => (
                                        <option key={level} value={level}>{level}</option>
                                    ))}
                                </select>
                            </Row>
                            <Row label={copy.row_xp} value={`${settings.dailyGoalXP} XP`} stacked>
                                <Segmented
                                    label={copy.row_xp}
                                    options={xpPresets.map((xp) => ({ value: xp, label: String(xp) }))}
                                    value={settings.dailyGoalXP}
                                    onChange={(xp) => updateSetting('dailyGoalXP', xp)}
                                />
                                <Field label={copy.field_other_xp}>
                                    <input
                                        type="number"
                                        className="av2-field__control st-number"
                                        min="10"
                                        max="500"
                                        step="10"
                                        value={settings.dailyGoalXP}
                                        onChange={(e) => updateSetting('dailyGoalXP', parseInt(e.target.value) || 50)}
                                    />
                                </Field>
                            </Row>
                            <Row label={copy.row_new_words} id="st-words-label">
                                <input
                                    type="number"
                                    className="av2-field__control st-number"
                                    aria-labelledby="st-words-label"
                                    min="1"
                                    max="50"
                                    value={settings.newWordsPerDay}
                                    onChange={(e) => updateSetting('newWordsPerDay', parseInt(e.target.value) || 10)}
                                />
                            </Row>
                            <Row
                                label={copy.row_direction}
                                id="st-direction-label"
                                hint={
                                    !GLOSS_LANGUAGES.includes(settings.nativeLanguage)
                                        ? copy.row_direction_hint
                                        : undefined
                                }
                            >
                                <select
                                    className="av2-field__control st-select"
                                    aria-labelledby="st-direction-label"
                                    value={settings.defaultVocabDirection}
                                    onChange={(e) => updateSetting('defaultVocabDirection', e.target.value)}
                                >
                                    {vocabDirectionOptions(settings.nativeLanguage, copy).map((option) => (
                                        <option key={option.value} value={option.value}>{option.label}</option>
                                    ))}
                                </select>
                            </Row>
                        </div>
                    </section>

                    {/* ---------------- Notifications ---------------- */}
                    <section id="settings-notifications" className="st-section" aria-labelledby="st-notifications-label">
                        <p className="av2-label st-section__label" id="st-notifications-label">{copy.section_notifications}</p>
                        <div className="st-card st-card--padded">
                            <div className="st-card__title">
                                <span>{copy.card_device_title}</span>
                            </div>
                            <p className="st-row__hint">{copy.card_device_hint}</p>
                            <Action tone="secondary" inline onClick={() => void enableDeviceNotifications()}>
                                {copy.action_link_device}
                            </Action>
                        </div>
                        {/* WP-67: «Distinctions» is not in this list.
                            The row promised «un avis lorsqu'une distinction est
                            classée» and nothing sends it: `achievement_notifications`
                            is stored on the account and read by no sender in the
                            codebase. The distinctions themselves are real and
                            already printed, with their dates, in La Collection
                            (Cahier › Le Relevé); what was false was the note.
                            The stored preference is left untouched and still
                            round-trips through this page's save. */}
                        <div className="st-card">
                            {[
                                { key: 'practiceReminders' as const, label: copy.notif_practice, desc: copy.notif_practice_hint },
                                { key: 'streakNotifications' as const, label: copy.notif_streak, desc: copy.notif_streak_hint },
                                { key: 'weeklyEmailSummary' as const, label: copy.notif_weekly, desc: copy.notif_weekly_hint },
                                { key: 'serialEditionNotifications' as const, label: copy.notif_serial, desc: copy.notif_serial_hint },
                            ].map(item => (
                                <React.Fragment key={item.key}>
                                    <Row id={`st-${item.key}-label`} label={item.label} hint={item.desc}>
                                        <Switch
                                            copy={copy}
                                            labelledBy={`st-${item.key}-label`}
                                            checked={settings[item.key]}
                                            onChange={(next) => void handleNotificationToggle(item.key, next)}
                                        />
                                    </Row>
                                    {item.key === 'practiceReminders' && settings.practiceReminders && (
                                        <Row label={copy.row_reminder_time} id="st-reminder-label">
                                            <input
                                                type="time"
                                                className="av2-field__control st-time"
                                                aria-labelledby="st-reminder-label"
                                                value={settings.reminderTime}
                                                onChange={(e) => updateSetting('reminderTime', e.target.value)}
                                            />
                                        </Row>
                                    )}
                                </React.Fragment>
                            ))}
                        </div>
                    </section>

                    {/* ---------------- Apparence ---------------- */}
                    <section id="settings-appearance" className="st-section" aria-labelledby="st-appearance-label">
                        <p className="av2-label st-section__label" id="st-appearance-label">{copy.section_appearance}</p>
                        <div className="st-card">
                            <Row label={copy.row_theme} hint={copy.row_theme_hint} stacked>
                                <Segmented
                                    label={copy.row_theme}
                                    options={[
                                        { value: 'light' as const, label: copy.theme_light },
                                        { value: 'dark' as const, label: copy.theme_dark },
                                        { value: 'system' as const, label: copy.theme_system },
                                    ]}
                                    value={settings.theme}
                                    onChange={(value) => updateSetting('theme', value)}
                                />
                            </Row>
                            <Row label={copy.row_font_size} hint={copy.row_font_size_hint} stacked>
                                <Segmented
                                    label={copy.row_font_size}
                                    options={[
                                        { value: 'small' as const, label: copy.font_small },
                                        { value: 'medium' as const, label: copy.font_medium },
                                        { value: 'large' as const, label: copy.font_large },
                                    ]}
                                    value={settings.fontSize}
                                    onChange={(value) => updateSetting('fontSize', value)}
                                />
                            </Row>
                        </div>
                    </section>

                    {/* ---------------- Voix ---------------- */}
                    <section id="settings-audio" className="st-section" aria-labelledby="st-audio-label">
                        <p className="av2-label st-section__label" id="st-audio-label">{copy.section_audio}</p>
                        <div className="st-card">
                            {/* The artboard's "Réponses à l’oral" toggle is the microphone preference. */}
                            {[
                                { key: 'voiceInputEnabled' as const, label: copy.row_voice_input, desc: copy.row_voice_input_hint },
                                { key: 'textToSpeechEnabled' as const, label: copy.row_tts, desc: copy.row_tts_hint },
                                { key: 'autoPlayPronunciation' as const, label: copy.row_autoplay, desc: copy.row_autoplay_hint },
                            ].map(item => (
                                <Row key={item.key} id={`st-${item.key}-label`} label={item.label} hint={item.desc}>
                                    <Switch
                                        copy={copy}
                                        labelledBy={`st-${item.key}-label`}
                                        checked={settings[item.key]}
                                        onChange={(next) => updateSetting(item.key, next)}
                                    />
                                </Row>
                            ))}
                            {/* WP-32 §9.2, applied by WP-37 — «Écouter d’abord».
                                The same `LISTEN_FIRST_KEY` the reader writes, so
                                the two controls can never disagree: this device,
                                this learner, nothing sent to the server. It is
                                off by default and stays that way — listening
                                first is the harder way to meet a scene, and the
                                evidence for it assumes a learner who chose it.
                                Until now the only way to choose was to be shown
                                the offer inside an episode. */}
                            {episodeAudioEnabled && (
                            <Row
                                id="st-listen-first-label"
                                label={copy.row_listen_first}
                                hint={copy.row_listen_first_hint}
                            >
                                <Switch
                                    copy={copy}
                                    labelledBy="st-listen-first-label"
                                    checked={listenFirst}
                                    onChange={(next) => {
                                        writeListenFirst(next);
                                        setListenFirst(next);
                                    }}
                                />
                            </Row>
                            )}
                            <Row label={copy.row_tts_speed} value={`${settings.ttsSpeed}×`} stacked>
                                <div className="st-range">
                                    <span className="st-row__hint">{copy.speed_slow}</span>
                                    <input
                                        type="range"
                                        min="0.5"
                                        max="1.5"
                                        step="0.1"
                                        value={settings.ttsSpeed}
                                        aria-label={copy.row_tts_speed}
                                        aria-valuetext={`${settings.ttsSpeed} ${copy.speed_valuetext}`}
                                        onChange={(e) => updateSetting('ttsSpeed', parseFloat(e.target.value))}
                                    />
                                    <span className="st-row__hint">{copy.speed_fast}</span>
                                </div>
                            </Row>
                        </div>
                    </section>

                    {/* ---------------- Données ---------------- */}
                    <section id="settings-privacy" className="st-section" aria-labelledby="st-privacy-label">
                        <p className="av2-label st-section__label" id="st-privacy-label">{copy.section_privacy}</p>
                        <div className="st-card">
                            <Row label={copy.row_export} hint={copy.row_export_hint}>
                                <Action
                                    tone="secondary"
                                    inline
                                    onClick={handleExportData}
                                    pending={privacyAction === 'export'}
                                    pendingLabel={copy.pending_export}
                                >
                                    {copy.action_export}
                                </Action>
                            </Row>
                            <Row label={copy.row_signout_all} hint={copy.row_signout_all_hint}>
                                <Action
                                    tone="secondary"
                                    inline
                                    onClick={handleSignOutAllDevices}
                                    pending={privacyAction === 'signout'}
                                    pendingLabel={copy.pending_signout_all}
                                >
                                    {copy.action_signout_all}
                                </Action>
                            </Row>
                            <Row
                                label={<><ShapeToken kind="action" size="sm" /> {copy.row_delete}</>}
                                hint={copy.row_delete_hint}
                            >
                                <Action
                                    tone="secondary"
                                    inline
                                    className="st-danger"
                                    onClick={handleDeleteAccount}
                                    pending={privacyAction === 'delete'}
                                    pendingLabel={copy.pending_delete}
                                    disabled={isSaving && privacyAction !== 'delete'}
                                >
                                    {copy.action_delete}
                                </Action>
                            </Row>
                        </div>
                    </section>
                </div>

                {/* The one 3D press on this screen: filing the changes. */}
                {(hasChanges || saveMessage) && (
                    <div className="st-savebar">
                        {saveMessage ? (
                            <Notice tone={saveFailed ? 'alert' : 'plain'} live={saveFailed ? 'alert' : 'status'} shape={saveFailed ? 'action' : 'done'}>
                                <p>{saveMessage}</p>
                            </Notice>
                        ) : (
                            <Action
                                tone="primary"
                                onClick={saveSettings}
                                pending={isSaving}
                                pendingLabel={copy.pending_save}
                            >
                                {copy.action_save}
                            </Action>
                        )}
                    </div>
                )}

                {confirmDialog}
            </AtelierV2Root>
            <SettingsStyles />
        </>
    );
}

/* Every rule is `.av2 .st-…` (0,2,0): the legacy page resets in globals.css
   are (0,1,1), and the tokens only resolve under `.av2`. */
function SettingsStyles() {
    return (
        <style jsx global>{`
            body { background: var(--app-paper); }
            .av2.st-page {
                display: block;
                width: 100%;
                max-width: 720px;
                margin: 0 auto;
                min-height: 100vh;
                padding: 0 0 calc(24px + var(--phone-bottom-nav-space, 0px));
            }
            .av2 .st-head {
                padding: 18px var(--av2-gutter) 0;
                min-width: 0;
            }
            .av2 .st-kicker {
                margin: 0;
                font-size: var(--av2-t-label);
                font-weight: 600;
                color: var(--av2-muted);
            }
            .av2 .st-head .av2-headline { margin-top: 3px; line-height: 1; }

            .av2 .st-jump {
                display: flex;
                flex-wrap: wrap;
                gap: 6px;
                padding: 16px var(--av2-gutter) 0;
                min-width: 0;
            }
            .av2 .st-jump .av2-chip { min-height: var(--av2-tap); }

            .av2 .st-stack {
                display: flex;
                flex-direction: column;
                gap: 20px;
                padding: 20px var(--av2-gutter) 0;
                min-width: 0;
            }
            .av2 .st-section {
                display: flex;
                flex-direction: column;
                gap: 10px;
                min-width: 0;
                scroll-margin-top: 16px;
            }
            .av2 .st-section__label { padding: 0 2px; }

            /* The artboard's two cards: radius 18, card ground, rows split by
               hairlines. */
            .av2 .st-card {
                display: flex;
                flex-direction: column;
                min-width: 0;
                border-radius: var(--av2-r-tile);
                background: var(--av2-card);
                overflow: hidden;
            }
            .av2 .st-card--padded {
                gap: 10px;
                padding: 14px 16px;
            }
            .av2 .st-card__title {
                display: flex;
                justify-content: space-between;
                gap: 12px;
                min-width: 0;
                font-size: 0.875rem;
                font-weight: 600;
                color: var(--av2-ink);
            }

            .av2 .st-row {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 12px;
                min-width: 0;
                width: 100%;
                min-height: var(--av2-tap);
                padding: 14px 16px;
                border: 0;
                border-bottom: 1px solid var(--av2-line);
                background: transparent;
                color: var(--av2-ink);
                font-family: inherit;
                font-size: 0.875rem;
                font-weight: 600;
                line-height: 1.3;
                text-align: left;
            }
            .av2 .st-card > .st-row:last-child { border-bottom: 0; }
            .av2 .st-row--stacked { flex-direction: column; align-items: stretch; gap: 10px; }
            .av2 .st-row--stacked .st-row__control { width: 100%; }
            .av2 .st-row--link, .av2 .st-row--option { cursor: pointer; }
            .av2 .st-row--option[aria-checked='true'] .st-row__label { color: var(--av2-blue); }
            .av2 .st-row__text { display: flex; flex-direction: column; gap: 2px; min-width: 0; flex: 1 1 auto; }
            .av2 .st-row__label { display: inline-flex; align-items: center; gap: 6px; overflow-wrap: anywhere; }
            .av2 .st-row__hint {
                margin: 0;
                font-size: var(--av2-t-meta);
                font-weight: 400;
                line-height: 1.4;
                color: var(--av2-muted);
                overflow-wrap: anywhere;
            }
            .av2 .st-row__value {
                flex: none;
                font-weight: 500;
                color: var(--av2-muted);
                text-align: right;
            }
            .av2 .st-row__control { display: flex; flex-direction: column; gap: 10px; flex: none; min-width: 0; max-width: 100%; }
            .av2 .st-row:not(.st-row--stacked) > .st-row__control { max-width: 60%; }
            .av2 .st-option__state { display: inline-flex; align-items: center; gap: 6px; font-size: var(--av2-t-meta); font-weight: 700; color: var(--av2-blue); }
            .av2 .st-email { word-break: break-all; font-weight: 500; }

            /* Controls inside a row sit on the paper ground so they read against
               the card. */
            .av2 .st-row .av2-field__control,
            .av2 .st-card--padded .av2-field__control {
                background: var(--av2-paper);
                min-height: var(--av2-tap);
            }
            .av2 .st-select { width: auto; max-width: 100%; padding-right: 2.25rem; appearance: auto; }
            .av2 .st-number { width: 6.5rem; }
            .av2 .st-time { width: auto; }
            .av2 .st-field { width: 100%; }
            .av2 .st-form { display: flex; flex-direction: column; gap: 10px; min-width: 0; }
            .av2 .st-form .av2-btn--inline { align-self: flex-start; }
            .av2 .st-inline { display: flex; gap: 8px; align-items: stretch; min-width: 0; }
            .av2 .st-inline .av2-field__control { flex: 1 1 auto; }
            .av2 .st-inline .av2-btn--inline { flex: none; }
            .av2 .st-topics { display: flex; flex-wrap: wrap; gap: 6px; min-width: 0; }
            .av2 .st-topics .av2-chip { background: var(--av2-paper); }
            .av2 .st-topics .av2-chip--reward { background: var(--av2-yellow); }
            .av2 .st-jump .av2-chip--story { background: var(--av2-blue); }

            /* The segmented control, as drawn: radius 12, 700 14px; active =
               ink face, paper label, 3px press; inactive = paper face, line-2
               press. The design draws it 40px tall; it is floored at the 44px
               tap minimum, which is the one number the design does not get to
               set (WP-20 D-10). */
            .av2 .st-seg { display: flex; gap: 6px; min-width: 0; width: 100%; }
            .av2 .st-seg__btn {
                flex: 1 1 0;
                min-width: 0;
                min-height: max(2.5rem, var(--av2-tap));
                padding: 0 4px;
                border: 0;
                border-radius: 12px;
                background: var(--av2-paper);
                color: var(--av2-ink);
                box-shadow: 0 var(--av2-press-sm) 0 var(--av2-line-2);
                font-family: inherit;
                font-size: 0.875rem;
                font-weight: 700;
                line-height: 1.2;
                cursor: pointer;
                transition: transform var(--av2-press-dur), box-shadow var(--av2-press-dur), background 0.15s;
                overflow-wrap: anywhere;
            }
            .av2 .st-seg__btn[data-active='true'] {
                background: var(--av2-ink);
                color: var(--av2-on-ink);
                box-shadow: 0 var(--av2-press-sm) 0 var(--av2-ink-deep);
            }
            .av2 .st-seg__btn:active {
                transform: translateY(var(--av2-press-sm));
                box-shadow: 0 0 0 transparent;
            }

            /* The pill toggle, as drawn: 48×28, blue on / line-2 off, 22px paper
               knob at 3px. The 44px tap floor is the transparent button around it. */
            .av2 .st-switch {
                display: inline-grid;
                place-items: center;
                flex: none;
                width: 3rem;
                height: var(--av2-tap);
                padding: 0;
                border: 0;
                background: transparent;
                cursor: pointer;
            }
            .av2 .st-switch__pill {
                position: relative;
                display: block;
                width: 48px;
                height: 28px;
                border-radius: var(--av2-r-pill);
                background: var(--av2-line-2);
                transition: background 0.2s;
            }
            .av2 .st-switch[aria-checked='true'] .st-switch__pill { background: var(--av2-blue); }
            .av2 .st-switch__knob {
                position: absolute;
                top: 3px;
                left: 3px;
                width: 22px;
                height: 22px;
                border-radius: var(--av2-r-pill);
                background: var(--av2-card);
                transition: left 0.2s;
            }
            .av2 .st-switch[aria-checked='true'] .st-switch__knob { left: 23px; }
            .av2 .st-switch:disabled { cursor: not-allowed; }
            .av2 .st-switch:disabled .st-switch__pill { background: var(--av2-line); }

            .av2 .st-range { display: flex; align-items: center; gap: 10px; min-width: 0; }
            .av2 .st-range input[type='range'] { flex: 1 1 auto; min-width: 0; height: var(--av2-tap); accent-color: var(--av2-blue); background: transparent; }

            .av2 .st-danger { color: var(--av2-red); }
            .av2 .st-danger:disabled { color: var(--av2-ink-2); }

            /* The save bar stays reachable above the tab bar while the sheet scrolls. */
            .av2 .st-savebar {
                position: sticky;
                bottom: 12px;
                z-index: 5;
                margin: 20px var(--av2-gutter) 0;
                min-width: 0;
            }
            .av2 .st-savebar .av2-notice { background: var(--av2-card); box-shadow: 0 var(--av2-press-md) 0 var(--av2-line-2); }
            @media (max-width: 760px) {
                .av2 .st-savebar { bottom: calc(var(--phone-bottom-nav-space, 0px) + 12px); }
            }
            @media (max-width: 400px) {
                .av2 .st-row:not(.st-row--stacked) > .st-row__control { max-width: 50%; }
                .av2 .st-seg { flex-wrap: wrap; }
                .av2 .st-seg__btn { flex-basis: calc(33.333% - 4px); }
            }
        `}</style>
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
