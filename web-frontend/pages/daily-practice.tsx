/**
 * Daily Practice - Unified SRS page
 * 
 * Combines vocab, grammar, and error reviews into single session
 * with intelligent interleaving and time budgeting.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/router';
import { motion, AnimatePresence } from 'framer-motion';
import {
    BookOpen,
    Brain,
    AlertTriangle,
    Clock,
    Play,
    Pause,
    SkipForward,
    CheckCircle,
    Settings,
    RefreshCw,
    Target,
    Zap,
    Timer,
    Eye,
    EyeOff,
    ArrowRight,
    Send,
    Loader2,
    Sparkles,
    PenLine,
} from 'lucide-react';
import toast from 'react-hot-toast';

import { apiService as api } from '@/services/api';

// Type icons for each item type
const TYPE_ICONS = {
    vocab: BookOpen,
    grammar: Brain,
    error: AlertTriangle,
};

const TYPE_COLORS = {
    vocab: 'bg-blue-100 text-blue-700 border-blue-200',
    grammar: 'bg-purple-100 text-purple-700 border-purple-200',
    error: 'bg-orange-100 text-orange-700 border-orange-200',
};

const TYPE_LABELS = {
    vocab: 'Vokabeln',
    grammar: 'Grammatik',
    error: 'Fehler',
};

interface QueueItem {
    id: string;
    item_type: 'vocab' | 'grammar' | 'error';
    priority_score: number;
    display_title: string;
    display_subtitle: string;
    level: string;
    due_since_days: number;
    estimated_seconds: number;
    original_id: string | null;
    metadata: Record<string, any>;
}

interface Summary {
    total_due: number;
    total_new: number;
    estimated_minutes: number;
    by_type: Record<string, { due: number; new: number; minutes: number }>;
}

export default function DailyPracticePage() {
    const router = useRouter();

    // Data state
    const [summary, setSummary] = useState<Summary | null>(null);
    const [queue, setQueue] = useState<QueueItem[]>([]);
    const [loading, setLoading] = useState(true);

    // Session state
    const [sessionActive, setSessionActive] = useState(false);
    const [currentIndex, setCurrentIndex] = useState(0);
    const [completedCount, setCompletedCount] = useState(0);
    const [elapsedSeconds, setElapsedSeconds] = useState(0);

    // Settings
    const [timeBudget, setTimeBudget] = useState<number | null>(null); // null = unlimited
    const [interleavingMode, setInterleavingMode] = useState<'random' | 'blocks' | 'priority'>('random');
    const [showSettings, setShowSettings] = useState(false);

    // Quiz state
    const [answerRevealed, setAnswerRevealed] = useState(false);
    const [grammarExercises, setGrammarExercises] = useState<any[]>([]);
    const [currentExerciseIndex, setCurrentExerciseIndex] = useState(0);
    const [loadingExercises, setLoadingExercises] = useState(false);

    // Exercise interaction state
    const [userAnswer, setUserAnswer] = useState('');
    const [exerciseFeedback, setExerciseFeedback] = useState<{
        is_correct: boolean;
        feedback: string;
        explanation?: string;
    } | null>(null);
    const [checkingAnswer, setCheckingAnswer] = useState(false);
    const [exercisesCompleted, setExercisesCompleted] = useState(false);

    // Error exercise state
    const [errorExercise, setErrorExercise] = useState<any | null>(null);
    const [loadingErrorExercise, setLoadingErrorExercise] = useState(false);

    // Timer
    useEffect(() => {
        let interval: NodeJS.Timeout;
        if (sessionActive) {
            interval = setInterval(() => {
                setElapsedSeconds(s => s + 1);
            }, 1000);
        }
        return () => clearInterval(interval);
    }, [sessionActive]);

    const loadQueue = useCallback(async () => {
        setLoading(true);
        try {
            const response = await api.getDailyPracticeQueue({
                time_budget_minutes: timeBudget,
                interleaving_mode: interleavingMode,
            }) as any;

            setSummary(response.summary);
            if (response && Array.isArray(response.queue)) {
                setQueue(response.queue);
                if (response.queue.length > 0) {
                    setCurrentIndex(0);
                    setCompletedCount(0); // Reset completed count instead of non-existent sessionStats
                }
            }
        } catch (error) {
            console.error('Failed to load daily practice queue', error);
            toast.error('Failed to load practice session');
        } finally {
            setLoading(false);
        }
    }, [timeBudget, interleavingMode]);

    // Load data
    useEffect(() => {
        loadQueue();
    }, [loadQueue]);

    const formatTime = (seconds: number) => {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    };

    const currentItem = queue[currentIndex];

    const handleStartSession = () => {
        setSessionActive(true);
        setCurrentIndex(0);
        setCompletedCount(0);
        setElapsedSeconds(0);
        setAnswerRevealed(false);
        setGrammarExercises([]);
        setCurrentExerciseIndex(0);
        setUserAnswer('');
        setExerciseFeedback(null);
        setExercisesCompleted(false);
        setErrorExercise(null);
    };

    // Load grammar exercises when user clicks "Ich habe es wiederholt"
    const handleLoadGrammarExercises = async () => {
        if (!currentItem || !currentItem.original_id) return;

        setLoadingExercises(true);
        try {
            const result = await api.generateBriefGrammarExercises(Number(currentItem.original_id));
            setGrammarExercises(result.exercises || []);
            setCurrentExerciseIndex(0);
            setAnswerRevealed(true);
            setUserAnswer('');
            setExerciseFeedback(null);
        } catch (error) {
            console.error('Failed to load exercises', error);
            toast.error('Übungen konnten nicht geladen werden');
            setAnswerRevealed(true); // Fallback to simple reveal
        } finally {
            setLoadingExercises(false);
        }
    };

    // Submit answer for grammar exercise
    const handleSubmitExerciseAnswer = async () => {
        if (!userAnswer.trim() || !grammarExercises[currentExerciseIndex]) return;

        const exercise = grammarExercises[currentExerciseIndex];
        setCheckingAnswer(true);

        try {
            const result = await api.checkBriefAnswer({
                exercise_type: exercise.type,
                prompt: exercise.prompt,
                correct_answer: exercise.correct_answer,
                user_answer: userAnswer,
                concept_id: Number(currentItem.original_id), // Pass concept ID for error tracking
            });
            setExerciseFeedback(result);
        } catch (error) {
            console.error('Failed to check answer', error);
            // Simple fallback check
            const isCorrect = userAnswer.trim().toLowerCase() === exercise.correct_answer.trim().toLowerCase();
            setExerciseFeedback({
                is_correct: isCorrect,
                feedback: isCorrect ? 'Richtig! 🎉' : `Richtig wäre: ${exercise.correct_answer}`,
            });
        } finally {
            setCheckingAnswer(false);
        }
    };

    // Move to next exercise
    const handleNextExercise = () => {
        if (currentExerciseIndex < grammarExercises.length - 1) {
            setCurrentExerciseIndex(i => i + 1);
            setUserAnswer('');
            setExerciseFeedback(null);
        } else {
            // All exercises done
            setExercisesCompleted(true);
        }
    };

    // Load error correction exercise
    const handleLoadErrorExercise = async () => {
        if (!currentItem || !currentItem.original_id) return;

        setLoadingErrorExercise(true);
        try {
            const result = await api.generateErrorExercise(currentItem.original_id);
            setErrorExercise(result);
            setAnswerRevealed(true);
            setUserAnswer('');
            setExerciseFeedback(null);
        } catch (error) {
            console.error('Failed to load error exercise', error);
            // Fallback: just reveal the correction
            setAnswerRevealed(true);
        } finally {
            setLoadingErrorExercise(false);
        }
    };

    // Submit answer for error correction
    const handleSubmitErrorAnswer = async () => {
        if (!userAnswer.trim()) return;

        const correctAnswer = errorExercise?.correct_answer || currentItem?.metadata?.correction || '';
        setCheckingAnswer(true);

        try {
            const result = await api.checkBriefAnswer({
                exercise_type: 'correction',
                prompt: errorExercise?.prompt || currentItem?.display_title || '',
                correct_answer: correctAnswer,
                user_answer: userAnswer,
            });
            setExerciseFeedback(result);
        } catch (error) {
            console.error('Failed to check answer', error);
            const isCorrect = userAnswer.trim().toLowerCase() === correctAnswer.trim().toLowerCase();
            setExerciseFeedback({
                is_correct: isCorrect,
                feedback: isCorrect ? 'Richtig! 🎉' : `Richtig wäre: ${correctAnswer}`,
            });
        } finally {
            setCheckingAnswer(false);
        }
    };

    const handleComplete = async (rating: number) => {
        if (!currentItem) return;

        try {
            await api.completePracticeItem(
                currentItem.item_type,
                currentItem.original_id || currentItem.id,
                { rating }
            );

            setCompletedCount(c => c + 1);

            if (currentIndex < queue.length - 1) {
                setCurrentIndex(i => i + 1);
                // Reset quiz state for next card
                setAnswerRevealed(false);
                setGrammarExercises([]);
                setCurrentExerciseIndex(0);
                setUserAnswer('');
                setExerciseFeedback(null);
                setExercisesCompleted(false);
                setErrorExercise(null);
            } else {
                setSessionActive(false);
                toast.success('🎉 Session abgeschlossen!');
            }
        } catch (error) {
            console.error('Failed to complete item', error);
            toast.error('Fehler beim Speichern');
        }
    };

    const handleSkip = () => {
        if (currentIndex < queue.length - 1) {
            setCurrentIndex(i => i + 1);
        }
    };

    const navigateToReview = (item: QueueItem) => {
        if (item.item_type === 'vocab') {
            router.push('/practice');
        } else if (item.item_type === 'grammar') {
            router.push('/grammar');
        } else {
            // Show error review modal or navigate
            toast('Fehler-Review kommt bald!');
        }
    };

    return (
        <div className="max-w-4xl mx-auto space-y-8 p-4">
            {/* Header */}
            <div className="flex items-center justify-between bg-white border-4 border-black p-6 shadow-[8px_8px_0px_0px_#000]">
                <div>
                    <h1 className="text-3xl font-extrabold text-black uppercase tracking-tight">Tägliches Training</h1>
                    <p className="text-gray-600 font-bold mt-1">Alle fälligen Elemente in einer Session</p>
                </div>
                <button
                    onClick={() => setShowSettings(!showSettings)}
                    className="p-3 bg-bauhaus-yellow border-2 border-black hover:bg-bauhaus-yellow/80 transition-colors shadow-[4px_4px_0px_0px_#000] active:translate-x-[2px] active:translate-y-[2px] active:shadow-none"
                >
                    <Settings className="w-6 h-6 text-black" />
                </button>
            </div>

            {/* Settings Panel */}
            <AnimatePresence>
                {showSettings && (
                    <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        className="bg-white border-4 border-black p-6 shadow-[8px_8px_0px_0px_#000]"
                    >
                        <h3 className="font-black text-xl mb-4 uppercase">Einstellungen</h3>
                        <div className="grid grid-cols-2 gap-6">
                            <div>
                                <label className="text-sm font-bold text-black uppercase">Zeitbudget (Min)</label>
                                <select
                                    value={timeBudget || 'unlimited'}
                                    onChange={(e) => setTimeBudget(e.target.value === 'unlimited' ? null : parseInt(e.target.value))}
                                    className="w-full mt-2 p-3 font-bold border-2 border-black focus:shadow-[4px_4px_0px_0px_#F4B400] outline-none"
                                >
                                    <option value="unlimited">Unbegrenzt</option>
                                    <option value="15">15 Minuten</option>
                                    <option value="30">30 Minuten</option>
                                    <option value="60">60 Minuten</option>
                                    <option value="90">90 Minuten</option>
                                </select>
                            </div>
                            <div>
                                <label className="text-sm font-bold text-black uppercase">Reihenfolge</label>
                                <select
                                    value={interleavingMode}
                                    onChange={(e) => setInterleavingMode(e.target.value as any)}
                                    className="w-full mt-2 p-3 font-bold border-2 border-black focus:shadow-[4px_4px_0px_0px_#F4B400] outline-none"
                                >
                                    <option value="random">🔀 Gemischt (empfohlen)</option>
                                    <option value="blocks">📦 Nach Typ</option>
                                    <option value="priority">⚡ Nach Priorität</option>
                                </select>
                            </div>
                        </div>
                        <button
                            onClick={loadQueue}
                            className="mt-6 px-6 py-3 bg-black text-white font-bold text-sm uppercase flex items-center gap-2 hover:bg-gray-800 transition-colors"
                        >
                            <RefreshCw className="w-4 h-4" /> Neu laden
                        </button>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Summary Stats */}
            {!loading && summary && (
                <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                    <div className="bg-bauhaus-blue border-4 border-black p-4 text-white shadow-[8px_8px_0px_0px_#000]">
                        <div className="text-5xl font-black">{summary.total_due}</div>
                        <div className="text-sm font-bold uppercase mt-1">Fällige Elemente</div>
                    </div>

                    {Object.entries(summary.by_type).map(([type, data]) => {
                        const Icon = TYPE_ICONS[type as keyof typeof TYPE_ICONS] || BookOpen;
                        return (
                            <div key={type} className="bg-white p-4 border-4 border-black shadow-[8px_8px_0px_0px_#000]">
                                <div className="flex items-center gap-2 mb-3 border-b-2 border-black pb-2">
                                    <Icon className="w-5 h-5 text-black" />
                                    <span className="text-sm font-bold uppercase">{TYPE_LABELS[type as keyof typeof TYPE_LABELS]}</span>
                                </div>
                                <div className="text-3xl font-black">{data.due}</div>
                                <div className="text-xs font-bold bg-bauhaus-yellow inline-block px-2 py-1 mt-2 border border-black">
                                    ~{data.minutes} Min
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}

            {/* Session Controls */}
            {!sessionActive && queue.length > 0 && (
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="bg-bauhaus-yellow border-4 border-black p-8 text-black text-center shadow-[12px_12px_0px_0px_#000]"
                >
                    <div className="flex items-center justify-center gap-3 mb-6">
                        <Timer className="w-8 h-8" />
                        <span className="text-xl font-black uppercase">
                            Geschätzte Zeit: <span className="bg-white px-2 border-2 border-black">{summary?.estimated_minutes || 0} Minuten</span>
                        </span>
                    </div>
                    <button
                        onClick={handleStartSession}
                        className="bg-black text-white px-12 py-4 text-lg font-black uppercase hover:bg-gray-900 transition flex items-center gap-3 mx-auto shadow-[6px_6px_0px_0px_#fff] active:shadow-none active:translate-x-[6px] active:translate-y-[6px]"
                    >
                        <Play className="w-6 h-6" />
                        Session starten
                    </button>
                </motion.div>
            )}

            {/* Active Session */}
            {sessionActive && currentItem && (
                <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    className="space-y-6"
                >
                    {/* Progress bar */}
                    <div className="flex items-center gap-4 bg-white p-4 border-4 border-black shadow-[4px_4px_0px_0px_#000]">
                        <div className="flex-1 h-6 bg-gray-200 border-2 border-black overflow-hidden relative">
                            <motion.div
                                className="h-full bg-bauhaus-blue border-r-2 border-black"
                                initial={{ width: 0 }}
                                animate={{ width: `${((currentIndex + 1) / queue.length) * 100}%` }}
                            />
                        </div>
                        <div className="text-lg font-black font-mono">
                            {currentIndex + 1} / {queue.length}
                        </div>
                        <div className="flex items-center gap-2 font-bold font-mono bg-bauhaus-yellow px-3 py-1 border-2 border-black">
                            <Clock className="w-4 h-4" />
                            {formatTime(elapsedSeconds)}
                        </div>
                    </div>

                    {/* Current Item Card */}
                    <div className="bg-white border-4 border-black shadow-[12px_12px_0px_0px_#000] overflow-hidden">
                        {/* Type Header */}
                        <div className={`px-6 py-3 border-b-4 border-black flex items-center justify-between bg-gray-50`}>
                            <div className="flex items-center gap-3">
                                <div className={`p-2 border-2 border-black shadow-[2px_2px_0px_0px_#000] bg-white`}>
                                    {(() => {
                                        const Icon = TYPE_ICONS[currentItem.item_type];
                                        return <Icon className="w-5 h-5 text-black" />;
                                    })()}
                                </div>
                                <span className="font-black uppercase tracking-wide text-lg">{TYPE_LABELS[currentItem.item_type]}</span>
                            </div>
                            <span className="font-bold bg-black text-white px-3 py-1 text-xs uppercase">{currentItem.level}</span>
                        </div>

                        {/* Content - Type-specific rendering */}
                        <div className="p-8 text-center min-h-[280px] flex flex-col justify-center">
                            {/* VOCABULARY: Flip card */}
                            {currentItem.item_type === 'vocab' && (
                                <div className="space-y-6">
                                    <h2 className="text-5xl font-black text-black leading-tight">{currentItem.display_title}</h2>

                                    {!answerRevealed ? (
                                        <>
                                            <p className="text-lg text-gray-500 italic blur-sm select-none" aria-hidden="true">
                                                {currentItem.display_subtitle.replace(/[a-zA-Z0-9]/g, 'x')}
                                            </p>
                                            <button
                                                onClick={() => setAnswerRevealed(true)}
                                                className="mt-6 px-8 py-4 bg-bauhaus-blue text-white font-bold uppercase border-2 border-black shadow-[4px_4px_0px_0px_#000] hover:shadow-[6px_6px_0px_0px_#000] hover:-translate-x-0.5 hover:-translate-y-0.5 transition-all flex items-center gap-3 mx-auto"
                                            >
                                                <Eye className="w-5 h-5" /> Antwort zeigen
                                            </button>
                                        </>
                                    ) : (
                                        <motion.div
                                            initial={{ opacity: 0, y: 10 }}
                                            animate={{ opacity: 1, y: 0 }}
                                            className="space-y-4"
                                        >
                                            <div className="p-6 bg-green-50 border-2 border-green-500">
                                                <p className="text-2xl font-bold text-green-800">
                                                    ✓ {currentItem.metadata?.answer || currentItem.display_subtitle}
                                                </p>
                                            </div>
                                        </motion.div>
                                    )}
                                </div>
                            )}

                            {/* ERROR: Interactive correction exercise */}
                            {currentItem.item_type === 'error' && (
                                <div className="space-y-6">
                                    <div className="p-4 bg-red-50 border-2 border-red-300">
                                        <p className="text-sm font-bold text-red-600 uppercase mb-2">Dein Fehler:</p>
                                        <h2 className="text-3xl font-black text-red-800">{currentItem.display_title}</h2>
                                    </div>
                                    <p className="text-gray-600 font-medium">{currentItem.display_subtitle}</p>

                                    {!answerRevealed ? (
                                        <div className="space-y-4">
                                            <p className="text-gray-500 italic">Korrigiere den Fehler selbst:</p>

                                            {/* Correction input */}
                                            <div className="flex gap-3">
                                                <input
                                                    type="text"
                                                    value={userAnswer}
                                                    onChange={(e) => setUserAnswer(e.target.value)}
                                                    onKeyDown={(e) => e.key === 'Enter' && !checkingAnswer && handleSubmitErrorAnswer()}
                                                    placeholder="Schreibe die Korrektur..."
                                                    className="flex-1 px-4 py-3 border-2 border-black font-medium focus:shadow-[4px_4px_0px_0px_#F4B400] outline-none"
                                                    disabled={checkingAnswer || exerciseFeedback !== null}
                                                />
                                                <button
                                                    onClick={handleSubmitErrorAnswer}
                                                    disabled={!userAnswer.trim() || checkingAnswer || exerciseFeedback !== null}
                                                    className="px-6 py-3 bg-bauhaus-yellow text-black font-bold uppercase border-2 border-black shadow-[4px_4px_0px_0px_#000] hover:shadow-[6px_6px_0px_0px_#000] transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                                                >
                                                    {checkingAnswer ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
                                                </button>
                                            </div>

                                            {/* Feedback */}
                                            {exerciseFeedback && (
                                                <motion.div
                                                    initial={{ opacity: 0, y: 10 }}
                                                    animate={{ opacity: 1, y: 0 }}
                                                    className={`p-4 border-2 ${exerciseFeedback.is_correct ? 'bg-green-50 border-green-500' : 'bg-orange-50 border-orange-500'}`}
                                                >
                                                    <p className={`font-bold ${exerciseFeedback.is_correct ? 'text-green-800' : 'text-orange-800'}`}>
                                                        {exerciseFeedback.feedback}
                                                    </p>
                                                    {exerciseFeedback.explanation && (
                                                        <p className="text-sm mt-2 text-gray-700">{exerciseFeedback.explanation}</p>
                                                    )}
                                                </motion.div>
                                            )}

                                            {/* Show answer button */}
                                            {!exerciseFeedback && (
                                                <button
                                                    onClick={handleLoadErrorExercise}
                                                    disabled={loadingErrorExercise}
                                                    className="mt-2 text-sm font-medium text-gray-500 hover:text-gray-700 underline flex items-center gap-2 mx-auto"
                                                >
                                                    {loadingErrorExercise ? <Loader2 className="w-4 h-4 animate-spin" /> : <Eye className="w-4 h-4" />}
                                                    Korrektur zeigen
                                                </button>
                                            )}

                                            {/* Continue after feedback */}
                                            {exerciseFeedback && (
                                                <button
                                                    onClick={() => setAnswerRevealed(true)}
                                                    className="mt-4 px-8 py-4 bg-black text-white font-bold uppercase border-2 border-black shadow-[4px_4px_0px_0px_#666] hover:shadow-[6px_6px_0px_0px_#666] transition-all flex items-center gap-3 mx-auto"
                                                >
                                                    <ArrowRight className="w-5 h-5" /> Weiter zur Bewertung
                                                </button>
                                            )}
                                        </div>
                                    ) : (
                                        <motion.div
                                            initial={{ opacity: 0, y: 10 }}
                                            animate={{ opacity: 1, y: 0 }}
                                            className="space-y-4"
                                        >
                                            <div className="p-6 bg-green-50 border-2 border-green-500">
                                                <p className="text-sm font-bold text-green-600 uppercase mb-2">Richtig:</p>
                                                <p className="text-2xl font-bold text-green-800">
                                                    ✓ {errorExercise?.correct_answer || currentItem.metadata?.correction || 'Korrektur nicht verfügbar'}
                                                </p>
                                            </div>
                                            {(errorExercise?.explanation || currentItem.metadata?.context) && (
                                                <div className="p-4 bg-gray-100 border border-gray-300 text-left">
                                                    <p className="text-sm font-bold text-gray-600 uppercase mb-1">Erklärung:</p>
                                                    <p className="text-gray-800">{errorExercise?.explanation || currentItem.metadata.context}</p>
                                                </div>
                                            )}
                                            {errorExercise?.memory_tip && (
                                                <div className="p-4 bg-purple-50 border border-purple-300 text-left">
                                                    <p className="text-sm font-bold text-purple-600 uppercase mb-1">💡 Merkhilfe:</p>
                                                    <p className="text-purple-800">{errorExercise.memory_tip}</p>
                                                </div>
                                            )}
                                        </motion.div>
                                    )}
                                </div>
                            )}

                            {/* GRAMMAR: Interactive 3-exercise flow */}
                            {currentItem.item_type === 'grammar' && (
                                <div className="space-y-6">
                                    <h2 className="text-3xl font-black text-black leading-tight">{currentItem.display_title}</h2>
                                    <p className="text-lg text-gray-600">{currentItem.display_subtitle}</p>

                                    {!answerRevealed ? (
                                        <div className="space-y-4">
                                            <p className="text-gray-500 italic">Grammatikkonzept wiederholen</p>
                                            <button
                                                onClick={handleLoadGrammarExercises}
                                                disabled={loadingExercises}
                                                className="mt-4 px-8 py-4 bg-purple-600 text-white font-bold uppercase border-2 border-black shadow-[4px_4px_0px_0px_#000] hover:shadow-[6px_6px_0px_0px_#000] transition-all flex items-center gap-3 mx-auto disabled:opacity-50"
                                            >
                                                {loadingExercises ? (
                                                    <><Loader2 className="w-5 h-5 animate-spin" /> Übungen werden geladen...</>
                                                ) : (
                                                    <><Sparkles className="w-5 h-5" /> 3 Übungen starten</>
                                                )}
                                            </button>
                                        </div>
                                    ) : exercisesCompleted ? (
                                        /* All exercises done - show success and rating */
                                        <motion.div
                                            initial={{ opacity: 0, scale: 0.95 }}
                                            animate={{ opacity: 1, scale: 1 }}
                                            className="p-6 bg-green-50 border-2 border-green-500 text-center"
                                        >
                                            <CheckCircle className="w-12 h-12 text-green-600 mx-auto mb-3" />
                                            <p className="text-xl font-bold text-green-800">Alle 3 Übungen abgeschlossen!</p>
                                            <p className="text-green-700 mt-2">Wie gut konntest du das Konzept anwenden?</p>
                                        </motion.div>
                                    ) : grammarExercises.length > 0 ? (
                                        /* Show current exercise */
                                        <motion.div
                                            key={currentExerciseIndex}
                                            initial={{ opacity: 0, x: 20 }}
                                            animate={{ opacity: 1, x: 0 }}
                                            className="space-y-4"
                                        >
                                            {/* Progress indicator */}
                                            <div className="flex items-center justify-center gap-2 mb-4">
                                                {grammarExercises.map((_, idx) => (
                                                    <div
                                                        key={idx}
                                                        className={`w-10 h-10 border-2 border-black flex items-center justify-center font-black text-lg ${idx < currentExerciseIndex
                                                            ? 'bg-green-500 text-white'
                                                            : idx === currentExerciseIndex
                                                                ? 'bg-purple-600 text-white shadow-[4px_4px_0px_0px_#000]'
                                                                : 'bg-gray-100 text-gray-400'
                                                            }`}
                                                    >
                                                        {idx < currentExerciseIndex ? '✓' : idx + 1}
                                                    </div>
                                                ))}
                                            </div>

                                            {/* Exercise content */}
                                            <div className="p-4 bg-purple-50 border-2 border-purple-300">
                                                <p className="text-sm font-bold text-purple-600 uppercase mb-2">
                                                    {grammarExercises[currentExerciseIndex]?.instruction || 'Übung'}
                                                </p>
                                                <p className="text-xl font-medium text-purple-900">
                                                    {grammarExercises[currentExerciseIndex]?.prompt}
                                                </p>
                                                {grammarExercises[currentExerciseIndex]?.hint && !exerciseFeedback && (
                                                    <p className="text-sm text-purple-600 mt-2 italic">
                                                        💡 {grammarExercises[currentExerciseIndex].hint}
                                                    </p>
                                                )}
                                            </div>

                                            {/* Answer input */}
                                            <div className="flex gap-3">
                                                <input
                                                    type="text"
                                                    value={userAnswer}
                                                    onChange={(e) => setUserAnswer(e.target.value)}
                                                    onKeyDown={(e) => e.key === 'Enter' && !checkingAnswer && !exerciseFeedback && handleSubmitExerciseAnswer()}
                                                    placeholder="Deine Antwort..."
                                                    className="flex-1 px-4 py-3 border-2 border-black font-medium focus:shadow-[4px_4px_0px_0px_#9333ea] outline-none"
                                                    disabled={checkingAnswer || exerciseFeedback !== null}
                                                />
                                                {!exerciseFeedback ? (
                                                    <button
                                                        onClick={handleSubmitExerciseAnswer}
                                                        disabled={!userAnswer.trim() || checkingAnswer}
                                                        className="px-6 py-3 bg-purple-600 text-white font-bold uppercase border-2 border-black shadow-[4px_4px_0px_0px_#000] hover:shadow-[6px_6px_0px_0px_#000] transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                                                    >
                                                        {checkingAnswer ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
                                                    </button>
                                                ) : (
                                                    <button
                                                        onClick={handleNextExercise}
                                                        className="px-6 py-3 bg-black text-white font-bold uppercase border-2 border-black shadow-[4px_4px_0px_0px_#666] hover:shadow-[6px_6px_0px_0px_#666] transition-all flex items-center gap-2"
                                                    >
                                                        <ArrowRight className="w-5 h-5" />
                                                    </button>
                                                )}
                                            </div>

                                            {/* Feedback */}
                                            {exerciseFeedback && (
                                                <motion.div
                                                    initial={{ opacity: 0, y: 10 }}
                                                    animate={{ opacity: 1, y: 0 }}
                                                    className={`p-4 border-2 ${exerciseFeedback.is_correct ? 'bg-green-50 border-green-500' : 'bg-orange-50 border-orange-500'}`}
                                                >
                                                    <p className={`font-bold ${exerciseFeedback.is_correct ? 'text-green-800' : 'text-orange-800'}`}>
                                                        {exerciseFeedback.feedback}
                                                    </p>
                                                    {!exerciseFeedback.is_correct && (
                                                        <p className="text-sm mt-1 text-gray-600">
                                                            Richtig: <span className="font-medium">{grammarExercises[currentExerciseIndex]?.correct_answer}</span>
                                                        </p>
                                                    )}
                                                    {exerciseFeedback.explanation && (
                                                        <p className="text-sm mt-2 text-gray-700">{exerciseFeedback.explanation}</p>
                                                    )}
                                                </motion.div>
                                            )}
                                        </motion.div>
                                    ) : (
                                        /* Fallback: simple review */
                                        <motion.div
                                            initial={{ opacity: 0 }}
                                            animate={{ opacity: 1 }}
                                            className="p-4 bg-purple-50 border-2 border-purple-300"
                                        >
                                            <p className="text-purple-800 font-medium">Wie gut konntest du das Konzept erklären?</p>
                                        </motion.div>
                                    )}
                                </div>
                            )}

                            {/* Overdue badge */}
                            {currentItem.due_since_days > 0 && (
                                <div className="mt-6 inline-flex items-center gap-2 bg-bauhaus-red text-white px-4 py-2 border-2 border-black font-bold shadow-[4px_4px_0px_0px_#000]">
                                    <AlertTriangle className="w-5 h-5" /> {currentItem.due_since_days} Tag(e) überfällig
                                </div>
                            )}
                        </div>

                        {/* Rating Buttons - Show after exercises complete (grammar) or answer revealed (vocab/error) */}
                        {((currentItem.item_type === 'grammar' && exercisesCompleted) ||
                            (currentItem.item_type !== 'grammar' && answerRevealed)) && (
                                <div className="p-6 bg-gray-50 border-t-4 border-black">
                                    <p className="text-center font-bold text-black uppercase mb-4 tracking-widest text-sm">Wie gut konntest du das?</p>
                                    <div className="grid grid-cols-4 gap-4">
                                        <button onClick={() => handleComplete(1)} className="group relative">
                                            <div className="absolute inset-0 bg-bauhaus-red translate-x-1 translate-y-1 border-2 border-black" />
                                            <div className="relative bg-white border-2 border-black p-4 text-center font-bold hover:-translate-y-1 hover:-translate-x-1 transition-transform cursor-pointer group-active:translate-x-0 group-active:translate-y-0">
                                                😣 Nochmal
                                            </div>
                                        </button>
                                        <button onClick={() => handleComplete(2)} className="group relative">
                                            <div className="absolute inset-0 bg-orange-500 translate-x-1 translate-y-1 border-2 border-black" />
                                            <div className="relative bg-white border-2 border-black p-4 text-center font-bold hover:-translate-y-1 hover:-translate-x-1 transition-transform cursor-pointer group-active:translate-x-0 group-active:translate-y-0">
                                                🤔 Schwer
                                            </div>
                                        </button>
                                        <button onClick={() => handleComplete(3)} className="group relative">
                                            <div className="absolute inset-0 bg-bauhaus-yellow translate-x-1 translate-y-1 border-2 border-black" />
                                            <div className="relative bg-white border-2 border-black p-4 text-center font-bold hover:-translate-y-1 hover:-translate-x-1 transition-transform cursor-pointer group-active:translate-x-0 group-active:translate-y-0">
                                                🙂 Gut
                                            </div>
                                        </button>
                                        <button onClick={() => handleComplete(4)} className="group relative">
                                            <div className="absolute inset-0 bg-bauhaus-blue translate-x-1 translate-y-1 border-2 border-black" />
                                            <div className="relative bg-white border-2 border-black p-4 text-center font-bold hover:-translate-y-1 hover:-translate-x-1 transition-transform cursor-pointer group-active:translate-x-0 group-active:translate-y-0">
                                                😎 Leicht
                                            </div>
                                        </button>
                                    </div>
                                </div>
                            )}
                    </div>

                    {/* Session Actions */}
                    <div className="flex justify-center gap-6 pt-4">
                        <button
                            onClick={() => setSessionActive(false)}
                            className="px-6 py-3 bg-white border-2 border-black font-bold hover:bg-gray-50 flex items-center gap-2 shadow-[4px_4px_0px_0px_#000]"
                        >
                            <Pause className="w-5 h-5" /> PAUSIEREN
                        </button>
                        <button
                            onClick={handleSkip}
                            className="px-6 py-3 bg-white border-2 border-black font-bold hover:bg-gray-50 flex items-center gap-2 shadow-[4px_4px_0px_0px_#000]"
                        >
                            <SkipForward className="w-5 h-5" /> ÜBERSPRINGEN
                        </button>
                    </div>
                </motion.div>
            )}

            {/* Empty State */}
            {!loading && queue.length === 0 && (
                <div className="text-center py-24 border-4 border-black bg-white shadow-[12px_12px_0px_0px_#000]">
                    <CheckCircle className="w-20 h-20 text-green-600 mx-auto mb-6" />
                    <h2 className="text-4xl font-black text-black mb-3 uppercase">Alles erledigt! 🎉</h2>
                    <p className="text-xl font-bold text-gray-600">Keine fälligen Elemente. Komm später wieder!</p>
                </div>
            )}

            {/* Queue Preview (when not in session) */}
            {!sessionActive && queue.length > 0 && (
                <div className="space-y-4">
                    <h3 className="font-black text-2xl uppercase border-b-4 border-black inline-block pb-1">Warteschlange</h3>
                    <div className="space-y-3 max-h-96 overflow-y-auto pr-2">
                        {queue.slice(0, 20).map((item, idx) => {
                            const Icon = TYPE_ICONS[item.item_type];
                            return (
                                <div
                                    key={item.id}
                                    className="flex items-center gap-4 p-4 bg-white border-2 border-black shadow-[4px_4px_0px_0px_#000] hover:translate-x-1 transition-transform cursor-pointer group"
                                    onClick={() => navigateToReview(item)}
                                >
                                    <span className="font-black text-lg w-8 text-center bg-black text-white py-1">{idx + 1}</span>
                                    <div className={`p-2 border-2 border-black bg-white group-hover:bg-bauhaus-yellow transition-colors`}>
                                        <Icon className="w-5 h-5 text-black" />
                                    </div>
                                    <div className="flex-1">
                                        <div className="font-bold text-lg">{item.display_title}</div>
                                        <div className="text-sm font-medium text-gray-600">{item.display_subtitle}</div>
                                    </div>
                                    <div className="text-right">
                                        <div className="text-xs font-bold uppercase bg-gray-200 px-2 py-1 inline-block border border-black">{item.level}</div>
                                        {item.due_since_days > 0 && (
                                            <div className="mt-1 text-xs font-bold text-red-600">+{item.due_since_days}d</div>
                                        )}
                                    </div>
                                </div>
                            );
                        })}
                        {queue.length > 20 && (
                            <div className="text-center font-bold text-black py-4 bg-gray-100 border-2 border-black border-dashed">
                                +{queue.length - 20} weitere Elemente
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Loading State */}
            {loading && (
                <div className="flex items-center justify-center py-24">
                    <RefreshCw className="w-12 h-12 text-black animate-spin" />
                </div>
            )}
        </div>
    );
}
