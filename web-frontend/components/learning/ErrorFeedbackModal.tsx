import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    AlertTriangle,
    CheckCircle,
    TrendingUp,
    X,
    BookOpen,
    Clock,
    Calendar,
    RefreshCw,
    Brain,
    Activity
} from 'lucide-react';

export interface DetectedError {
    code: string;
    message: string;
    span: string;
    suggestion: string | null;
    category: string;
    severity: string;
    confidence?: number;
    occurrence_count?: number;
    last_seen?: string;
    is_recurring?: boolean;
}

export interface ErrorOccurrenceStats {
    category: string;
    pattern?: string | null;
    total_occurrences: number;
    occurrences_today: number;
    last_seen?: string | null;
    next_review?: string | null;
    state: string;
}

export interface ErrorFeedbackData {
    summary: string;
    errors: DetectedError[];
    review_vocabulary?: string[];
    metadata?: {
        total_occurrences?: number;
        last_seen?: string;
    };
    error_stats?: ErrorOccurrenceStats[];
}

interface ErrorFeedbackModalProps {
    errorFeedback: ErrorFeedbackData;
    onClose: () => void;
    autoClose?: boolean;
    autoCloseDelay?: number;
    /** When true, shows compact view with faster auto-close for voice mode */
    isVoiceMode?: boolean;
}

const categoryColors: Record<string, { bg: string; border: string; text: string; icon: React.ReactNode }> = {
    grammar: {
        bg: 'bg-red-50',
        border: 'border-red-200',
        text: 'text-red-700',
        icon: <BookOpen className="w-4 h-4" />
    },
    spelling: {
        bg: 'bg-orange-50',
        border: 'border-orange-200',
        text: 'text-orange-700',
        icon: <Activity className="w-4 h-4" />
    },
    vocabulary: {
        bg: 'bg-blue-50',
        border: 'border-blue-200',
        text: 'text-blue-700',
        icon: <Brain className="w-4 h-4" />
    },
    syntax: {
        bg: 'bg-purple-50',
        border: 'border-purple-200',
        text: 'text-purple-700',
        icon: <RefreshCw className="w-4 h-4" />
    },
    default: {
        bg: 'bg-gray-50',
        border: 'border-gray-200',
        text: 'text-gray-700',
        icon: <AlertTriangle className="w-4 h-4" />
    },
};

const severityIcons: Record<string, { icon: React.ReactNode; color: string }> = {
    high: { icon: <AlertTriangle className="w-5 h-5" />, color: 'text-red-500' },
    medium: { icon: <AlertTriangle className="w-5 h-5" />, color: 'text-orange-500' },
    low: { icon: <BookOpen className="w-5 h-5" />, color: 'text-blue-500' },
};

const getStateColor = (state: string) => {
    switch (state?.toLowerCase()) {
        case 'new': return 'bg-blue-500';
        case 'learning': return 'bg-yellow-500';
        case 'review': return 'bg-orange-500';
        case 'mastered': return 'bg-green-500';
        default: return 'bg-gray-400';
    }
};

const getStateLabel = (state: string) => {
    switch (state?.toLowerCase()) {
        case 'new': return 'New Error';
        case 'learning': return 'Learning';
        case 'review': return 'Reviewing';
        case 'mastered': return 'Mastered';
        default: return 'Unknown';
    }
};
const subcategoryLabels: Record<string, string> = {
    gender_agreement: 'Genus / Artikel',
    verb_tenses: 'Zeitformen',
    subjonctif: 'Subjonctif',
    conditional: 'Konditional',
    negation: 'Verneinung',
    prepositions: 'Präpositionen',
    articles: 'Artikel',
    pronouns: 'Pronomen',
    word_order: 'Wortstellung',
    subject_verb_agreement: 'Subjekt-Verb',
    accents: 'Akzente',
    common_misspellings: 'Rechtschreibung',
    false_friends: 'Falsche Freunde',
    word_choice: 'Wortwahl',
    capitalization: 'Großschreibung',
    quotation_marks: 'Anführungszeichen',
};

