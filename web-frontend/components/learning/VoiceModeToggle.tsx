import React from 'react';
import { Mic, Volume2, VolumeX, EarOff, Ear } from 'lucide-react';
import { useSpeakingMode } from '@/contexts/SpeakingModeContext';

interface VoiceModeToggleProps {
    className?: string;
}

/**
 * Toggle button to enable/disable voice-first conversation mode
 * When enabled:
 * - AI responses are automatically spoken
 * - User input switches to voice recording
 * - Messages use the speaking_first style for shorter responses
 * 
 * Audio-only mode (listening practice):
 * - AI text is hidden, user must rely on listening
 * - Text is revealed only when user speaks or clicks to reveal
 * - Forces improvement of listening skills
 */
export default function VoiceModeToggle({ className }: VoiceModeToggleProps) {
    const {
        isSpeakingMode,
        toggleSpeakingMode,
        isSpeaking,
        isAudioOnlyMode,
        toggleAudioOnlyMode
    } = useSpeakingMode();

    return (
        <div className={`flex flex-wrap items-center gap-2 ${className || ''}`}>
            <button
                type="button"
                onClick={toggleSpeakingMode}
                className={`inline-flex items-center gap-2 rounded-full border px-3 py-2 text-sm font-medium transition-colors ${
                    isSpeakingMode
                        ? 'border-stone-900 bg-stone-900 text-stone-50'
                        : 'border-stone-200 bg-white text-stone-700 hover:border-stone-300 hover:bg-stone-50'
                }`}
                title={isSpeakingMode ? 'Disable speaking mode' : 'Enable speaking mode'}
            >
                {isSpeakingMode ? (
                    <Volume2 className={`h-4 w-4 ${isSpeaking ? 'animate-pulse' : ''}`} />
                ) : (
                    <VolumeX className="h-4 w-4" />
                )}
                <span>{isSpeakingMode ? 'Voice on' : 'Voice'}</span>
            </button>

            {isSpeakingMode ? (
                <button
                    type="button"
                    onClick={toggleAudioOnlyMode}
                    className={`inline-flex items-center gap-2 rounded-full border px-3 py-2 text-sm font-medium transition-colors ${
                        isAudioOnlyMode
                            ? 'border-amber-300 bg-amber-50 text-amber-800'
                            : 'border-stone-200 bg-white text-stone-700 hover:border-stone-300 hover:bg-stone-50'
                    }`}
                    title={
                        isAudioOnlyMode
                            ? 'Disable listening mode (show text)'
                            : 'Enable listening mode (hide AI text for practice)'
                    }
                >
                    {isAudioOnlyMode ? <Ear className="h-4 w-4" /> : <EarOff className="h-4 w-4" />}
                    <span>{isAudioOnlyMode ? 'Listening' : 'Listen'}</span>
                </button>
            ) : null}

            {isSpeakingMode ? (
                <div className="hidden items-center gap-1 text-xs text-stone-500 lg:flex">
                    {isAudioOnlyMode ? (
                        <>
                            <Ear className="h-3 w-3 text-amber-600" />
                            <span>Text stays hidden until reveal or reply.</span>
                        </>
                    ) : (
                        <>
                            <Mic className="h-3 w-3" />
                            <span>Use the mic in the composer when you want to speak.</span>
                        </>
                    )}
                </div>
            ) : null}
        </div>
    );
}
