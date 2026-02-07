import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Check, X, Loader2, Lightbulb, Send, RefreshCw,
    BookOpen, PenTool, Languages, AlertCircle, MessageSquare, Trophy,
    ChevronRight, MessageCircle, Clock, Search, Mic
} from 'lucide-react';
import { DueConcept } from '@/types/grammar';
import api from '@/services/api';
import toast from 'react-hot-toast';

interface GrammarReviewProps {
    initialQueue: DueConcept[];
    onComplete: () => void;
}

interface ExerciseItem {
    id: string;
    block: number;
    type: string;
    level: 'a' | 'b' | 'c';
    instruction: string;
    prompt: string;
    correct_answer: string;
    explanation?: string;
}

interface ExerciseResult {
    level: string;
    is_correct: boolean;
    user_answer: string;
    correct_answer: string;
    feedback: string;
    points: number;
}

const difficultyLabels = { a: 'Einfach', b: 'Mittel', c: 'Schwer' };
const difficultyColors = {
    a: 'bg-green-100 text-green-700 border-green-200',
    b: 'bg-yellow-100 text-yellow-700 border-yellow-200',
    c: 'bg-red-100 text-red-700 border-red-200'
};

const typeIcons: Record<string, React.ReactNode> = {
    fill_blank: <PenTool className="w-4 h-4" />,
    translation: <Languages className="w-4 h-4" />,
    error_correction: <AlertCircle className="w-4 h-4" />,
    sentence_build: <BookOpen className="w-4 h-4" />,
    production: <MessageSquare className="w-4 h-4" />,
    // New immersive types
    chat_roleplay: <MessageCircle className="w-4 h-4" />,
    timeline_order: <Clock className="w-4 h-4" />,
    error_hunt: <Search className="w-4 h-4" />,
    voice_production: <Mic className="w-4 h-4" />,
};

const typeLabels: Record<string, string> = {
    fill_blank: 'Lückentext',
    translation: 'Übersetzung',
    error_correction: 'Fehlerkorrektur',
    sentence_build: 'Satzbildung',
    production: 'Produktion',
    // New immersive types
    chat_roleplay: 'Chat-Roleplay',
    timeline_order: 'Timeline',
    error_hunt: 'Fehlersuche',
    voice_production: 'Sprechübung',
};

// Helper function to render prompts based on exercise type
function renderPrompt(exercise: ExerciseItem) {
    const { type, prompt } = exercise;

    // Chat Roleplay: Render as chat bubbles
    if (type === 'chat_roleplay') {
        const lines = prompt.split('\n').filter(l => l.trim());
        return (
            <div className="space-y-2">
                {lines.map((line, i) => {
                    const isUser = line.startsWith('👤') || line.toLowerCase().includes('marc:') || line.toLowerCase().includes('freund:');
                    const isPrompt = line.startsWith('🎯') || line.includes('[');
                    const cleanLine = line.replace(/^(👤|🎯)\s*/, '');

                    if (isPrompt) {
                        return (
                            <div key={i} className="bg-gradient-to-r from-primary-50 to-indigo-50 border-2 border-dashed border-primary-300 rounded-lg p-3 text-primary-800">
                                <span className="text-xs font-bold text-primary-600 block mb-1">DEINE ANTWORT:</span>
                                {cleanLine}
                            </div>
                        );
                    }
                    return (
                        <div key={i} className={`flex ${isUser ? 'justify-start' : 'justify-end'}`}>
                            <div className={`max-w-[80%] rounded-2xl px-4 py-2 ${isUser ? 'bg-gray-200 text-gray-800 rounded-bl-sm' : 'bg-blue-500 text-white rounded-br-sm'}`}>
                                {cleanLine}
                            </div>
                        </div>
                    );
                })}
            </div>
        );
    }

    // Timeline Order: Render as draggable-looking cards
    if (type === 'timeline_order') {
        const lines = prompt.split('\n').filter(l => l.trim());
        const events = lines.filter(l => l.startsWith('['));
        const instruction = lines.filter(l => !l.startsWith('[') && l.includes('→'));

        return (
            <div className="space-y-3">
                <div className="flex flex-wrap gap-2">
                    {events.map((event, i) => (
                        <div key={i} className="flex items-center gap-2 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 text-sm">
                            <span className="w-6 h-6 bg-amber-200 rounded-full flex items-center justify-center text-amber-700 font-bold text-xs">?</span>
                            <span>{event.replace(/^\[\s*\]\s*/, '')}</span>
                        </div>
                    ))}
                </div>
                {instruction.length > 0 && (
                    <div className="text-sm text-gray-600 italic border-t border-gray-100 pt-2">
                        {instruction.join(' ')}
                    </div>
                )}
            </div>
        );
    }

    // Error Hunt: Highlight the text to search for errors
    if (type === 'error_hunt') {
        return (
            <div className="relative">
                <div className="absolute -top-2 -right-2 bg-red-500 text-white text-xs px-2 py-1 rounded-full flex items-center gap-1">
                    <Search className="w-3 h-3" />
                    Fehler finden!
                </div>
                <div className="bg-yellow-50 border-2 border-yellow-300 rounded-lg p-4 text-gray-800 leading-relaxed font-serif italic">
                    &ldquo;{prompt}&rdquo;
                </div>
            </div>
        );
    }

    // Voice Production: Render with microphone hint
    if (type === 'voice_production') {
        return (
            <div className="space-y-2">
                <div className="flex items-center gap-2 text-purple-600 text-sm font-medium">
                    <Mic className="w-4 h-4" />
                    Sprechaufgabe - formuliere deine Antwort
                </div>
                <div className="bg-purple-50 border border-purple-200 rounded-lg p-4 text-gray-800">
                    {prompt}
                </div>
            </div>
        );
    }

    // Default: Plain text with whitespace preserved
    return (
        <div className="whitespace-pre-wrap">{prompt}</div>
    );
}