const getErrorTitle = (category: string, code: string) => {
    const clean = code.replace(/^llm_/, '');
    if (subcategoryLabels[clean]) return subcategoryLabels[clean];
    if (clean === category || clean === 'unknown' || clean === 'grammar') return `${category} Error`;
    return clean.replace(/_/g, ' ').toUpperCase();
};
export const ErrorFeedbackModal: React.FC<ErrorFeedbackModalProps> = ({
    errorFeedback,
    onClose,
    autoClose = true,
    autoCloseDelay = 10000, // Increased delay to allow reading stats
    isVoiceMode = false,
}) => {
    const [show, setShow] = useState(true);
    const [currentErrorIndex, setCurrentErrorIndex] = useState(0);
    const [isPaused, setIsPaused] = useState(false);

    // Voice mode uses faster auto-close (5s instead of 10s)
    const effectiveAutoCloseDelay = isVoiceMode ? 5000 : autoCloseDelay;

    // Debug logging
    useEffect(() => {
        console.log('[ErrorFeedbackModal] Rendered with feedback:', errorFeedback);
    }, [errorFeedback]);

    useEffect(() => {
        if (autoClose && !isPaused) {
            const timer = setTimeout(() => {
                setShow(false);
                setTimeout(onClose, 300);
            }, effectiveAutoCloseDelay);
            return () => clearTimeout(timer);
        }
    }, [autoClose, effectiveAutoCloseDelay, onClose, isPaused]);

    // Cycle through errors if there are multiple
    useEffect(() => {
        if (errorFeedback.errors.length > 1 && !isPaused) {
            const interval = setInterval(() => {
                setCurrentErrorIndex((prev) => (prev + 1) % errorFeedback.errors.length);
            }, 5000);
            return () => clearInterval(interval);
        }
    }, [errorFeedback.errors.length, isPaused]);

    if (!errorFeedback.errors || errorFeedback.errors.length === 0) {
        return null;
    }

    const currentError = errorFeedback.errors[currentErrorIndex];
    const colors = categoryColors[currentError.category] || categoryColors.default;
    const severity = severityIcons[currentError.severity] || severityIcons.medium;

    // Find matching stats for this error
    const stats = errorFeedback.error_stats?.find(
        s => s.category === currentError.category && s.pattern === currentError.code
    );

    const totalOccurrences = stats?.total_occurrences || currentError.occurrence_count || 1;
    const occurrencesToday = stats?.occurrences_today || 1;
    const isRecurring = totalOccurrences > 1;

    return (
        <AnimatePresence>
            {show && (
                <motion.div
                    initial={{ opacity: 0, x: 100, scale: 0.9 }}
                    animate={{ opacity: 1, x: 0, scale: 1 }}
                    exit={{ opacity: 0, x: 100, scale: 0.9 }}
                    transition={{ type: 'spring', stiffness: 300, damping: 25 }}
                    className="fixed bottom-24 right-6 z-[100] max-w-md w-full"
                    onMouseEnter={() => setIsPaused(true)}
                    onMouseLeave={() => setIsPaused(false)}
                >
                    <div className={`
                        bg-white border-4 border-black rounded-2xl 
                        shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] overflow-hidden
                        flex flex-col
                    `}>
                        {/* Header */}
                        <div className="bg-black text-white px-4 py-3 flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <div className={`p-1 rounded bg-white/10 ${severity.color}`}>
                                    {severity.icon}
                                </div>
                                <div className="flex flex-col">
                                    <span className="font-black text-sm uppercase tracking-wider leading-none">
                                        {getErrorTitle(currentError.category, currentError.code)}
                                    </span>


                                    {isRecurring && (
                                        <span className="text-[10px] text-yellow-400 font-bold uppercase tracking-wide mt-0.5">
                                            Recurring Mistake
                                        </span>
                                    )}
                                </div>
                            </div>
                            <button
                                onClick={() => {
                                    setShow(false);
                                    setTimeout(onClose, 300);
                                }}
                                className="hover:bg-white/20 rounded p-1 transition-colors"
                            >
                                <X className="w-5 h-5" />
                            </button>
                        </div>

                        {/* Content */}
                        <div className="p-5 space-y-4 bg-white">
                            {/* Correction Block */}
                            <div className={`${colors.bg} ${colors.border} border-l-4 p-4 rounded-r-lg`}>
                                <div className="space-y-2">
                                    <div className="text-gray-500 line-through text-sm font-medium">
                                        {currentError.span}
                                    </div>
                                    {currentError.suggestion && (
                                        <div className="flex items-start gap-2">
                                            <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
                                            <span className="font-bold text-lg text-gray-900 leading-tight">
                                                {currentError.suggestion}
                                            </span>
                                        </div>
                                    )}
                                </div>
                            </div>

                            {/* Explanation */}
                            <div className="text-gray-600 text-sm leading-relaxed font-medium">
                                {currentError.message}
                            </div>

                            {/* Spaced Repetition Stats */}
                            {stats && (
                                <motion.div
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    className="bg-gray-50 rounded-xl p-3 border-2 border-gray-100 space-y-3"
                                >
                                    {/* Stats Header */}
                                    <div className="flex items-center justify-between text-xs font-bold text-gray-400 uppercase tracking-wider">
                                        <div className="flex items-center gap-1">
                                            <Activity className="w-3 h-3" />
                                            Error Statistics
                                        </div>
                                        <span className={`px-2 py-0.5 rounded-full text-[10px] text-white ${getStateColor(stats.state)}`}>
                                            {getStateLabel(stats.state)}
                                        </span>
                                    </div>

                                    {/* Grid Stats */}
                                    <div className="grid grid-cols-2 gap-3">
                                        <div className="bg-white p-2 rounded-lg border border-gray-100 shadow-sm">
                                            <div className="text-xs text-gray-400 font-medium mb-1">Occurrences</div>
                                            <div className="flex items-baseline gap-1">
                                                <span className="text-xl font-black text-gray-900">{stats.total_occurrences}</span>
                                                <span className="text-xs font-bold text-gray-400">total</span>
                                            </div>
                                            {occurrencesToday > 0 && (
                                                <div className="text-[10px] font-bold text-orange-500 mt-1">
                                                    +{occurrencesToday} today
                                                </div>
                                            )}
                                        </div>

                                        <div className="bg-white p-2 rounded-lg border border-gray-100 shadow-sm">
                                            <div className="text-xs text-gray-400 font-medium mb-1">Next Review</div>
                                            <div className="flex items-center gap-1.5 mt-1">
                                                <Calendar className="w-4 h-4 text-blue-500" />
                                                <span className="text-sm font-bold text-gray-700">
                                                    {stats.next_review
                                                        ? new Date(stats.next_review).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
                                                        : 'Soon'
                                                    }
                                                </span>
                                            </div>
                                            <div className="text-[10px] font-medium text-gray-400 mt-1">
                                                Spaced Repetition
                                            </div>
                                        </div>
                                    </div>

                                    {/* Progress Bar */}
                                    <div className="space-y-1.5">
                                        <div className="flex justify-between text-[10px] font-bold text-gray-400 uppercase">
                                            <span>Mastery Progress</span>
                                            <span>{Math.min(100, Math.max(0, 100 - (stats.total_occurrences * 10)))}%</span>
                                        </div>
                                        <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                                            <motion.div
                                                className={`h-full ${getStateColor(stats.state)}`}
                                                initial={{ width: 0 }}
                                                animate={{ width: `${Math.min(100, Math.max(5, 100 - (stats.total_occurrences * 10)))}%` }}
                                                transition={{ duration: 1, ease: "easeOut" }}
                                            />
                                        </div>
                                    </div>
                                </motion.div>
                            )}

                            {/* Multiple errors pagination dots */}
                            {errorFeedback.errors.length > 1 && (
                                <div className="flex justify-center gap-1.5 pt-1">
                                    {errorFeedback.errors.map((_, idx) => (
                                        <button
                                            key={idx}
                                            onClick={() => setCurrentErrorIndex(idx)}
                                            className={`
                                                transition-all duration-300 rounded-full 
                                                ${idx === currentErrorIndex ? 'w-6 bg-black' : 'w-2 bg-gray-300 hover:bg-gray-400'}
                                                h-2
                                            `}
                                        />
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                </motion.div>
            )}
        </AnimatePresence>
    );
};

export default ErrorFeedbackModal;
