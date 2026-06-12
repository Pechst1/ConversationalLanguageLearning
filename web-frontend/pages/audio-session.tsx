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
    AlertTriangle,
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
            <div className="min-h-screen bg-[var(--app-paper)] flex items-center justify-center">
                <div className="animate-spin rounded-full h-12 w-12 border-4 border-black border-t-transparent" />
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
            <div className="min-h-screen bg-[var(--app-paper)] text-[var(--app-ink)] flex flex-col items-center justify-center p-6">
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="text-center"
                >
                    <div className="mb-8 font-black">
                        <motion.div
                            animate={{
                                scale: [1, 1.05, 1],
                                rotate: [0, 2, -2, 0],
                            }}
                            transition={{ duration: 3, repeat: Infinity }}
                            className="inline-block p-6 bg-white border-4 border-black rounded-none shadow-[6px_6px_0px_0px_#000]"
                        >
                            <MessageCircle className="w-16 h-16 text-black" />
                        </motion.div>
                    </div>

                    <h1 className="font-serif text-5xl italic text-[var(--app-ink)] mb-4">
                        Audio Mode
                    </h1>
                    <p className="text-lg text-[var(--app-ink-2)] mb-8 max-w-md mx-auto font-medium">
                        5 minutes of pure conversation. No reading, just listening and speaking.
                    </p>

                    <button
                        onClick={() => setState(prev => ({ ...prev, status: 'selecting' }))}
                        className="px-12 py-5 bg-black hover:bg-black/90 text-white text-2xl font-bold rounded-none border-4 border-black shadow-[6px_6px_0px_0px_#000] hover:-translate-y-0.5 hover:shadow-[8px_8px_0px_0px_#000] transition-all flex items-center gap-3 mx-auto"
                    >
                        <Sparkles className="w-7 h-7 text-bauhaus-yellow" />
                        Start Talking
                    </button>

                    <button
                        onClick={() => router.push('/learn')}
                        className="mt-8 text-[var(--app-ink-2)] hover:text-black transition-colors font-bold uppercase text-xs tracking-wider flex items-center gap-2 mx-auto"
                    >
                        <ArrowLeft className="w-4 h-4" />
                        Back to Learning
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
            <div className="min-h-screen bg-[var(--app-paper)] text-[var(--app-ink)] flex flex-col items-center justify-center p-6 bg-fixed">
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
            <div className="min-h-screen bg-[var(--app-paper)] text-[var(--app-ink)] flex flex-col items-center justify-center">
                <div className="w-20 h-20 border-4 border-black border-t-transparent rounded-full animate-spin" />
                <p className="mt-6 text-lg font-bold uppercase tracking-wider text-[var(--app-ink-2)]">Preparing your conversation...</p>
            </div>
        );
    }

    // ─────────────────────────────────────────────────────────────────
    // Render: Ended State
    // ─────────────────────────────────────────────────────────────────

    if (state.status === 'ended') {
        return (
            <div className="min-h-screen bg-[var(--app-paper)] text-[var(--app-ink)] flex flex-col items-center justify-center p-6">
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
                            className="inline-block p-6 bg-white border-4 border-black rounded-none shadow-[4px_4px_0px_0px_#000]"
                        >
                            <Sparkles className="w-16 h-16 text-black" />
                        </motion.div>
                    </div>

                    <h1 className="font-serif text-5xl italic text-[var(--app-ink)] mb-4">
                        Great Session! 🎉
                    </h1>

                    <div className="grid grid-cols-2 gap-6 max-w-sm mx-auto mb-8">
                        <div className="bg-white border-2 border-black rounded-none p-4 shadow-[4px_4px_0px_0px_#000]">
                            <p className="text-3xl font-black text-black">{formatTime(state.elapsedSeconds)}</p>
                            <p className="text-[var(--app-ink-3)] text-xs uppercase font-bold tracking-wider mt-1">Duration</p>
                        </div>
                        <div className="bg-white border-2 border-black rounded-none p-4 shadow-[4px_4px_0px_0px_#000]">
                            <p className="text-3xl font-black text-black">{state.totalXP} XP</p>
                            <p className="text-[var(--app-ink-3)] text-xs uppercase font-bold tracking-wider mt-1">Earned</p>
                        </div>
                    </div>

                    {state.errors.length > 0 && (
                        <div className="mb-8 max-w-md mx-auto">
                            <h3 className="text-lg font-black uppercase tracking-wider text-[var(--app-ink)] mb-3 flex items-center justify-center gap-2">
                                <AlertTriangle className="w-5 h-5 text-bauhaus-red" />
                                Corrections
                            </h3>
                            <div className="space-y-4">
                                {state.errors.map((error, i) => (
                                    <div key={i} className="bg-white border-2 border-black rounded-none p-4 text-left shadow-[3px_3px_0px_0px_#000]">
                                        <p className="text-stone-400 line-through text-sm font-medium">{error.original}</p>
                                        <p className="text-rose-700 font-bold text-base">{error.correction}</p>
                                        <p className="text-stone-600 text-xs mt-1 italic">{error.explanation}</p>
                                        {error.concept_id && (
                                            <Link
                                                href={`/grammar`}
                                                className="inline-flex items-center gap-1 mt-3 px-2 py-1 border border-black bg-bauhaus-yellow text-black text-[10px] font-bold transition-all hover:-translate-y-0.5 hover:shadow-[1px_1px_0px_0px_#000] uppercase tracking-wider"
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
                        <button
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
                            className="px-8 py-3 border-2 border-black bg-black text-white hover:bg-black/90 font-bold rounded-none shadow-[3px_3px_0px_0px_#000] hover:-translate-y-0.5 hover:shadow-[4px_4px_0px_0px_#000] transition-all"
                        >
                            Another Session
                        </button>
                        <button
                            onClick={() => router.push('/learn')}
                            className="px-8 py-3 border-2 border-black bg-white text-black hover:bg-stone-50 font-bold rounded-none shadow-[3px_3px_0px_0px_#000] hover:-translate-y-0.5 hover:shadow-[4px_4px_0px_0px_#000] transition-all"
                        >
                            Back to Learning
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
        <div className="min-h-screen bg-[var(--app-paper)] text-[var(--app-ink)] flex flex-col">
            {/* Header */}
            <div className="flex items-center justify-between p-6">
                <button
                    onClick={() => setShowEndConfirm(true)}
                    className="p-2 border-2 border-black bg-white hover:bg-stone-50 text-black rounded-none shadow-[2px_2px_0px_0px_#000] transition-all"
                >
                    <X className="w-5 h-5" />
                </button>

                <div className="flex items-center gap-2 bg-white border-2 border-black px-4 py-2 rounded-none shadow-[3px_3px_0px_0px_#000]">
                    <Clock className="w-4 h-4 text-black" />
                    <span className="text-black font-mono font-bold">{formatTime(state.elapsedSeconds)}</span>
                </div>

                <button
                    onClick={() => setShowHelp(true)}
                    className="p-2 border-2 border-black bg-white hover:bg-stone-50 text-black rounded-none shadow-[2px_2px_0px_0px_#000] transition-all"
                >
                    <HelpCircle className="w-5 h-5" />
                </button>
            </div>

            {/* Main Content */}
            <div className="flex-1 flex flex-col items-center justify-center px-6">
                {/* Neobrutalist Audio Visualizer Panel */}
                <div className="w-72 h-72 bg-white border-4 border-black relative mb-8 flex flex-col items-center justify-center shadow-[6px_6px_0px_0px_#000]">
                    {/* Retro Grid Background */}
                    <div className="absolute inset-0 bg-[linear-gradient(rgba(0,0,0,0.05)_1px,transparent_1px),linear-gradient(90deg,rgba(0,0,0,0.05)_1px,transparent_1px)] bg-[size:20px_20px] pointer-events-none" />

                    {/* Waveform/Equalizer Bars behind the orb */}
                    <div className="absolute inset-x-0 h-44 flex items-center justify-center gap-1.5 pointer-events-none">
                        {state.status === 'listening' || state.status === 'speaking' ? (
                            [...Array(11)].map((_, i) => {
                                const delay = i * 0.08;
                                const heightFactor = [0.2, 0.4, 0.7, 0.9, 1.0, 0.8, 1.0, 0.9, 0.7, 0.4, 0.2][i];
                                return (
                                    <motion.div
                                        key={i}
                                        className={`w-3 border-2 border-black ${
                                            state.status === 'speaking' ? 'bg-bauhaus-blue' : 'bg-bauhaus-yellow'
                                        }`}
                                        animate={{
                                            height: [
                                                `${heightFactor * 20}px`,
                                                `${heightFactor * 140}px`,
                                                `${heightFactor * 20}px`
                                            ]
                                        }}
                                        transition={{
                                            duration: state.status === 'speaking' ? 0.7 : 0.9,
                                            repeat: Infinity,
                                            ease: 'easeInOut',
                                            delay: delay,
                                        }}
                                    />
                                );
                            })
                        ) : state.status === 'processing' ? (
                            <svg className="w-full h-full p-6" viewBox="0 0 288 176">
                                <motion.path
                                    d="M 10 88 Q 44 20, 78 88 T 146 88 T 214 88 T 278 88"
                                    fill="none"
                                    stroke="black"
                                    strokeWidth="4"
                                    animate={{
                                        d: [
                                            "M 10 88 Q 44 20, 78 88 T 146 88 T 214 88 T 278 88",
                                            "M 10 88 Q 44 156, 78 88 T 146 88 T 214 88 T 278 88",
                                            "M 10 88 Q 44 20, 78 88 T 146 88 T 214 88 T 278 88",
                                        ]
                                    }}
                                    transition={{
                                        duration: 1.2,
                                        repeat: Infinity,
                                        ease: 'easeInOut'
                                    }}
                                />
                            </svg>
                        ) : (
                            <div className="w-48 h-1 bg-stone-300 border-b-2 border-dashed border-black/40" />
                        )}
                    </div>

                    {/* Central Interactive Orb */}
                    <motion.div
                        className={`w-28 h-28 rounded-full border-4 border-black flex items-center justify-center z-10 shadow-[4px_4px_0px_0px_#000] relative ${
                            state.status === 'speaking'
                                ? 'bg-bauhaus-blue text-white'
                                : state.status === 'listening'
                                    ? 'bg-bauhaus-yellow text-black'
                                    : 'bg-white text-black'
                        }`}
                        animate={{
                            scale: state.status === 'processing' ? [1, 0.93, 1] : 1,
                        }}
                        transition={{ duration: 0.5, repeat: state.status === 'processing' ? Infinity : 0 }}
                    >
                        {state.status === 'speaking' && <Volume2 className="w-10 h-10 text-white" />}
                        {state.status === 'listening' && <Mic className="w-10 h-10 text-black" />}
                        {state.status === 'processing' && (
                            <motion.div
                                animate={{ rotate: 360 }}
                                transition={{ duration: 1.5, repeat: Infinity, ease: 'linear' }}
                            >
                                <RefreshCw className="w-10 h-10 text-black" />
                            </motion.div>
                        )}
                    </motion.div>

                    {/* Miniature state indicator badge */}
                    <div className="absolute bottom-3 right-3 bg-white border-2 border-black px-2 py-0.5 text-[10px] font-mono font-bold uppercase tracking-wider">
                        {state.status}
                    </div>
                </div>

                {/* Status text */}
                <p className="text-lg text-black font-bold uppercase tracking-wider mb-8">
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
                            className="max-w-md mx-auto mb-8 p-4 bg-white border-4 border-black rounded-none shadow-[6px_6px_0px_0px_#000]"
                        >
                            <p className="text-black font-medium text-center">{state.aiResponse}</p>
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
                        className={`p-4 rounded-none border-2 border-black transition-all ${isMuted
                            ? 'bg-bauhaus-red text-white shadow-[2px_2px_0px_0px_#000]'
                            : 'bg-white text-black hover:bg-stone-50 shadow-[2px_2px_0px_0px_#000] hover:shadow-[3px_3px_0px_0px_#000]'
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
                        className={`p-8 rounded-none border-4 border-black transition-all ${state.status === 'listening'
                            ? 'bg-bauhaus-yellow hover:bg-bauhaus-yellow/95 shadow-[4px_4px_0px_0px_#000] hover:-translate-y-0.5 hover:shadow-[6px_6px_0px_0px_#000] cursor-pointer'
                            : 'bg-stone-200 text-stone-400 cursor-not-allowed border-stone-300 shadow-none'
                        }`}
                    >
                        <Mic className="w-10 h-10 text-black" />
                    </motion.button>

                    {/* Show text button */}
                    <button
                        onClick={() => setState(prev => ({ ...prev, showText: !prev.showText }))}
                        className={`p-4 rounded-none border-2 border-black transition-all ${state.showText
                            ? 'bg-bauhaus-blue text-white shadow-[2px_2px_0px_0px_#000]'
                            : 'bg-white text-black hover:bg-stone-50 shadow-[2px_2px_0px_0px_#000] hover:shadow-[3px_3px_0px_0px_#000]'
                        }`}
                    >
                        {state.showText ? <EyeOff className="w-6 h-6" /> : <Eye className="w-6 h-6" />}
                    </button>
                </div>

                {/* XP indicator */}
                <div className="text-center mt-4">
                    <span className="text-black font-black text-sm uppercase tracking-wider">{state.totalXP} XP</span>
                </div>
            </div>

            {/* Help Modal */}
            <AnimatePresence>
                {showHelp && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-6"
                        onClick={() => setShowHelp(false)}
                    >
                        <motion.div
                            initial={{ scale: 0.9, y: 20 }}
                            animate={{ scale: 1, y: 0 }}
                            exit={{ scale: 0.9, y: 20 }}
                            onClick={e => e.stopPropagation()}
                            className="bg-white border-4 border-black rounded-none p-6 max-w-sm w-full shadow-[8px_8px_0px_0px_#000] text-black"
                        >
                            <h2 className="font-serif text-3xl italic text-black mb-4">How it works</h2>
                            <div className="space-y-4">
                                {helpTips.map((tip, i) => (
                                    <div key={i} className="flex gap-4">
                                        <div className="p-2 border border-black bg-white text-black h-10 w-10 flex items-center justify-center">
                                            {tip.icon}
                                        </div>
                                        <div>
                                            <h3 className="font-bold text-black">{tip.title}</h3>
                                            <p className="text-stone-600 text-xs mt-0.5">{tip.description}</p>
                                        </div>
                                    </div>
                                ))}
                            </div>
                            <button
                                onClick={() => setShowHelp(false)}
                                className="mt-6 w-full py-3 border-2 border-black bg-black hover:bg-black/90 text-white font-bold rounded-none shadow-[3px_3px_0px_0px_#000] transition-all"
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
                        className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-6"
                        onClick={() => setShowEndConfirm(false)}
                    >
                        <motion.div
                            initial={{ scale: 0.9, y: 20 }}
                            animate={{ scale: 1, y: 0 }}
                            exit={{ scale: 0.9, y: 20 }}
                            onClick={e => e.stopPropagation()}
                            className="bg-white border-4 border-black rounded-none p-6 max-w-sm w-full text-center shadow-[8px_8px_0px_0px_#000] text-black"
                        >
                            <h2 className="font-serif text-3xl italic text-black mb-2">End Session?</h2>
                            <p className="text-stone-600 text-sm mb-6 font-medium">You&apos;ve been talking for {formatTime(state.elapsedSeconds)}</p>
                            <div className="flex gap-4">
                                <button
                                    onClick={() => setShowEndConfirm(false)}
                                    className="flex-1 py-3 border-2 border-black bg-white text-black hover:bg-stone-50 font-bold rounded-none shadow-[3px_3px_0px_0px_#000] transition-all"
                                >
                                    Keep Going
                                </button>
                                <button
                                    onClick={endSession}
                                    className="flex-1 py-3 border-2 border-black bg-bauhaus-red text-white hover:bg-red-700 font-bold rounded-none shadow-[3px_3px_0px_0px_#000] transition-all"
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
