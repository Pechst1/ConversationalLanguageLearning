import React from 'react';
import { motion } from 'framer-motion';
import { CheckCircle, XCircle, Clock, Trophy, Star, Flame } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import type { SessionStats } from '@/types/learning';

interface SessionSummaryProps {
  stats: SessionStats;
  onStartNewSession: () => void;
  onReturnToDashboard: () => void;
}

export default function SessionSummary({
  stats,
  onStartNewSession,
  onReturnToDashboard,
}: SessionSummaryProps) {
  const normalized = React.useMemo(() => {
    const totalReviews =
      (typeof stats.totalReviews === 'number' ? stats.totalReviews : undefined) ??
      (typeof stats.words_reviewed === 'number' ? stats.words_reviewed : undefined) ??
      (typeof stats.words_practiced === 'number' ? stats.words_practiced : undefined) ??
      0;

    const correctAnswers =
      (typeof stats.correctAnswers === 'number' ? stats.correctAnswers : undefined) ??
      (typeof stats.correct_responses === 'number' ? stats.correct_responses : undefined) ??
      Math.max(0, totalReviews - ((typeof stats.incorrect_responses === 'number' ? stats.incorrect_responses : 0)));

    const xpEarned =
      (typeof stats.xpEarned === 'number' ? stats.xpEarned : undefined) ??
      (typeof stats.xp_earned === 'number' ? stats.xp_earned : undefined) ??
      0;

    const newCards =
      (typeof stats.newCards === 'number' ? stats.newCards : undefined) ??
      (typeof stats.new_words_introduced === 'number' ? stats.new_words_introduced : undefined) ??
      0;

    const sessionDuration =
      (typeof stats.sessionDuration === 'number' ? stats.sessionDuration : undefined) ??
      undefined;

    const accuracyExplicit =
      (typeof stats.accuracy === 'number' ? stats.accuracy : undefined) ??
      (typeof stats.accuracy_rate === 'number' ? Math.round(stats.accuracy_rate * 100) : undefined);

    return {
      totalReviews,
      correctAnswers,
      xpEarned,
      sessionDuration,
      newCards,
      accuracyExplicit,
    };
  }, [stats]);

  const effectiveTotal = normalized.totalReviews;
  const effectiveCorrect = normalized.correctAnswers;
  const effectiveAccuracy = normalized.accuracyExplicit ?? (effectiveTotal > 0 ? Math.round((effectiveCorrect / effectiveTotal) * 100) : 0);
  const incorrectAnswers = Math.max(0, effectiveTotal - effectiveCorrect);

  const getPerformanceTier = (accuracy: number) => {
    if (accuracy >= 90) return { label: 'Perfect!', color: 'from-yellow-400 to-orange-400', icon: Trophy };
    if (accuracy >= 80) return { label: 'Excellent!', color: 'from-green-400 to-emerald-400', icon: Star };
    if (accuracy >= 60) return { label: 'Good Job!', color: 'from-blue-400 to-cyan-400', icon: CheckCircle };
    return { label: 'Keep Practicing!', color: 'from-gray-400 to-gray-500', icon: Flame };
  };

  const tier = getPerformanceTier(effectiveAccuracy);
  const TierIcon = tier.icon;

  // Emit custom event when component mounts
  React.useEffect(() => {
    const event = new CustomEvent('learningSessionComplete', {
      detail: { stats, timestamp: new Date().toISOString() }
    });
    window.dispatchEvent(event);

    try {
      if (typeof window !== 'undefined' && window.localStorage) {
        window.localStorage.setItem('lastSessionComplete', new Date().toISOString());
      }
    } catch (error) {
      console.debug('Could not update localStorage:', error);
    }
  }, [stats]);

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ type: 'spring', duration: 0.5 }}
      className="w-full max-w-2xl mx-auto"
    >
      {/* Header with celebration */}
      <div className={`relative mb-8 p-8 rounded-2xl border-4 border-black shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] bg-gradient-to-br ${tier.color}`}>
        <motion.div
          initial={{ scale: 0, rotate: -180 }}
          animate={{ scale: 1, rotate: 0 }}
          transition={{ type: 'spring', delay: 0.2 }}
          className="flex justify-center mb-4"
        >
          <div className="p-4 bg-white rounded-full border-4 border-black shadow-lg">
            <TierIcon className="w-16 h-16 text-black" />
          </div>
        </motion.div>

        <motion.h2
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="text-4xl font-black text-center text-white drop-shadow-lg mb-2"
        >
          {tier.label}
        </motion.h2>

        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.4 }}
          className="text-center text-white/90 text-lg font-semibold"
        >
          Session Complete
        </motion.p>
      </div>

      {/* Main stats cards */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
          className="p-6 bg-blue-400 border-4 border-black rounded-xl shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]"
        >
          <div className="text-center">
            <div className="text-4xl font-black text-black">{effectiveTotal}</div>
            <div className="text-sm font-bold text-black/80 mt-1">Words</div>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.6 }}
          className="p-6 bg-yellow-400 border-4 border-black rounded-xl shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]"
        >
          <div className="text-center">
            <div className="text-4xl font-black text-black">{effectiveAccuracy}%</div>
            <div className="text-sm font-bold text-black/80 mt-1">Accuracy</div>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.7 }}
          className="p-6 bg-purple-400 border-4 border-black rounded-xl shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]"
        >
          <div className="text-center">
            <div className="text-4xl font-black text-black">{normalized.xpEarned}</div>
            <div className="text-sm font-bold text-black/80 mt-1">XP Earned</div>
          </div>
        </motion.div>
      </div>

      {/* Detailed breakdown */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.8 }}
        className="mb-6 p-6 bg-white border-4 border-black rounded-xl shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]"
      >
        <h3 className="text-xl font-black text-black mb-4">Session Details</h3>

        <div className="grid grid-cols-2 gap-3">
          <div className="flex items-center justify-between p-3 bg-green-50 border-2 border-green-300 rounded-lg">
            <div className="flex items-center gap-2">
              <CheckCircle className="w-4 h-4 text-green-600" />
              <span className="font-bold text-sm">Correct</span>
            </div>
            <span className="font-black text-green-700">{effectiveCorrect}</span>
          </div>

          <div className="flex items-center justify-between p-3 bg-red-50 border-2 border-red-300 rounded-lg">
            <div className="flex items-center gap-2">
              <XCircle className="w-4 h-4 text-red-600" />
              <span className="font-bold text-sm">Incorrect</span>
            </div>
            <span className="font-black text-red-700">{incorrectAnswers}</span>
          </div>

          <div className="flex items-center justify-between p-3 bg-blue-50 border-2 border-blue-300 rounded-lg">
            <div className="flex items-center gap-2">
              <Clock className="w-4 h-4 text-blue-600" />
              <span className="font-bold text-sm">Duration</span>
            </div>
            <span className="font-black text-blue-700">
              {normalized.sessionDuration ? `${Math.round(normalized.sessionDuration / 60)}m` : 'N/A'}
            </span>
          </div>

          <div className="flex items-center justify-between p-3 bg-purple-50 border-2 border-purple-300 rounded-lg">
            <div className="flex items-center gap-2">
              <Star className="w-4 h-4 text-purple-600" />
              <span className="font-bold text-sm">New Cards</span>
            </div>
            <span className="font-black text-purple-700">{normalized.newCards || 0}</span>
          </div>
        </div>
      </motion.div>

      {/* Action buttons */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.9 }}
        className="flex flex-col sm:flex-row gap-4"
      >
        <Button
          onClick={onStartNewSession}
          className="flex-1 bg-yellow-400 hover:bg-yellow-500 text-black font-black py-6 text-lg border-4 border-black shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] hover:shadow-[6px_6px_0px_0px_rgba(0,0,0,1)] hover:translate-x-[-2px] hover:translate-y-[-2px] transition-all"
        >
          Start New Session ⚡
        </Button>
        <Button
          onClick={onReturnToDashboard}
          className="flex-1 bg-white hover:bg-gray-100 text-black font-black py-6 text-lg border-4 border-black shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] hover:shadow-[6px_6px_0px_0px_rgba(0,0,0,1)] hover:translate-x-[-2px] hover:translate-y-[-2px] transition-all"
        >
          Dashboard
        </Button>
      </motion.div>
    </motion.div>
  );
}
