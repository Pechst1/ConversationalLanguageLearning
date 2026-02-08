/**
 * Audio-Only Conversation Mode
 * 
 * Zero-decision, 5-minute audio-only conversation with:
 * - One-tap start (no topic selection)
 * - Minimal UI (waveform, mic button, help)
 * - Smart auto-context based on errors, interests, time of day
 * - Hidden text by default (audio-focused)
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/router';
import { useSession } from 'next-auth/react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Mic,
    MicOff,
    Volume2,
    VolumeX,
    Eye,
    EyeOff,
    HelpCircle,
    X,
    RefreshCw,
    Clock,
    Sparkles,
    ArrowLeft,
    MessageCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/Button';
import apiService from '@/services/api';
import { RoleplaySelection } from '@/components/audio/RoleplaySelection';
import Link from 'next/link';

// ─────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────

interface AudioSessionState {
    sessionId: string | null;
    status: 'idle' | 'selecting' | 'starting' | 'listening' | 'processing' | 'speaking' | 'ended';
    systemPrompt: string;
    conversationHistory: Array<{ role: 'user' | 'assistant'; content: string }>;
    currentTranscript: string;
    aiResponse: string;
    showText: boolean;
    elapsedSeconds: number;
    totalXP: number;
    errors: Array<{
        original: string;
        correction: string;
        explanation: string;
        concept_id?: number | null;
        concept_name?: string | null;
    }>;
}

interface HelpTip {
    icon: React.ReactNode;
    title: string;
    description: string;
}

// ─────────────────────────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────────────────────────

export default function AudioSessionPage() {
    const router = useRouter();
    const { data: session, status: authStatus } = useSession();

    // State
    const [state, setState] = useState<AudioSessionState>({
        sessionId: null,
        status: 'idle',
        systemPrompt: '',
        conversationHistory: [],
        currentTranscript: '',
        aiResponse: '',
        showText: false,
        elapsedSeconds: 0,
        totalXP: 0,
        errors: [],
    });

    const [showHelp, setShowHelp] = useState(false);
    const [isMuted, setIsMuted] = useState(false);
    const [showEndConfirm, setShowEndConfirm] = useState(false);

    // Refs
    const mediaRecorderRef = useRef<MediaRecorder | null>(null);
    const audioChunksRef = useRef<Blob[]>([]);
    const timerRef = useRef<NodeJS.Timeout | null>(null);
    const audioRef = useRef<HTMLAudioElement | null>(null);

    // ─────────────────────────────────────────────────────────────────
    // Timer
    // ─────────────────────────────────────────────────────────────────

    useEffect(() => {
        if (state.status !== 'idle' && state.status !== 'ended' && state.status !== 'starting') {
            timerRef.current = setInterval(() => {
                setState(prev => ({ ...prev, elapsedSeconds: prev.elapsedSeconds + 1 }));
            }, 1000);
        }

        return () => {
            if (timerRef.current) clearInterval(timerRef.current);
        };
    }, [state.status]);

    // ─────────────────────────────────────────────────────────────────
    // Start Session
    // ─────────────────────────────────────────────────────────────────

    const startSession = async (scenarioId: string | null = null) => {
        setState(prev => ({ ...prev, status: 'starting' }));

        try {
            const response = await apiService.startAudioSession(scenarioId || undefined);

            setState(prev => ({
                ...prev,
                sessionId: response.session_id,
                systemPrompt: response.context.system_prompt || '',
                status: 'speaking',
                conversationHistory: [
                    { role: 'assistant', content: response.opening_message }
                ],
                aiResponse: response.opening_message,
            }));

            // Play opening audio
            await playTTS(response.opening_message);

        } catch (error) {
            console.error('Failed to start audio session:', error);
            setState(prev => ({ ...prev, status: 'idle' }));
        }
    };

    // ─────────────────────────────────────────────────────────────────
    // TTS Playback
    // ─────────────────────────────────────────────────────────────────

    // ─────────────────────────────────────────────────────────────────
    // TTS Playback
    // ─────────────────────────────────────────────────────────────────

    const playTTS = async (text: string) => {
        if (isMuted) {
            setState(prev => ({ ...prev, status: 'listening' }));
            return;
        }

        try {
            // Try backend TTS (ElevenLabs / OpenAI) first
            const audioData = await apiService.synthesizeSpeech(text);
            const blob = new Blob([audioData], { type: 'audio/mpeg' });
            const url = URL.createObjectURL(blob);

            if (audioRef.current) {
                audioRef.current.pause();
                audioRef.current = null;
            }

            const audio = new Audio(url);
            audioRef.current = audio;

            audio.onended = () => {
                setState(prev => ({ ...prev, status: 'listening' }));
                URL.revokeObjectURL(url);
            };

            await audio.play();
        } catch (error) {
            console.error('TTS error, falling back to browser:', error);

            // Fallback to browser's Web Speech API
            try {
                const utterance = new SpeechSynthesisUtterance(text);
                utterance.lang = 'fr-FR'; // French TTS
                utterance.rate = 0.9;

                utterance.onend = () => {
                    setState(prev => ({ ...prev, status: 'listening' }));
                };

                window.speechSynthesis.speak(utterance);
            } catch (fallbackError) {
                console.error("Fallback TTS also failed", fallbackError);
                // Just move state forward so user isn't stuck
                setState(prev => ({ ...prev, status: 'listening' }));
            }
        }
    };

    // ─────────────────────────────────────────────────────────────────
    // Speech Recognition
    // ─────────────────────────────────────────────────────────────────

    const startRecording = async () => {
        // Stop any playing audio
        if (audioRef.current) {
            audioRef.current.pause();
        }
        window.speechSynthesis.cancel();

        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const mediaRecorder = new MediaRecorder(stream);
            mediaRecorderRef.current = mediaRecorder;
            audioChunksRef.current = [];

            mediaRecorder.ondataavailable = (event) => {
                audioChunksRef.current.push(event.data);
            };

            mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
                await processAudio(audioBlob);
                stream.getTracks().forEach(track => track.stop());
            };

            mediaRecorder.start();
            setState(prev => ({ ...prev, status: 'listening' }));
        } catch (error) {
            console.error('Failed to start recording:', error);
        }
    };

    const stopRecording = () => {
        if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
            mediaRecorderRef.current.stop();
            setState(prev => ({ ...prev, status: 'processing' }));
        }
    };

    // ─────────────────────────────────────────────────────────────────
    // Process Audio (Whisper STT + AI Response)
    // ─────────────────────────────────────────────────────────────────

    const processAudio = async (audioBlob: Blob) => {
        try {
            // Transcribe with Whisper
            const transcript = await apiService.transcribeAudio(audioBlob);

            // Check for exit commands
            const lower = transcript.toLowerCase().trim().replace(/[.,!?]/g, '');
            if (['stop', 'exit', 'goodbye', 'au revoir', 'terminer', 'finir'].includes(lower)) {
                await endSession();
                return;
            }

            if (!transcript || transcript.trim().length === 0) {
                setState(prev => ({ ...prev, status: 'listening' }));
                return;
            }

            setState(prev => ({
                ...prev,
                currentTranscript: transcript,
                conversationHistory: [
                    ...prev.conversationHistory,
                    { role: 'user', content: transcript }
                ],
            }));

            // Get AI response
            const response = await apiService.respondToAudioSession({
                session_id: state.sessionId!,
                user_text: transcript,
                system_prompt: state.systemPrompt,
                conversation_history: state.conversationHistory,
            });

            const newHistory = [
                ...state.conversationHistory,
                { role: 'user' as const, content: transcript },
                { role: 'assistant' as const, content: response.ai_response },
            ];

            setState(prev => ({
                ...prev,
                aiResponse: response.ai_response,
                conversationHistory: newHistory,
                totalXP: prev.totalXP + (response.xp_awarded || 10),
                showText: response.should_show_text || prev.showText,
                errors: response.detected_errors?.length > 0
                    ? [...prev.errors, ...response.detected_errors]
                    : prev.errors,
                status: 'speaking',
            }));

            // Play AI response
            await playTTS(response.ai_response);

        } catch (error) {
            console.error('Failed to process audio:', error);
            setState(prev => ({ ...prev, status: 'listening' }));
        }
    };

    // ─────────────────────────────────────────────────────────────────
    // End Session
    // ─────────────────────────────────────────────────────────────────

    const endSession = async () => {
        if (timerRef.current) clearInterval(timerRef.current);
        window.speechSynthesis.cancel();
        if (audioRef.current) {
            audioRef.current.pause();
            audioRef.current = null;
        }

        if (state.sessionId) {
            try {
                await apiService.endAudioSession({ session_id: state.sessionId });
            } catch (error) {
                console.error('Failed to end session:', error);
            }
        }

        setState(prev => ({ ...prev, status: 'ended' }));
    };

    // ─────────────────────────────────────────────────────────────────
    // Format time
    // ─────────────────────────────────────────────────────────────────

    const formatTime = (seconds: number) => {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    };

    // ─────────────────────────────────────────────────────────────────
    // Help Tips
    // ─────────────────────────────────────────────────────────────────

    const helpTips: HelpTip[] = [
        {
            icon: <Mic className="w-5 h-5" />,
            title: 'Tap to speak',
            description: 'Hold the microphone button while speaking, release when done.',
        },
        {
            icon: <Eye className="w-5 h-5" />,
            title: 'Show text',
            description: 'Tap the eye icon to reveal what was said if you need help.',
        },
        {
            icon: <RefreshCw className="w-5 h-5" />,
            title: 'Repeat',
            description: 'Tap the speaker icon to hear the AI response again.',
        },
    ];

    // ─────────────────────────────────────────────────────────────────
    // Auth check
    // ─────────────────────────────────────────────────────────────────

    if (authStatus === 'loading') {
        return (
            <div className="min-h-screen bg-gradient-to-br from-indigo-900 via-purple-900 to-black flex items-center justify-center">
                <div className="animate-spin rounded-full h-12 w-12 border-4 border-white border-t-transparent" />
            </div>
        );
    }

    if (!session) {
        router.push('/auth/signin');
        return null;
    }

    // ─────────────────────────────────────────────────────────────────
    // Render: Idle State (Start Screen)
    // ─────────────────────────────────────────────────────────────────

    if (state.status === 'idle') {
        return (
            <div className="min-h-screen bg-gradient-to-br from-indigo-900 via-purple-900 to-black flex flex-col items-center justify-center p-6">
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="text-center"
                >
                    <div className="mb-8">
                        <motion.div
                            animate={{
                                scale: [1, 1.1, 1],
                                rotate: [0, 5, -5, 0],
                            }}
                            transition={{ duration: 3, repeat: Infinity }}
                            className="inline-block p-6 bg-gradient-to-br from-purple-500 to-pink-500 rounded-full shadow-2xl"
                        >
                            <MessageCircle className="w-16 h-16 text-white" />
                        </motion.div>
                    </div>

                    <h1 className="text-4xl font-black text-white mb-4">
                        Audio Mode
                    </h1>
                    <p className="text-xl text-purple-200 mb-8 max-w-md mx-auto">
                        5 minutes of pure conversation. No reading, just listening and speaking.
                    </p>

                    <motion.button
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                        onClick={() => setState(prev => ({ ...prev, status: 'selecting' }))}
                        className="px-12 py-5 bg-gradient-to-r from-green-400 to-emerald-500 text-white text-2xl font-bold rounded-full shadow-2xl hover:shadow-green-500/50 transition-all"
                    >
                        <span className="flex items-center gap-3">
                            <Sparkles className="w-7 h-7" />
                            Start Talking
                        </span>
                    </motion.button>

                    <button
                        onClick={() => router.push('/dashboard')}
                        className="mt-6 text-purple-300 hover:text-white transition-colors flex items-center gap-2 mx-auto"
                    >
                        <ArrowLeft className="w-4 h-4" />
                        Back to Dashboard
                    </button>
                </motion.div>
            </div>
        );
    }

    // ─────────────────────────────────────────────────────────────────
    // Render: Selecting State
    // ─────────────────────────────────────────────────────────────────

    if (state.status === 'selecting') {
        return (
            <div className="min-h-screen bg-gradient-to-br from-indigo-900 via-purple-900 to-black flex flex-col items-center justify-center p-6 bg-fixed">
                <RoleplaySelection
                    onSelect={startSession}
                    onCancel={() => setState(prev => ({ ...prev, status: 'idle' }))}
                />
            </div>
        );
    }

    // ─────────────────────────────────────────────────────────────────
    // Render: Starting State
    // ─────────────────────────────────────────────────────────────────

    if (state.status === 'starting') {
        return (
            <div className="min-h-screen bg-gradient-to-br from-indigo-900 via-purple-900 to-black flex flex-col items-center justify-center">
                <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
                    className="w-20 h-20 border-4 border-t-purple-400 border-r-pink-400 border-b-blue-400 border-l-transparent rounded-full"
                />
                <p className="mt-6 text-xl text-purple-200">Preparing your conversation...</p>
            </div>
        );
    }

    // ─────────────────────────────────────────────────────────────────
    // Render: Ended State
    // ─────────────────────────────────────────────────────────────────

    if (state.status === 'ended') {
        return (
            <div className="min-h-screen bg-gradient-to-br from-indigo-900 via-purple-900 to-black flex flex-col items-center justify-center p-6">
                <motion.div
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    className="text-center"
                >
                    <div className="mb-8">
                        <motion.div
                            initial={{ scale: 0 }}
                            animate={{ scale: 1 }}
                            transition={{ type: 'spring', delay: 0.2 }}
                            className="inline-block p-6 bg-gradient-to-br from-green-400 to-emerald-500 rounded-full"
                        >
                            <Sparkles className="w-16 h-16 text-white" />
                        </motion.div>
                    </div>

                    <h1 className="text-4xl font-black text-white mb-4">
                        Great Session! 🎉
                    </h1>

                    <div className="grid grid-cols-2 gap-6 max-w-sm mx-auto mb-8">
                        <div className="bg-white/10 backdrop-blur rounded-xl p-4">
                            <p className="text-3xl font-black text-white">{formatTime(state.elapsedSeconds)}</p>
                            <p className="text-purple-300 text-sm">Duration</p>
                        </div>
                        <div className="bg-white/10 backdrop-blur rounded-xl p-4">
                            <p className="text-3xl font-black text-yellow-400">{state.totalXP} XP</p>
                            <p className="text-purple-300 text-sm">Earned</p>
                        </div>
                    </div>

                    {state.errors.length > 0 && (
                        <div className="mb-8 max-w-md mx-auto">
                            <h3 className="text-lg font-bold text-white mb-3">Corrections</h3>
                            <div className="space-y-3">
                                {state.errors.map((error, i) => (
                                    <div key={i} className="bg-white/10 rounded-lg p-3 text-left">
                                        <p className="text-red-300 line-through text-sm">{error.original}</p>
                                        <p className="text-green-300 font-medium">{error.correction}</p>
                                        <p className="text-purple-200 text-xs mt-1">{error.explanation}</p>
                                        {error.concept_id && (
                                            <Link
                                                href={`/grammar`}
                                                className="inline-flex items-center gap-1 mt-2 text-xs font-bold text-yellow-400 hover:text-yellow-300 transition-colors uppercase tracking-wide"
                                            >
                                                <Sparkles className="w-3 h-3" />
                                                Review: {error.concept_name || 'Grammar Rule'}
                                            </Link>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    <div className="flex gap-4 justify-center">
                        <motion.button
                            whileHover={{ scale: 1.05 }}
                            whileTap={{ scale: 0.95 }}
                            onClick={() => {
                                setState({
                                    sessionId: null,
                                    status: 'idle',
                                    systemPrompt: '',
                                    conversationHistory: [],
                                    currentTranscript: '',
                                    aiResponse: '',
                                    showText: false,
                                    elapsedSeconds: 0,
                                    totalXP: 0,
                                    errors: [],
                                });
                            }}
                            className="px-8 py-3 bg-gradient-to-r from-purple-500 to-pink-500 text-white font-bold rounded-full"
                        >
                            Another Session
                        </motion.button>
                        <button
                            onClick={() => router.push('/dashboard')}
                            className="px-8 py-3 bg-white/10 text-white font-medium rounded-full hover:bg-white/20 transition-colors"
                        >
                            Back to Dashboard
                        </button>
                    </div>
                </motion.div>
            </div>
        );
    }

    // ─────────────────────────────────────────────────────────────────
    // Render: Active Session
    // ─────────────────────────────────────────────────────────────────

    return (
        <div className="min-h-screen bg-gradient-to-br from-indigo-900 via-purple-900 to-black flex flex-col">
            {/* Header */}
            <div className="flex items-center justify-between p-4">
                <button
                    onClick={() => setShowEndConfirm(true)}
                    className="p-2 text-white/60 hover:text-white transition-colors"
                >
                    <X className="w-6 h-6" />
                </button>

                <div className="flex items-center gap-2 bg-white/10 backdrop-blur px-4 py-2 rounded-full">
                    <Clock className="w-4 h-4 text-purple-300" />
                    <span className="text-white font-mono font-bold">{formatTime(state.elapsedSeconds)}</span>
                </div>

                <button
                    onClick={() => setShowHelp(true)}
                    className="p-2 text-white/60 hover:text-white transition-colors"
                >
                    <HelpCircle className="w-6 h-6" />
                </button>
            </div>

            {/* Main Content */}
            <div className="flex-1 flex flex-col items-center justify-center px-6">
                {/* Waveform Animation */}
                <motion.div
                    className="w-48 h-48 relative mb-8"
                    animate={{
                        scale: state.status === 'speaking' ? [1, 1.1, 1] : 1,
                    }}
                    transition={{ duration: 0.5, repeat: state.status === 'speaking' ? Infinity : 0 }}
                >
                    {/* Animated rings */}
                    {[...Array(3)].map((_, i) => (
                        <motion.div
                            key={i}
                            className="absolute inset-0 rounded-full border-2 border-purple-400/30"
                            animate={{
                                scale: state.status === 'listening' || state.status === 'speaking'
                                    ? [1, 1.5 + i * 0.3]
                                    : 1,
                                opacity: state.status === 'listening' || state.status === 'speaking'
                                    ? [0.6, 0]
                                    : 0.3,
                            }}
                            transition={{
                                duration: 1.5,
                                repeat: Infinity,
                                delay: i * 0.3,
                            }}
                        />
                    ))}

                    {/* Center orb */}
                    <motion.div
                        className={`absolute inset-4 rounded-full flex items-center justify-center ${state.status === 'speaking'
                            ? 'bg-gradient-to-br from-pink-500 to-purple-600'
                            : state.status === 'listening'
                                ? 'bg-gradient-to-br from-green-400 to-emerald-500'
                                : 'bg-gradient-to-br from-blue-500 to-indigo-600'
                            }`}
                        animate={{
                            scale: state.status === 'processing' ? [1, 0.95, 1] : 1,
                        }}
                        transition={{ duration: 0.5, repeat: state.status === 'processing' ? Infinity : 0 }}
                    >
                        {state.status === 'speaking' && <Volume2 className="w-12 h-12 text-white" />}
                        {state.status === 'listening' && <Mic className="w-12 h-12 text-white" />}
                        {state.status === 'processing' && (
                            <motion.div
                                animate={{ rotate: 360 }}
                                transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                            >
                                <RefreshCw className="w-12 h-12 text-white" />
                            </motion.div>
                        )}
                    </motion.div>
                </motion.div>

                {/* Status text */}
                <p className="text-lg text-purple-200 mb-8">
                    {state.status === 'speaking' && 'AI is speaking...'}
                    {state.status === 'listening' && 'Your turn to speak'}
                    {state.status === 'processing' && 'Thinking...'}
                </p>

                {/* Text display (when enabled) */}
                <AnimatePresence>
                    {state.showText && state.aiResponse && (
                        <motion.div
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -20 }}
                            className="max-w-md mx-auto mb-8 p-4 bg-white/10 backdrop-blur rounded-xl"
                        >
                            <p className="text-white text-center">{state.aiResponse}</p>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>

            {/* Bottom Controls */}
            <div className="p-6 pb-10">
                <div className="flex items-center justify-center gap-6">
                    {/* Mute button */}
                    <button
                        onClick={() => setIsMuted(!isMuted)}
                        className={`p-4 rounded-full transition-colors ${isMuted ? 'bg-red-500/20 text-red-400' : 'bg-white/10 text-white/60 hover:text-white'
                            }`}
                    >
                        {isMuted ? <VolumeX className="w-6 h-6" /> : <Volume2 className="w-6 h-6" />}
                    </button>

                    {/* Microphone button */}
                    <motion.button
                        whileTap={{ scale: 0.9 }}
                        onMouseDown={startRecording}
                        onMouseUp={stopRecording}
                        onTouchStart={startRecording}
                        onTouchEnd={stopRecording}
                        disabled={state.status !== 'listening'}
                        className={`p-8 rounded-full transition-all ${state.status === 'listening'
                            ? 'bg-gradient-to-br from-green-400 to-emerald-500 shadow-lg shadow-green-500/30'
                            : 'bg-white/20 cursor-not-allowed'
                            }`}
                    >
                        <Mic className="w-10 h-10 text-white" />
                    </motion.button>

                    {/* Show text button */}
                    <button
                        onClick={() => setState(prev => ({ ...prev, showText: !prev.showText }))}
                        className={`p-4 rounded-full transition-colors ${state.showText ? 'bg-purple-500/20 text-purple-400' : 'bg-white/10 text-white/60 hover:text-white'
                            }`}
                    >
                        {state.showText ? <EyeOff className="w-6 h-6" /> : <Eye className="w-6 h-6" />}
                    </button>
                </div>

                {/* XP indicator */}
                <div className="text-center mt-4">
                    <span className="text-yellow-400 font-bold">{state.totalXP} XP</span>
                </div>
            </div>

            {/* Help Modal */}
            <AnimatePresence>
                {showHelp && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-6"
                        onClick={() => setShowHelp(false)}
                    >
                        <motion.div
                            initial={{ scale: 0.9, y: 20 }}
                            animate={{ scale: 1, y: 0 }}
                            exit={{ scale: 0.9, y: 20 }}
                            onClick={e => e.stopPropagation()}
                            className="bg-gradient-to-br from-purple-900 to-indigo-900 rounded-2xl p-6 max-w-sm w-full"
                        >
                            <h2 className="text-2xl font-bold text-white mb-4">How it works</h2>
                            <div className="space-y-4">
                                {helpTips.map((tip, i) => (
                                    <div key={i} className="flex gap-4">
                                        <div className="p-2 bg-white/10 rounded-lg text-purple-300">
                                            {tip.icon}
                                        </div>
                                        <div>
                                            <h3 className="font-bold text-white">{tip.title}</h3>
                                            <p className="text-purple-200 text-sm">{tip.description}</p>
                                        </div>
                                    </div>
                                ))}
                            </div>
                            <button
                                onClick={() => setShowHelp(false)}
                                className="mt-6 w-full py-3 bg-white/10 text-white rounded-full font-medium hover:bg-white/20 transition-colors"
                            >
                                Got it!
                            </button>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* End Confirm Modal */}
            <AnimatePresence>
                {showEndConfirm && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-6"
                        onClick={() => setShowEndConfirm(false)}
                    >
                        <motion.div
                            initial={{ scale: 0.9, y: 20 }}
                            animate={{ scale: 1, y: 0 }}
                            exit={{ scale: 0.9, y: 20 }}
                            onClick={e => e.stopPropagation()}
                            className="bg-gradient-to-br from-red-900 to-pink-900 rounded-2xl p-6 max-w-sm w-full text-center"
                        >
                            <h2 className="text-2xl font-bold text-white mb-2">End Session?</h2>
                            <p className="text-pink-200 mb-6">You&apos;ve been talking for {formatTime(state.elapsedSeconds)}</p>
                            <div className="flex gap-4">
                                <button
                                    onClick={() => setShowEndConfirm(false)}
                                    className="flex-1 py-3 bg-white/10 text-white rounded-full font-medium hover:bg-white/20 transition-colors"
                                >
                                    Keep Going
                                </button>
                                <button
                                    onClick={endSession}
                                    className="flex-1 py-3 bg-white text-red-900 rounded-full font-bold hover:bg-white/90 transition-colors"
                                >
                                    End
                                </button>
                            </div>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}
