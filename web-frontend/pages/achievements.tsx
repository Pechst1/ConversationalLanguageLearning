import React from 'react';
import { getSession } from 'next-auth/react';
import { Trophy, Star, Lock, CheckCircle, Zap, BookOpen, Target, Flame } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import apiService from '@/services/api';
import toast from 'react-hot-toast';

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
    achievements: Achievement[];
}

const tierColors: Record<string, { bg: string; border: string; text: string }> = {
    bronze: { bg: 'bg-orange-100', border: 'border-orange-400', text: 'text-orange-700' },
    silver: { bg: 'bg-gray-100', border: 'border-gray-400', text: 'text-gray-700' },
    gold: { bg: 'bg-yellow-100', border: 'border-yellow-500', text: 'text-yellow-700' },
    platinum: { bg: 'bg-purple-100', border: 'border-purple-500', text: 'text-purple-700' },
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

export default function AchievementsPage({ achievements }: AchievementsPageProps) {
    const [isChecking, setIsChecking] = React.useState(false);
    const [achievementList, setAchievementList] = React.useState(achievements);

    const completedCount = achievementList.filter(a => a.completed).length;
    const totalXP = achievementList
        .filter(a => a.completed)
        .reduce((sum, a) => sum + a.xp_reward, 0);

    const handleCheckAchievements = async () => {
        setIsChecking(true);
        try {
            const response = await apiService.post('/achievements/check', {}) as any;
            if (response.newly_unlocked?.length > 0) {
                toast.success(`🎉 Unlocked ${response.newly_unlocked.length} new achievement(s)!`);
                // Refresh achievements list
                const updated = await apiService.get('/achievements/my?include_locked=true') as Achievement[];
                setAchievementList(updated);
            } else {
                toast.success('No new achievements to unlock. Keep learning!');
            }
        } catch (error) {
            toast.error('Failed to check achievements');
        } finally {
            setIsChecking(false);
        }
    };

    return (
        <div className="space-y-8 p-4">
            {/* Header */}
            <div className="flex items-center justify-between border-b-4 border-black pb-6 bg-white p-4 shadow-[4px_4px_0px_0px_#000]">
                <div>
                    <h1 className="text-4xl font-extrabold text-black uppercase tracking-tight">Achievements</h1>
                    <p className="text-gray-600 font-bold mt-1">Track your learning milestones</p>
                </div>
                <Button
                    onClick={handleCheckAchievements}
                    loading={isChecking}
                    className="shadow-[4px_4px_0px_0px_#000] border-2 border-black"
                >
                    Check Progress
                </Button>
            </div>

            {/* Stats Summary */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <Card className="border-4 border-black shadow-[8px_8px_0px_0px_#000]">
                    <CardContent className="p-6 text-center">
                        <Trophy className="h-12 w-12 mx-auto mb-2 text-yellow-500" />
                        <p className="text-4xl font-black">{completedCount}/{achievementList.length}</p>
                        <p className="text-sm font-bold text-gray-600 uppercase tracking-wider">Unlocked</p>
                    </CardContent>
                </Card>
                <Card className="border-4 border-black shadow-[8px_8px_0px_0px_#000]">
                    <CardContent className="p-6 text-center">
                        <Zap className="h-12 w-12 mx-auto mb-2 text-purple-500" />
                        <p className="text-4xl font-black">{totalXP}</p>
                        <p className="text-sm font-bold text-gray-600 uppercase tracking-wider">XP Earned</p>
                    </CardContent>
                </Card>
                <Card className="border-4 border-black shadow-[8px_8px_0px_0px_#000]">
                    <CardContent className="p-6 text-center">
                        <Star className="h-12 w-12 mx-auto mb-2 text-blue-500" />
                        <p className="text-4xl font-black">{Math.round((completedCount / achievementList.length) * 100) || 0}%</p>
                        <p className="text-sm font-bold text-gray-600 uppercase tracking-wider">Complete</p>
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
                            className={`border-4 border-black shadow-[6px_6px_0px_0px_#000] transition-all duration-200 ${achievement.completed
                                    ? 'hover:-translate-y-1 hover:shadow-[8px_8px_0px_0px_#000]'
                                    : 'opacity-75'
                                }`}
                        >
                            <CardContent className="p-6">
                                <div className="flex items-start gap-4">
                                    <div className={`p-3 border-2 border-black ${tierStyle.bg} shadow-[2px_2px_0px_0px_#000]`}>
                                        {achievement.completed ? (
                                            <IconComponent className={`h-8 w-8 ${tierStyle.text}`} />
                                        ) : (
                                            <Lock className="h-8 w-8 text-gray-400" />
                                        )}
                                    </div>
                                    <div className="flex-1">
                                        <div className="flex items-center gap-2 mb-1">
                                            <h3 className={`font-black text-lg ${achievement.completed ? 'text-black' : 'text-gray-500'}`}>
                                                {achievement.name}
                                            </h3>
                                            {achievement.completed && (
                                                <CheckCircle className="h-5 w-5 text-green-500" />
                                            )}
                                        </div>
                                        <p className="text-sm text-gray-600 mb-3">{achievement.description}</p>

                                        {/* Progress Bar */}
                                        <div className="mb-2">
                                            <div className="w-full bg-gray-200 border-2 border-black h-4">
                                                <div
                                                    className={`h-full transition-all duration-500 ${achievement.completed ? 'bg-green-500' : 'bg-bauhaus-blue'}`}
                                                    style={{ width: `${progress}%` }}
                                                />
                                            </div>
                                            <p className="text-xs font-bold text-gray-500 mt-1">
                                                {achievement.current_progress} / {achievement.target_progress}
                                            </p>
                                        </div>

                                        {/* Reward & Tier */}
                                        <div className="flex items-center justify-between">
                                            <span className={`px-2 py-1 text-xs font-black uppercase ${tierStyle.bg} ${tierStyle.text} border-2 ${tierStyle.border}`}>
                                                {achievement.tier}
                                            </span>
                                            <span className="text-sm font-bold text-purple-600">
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
                <div className="text-center py-16 border-4 border-dashed border-gray-300">
                    <Trophy className="h-16 w-16 mx-auto text-gray-400 mb-4" />
                    <h3 className="text-2xl font-black text-gray-500 mb-2">No Achievements Yet</h3>
                    <p className="text-gray-500">Start learning to unlock your first achievement!</p>
                </div>
            )}
        </div>
    );
}

export async function getServerSideProps(context: any) {
    const session = await getSession(context);

    if (!session) {
        return {
            redirect: {
                destination: '/auth/signin',
                permanent: false,
            },
        };
    }

    try {
        const baseUrl = process.env.API_URL || 'http://localhost:8000';
        const headers = {
            'Authorization': `Bearer ${session.accessToken}`,
            'Content-Type': 'application/json',
        };

        const response = await fetch(`${baseUrl}/api/v1/achievements/my?include_locked=true`, { headers });
        const achievements = response.ok ? await response.json() : [];

        return {
            props: {
                achievements,
            },
        };
    } catch (error) {
        console.error('Failed to fetch achievements:', error);
        return {
            props: {
                achievements: [],
            },
        };
    }
}
