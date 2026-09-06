import React from 'react';
import { Trophy, Star, Lock, CheckCircle, Zap, BookOpen, Target, Flame } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/Card';
import apiService from '@/services/api';

interface Achievement {
    achievement_id: number;
    achievement_key: string;
    name: string;
    description: string;
    tier: 'bronze' | 'silver' | 'gold' | 'platinum';
    xp_reward: number;
    icon_url: string | null;
    current_progress: number;
    target_progress: number;
    completed: boolean;
    unlocked_at: string | null;
}

interface AchievementsPageProps {
    achievements?: Achievement[];
    /** Rendered inside the Cahier, which supplies its own masthead. */
    embedded?: boolean;
}

const tierColors: Record<string, { bg: string; border: string; text: string }> = {
    bronze: { bg: 'bg-[var(--app-paper-2)]', border: 'border-[var(--app-paper-3)]', text: 'text-[var(--app-ink-2)]' },
    silver: { bg: 'bg-[var(--app-paper-2)]', border: 'border-[var(--app-paper-3)]', text: 'text-[var(--app-ink-2)]' },
    gold: { bg: 'bg-[var(--app-paper-2)]', border: 'border-[var(--app-yellow)]', text: 'text-[var(--app-ink-2)]' },
    platinum: { bg: 'bg-[var(--app-paper-2)]', border: 'border-[var(--app-blue)]', text: 'text-[var(--app-ink-2)]' },
};

const categoryIcons: Record<string, React.ElementType> = {
    streak: Flame,
    vocabulary: BookOpen,
    session: Target,
    xp: Zap,
    accuracy: Star,
};

function getIconForKey(key: string): React.ElementType {
    const category = key.split('_')[0];
    return categoryIcons[category] || Trophy;
}

