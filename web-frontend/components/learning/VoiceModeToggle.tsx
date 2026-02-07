import React from 'react';
import { Mic, Volume2, VolumeX, EarOff, Ear } from 'lucide-react';
import { Button } from '@/components/ui/Button';
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
        <div className={`flex items-center gap-2 ${className || ''}`}>
            {/* Speaking Mode Toggle */}
            <Button
                type="button"
                variant={isSpeakingMode ? "default" : "outline"}
                size="sm"
                onClick={toggleSpeakingMode}
                className={`
                    relative overflow-hidden transition-all duration-300
                    ${isSpeakingMode
                        ? 'bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white border-0 shadow-lg'
                        : 'hover:bg-gray-100'
                    }
                `}
                title={isSpeakingMode ? "Disable speaking mode" : "Enable speaking mode"}
            >
                <div className="flex items-center gap-2">
                    {isSpeakingMode ? (
                        <>
                            <Volume2 className={`h-4 w-4 ${isSpeaking ? 'animate-pulse' : ''}`} />
                            <span className="text-sm font-medium hidden sm:inline">Voice ON</span>
                            {isSpeaking && (
                                <span className="absolute top-0 right-0 flex h-2 w-2">
                                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-white opacity-75" />
                                    <span className="relative inline-flex rounded-full h-2 w-2 bg-white" />
                                </span>
                            )}
                        </>
                    ) : (
                        <>
                            <VolumeX className="h-4 w-4" />
                            <span className="text-sm font-medium hidden sm:inline">Voice</span>
                        </>
                    )}
                </div>
            </Button>

            {/* Audio-Only Mode Toggle - Only visible when speaking mode is on */}
            {isSpeakingMode && (
                <Button
                    type="button"
                    variant={isAudioOnlyMode ? "default" : "outline"}
                    size="sm"
                    onClick={toggleAudioOnlyMode}
                    className={`
                        relative overflow-hidden transition-all duration-300
                        ${isAudioOnlyMode
                            ? 'bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700 text-white border-0 shadow-lg'
                            : 'hover:bg-gray-100 border-dashed'
                        }
                    `}
                    title={isAudioOnlyMode
                        ? "Disable listening mode (show text)"
                        : "Enable listening mode (hide AI text for practice)"
                    }
                >
                    <div className="flex items-center gap-2">
                        {isAudioOnlyMode ? (
                            <>
                                <Ear className="h-4 w-4" />
                                <span className="text-sm font-medium hidden sm:inline">Listening</span>
                            </>
                        ) : (
                            <>
                                <EarOff className="h-4 w-4" />
                                <span className="text-sm font-medium hidden sm:inline">Listen</span>
                            </>
                        )}
                    </div>
                </Button>
            )}

            {/* Help text */}
            {isSpeakingMode && (
                <div className="text-xs text-gray-500 hidden lg:block max-w-[150px]">
                    {isAudioOnlyMode ? (
                        <span className="flex items-center gap-1 text-amber-600 font-medium">
                            <Ear className="h-3 w-3" />
                            Text hidden - click to reveal
                        </span>
                    ) : (
                        <span className="flex items-center gap-1">
                            <Mic className="h-3 w-3" />
                            Press mic to speak
                        </span>
                    )}
                </div>
            )}
        </div>
    );
}
