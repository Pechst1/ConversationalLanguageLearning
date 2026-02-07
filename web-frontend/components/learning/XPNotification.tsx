import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Sparkles, Flame, Star, Trophy, Zap, Award, TrendingUp, Info } from 'lucide-react';

export interface XPBreakdown {
    baseXP: number;
    wordBonus: number;
    difficultyBonus: number;
    comboBonus: number;
    perfectBonus?: number;
    total: number;
    words?: string[];
    difficulty?: 'easy' | 'medium' | 'hard';
    // Enhanced word details for explaining bonuses
    hardWords?: Array<{
        word: string;
        bonus: number;
        reason: string;
    }>;
}

interface XPNotificationProps {
    xpGained: number;
    breakdown?: XPBreakdown;
    onComplete?: () => void;
}

export const XPNotification: React.FC<XPNotificationProps> = ({
    xpGained,
    breakdown,
    onComplete,
}) => {
    const [show, setShow] = useState(true);
    const [showDetails, setShowDetails] = useState(false);

    useEffect(() => {
        const timer = setTimeout(() => {
            setShow(false);
            if (onComplete) {
                setTimeout(onComplete, 300);
            }
        }, 5000); // Extended to 5 seconds to allow reading details

        return () => clearTimeout(timer);
    }, [onComplete]);

    // Show details panel after initial animation
    useEffect(() => {
        const detailTimer = setTimeout(() => setShowDetails(true), 800);
        return () => clearTimeout(detailTimer);
    }, []);

    const isCombo = (breakdown?.comboBonus ?? 0) > 0;
    const isPerfect = (breakdown?.perfectBonus ?? 0) > 0;
    const isHighDifficulty = breakdown?.difficulty === 'hard';
    const hasHardWords = (breakdown?.hardWords?.length ?? 0) > 0 || (breakdown?.difficultyBonus ?? 0) > 0;

    // Calculate explanatory text for XP earned
    const getXPExplanation = () => {
        const parts: string[] = [];
        if (breakdown?.baseXP) parts.push(`${breakdown.baseXP} base`);
        if (breakdown?.wordBonus) parts.push(`${breakdown.wordBonus} for vocabulary`);
        if (breakdown?.difficultyBonus) parts.push(`${breakdown.difficultyBonus} hard word bonus`);
        if (breakdown?.comboBonus) parts.push(`${breakdown.comboBonus} combo`);
        if (breakdown?.perfectBonus) parts.push(`${breakdown.perfectBonus} perfect`);
        return parts.join(' + ');
    };

    return (
        <AnimatePresence>
            {show && (
                <motion.div
                    initial={{ opacity: 0, y: -50, scale: 0.3 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.5, y: -20 }}
                    transition={{
                        type: 'spring',
                        stiffness: 260,
                        damping: 20,
                    }}
                    className="fixed top-24 left-1/2 -translate-x-1/2 z-[100] pointer-events-none"
                >
                    <div className="relative">
                        {/* Celebration particles */}
                        {(isCombo || hasHardWords) && (
                            <motion.div
                                initial={{ opacity: 0 }}
                                animate={{ opacity: [0, 1, 1, 0] }}
                                transition={{ duration: 2, times: [0, 0.1, 0.9, 1] }}
                                className="absolute inset-0 -z-10"
                            >
                                {[...Array(12)].map((_, i) => (
                                    <motion.div
                                        key={i}
                                        initial={{ scale: 0, x: 0, y: 0 }}
                                        animate={{
                                            scale: [0, 1, 0],
                                            x: [0, Math.cos((i / 12) * Math.PI * 2) * 100],
                                            y: [0, Math.sin((i / 12) * Math.PI * 2) * 100],
                                        }}
                                        transition={{ duration: 1.5, delay: i * 0.05 }}
                                        className={`absolute left-1/2 top-1/2 w-2 h-2 rounded-full ${hasHardWords ? 'bg-purple-500' : 'bg-yellow-400'
                                            }`}
                                    />
                                ))}
                            </motion.div>
                        )}

                        {/* Main card */}
                        <motion.div
                            className={`
                px-8 py-6 rounded-2xl border-4 border-black shadow-[8px_8px_0px_0px_rgba(0,0,0,1)]
                ${isCombo ? 'bg-gradient-to-br from-yellow-400 via-orange-400 to-red-500' :
                                    hasHardWords ? 'bg-gradient-to-br from-purple-400 via-purple-500 to-indigo-600' :
                                        'bg-yellow-400'}
                ${isPerfect ? 'ring-4 ring-white ring-opacity-50' : ''}
                min-w-[320px] max-w-[400px]
              `}
                            animate={isCombo ? {
                                rotate: [0, -2, 2, -2, 2, 0],
                            } : hasHardWords ? {
                                scale: [1, 1.02, 1],
                            } : {}}
                            transition={{ duration: 0.4 }}
                        >
                            {/* Icon */}
                            <div className="flex justify-center mb-3">
                                {isCombo ? (
                                    <motion.div
                                        animate={{ rotate: [0, 360] }}
                                        transition={{ duration: 0.6, ease: 'easeInOut' }}
                                    >
                                        <Flame className="w-12 h-12 text-white drop-shadow-lg" />
                                    </motion.div>
                                ) : hasHardWords ? (
                                    <motion.div
                                        animate={{ scale: [1, 1.2, 1] }}
                                        transition={{ duration: 0.8, repeat: 2 }}
                                    >
                                        <Trophy className="w-12 h-12 text-yellow-300 drop-shadow-lg" />
                                    </motion.div>
                                ) : (
                                    <Star className="w-10 h-10 text-black" />
                                )}
                            </div>

                            {/* Main XP display */}
                            <motion.div
                                initial={{ scale: 0.5 }}
                                animate={{ scale: 1 }}
                                transition={{ delay: 0.1, type: 'spring' }}
                                className="text-center mb-3"
                            >
                                <div className="flex items-center justify-center gap-2">
                                    <span className={`text-5xl font-black ${hasHardWords ? 'text-white' : 'text-black'}`}>
                                        +{xpGained}
                                    </span>
                                    <Sparkles className={`w-8 h-8 ${hasHardWords ? 'text-yellow-300' : 'text-black'}`} />
                                </div>

                                {/* Title based on achievement */}
                                {hasHardWords && (
                                    <motion.div
                                        initial={{ opacity: 0 }}
                                        animate={{ opacity: 1 }}
                                        transition={{ delay: 0.3 }}
                                        className="text-xl font-bold text-yellow-200 mt-1 flex items-center justify-center gap-2"
                                    >
                                        <Award className="w-5 h-5" />
                                        SCHWIERIGES WORT GEMEISTERT!
                                    </motion.div>
                                )}
                                {isCombo && !hasHardWords && (
                                    <motion.div
                                        initial={{ opacity: 0 }}
                                        animate={{ opacity: 1 }}
                                        transition={{ delay: 0.3 }}
                                        className="text-xl font-bold text-white mt-1 drop-shadow-md"
                                    >
                                        COMBO BONUS! 🔥
                                    </motion.div>
                                )}
                            </motion.div>

                            {/* Breakdown */}
                            {breakdown && showDetails && (
                                <motion.div
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ delay: 0.4 }}
                                    className={`text-sm space-y-1 rounded-lg p-3 backdrop-blur-sm ${hasHardWords ? 'bg-white/20' : 'bg-black/10'
                                        }`}
                                >
                                    {breakdown.baseXP > 0 && (
                                        <div className={`flex justify-between font-semibold ${hasHardWords ? 'text-white' : 'text-black'}`}>
                                            <span className="flex items-center gap-1">
                                                <Zap className="w-3 h-3" />
                                                Basis-XP
                                            </span>
                                            <span>+{breakdown.baseXP}</span>
                                        </div>
                                    )}
                                    {breakdown.wordBonus > 0 && (
                                        <div className={`flex justify-between font-semibold ${hasHardWords ? 'text-white' : 'text-black'}`}>
                                            <span className="flex items-center gap-1">
                                                <TrendingUp className="w-3 h-3" />
                                                Wortschatz verwendet
                                            </span>
                                            <span>+{breakdown.wordBonus}</span>
                                        </div>
                                    )}
                                    {breakdown.difficultyBonus > 0 && (
                                        <motion.div
                                            className="flex justify-between font-bold text-yellow-200 bg-purple-700/50 rounded px-2 py-1"
                                            animate={{ backgroundColor: ['rgba(126,34,206,0.5)', 'rgba(126,34,206,0.8)', 'rgba(126,34,206,0.5)'] }}
                                            transition={{ duration: 1.5, repeat: Infinity }}
                                        >
                                            <span className="flex items-center gap-1">
                                                <Trophy className="w-3 h-3" />
                                                Schwierigkeitsbonus
                                            </span>
                                            <span>+{breakdown.difficultyBonus}</span>
                                        </motion.div>
                                    )}
                                    {breakdown.comboBonus > 0 && (
                                        <div className={`flex justify-between font-bold ${hasHardWords ? 'text-orange-200' : 'text-red-900'}`}>
                                            <span className="flex items-center gap-1">
                                                <Flame className="w-3 h-3" />
                                                Combo ({breakdown.words?.length || 0} Wörter)
                                            </span>
                                            <span>+{breakdown.comboBonus}</span>
                                        </div>
                                    )}
                                    {breakdown.perfectBonus && breakdown.perfectBonus > 0 && (
                                        <div className={`flex justify-between font-bold ${hasHardWords ? 'text-green-200' : 'text-green-900'}`}>
                                            <span>Perfekt! ✨</span>
                                            <span>+{breakdown.perfectBonus}</span>
                                        </div>
                                    )}
                                </motion.div>
                            )}

                            {/* Hard Words Details with individual explanations */}
                            {breakdown?.hardWords && breakdown.hardWords.length > 0 && showDetails && (
                                <motion.div
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ delay: 0.6 }}
                                    className="mt-3 space-y-2"
                                >
                                    <div className="text-xs font-bold text-yellow-200 uppercase tracking-wider flex items-center gap-1">
                                        <Trophy className="w-3 h-3" />
                                        Schwierige Wörter gemeistert:
                                    </div>
                                    <div className="space-y-1.5">
                                        {breakdown.hardWords.map((hw, i) => (
                                            <motion.div
                                                key={i}
                                                initial={{ opacity: 0, x: -10 }}
                                                animate={{ opacity: 1, x: 0 }}
                                                transition={{ delay: 0.7 + i * 0.1 }}
                                                className="flex items-center justify-between bg-white/15 rounded-lg px-3 py-2"
                                            >
                                                <div className="flex items-center gap-2">
                                                    <span className="text-yellow-300 font-bold">{hw.word}</span>
                                                    <span className="text-white/60 text-xs">{hw.reason}</span>
                                                </div>
                                                <span className="text-green-300 font-bold text-sm">+{hw.bonus} XP</span>
                                            </motion.div>
                                        ))}
                                    </div>
                                </motion.div>
                            )}

                            {/* General explanation tooltip (only if no specific hardWords) */}
                            {hasHardWords && (!breakdown?.hardWords || breakdown.hardWords.length === 0) && showDetails && (
                                <motion.div
                                    initial={{ opacity: 0 }}
                                    animate={{ opacity: 1 }}
                                    transition={{ delay: 0.8 }}
                                    className="mt-3 text-xs text-white/80 flex items-start gap-2 bg-white/10 rounded-lg p-2"
                                >
                                    <Info className="w-4 h-4 flex-shrink-0 mt-0.5" />
                                    <span>
                                        Du erhältst Bonuspunkte für die korrekte Verwendung schwieriger Vokabeln!
                                        Je öfter du sie richtig verwendest, desto mehr XP verdienst du.
                                    </span>
                                </motion.div>
                            )}

                            {/* Words used */}
                            {breakdown?.words && breakdown.words.length > 0 && (
                                <motion.div
                                    initial={{ opacity: 0 }}
                                    animate={{ opacity: 1 }}
                                    transition={{ delay: 0.6 }}
                                    className="mt-3 flex flex-wrap gap-2 justify-center"
                                >
                                    {breakdown.words.map((word, i) => (
                                        <motion.span
                                            key={i}
                                            initial={{ scale: 0 }}
                                            animate={{ scale: 1 }}
                                            transition={{ delay: 0.6 + i * 0.1 }}
                                            className={`px-3 py-1 text-xs font-bold rounded-full ${hasHardWords
                                                ? 'bg-yellow-300 text-purple-900 border-2 border-yellow-100'
                                                : 'bg-black text-white'
                                                }`}
                                        >
                                            {word}
                                        </motion.span>
                                    ))}
                                </motion.div>
                            )}
                        </motion.div>
                    </div>
                </motion.div>
            )}
        </AnimatePresence>
    );
};

export default XPNotification;
