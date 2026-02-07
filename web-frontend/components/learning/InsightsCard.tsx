import React, { useState, useEffect } from 'react';
import { Sparkles, RefreshCw, ChevronRight, Check, TrendingUp, AlertCircle, BookOpen, MessageCircle, Clock } from 'lucide-react';

interface Recommendation {
    type: 'grammar' | 'vocabulary' | 'practice';
    title: string;
    description: string;
}

interface LearningInsight {
    generated_at: string;
    period_days: number;
    headline: string;
    progress_summary: string;
    strengths: string[];
    improvements: string[];
    recommendations: Recommendation[];
    encouragement: string;
}

const typeIcons: Record<string, React.ReactNode> = {
    grammar: <BookOpen className="w-4 h-4" />,
    vocabulary: <MessageCircle className="w-4 h-4" />,
    practice: <Clock className="w-4 h-4" />,
};

const typeColors: Record<string, string> = {
    grammar: 'bg-purple-100 text-purple-800 border-purple-300',
    vocabulary: 'bg-blue-100 text-blue-800 border-blue-300',
    practice: 'bg-green-100 text-green-800 border-green-300',
};

export default function InsightsCard() {
    const [insight, setInsight] = useState<LearningInsight | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [refreshing, setRefreshing] = useState(false);

    const fetchInsights = async (forceRefresh = false) => {
        try {
            if (forceRefresh) setRefreshing(true);
            else setLoading(true);

            const response = await fetch(`/api/v1/progress/insights/weekly?force_refresh=${forceRefresh}`, {
                credentials: 'include',
            });

            if (!response.ok) {
                throw new Error('Failed to fetch insights');
            }

            const data = await response.json();
            setInsight(data);
            setError(null);
        } catch (err) {
            setError('Unable to load insights');
            console.error('Insights fetch error:', err);
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    };

    useEffect(() => {
        fetchInsights();
    }, []);

    if (loading) {
        return (
            <div className="bg-gradient-to-br from-indigo-50 to-purple-50 border-4 border-black shadow-[6px_6px_0px_0px_#000] p-6">
                <div className="flex items-center gap-3 mb-4">
                    <Sparkles className="w-6 h-6 text-indigo-600 animate-pulse" />
                    <h3 className="text-lg font-extrabold text-black uppercase tracking-tight">AI Insights</h3>
                </div>
                <div className="animate-pulse space-y-3">
                    <div className="h-6 bg-gray-300 rounded w-3/4"></div>
                    <div className="h-4 bg-gray-200 rounded w-full"></div>
                    <div className="h-4 bg-gray-200 rounded w-5/6"></div>
                </div>
            </div>
        );
    }

    if (error || !insight) {
        return (
            <div className="bg-gray-50 border-4 border-black shadow-[6px_6px_0px_0px_#000] p-6">
                <div className="flex items-center gap-3 mb-4">
                    <AlertCircle className="w-6 h-6 text-gray-400" />
                    <h3 className="text-lg font-extrabold text-black uppercase tracking-tight">AI Insights</h3>
                </div>
                <p className="text-gray-500 text-sm">{error || 'No insights available yet'}</p>
                <button
                    onClick={() => fetchInsights()}
                    className="mt-4 text-sm font-bold text-indigo-600 hover:text-indigo-800 flex items-center gap-1"
                >
                    Try again <ChevronRight className="w-4 h-4" />
                </button>
            </div>
        );
    }

    return (
        <div className="bg-gradient-to-br from-indigo-50 via-purple-50 to-pink-50 border-4 border-black shadow-[6px_6px_0px_0px_#000] overflow-hidden">
            {/* Header */}
            <div className="px-6 py-4 bg-gradient-to-r from-indigo-600 to-purple-600 text-white">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <Sparkles className="w-6 h-6" />
                        <h3 className="text-lg font-extrabold uppercase tracking-tight">AI Weekly Insights</h3>
                    </div>
                    <button
                        onClick={() => fetchInsights(true)}
                        disabled={refreshing}
                        className="p-2 hover:bg-white/20 rounded-lg transition-colors disabled:opacity-50"
                        title="Refresh insights"
                    >
                        <RefreshCw className={`w-5 h-5 ${refreshing ? 'animate-spin' : ''}`} />
                    </button>
                </div>
                <p className="text-xl font-bold mt-2">{insight.headline}</p>
            </div>

            <div className="p-6 space-y-5">
                {/* Progress Summary */}
                <p className="text-gray-700 text-sm leading-relaxed">{insight.progress_summary}</p>

                {/* Strengths */}
                {insight.strengths.length > 0 && (
                    <div className="space-y-2">
                        <h4 className="text-xs font-extrabold text-green-700 uppercase tracking-wider flex items-center gap-2">
                            <TrendingUp className="w-4 h-4" /> Strengths
                        </h4>
                        <div className="space-y-1">
                            {insight.strengths.map((strength, idx) => (
                                <div key={idx} className="flex items-start gap-2 text-sm text-gray-700">
                                    <Check className="w-4 h-4 text-green-600 flex-shrink-0 mt-0.5" />
                                    <span>{strength}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Recommendations */}
                {insight.recommendations.length > 0 && (
                    <div className="space-y-3">
                        <h4 className="text-xs font-extrabold text-indigo-700 uppercase tracking-wider">
                            This Week's Focus
                        </h4>
                        <div className="space-y-2">
                            {insight.recommendations.map((rec, idx) => (
                                <div
                                    key={idx}
                                    className={`p-3 rounded-lg border-2 ${typeColors[rec.type] || 'bg-gray-100 text-gray-800 border-gray-300'}`}
                                >
                                    <div className="flex items-center gap-2 mb-1">
                                        {typeIcons[rec.type]}
                                        <span className="font-bold text-sm">{rec.title}</span>
                                    </div>
                                    <p className="text-xs opacity-80">{rec.description}</p>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Encouragement */}
                {insight.encouragement && (
                    <div className="bg-white/60 border-2 border-indigo-200 rounded-lg p-4 text-center">
                        <p className="text-sm font-medium text-indigo-800 italic">
                            "{insight.encouragement}"
                        </p>
                    </div>
                )}

                {/* Generated timestamp */}
                <p className="text-xs text-gray-400 text-center">
                    Generated {new Date(insight.generated_at).toLocaleDateString()}
                </p>
            </div>
        </div>
    );
}
