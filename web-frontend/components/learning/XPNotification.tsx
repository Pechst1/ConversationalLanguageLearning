import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Sparkles, Flame, Star, Trophy } from 'lucide-react';

export interface XPBreakdown {
    baseXP: number;
    wordBonus: number;
    difficultyBonus: number;
    comboBonus: number;
    perfectBonus?: number;
    total: number;
    words?: string[];
    difficulty?: 'easy' | 'medium' | 'hard';
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

    useEffect(() => {
        const timer = setTimeout(() => {
            setShow(false);
            if (onComplete) {
                setTimeout(onComplete, 300);
            }
        }, 3500);

        return () => clearTimeout(timer);
    }, [onComplete]);

    const isCombo = (breakdown?.comboBonus ?? 0) > 0;
    const isPerfect = (breakdown?.perfectBonus ?? 0) > 0;
    const isHighDifficulty = breakdown?.difficulty === 'hard';

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
                        {isCombo && (
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
                                        className="absolute left-1/2 top-1/2 w-2 h-2 bg-yellow-400 rounded-full"
                                    />
                                ))}
                            </motion.div>
                        )}

                        {/* Main card */}
                        <motion.div
                            className={`
                px-8 py-6 rounded-2xl border-4 border-black shadow-[8px_8px_0px_0px_rgba(0,0,0,1)]
                ${isCombo ? 'bg-gradient-to-br from-yellow-400 via-orange-400 to-red-500' : 'bg-yellow-400'}
                ${isPerfect ? 'ring-4 ring-white ring-opacity-50' : ''}
              `}
                            animate={isCombo ? {
                                rotate: [0, -2, 2, -2, 2, 0],
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
                                ) : isHighDifficulty ? (
                                    <Trophy className="w-10 h-10 text-purple-700" />
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
                                    <span className="text-5xl font-black text-black">
                                        +{xpGained}
                                    </span>
                                    <Sparkles className="w-8 h-8 text-black" />
                                </div>
                                {isCombo && (
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
                            {breakdown && (
                                <motion.div
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ delay: 0.4 }}
                                    className="text-sm space-y-1 bg-black/10 rounded-lg p-3 backdrop-blur-sm"
                                >
                                    {breakdown.baseXP > 0 && (
                                        <div className="flex justify-between text-black font-semibold">
                                            <span>Base XP</span>
                                            <span>+{breakdown.baseXP}</span>
                                        </div>
                                    )}
                                    {breakdown.wordBonus > 0 && (
                                        <div className="flex justify-between text-black font-semibold">
                                            <span>Words Used</span>
                                            <span>+{breakdown.wordBonus}</span>
                                        </div>
                                    )}
                                    {breakdown.difficultyBonus > 0 && (
                                        <div className="flex justify-between text-purple-900 font-bold">
                                            <span className="flex items-center gap-1">
                                                <Trophy className="w-3 h-3" />
                                                Hard Word Bonus
                                            </span>
                                            <span>+{breakdown.difficultyBonus}</span>
                                        </div>
                                    )}
                                    {breakdown.comboBonus > 0 && (
                                        <div className="flex justify-between text-red-900 font-bold">
                                            <span className="flex items-center gap-1">
                                                <Flame className="w-3 h-3" />
                                                Combo
                                            </span>
                                            <span>+{breakdown.comboBonus}</span>
                                        </div>
                                    )}
                                    {breakdown.perfectBonus && (
                                        <div className="flex justify-between text-green-900 font-bold">
                                            <span>Perfect! ✨</span>
                                            <span>+{breakdown.perfectBonus}</span>
                                        </div>
                                    )}
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
                                            className="px-3 py-1 bg-black text-white text-xs font-bold rounded-full"
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