export default function GrammarReview({ initialQueue, onComplete }: GrammarReviewProps) {
    const [queue, setQueue] = useState<DueConcept[]>(initialQueue);
    const [currentIndex, setCurrentIndex] = useState(0);

    // Exercise state
    const [exercises, setExercises] = useState<ExerciseItem[]>([]);
    const [answers, setAnswers] = useState<Record<string, string>>({});
    const [results, setResults] = useState<ExerciseResult[] | null>(null);
    const [totalScore, setTotalScore] = useState<number>(0);
    const [feedback, setFeedback] = useState<string>('');
    const [focusAreas, setFocusAreas] = useState<string[]>([]);
    const [explanation, setExplanation] = useState<any>(null);
    const [showInfoBox, setShowInfoBox] = useState(true);

    // UI state
    const [loadingExercises, setLoadingExercises] = useState(false);
    const [checkingAnswers, setCheckingAnswers] = useState(false);
    const [showHint, setShowHint] = useState<string | null>(null);

    const currentConcept = queue[currentIndex];

    const loadExercises = useCallback(async () => {
        if (!currentConcept) return;

        setLoadingExercises(true);
        setExercises([]);
        setAnswers({});
        setResults(null);
        setShowHint(null);
        setExplanation(null);
        setShowInfoBox(true);

        try {
            const response = await api.generateGrammarExercise({
                concept_id: currentConcept.id,
                focus_areas: focusAreas
            });

            if (response && Array.isArray(response.flat_exercises) && response.flat_exercises.length > 0) {
                setExercises(response.flat_exercises);
                if (response.explanation) {
                    setExplanation(response.explanation);
                }
                // Initialize answers
                const initialAnswers: Record<string, string> = {};
                response.flat_exercises.forEach((ex: ExerciseItem) => {
                    initialAnswers[ex.id] = '';
                });
                setAnswers(initialAnswers);
            } else {
                setExercises([]);
                setExplanation(response?.explanation || null);
                setAnswers({});
            }
        } catch (error) {
            console.error('Failed to load exercises:', error);
            toast.error('Failed to generate exercises');
        } finally {
            setLoadingExercises(false);
        }
    }, [currentConcept, focusAreas]);

    const handleAnswerChange = (id: string, value: string) => {
        setAnswers(prev => ({ ...prev, [id]: value }));
    };

    const handleSubmitAnswers = async () => {
        if (!currentConcept || exercises.length === 0) return;

        setCheckingAnswers(true);
        try {
            const orderedAnswers = exercises.map(ex => answers[ex.id] || '');

            const response = await api.checkGrammarAnswers({
                concept_id: currentConcept.id,
                exercises,
                answers: orderedAnswers,
            }) as any;

            setResults(response.flat_results || []);
            setTotalScore(response.total_score || 0);
            setFeedback(response.overall_feedback || '');
            setFocusAreas(response.focus_areas || []);

            // Record the score
            await api.recordGrammarReview({
                concept_id: currentConcept.id,
                score: response.total_score || 0,
                notes: response.overall_feedback,
            });

        } catch (error) {
            console.error('Failed to check answers', error);
            toast.error('Antworten konnten nicht geprüft werden');
        } finally {
            setCheckingAnswers(false);
        }
    };

    const handleNextConcept = () => {
        if (currentIndex < queue.length - 1) {
            setCurrentIndex(prev => prev + 1);
        } else {
            toast.success('Session abgeschlossen! 🎉');
            onComplete();
        }
    };

    // Group exercises by block
    const groupedExercises = exercises.reduce((acc, ex) => {
        const block = ex.block || 1;
        if (!acc[block]) acc[block] = [];
        acc[block].push(ex);
        return acc;
    }, {} as Record<number, ExerciseItem[]>);

    // Completion screen
    if (!currentConcept) {
        return (
            <div className="learning-card p-8 text-center">
                <Trophy className="w-16 h-16 text-yellow-500 mx-auto mb-4" />
                <h2 className="text-2xl font-bold mb-2">Session abgeschlossen!</h2>
                <p className="text-gray-600 mb-6">Du hast alle fälligen Konzepte geübt.</p>
                <button onClick={onComplete} className="bg-primary-600 text-white px-6 py-2 rounded-lg hover:bg-primary-700 transition">
                    Zurück zur Übersicht
                </button>
            </div>
        );
    }

    return (
        <div className="max-w-4xl mx-auto space-y-6">
            {/* Progress */}
            <div className="flex items-center justify-between text-sm text-gray-500">
                <span>Konzept {currentIndex + 1} von {queue.length}</span>
                <span className="font-medium px-2 py-1 bg-primary-100 text-primary-700 rounded">{currentConcept.level}</span>
            </div>
            <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                <motion.div
                    className="h-full bg-gradient-to-r from-primary-500 to-indigo-500"
                    initial={{ width: 0 }}
                    animate={{ width: `${((currentIndex + 1) / queue.length) * 100}%` }}
                />
            </div>

            {/* Concept Header */}
            <div className="learning-card">
                <div className="flex items-start justify-between">
                    <div>
                        <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">{currentConcept.category || 'Grammatik'}</span>
                        <h2 className="text-2xl font-bold text-gray-900 mt-1">{currentConcept.name}</h2>
                    </div>
                    <button onClick={loadExercises} disabled={loadingExercises} className="text-gray-400 hover:text-gray-600 p-2" title="Neue Übungen">
                        <RefreshCw className={`w-5 h-5 ${loadingExercises ? 'animate-spin' : ''}`} />
                    </button>
                </div>
                <p className="text-sm text-gray-500 mt-3">
                    📝 3 Übungsblöcke mit je 3 Schwierigkeitsstufen (a → b → c)
                </p>
            </div>

            {/* Concept Info Box */}
            {explanation && showInfoBox && (
                <motion.div
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-200 rounded-xl p-5 shadow-sm"
                >
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="font-bold text-blue-900 flex items-center gap-2">
                            <Lightbulb className="w-5 h-5 text-yellow-500" />
                            Konzept-Überblick
                        </h3>
                        <button
                            onClick={() => setShowInfoBox(false)}
                            className="text-blue-400 hover:text-blue-600 text-sm"
                        >
                            Ausblenden
                        </button>
                    </div>

                    {/* Definition */}
                    <p className="text-gray-700 mb-4">{explanation.definition}</p>

                    {/* Usage */}
                    {explanation.usage && (
                        <div className="mb-4">
                            <h4 className="text-sm font-semibold text-blue-800 mb-2">📌 Wann verwendet man es?</h4>
                            <ul className="text-sm text-gray-600 space-y-1">
                                {explanation.usage.map((use: string, i: number) => (
                                    <li key={i} className="flex items-start gap-2">
                                        <span className="text-blue-400">•</span>
                                        {use}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}

                    {/* Distinction */}
                    {explanation.distinction?.vs && (
                        <div className="mb-4 bg-white/50 rounded-lg p-3 border border-blue-100">
                            <h4 className="text-sm font-semibold text-orange-700 mb-1">⚡ Unterschied zu: {explanation.distinction.vs}</h4>
                            <p className="text-sm text-gray-600">{explanation.distinction.difference}</p>
                        </div>
                    )}

                    {/* Examples */}
                    {explanation.examples && (
                        <div className="mb-4">
                            <h4 className="text-sm font-semibold text-blue-800 mb-2">💬 Beispiele</h4>
                            <div className="space-y-2">
                                {explanation.examples.map((ex: { fr: string, de: string }, i: number) => (
                                    <div key={i} className="bg-white rounded-lg p-2 border border-gray-100 text-sm">
                                        <p className="font-medium text-gray-900">{ex.fr}</p>
                                        <p className="text-gray-500 italic">{ex.de}</p>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Common Mistakes */}
                    {explanation.common_mistakes && (
                        <div className="mb-4">
                            <h4 className="text-sm font-semibold text-red-700 mb-2">❌ Häufige Fehler</h4>
                            <div className="space-y-2">
                                {explanation.common_mistakes.map((m: { wrong: string, correct: string, why: string }, i: number) => (
                                    <div key={i} className="text-sm bg-red-50/50 rounded-lg p-2 border border-red-100">
                                        <p><span className="text-red-600 line-through">{m.wrong}</span> → <span className="text-green-700 font-medium">{m.correct}</span></p>
                                        <p className="text-gray-500 text-xs mt-1">{m.why}</p>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Memory Tip */}
                    {explanation.memory_tip && (
                        <div className="bg-gradient-to-r from-yellow-100 to-amber-100 rounded-lg p-3 border border-yellow-200">
                            <h4 className="text-sm font-semibold text-amber-800 mb-1">💡 Merkhilfe</h4>
                            <p className="text-sm text-amber-900">{explanation.memory_tip}</p>
                        </div>
                    )}
                </motion.div>
            )}

            {/* Loading */}
            {loadingExercises && (
                <div className="learning-card p-12 text-center">
                    <Loader2 className="w-10 h-10 text-primary-500 animate-spin mx-auto mb-4" />
                    <p className="text-gray-600">Übungen werden generiert...</p>
                    <p className="text-xs text-gray-400 mt-2">Die KI erstellt 9 Aufgaben mit steigender Schwierigkeit.</p>
                </div>
            )}

            {/* Exercises */}
            {!loadingExercises && exercises.length > 0 && (
                <div className="space-y-6">
                    {Object.entries(groupedExercises).map(([blockNum, blockExercises]) => (
                        <motion.div
                            key={blockNum}
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: parseInt(blockNum) * 0.1 }}
                            className="learning-card"
                        >
                            {/* Block Header */}
                            <div className="flex items-center gap-3 mb-4 pb-3 border-b border-gray-100">
                                <div className="w-8 h-8 bg-primary-100 text-primary-700 rounded-lg flex items-center justify-center font-bold">
                                    {blockNum}
                                </div>
                                <div className="flex items-center gap-2">
                                    {typeIcons[blockExercises[0]?.type] || <BookOpen className="w-4 h-4" />}
                                    <span className="font-medium">{typeLabels[blockExercises[0]?.type] || 'Übung'}</span>
                                </div>
                            </div>

                            {/* Block Items */}
                            <div className="space-y-4">
                                {blockExercises.map((exercise, idx) => {
                                    const result = results?.[exercises.findIndex(e => e.id === exercise.id)];

                                    return (
                                        <div
                                            key={exercise.id}
                                            className={`p-4 rounded-lg border-2 transition-all ${result?.is_correct === true ? 'bg-green-50 border-green-300' :
                                                result?.is_correct === false ? 'bg-red-50 border-red-300' :
                                                    'bg-gray-50 border-gray-200'
                                                }`}
                                        >
                                            {/* Difficulty Badge */}
                                            <div className="flex items-center gap-2 mb-2">
                                                <span className={`text-xs font-bold px-2 py-0.5 rounded border ${difficultyColors[exercise.level]}`}>
                                                    {exercise.level}) {difficultyLabels[exercise.level]}
                                                </span>
                                                <span className="text-xs text-gray-500">{exercise.instruction}</span>
                                            </div>

                                            {/* Prompt - rendered based on exercise type */}
                                            <div className="text-gray-900 mb-3 p-3 bg-white rounded border border-gray-100">
                                                {renderPrompt(exercise)}
                                            </div>

                                            {/* Answer Input or Result */}
                                            {!results ? (
                                                <textarea
                                                    value={answers[exercise.id] || ''}
                                                    onChange={(e) => handleAnswerChange(exercise.id, e.target.value)}
                                                    placeholder="Deine Antwort..."
                                                    className="w-full p-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none text-sm"
                                                    rows={2}
                                                />
                                            ) : (
                                                <div className="space-y-3">
                                                    <div className={`flex items-start gap-2 p-3 rounded-lg ${result?.is_correct ? 'bg-green-100' : 'bg-red-100'}`}>
                                                        {result?.is_correct ? <Check className="w-5 h-5 text-green-600 mt-0.5" /> : <X className="w-5 h-5 text-red-600 mt-0.5" />}
                                                        <div className="flex-1 text-sm">
                                                            <p className="font-medium">Deine Antwort: {result?.user_answer || '(leer)'}</p>
                                                            {!result?.is_correct && (
                                                                <p className="text-blue-700 mt-1 font-medium">✓ Richtig: {result?.correct_answer}</p>
                                                            )}
                                                        </div>
                                                        <span className={`text-xs font-bold px-2.5 py-1.5 rounded-full ${result?.is_correct ? 'bg-green-200 text-green-800' : 'bg-red-200 text-red-800'}`}>
                                                            {result?.points}/10
                                                        </span>
                                                    </div>
                                                    {/* Rich Feedback Display */}
                                                    <div className="bg-white border border-gray-200 rounded-lg p-4 text-sm">
                                                        <div className="prose prose-sm max-w-none text-gray-700">
                                                            {result?.feedback?.split('\\n').map((line: string, i: number) => (
                                                                <p key={i} className={`${line.startsWith('**') ? 'font-bold text-gray-900 mt-3' : ''} ${line.startsWith('🔵') || line.startsWith('🟡') || line.startsWith('✓') ? 'font-medium' : ''} mb-1`}>
                                                                    {line.replace(/\*\*/g, '')}
                                                                </p>
                                                            ))}
                                                        </div>
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>
                        </motion.div>
                    ))}

                    {/* Submit / Results */}
                    <div className="flex justify-center pt-4">
                        {!results ? (
                            <button
                                onClick={handleSubmitAnswers}
                                disabled={checkingAnswers || Object.values(answers).every(a => !a.trim())}
                                className="flex items-center gap-2 px-8 py-3 bg-gradient-to-r from-primary-600 to-indigo-600 text-white rounded-xl font-bold shadow-lg hover:shadow-xl disabled:opacity-50 transition-all"
                            >
                                {checkingAnswers ? (
                                    <><Loader2 className="w-5 h-5 animate-spin" /> Wird geprüft...</>
                                ) : (
                                    <><Send className="w-5 h-5" /> Alle Antworten prüfen</>
                                )}
                            </button>
                        ) : (
                            <div className="w-full space-y-4">
                                {/* Score Summary */}
                                <div className="learning-card text-center">
                                    <div className={`text-5xl font-bold mb-2 ${totalScore >= 7 ? 'text-green-600' : totalScore >= 4 ? 'text-yellow-600' : 'text-red-600'
                                        }`}>
                                        {totalScore}/10
                                    </div>
                                    <p className="text-gray-600">{feedback}</p>

                                    {focusAreas.length > 0 && (
                                        <div className="mt-4 text-left bg-amber-50 border border-amber-200 rounded-lg p-4">
                                            <p className="text-sm font-medium text-amber-800 mb-2">🎯 Fokus für nächstes Mal:</p>
                                            <ul className="text-sm text-amber-700 space-y-1">
                                                {focusAreas.map((area, i) => <li key={i}>• {area}</li>)}
                                            </ul>
                                        </div>
                                    )}
                                </div>

                                <button
                                    onClick={handleNextConcept}
                                    className="w-full flex items-center justify-center gap-2 px-8 py-3 bg-gradient-to-r from-green-600 to-emerald-600 text-white rounded-xl font-bold shadow-lg hover:shadow-xl transition-all"
                                >
                                    {currentIndex < queue.length - 1 ? 'Nächstes Konzept' : 'Session beenden'}
                                    <ChevronRight className="w-5 h-5" />
                                </button>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* No exercises */}
            {!loadingExercises && exercises.length === 0 && (
                <div className="learning-card p-8 text-center">
                    <p className="text-gray-500 mb-4">Keine Übungen verfügbar.</p>
                    <button onClick={loadExercises} className="text-primary-600 hover:text-primary-700 font-medium">
                        Erneut versuchen
                    </button>
                </div>
            )}
        </div>
    );
}