export default function AchievementsPage({ achievements, embedded = false }: AchievementsPageProps) {
    const [achievementList, setAchievementList] = React.useState(achievements || []);

    const loadAchievements = React.useCallback(async () => {
        try {
            const updated = await apiService.get('/achievements/my?include_locked=true') as Achievement[];
            setAchievementList(Array.isArray(updated) ? updated : []);
        } catch (error) {
            console.error('Failed to fetch achievements:', error);
        }
    }, []);

    React.useEffect(() => {
        void loadAchievements();
    }, [loadAchievements]);

    const completedCount = achievementList.filter(a => a.completed).length;
    const totalXP = achievementList
        .filter(a => a.completed)
        .reduce((sum, a) => sum + a.xp_reward, 0);

    return (
        <div className={embedded ? 'space-y-8' : 'space-y-8 p-4'}>
            {/* Header */}
            <div className={embedded ? 'mb-6' : 'mb-8 border-b border-[var(--app-ink)] pb-5'}>
                <div className="text-xs font-black uppercase tracking-[0.16em] text-[var(--app-ink-3)]">
                    Milestones
                </div>
                <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4 mt-1">
                    <h1 className="font-serif text-5xl italic leading-none text-[var(--app-ink)]">
                        Achievements
                    </h1>
                    <div className="text-xs font-black uppercase tracking-[0.13em] text-[var(--app-ink-3)]">
                        Unlocked automatically
                    </div>
                </div>
                <p className="mt-3 max-w-2xl text-[var(--app-ink-2)]">
                    Your milestones and XP rewards appear here as soon as you earn them.
                </p>
            </div>

            {/* Stats Summary */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <Card className="border border-[var(--app-ink)]">
                    <CardContent className="p-6 text-center">
                        <Trophy className="h-12 w-12 mx-auto mb-2 text-[var(--app-yellow)]" />
                        <p className="text-4xl font-black">{completedCount}/{achievementList.length}</p>
                        <p className="text-sm font-bold text-[var(--app-ink-2)] uppercase tracking-wider">Unlocked</p>
                    </CardContent>
                </Card>
                <Card className="border border-[var(--app-ink)]">
                    <CardContent className="p-6 text-center">
                        <Zap className="h-12 w-12 mx-auto mb-2 text-[var(--app-blue)]" />
                        <p className="text-4xl font-black">{totalXP}</p>
                        <p className="text-sm font-bold text-[var(--app-ink-2)] uppercase tracking-wider">XP Earned</p>
                    </CardContent>
                </Card>
                <Card className="border border-[var(--app-ink)]">
                    <CardContent className="p-6 text-center">
                        <Star className="h-12 w-12 mx-auto mb-2 text-[var(--app-blue)]" />
                        <p className="text-4xl font-black">{Math.round((completedCount / achievementList.length) * 100) || 0}%</p>
                        <p className="text-sm font-bold text-[var(--app-ink-2)] uppercase tracking-wider">Complete</p>
                    </CardContent>
                </Card>
            </div>

            {/* Achievements Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {achievementList.map((achievement) => {
                    const IconComponent = getIconForKey(achievement.achievement_key);
                    const tierStyle = tierColors[achievement.tier] || tierColors.bronze;
                    const progress = Math.min((achievement.current_progress / achievement.target_progress) * 100, 100);

                    return (
                        <Card
                            key={achievement.achievement_id}
                            className={`border border-[var(--app-ink)] transition-all duration-200 ${achievement.completed
                                    ? 'hover:-translate-y-1'
                                    : 'opacity-75'
                                }`}
                        >
                            <CardContent className="p-6">
                                <div className="flex items-start gap-4">
                                    <div className={`p-3 border border-[var(--app-ink)] ${tierStyle.bg}`}>
                                        {achievement.completed ? (
                                            <IconComponent className={`h-8 w-8 ${tierStyle.text}`} />
                                        ) : (
                                            <Lock className="h-8 w-8 text-[var(--app-ink-3)]" />
                                        )}
                                    </div>
                                    <div className="flex-1">
                                        <div className="flex items-center gap-2 mb-1">
                                            <h3 className={`font-black text-lg ${achievement.completed ? 'text-[var(--app-ink)]' : 'text-[var(--app-ink-3)]'}`}>
                                                {achievement.name}
                                            </h3>
                                            {achievement.completed && (
                                                <CheckCircle className="h-5 w-5 text-[var(--app-green)]" />
                                            )}
                                        </div>
                                        <p className="text-sm text-[var(--app-ink-2)] mb-3">{achievement.description}</p>

                                        {/* Progress Bar */}
                                        <div className="mb-2">
                                            <div className="w-full bg-[var(--app-paper-3)] border border-[var(--app-ink)] h-4">
                                                <div
                                                    className={`h-full transition-all duration-500 ${achievement.completed ? 'bg-[var(--app-green)]' : 'bg-[var(--app-blue)]'}`}
                                                    style={{ width: `${progress}%` }}
                                                />
                                            </div>
                                            <p className="text-xs font-bold text-[var(--app-ink-3)] mt-1">
                                                {achievement.current_progress} / {achievement.target_progress}
                                            </p>
                                        </div>

                                        {/* Reward & Tier */}
                                        <div className="flex items-center justify-between">
                                            <span className={`px-2 py-1 text-xs font-black uppercase ${tierStyle.bg} ${tierStyle.text} border-2 ${tierStyle.border}`}>
                                                {achievement.tier}
                                            </span>
                                            <span className="text-sm font-bold text-[var(--app-blue)]">
                                                +{achievement.xp_reward} XP
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    );
                })}
            </div>

            {/* Empty State */}
            {achievementList.length === 0 && (
                <div className="text-center py-16 border-4 border-dashed border-[var(--app-paper-3)]">
                    <Trophy className="h-16 w-16 mx-auto text-[var(--app-ink-3)] mb-4" />
                    <h3 className="text-2xl font-black text-[var(--app-ink-3)] mb-2">No Achievements Yet</h3>
                    <p className="text-[var(--app-ink-3)]">Start learning to unlock your first achievement!</p>
                </div>
            )}
        </div>
    );
}
