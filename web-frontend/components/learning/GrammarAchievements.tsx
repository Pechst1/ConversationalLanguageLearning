import { motion } from 'framer-motion';
import { GrammarAchievement, StreakInfo } from '@/types/grammar';

interface GrammarAchievementsProps {
  achievements: GrammarAchievement[];
  streakInfo: StreakInfo;
  loading?: boolean;
}

const tierColors = {
  bronze: 'bg-amber-600',
  silver: 'bg-gray-400',
  gold: 'bg-yellow-500',
  platinum: 'bg-purple-500',
};

const tierBorders = {
  bronze: 'border-amber-600',
  silver: 'border-gray-400',
  gold: 'border-yellow-500',
  platinum: 'border-purple-500',
};

export default function GrammarAchievements({
  achievements,
  streakInfo,
  loading = false,
}: GrammarAchievementsProps) {
  const unlockedCount = achievements.filter(a => a.is_unlocked).length;

  if (loading) {
    return (
      <div className="animate-pulse space-y-4">
        <div className="h-24 bg-gray-200 dark:bg-gray-700 rounded-lg" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="h-32 bg-gray-200 dark:bg-gray-700 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Streak Card */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-gradient-to-r from-orange-500 to-red-500 rounded-xl p-6 text-white"
      >
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-medium opacity-90">Grammatik-Streak</h3>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-4xl font-bold">{streakInfo.current_streak}</span>
              <span className="text-lg opacity-75">Tage</span>
            </div>
            {streakInfo.current_streak > 0 && (
              <p className="text-sm opacity-75 mt-1">
                {streakInfo.is_active_today
                  ? 'Heute bereits geübt!'
                  : 'Übe heute, um deinen Streak zu behalten!'}
              </p>
            )}
          </div>
          <div className="text-right">
            <div className="text-6xl">🔥</div>
            <p className="text-sm opacity-75 mt-2">
              Rekord: {streakInfo.longest_streak} Tage
            </p>
          </div>
        </div>
      </motion.div>

      {/* Achievements Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
          Errungenschaften
        </h3>
        <span className="text-sm text-gray-500 dark:text-gray-400">
          {unlockedCount} / {achievements.length} freigeschaltet
        </span>
      </div>

      {/* Achievements Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {achievements.map((achievement, index) => (
          <motion.div
            key={achievement.id}
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: index * 0.05 }}
            className={`relative rounded-xl p-4 border-2 ${achievement.is_unlocked
              ? `${tierBorders[achievement.tier]} bg-white dark:bg-gray-800`
              : 'border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50'
              }`}
          >
            {/* Tier Badge */}
            <div
              className={`absolute -top-2 -right-2 w-6 h-6 rounded-full ${achievement.is_unlocked ? tierColors[achievement.tier] : 'bg-gray-400'
                } flex items-center justify-center`}
            >
              {achievement.is_unlocked ? (
                <span className="text-white text-xs">✓</span>
              ) : (
                <span className="text-white text-xs">🔒</span>
              )}
            </div>

            {/* Achievement Icon */}
            <div
              className={`text-3xl mb-2 ${achievement.is_unlocked ? '' : 'grayscale opacity-50'
                }`}
            >
              {getAchievementIcon(achievement.key)}
            </div>

            {/* Achievement Info */}
            <h4
              className={`font-medium text-sm ${achievement.is_unlocked
                ? 'text-gray-900 dark:text-white'
                : 'text-gray-500 dark:text-gray-400'
                }`}
            >
              {achievement.name}
            </h4>
            <p
              className={`text-xs mt-1 ${achievement.is_unlocked
                ? 'text-gray-600 dark:text-gray-300'
                : 'text-gray-400 dark:text-gray-500'
                }`}
            >
              {achievement.description}
            </p>

            {/* XP Reward */}
            <div
              className={`mt-2 text-xs font-medium ${achievement.is_unlocked
                ? 'text-green-600 dark:text-green-400'
                : 'text-gray-400 dark:text-gray-500'
                }`}
            >
              +{achievement.xp_reward} XP
            </div>

            {/* Unlock Date */}
            {achievement.is_unlocked && achievement.unlocked_at && (
              <p className="text-xs text-gray-400 mt-1">
                {new Date(achievement.unlocked_at).toLocaleDateString('de-DE')}
              </p>
            )}
          </motion.div>
        ))}
      </div>
    </div>
  );
}

function getAchievementIcon(key: string): string {
  const icons: Record<string, string> = {
    grammar_first_steps: '👣',
    grammar_streak_7: '🔥',
    grammar_streak_30: '🏆',
    grammar_perfect_score: '⭐',
    grammar_level_master_a1: '🥉',
    grammar_level_master_a2: '🥈',
    grammar_level_master_b1: '🥇',
    grammar_error_crusher: '💪',
  };
  return icons[key] || '🏅';
}
