import React, { createContext, useContext, useState, useCallback, useRef } from 'react';
import { getSession } from 'next-auth/react';

interface SpeakingModeContextType {
    isSpeakingMode: boolean;
    toggleSpeakingMode: () => void;
    speakText: (text: string) => Promise<void>;
    isSpeaking: boolean;
    stopSpeaking: () => void;
    // Voice-first mode additions
    isVoiceFirstMode: boolean;
    setVoiceFirstMode: (enabled: boolean) => void;
    onSpeechEnd: (() => void) | null;
    setOnSpeechEnd: (callback: (() => void) | null) => void;
    // Audio-only mode (listening practice)
    isAudioOnlyMode: boolean;
    toggleAudioOnlyMode: () => void;
    revealedMessages: Set<string>;
    revealMessage: (messageId: string) => void;
    revealAllMessages: () => void;
}

const SpeakingModeContext = createContext<SpeakingModeContextType | null>(null);

export function SpeakingModeProvider({ children }: { children: React.ReactNode }) {
    const [isSpeakingMode, setIsSpeakingMode] = useState(false);
    const [isSpeaking, setIsSpeaking] = useState(false);
    const [isVoiceFirstMode, setVoiceFirstMode] = useState(false);
    const [isAudioOnlyMode, setIsAudioOnlyMode] = useState(false);
    const [revealedMessages, setRevealedMessages] = useState<Set<string>>(new Set());
    const audioRef = useRef<HTMLAudioElement | null>(null);
    const onSpeechEndRef = useRef<(() => void) | null>(null);

    const toggleSpeakingMode = useCallback(() => {
        setIsSpeakingMode((prev) => {
            const newValue = !prev;
            // When speaking mode is enabled, also enable voice-first mode
            if (newValue) {
                setVoiceFirstMode(true);
            }
            return newValue;
        });
    }, []);

    const toggleAudioOnlyMode = useCallback(() => {
        setIsAudioOnlyMode((prev) => {
            const newValue = !prev;
            // When enabling audio-only mode, ensure speaking mode is also enabled
            if (newValue && !isSpeakingMode) {
                setIsSpeakingMode(true);
                setVoiceFirstMode(true);
            }
            // Clear revealed messages when toggling mode
            setRevealedMessages(new Set());
            return newValue;
        });
    }, [isSpeakingMode]);

    const revealMessage = useCallback((messageId: string) => {
        setRevealedMessages(prev => new Set(prev).add(messageId));
    }, []);

    const revealAllMessages = useCallback(() => {
        // Note: This will be overridden by the component that knows all message IDs
        // For now, we set a special flag
        setRevealedMessages(new Set(['__ALL__']));
    }, []);

    const setOnSpeechEnd = useCallback((callback: (() => void) | null) => {
        onSpeechEndRef.current = callback;
    }, []);

    const stopSpeaking = useCallback(() => {
        if (audioRef.current) {
            audioRef.current.pause();
            audioRef.current.currentTime = 0;
            audioRef.current = null;
        }
        setIsSpeaking(false);
    }, []);

    const speakText = useCallback(async (text: string) => {
        if (!text.trim()) return;

        // Stop any existing playback
        stopSpeaking();

        try {
            setIsSpeaking(true);
            const session = await getSession();
            const token = (session as any)?.accessToken;

            const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
            const response = await fetch(`${baseUrl}/audio/speak`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...(token ? { Authorization: `Bearer ${token}` } : {}),
                },
                body: JSON.stringify({ text, voice: 'nova' }),
            });

            if (!response.ok) {
                throw new Error('TTS request failed');
            }

            const audioBlob = await response.blob();
            const audioUrl = URL.createObjectURL(audioBlob);
            const audio = new Audio(audioUrl);
            audioRef.current = audio;

            audio.onended = () => {
                URL.revokeObjectURL(audioUrl);
                setIsSpeaking(false);
                audioRef.current = null;
                // Call the onSpeechEnd callback if set (for auto-recording in voice-first mode)
                if (onSpeechEndRef.current) {
                    onSpeechEndRef.current();
                }
            };

            audio.onerror = () => {
                URL.revokeObjectURL(audioUrl);
                setIsSpeaking(false);
                audioRef.current = null;
            };

            await audio.play();
        } catch (err) {
            console.error('TTS error:', err);
            setIsSpeaking(false);
        }
    }, [stopSpeaking]);

    return (
        <SpeakingModeContext.Provider
            value={{
                isSpeakingMode,
                toggleSpeakingMode,
                speakText,
                isSpeaking,
                stopSpeaking,
                isVoiceFirstMode,
                setVoiceFirstMode,
                onSpeechEnd: onSpeechEndRef.current,
                setOnSpeechEnd,
                // Audio-only mode
                isAudioOnlyMode,
                toggleAudioOnlyMode,
                revealedMessages,
                revealMessage,
                revealAllMessages,
            }}
        >
            {children}
        </SpeakingModeContext.Provider>
    );
}

export function useSpeakingMode() {
    const context = useContext(SpeakingModeContext);
    if (!context) {
        throw new Error('useSpeakingMode must be used within a SpeakingModeProvider');
    }
    return context;
}
