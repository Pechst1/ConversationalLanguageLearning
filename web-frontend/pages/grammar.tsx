import React, { useState } from 'react';
import { getSession } from 'next-auth/react';
import Head from 'next/head';
import { motion, AnimatePresence } from 'framer-motion';
import { Book, Play, Filter, Sparkles, Trophy, GitBranch, BarChart3 } from 'lucide-react';
import api from '@/services/api';
import useSWR from 'swr';
import {
    GrammarSummary,
    GrammarLevelGroup,
    DueConcept,
    GrammarAchievement,
    StreakInfo,
    ConceptGraph,
} from '@/types/grammar';
import GrammarLevelGrid from '@/components/learning/GrammarLevelGrid';
import GrammarReview from '@/components/learning/GrammarReview';
import GrammarAchievements from '@/components/learning/GrammarAchievements';
import GrammarGraph from '@/components/learning/GrammarGraph';

type TabType = 'overview' | 'review' | 'achievements' | 'graph';

export default function GrammarPage() {
    const [activeTab, setActiveTab] = useState<TabType>('overview');
    const [selectedLevel, setSelectedLevel] = useState<string | null>(null);
    const [reviewQueue, setReviewQueue] = useState<DueConcept[] | null>(null);

    // Data Fetching
    const { data: summary, mutate: refreshSummary } = useSWR<GrammarSummary>(
        '/grammar/summary',
        async () => (await api.getGrammarSummary()) as GrammarSummary
    );
    const { data: levels } = useSWR<GrammarLevelGroup>(
        '/grammar/by-level',
        async () => (await api.getGrammarConceptsByLevel()) as GrammarLevelGroup
    );
    const { data: dueConcepts, mutate: refreshDue } = useSWR<DueConcept[]>(
        '/grammar/due',
        async () => (await api.getDueGrammarConcepts({ limit: 10 })) as DueConcept[]
    );
    const { data: achievements, isLoading: achievementsLoading } = useSWR<GrammarAchievement[]>(
        activeTab === 'achievements' ? '/grammar/achievements' : null,
        async () => (await api.getGrammarAchievements('grammar')) as GrammarAchievement[]
    );
    const { data: streakInfo, isLoading: streakLoading } = useSWR<StreakInfo>(
        activeTab === 'achievements' ? '/grammar/streak' : null,
        async () => (await api.getGrammarStreak()) as StreakInfo
    );
    const { data: conceptGraph, isLoading: graphLoading } = useSWR<ConceptGraph>(
        activeTab === 'graph' ? `/grammar/graph${selectedLevel ? `?level=${selectedLevel}` : ''}` : null,
        async () => (await api.getGrammarGraph(selectedLevel || undefined)) as ConceptGraph
    );

    const hasDueReviews = dueConcepts && dueConcepts.length > 0;

    const handleReviewComplete = () => {
        refreshSummary();
        refreshDue();
        setReviewQueue(null);
        setActiveTab('overview');
    };

    const handleStartDueReview = () => {
        setReviewQueue(null); // Use standard due queue
        setActiveTab('review');
    };

    const handleConceptClick = (concept: any, level: string) => {
        // Map to DueConcept format for the reviewer
        const mappedConcept: DueConcept = {
            id: concept.id,
            name: concept.name,
            level: level,
            category: concept.category,
            description: concept.description,
            current_score: concept.score,
            current_state: concept.state,
            reps: concept.reps
        };

        setReviewQueue([mappedConcept]);
        setActiveTab('review');
    };

    return (
        <>
            <Head>
                <title>Grammatik | Conversational Learning</title>
            </Head>

            <div className="container mx-auto px-4 py-8 space-y-8">
                {/* Header */}
                <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                    <div>
                        <h1 className="text-3xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
                            <Book className="w-8 h-8 text-primary-600" />
                            Grammatik-Training
                        </h1>
                        <p className="text-gray-600 dark:text-gray-400 mt-1">
                            Verfolge deinen Fortschritt in der Grammatik nach dem Spaced-Repetition-Prinzip.
                        </p>
                    </div>

                    {activeTab === 'overview' && (
                        <button
                            onClick={handleStartDueReview}
                            disabled={!hasDueReviews}
                            className={`flex items-center gap-2 px-6 py-3 rounded-lg font-bold shadow-sm transition-all ${hasDueReviews
                                    ? 'bg-gradient-to-r from-primary-600 to-indigo-600 text-white hover:shadow-md hover:scale-105'
                                    : 'bg-gray-100 dark:bg-gray-800 text-gray-400 cursor-not-allowed'
                                }`}
                        >
                            <Play className="w-5 h-5 fill-current" />
                            {hasDueReviews ? 'Training starten' : 'Alles erledigt'}
                            {hasDueReviews && (
                                <span className="bg-white text-primary-600 text-xs px-2 py-0.5 rounded-full">
                                    {dueConcepts?.length}
                                </span>
                            )}
                        </button>
                    )}
                </div>

                {/* Tab Navigation */}
                {activeTab !== 'review' && (
                    <div className="flex gap-2 border-b border-gray-200 dark:border-gray-700 pb-2">
                        <TabButton
                            active={activeTab === 'overview'}
                            onClick={() => setActiveTab('overview')}
                            icon={<BarChart3 className="w-4 h-4" />}
                            label="Übersicht"
                        />
                        <TabButton
                            active={activeTab === 'achievements'}
                            onClick={() => setActiveTab('achievements')}
                            icon={<Trophy className="w-4 h-4" />}
                            label="Errungenschaften"
                        />
                        <TabButton
                            active={activeTab === 'graph'}
                            onClick={() => setActiveTab('graph')}
                            icon={<GitBranch className="w-4 h-4" />}
                            label="Konzept-Graph"
                        />
                    </div>
                )}

                {/* Tab Content */}
                <AnimatePresence mode="wait">
                    {activeTab === 'review' ? (
                        <motion.div
                            key={`review-${reviewQueue ? 'manual' : 'due'}`}
                            initial={{ opacity: 0, scale: 0.95 }}
                            animate={{ opacity: 1, scale: 1 }}
                            exit={{ opacity: 0, scale: 0.95 }}
                            className="py-6"
                        >
                            <button
                                onClick={() => setActiveTab('overview')}
                                className="mb-6 text-sm text-gray-500 hover:text-gray-900 dark:hover:text-white flex items-center gap-1"
                            >
                                ← Zurück zur Übersicht
                            </button>
                            <GrammarReview
                                initialQueue={reviewQueue || dueConcepts || []}
                                onComplete={handleReviewComplete}
                            />
                        </motion.div>
                    ) : activeTab === 'achievements' ? (
                        <motion.div
                            key="achievements"
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -20 }}
                        >
                            <GrammarAchievements
                                achievements={achievements || []}
                                streakInfo={streakInfo || { current_streak: 0, longest_streak: 0, is_active_today: false }}
                                loading={achievementsLoading || streakLoading}
                            />
                        </motion.div>
                    ) : activeTab === 'graph' ? (
                        <motion.div
                            key="graph"
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -20 }}
                            className="space-y-4"
                        >
                            {/* Level Filter for Graph */}
                            <div className="flex flex-wrap gap-2">
                                <button
                                    onClick={() => setSelectedLevel(null)}
                                    className={`px-3 py-1.5 rounded-full text-sm font-medium transition-all ${selectedLevel === null
                                            ? 'bg-primary-600 text-white shadow-sm'
                                            : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
                                        }`}
                                >
                                    Alle Level
                                </button>
                                {['A1', 'A2', 'B1', 'B2', 'C1', 'C2'].map(level => (
                                    <button
                                        key={level}
                                        onClick={() => setSelectedLevel(level)}
                                        className={`px-3 py-1.5 rounded-full text-sm font-medium transition-all ${selectedLevel === level
                                                ? 'bg-primary-600 text-white shadow-sm'
                                                : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
                                            }`}
                                    >
                                        {level}
                                    </button>
                                ))}
                            </div>

                            {graphLoading ? (
                                <div className="p-12 text-center text-gray-400 bg-gray-50 dark:bg-gray-800 rounded-lg">
                                    <div className="animate-spin w-8 h-8 border-4 border-gray-300 border-t-primary-500 rounded-full mx-auto mb-4" />
                                    <p>Lade Konzept-Graph...</p>
                                </div>
                            ) : conceptGraph ? (
                                <GrammarGraph
                                    graph={conceptGraph}
                                    onConceptClick={(id) => console.log('Graph click:', id)}
                                    selectedLevel={selectedLevel}
                                />
                            ) : (
                                <div className="p-12 text-center text-gray-400 bg-gray-50 dark:bg-gray-800 rounded-lg">
                                    <p>Keine Konzepte gefunden.</p>
                                </div>
                            )}
                        </motion.div>
                    ) : (
                        <motion.div
                            key="overview"
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -20 }}
                            className="space-y-8"
                        >
                            {/* Stats Overview */}
                            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                                <StatCard
                                    label="Gesamt Konzepte"
                                    value={summary?.total_concepts || 0}
                                    color="bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-400"
                                />
                                <StatCard
                                    label="Gemeistert"
                                    value={summary?.state_counts?.gemeistert || 0}
                                    color="bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400"
                                />
                                <StatCard
                                    label="In Arbeit"
                                    value={(summary?.started || 0) - (summary?.state_counts?.gemeistert || 0)}
                                    color="bg-yellow-50 dark:bg-yellow-900/20 text-yellow-700 dark:text-yellow-400"
                                />
                                <StatCard
                                    label="Fällig heute"
                                    value={summary?.due_today || 0}
                                    color="bg-orange-50 dark:bg-orange-900/20 text-orange-700 dark:text-orange-400"
                                    highlight={!!summary?.due_today}
                                />
                            </div>

                            {/* Level Selector & Content */}
                            <div className="space-y-4">
                                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                                    <h2 className="text-xl font-bold flex items-center gap-2 text-gray-900 dark:text-white">
                                        <Filter className="w-5 h-5 text-gray-400" />
                                        Konzepte nach Niveau
                                    </h2>

                                    {/* Level Filter Buttons */}
                                    <div className="flex flex-wrap gap-2">
                                        <button
                                            onClick={() => setSelectedLevel(null)}
                                            className={`px-3 py-1.5 rounded-full text-sm font-medium transition-all ${selectedLevel === null
                                                    ? 'bg-primary-600 text-white shadow-sm'
                                                    : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
                                                }`}
                                        >
                                            Alle
                                        </button>
                                        {['A1', 'A2', 'B1', 'B2', 'C1', 'C2'].map(level => (
                                            <button
                                                key={level}
                                                onClick={() => setSelectedLevel(level)}
                                                className={`px-3 py-1.5 rounded-full text-sm font-medium transition-all ${selectedLevel === level
                                                        ? 'bg-primary-600 text-white shadow-sm'
                                                        : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
                                                    }`}
                                            >
                                                {level}
                                                {levels && levels[level] && (
                                                    <span className="ml-1 text-xs opacity-75">
                                                        ({levels[level].length})
                                                    </span>
                                                )}
                                            </button>
                                        ))}
                                    </div>
                                </div>

                                {levels ? (
                                    <GrammarLevelGrid
                                        levels={selectedLevel ? { [selectedLevel]: levels[selectedLevel] || [] } : levels}
                                        onConceptClick={handleConceptClick}
                                    />
                                ) : (
                                    <div className="p-12 text-center text-gray-400 bg-gray-50 dark:bg-gray-800 rounded-lg border-2 border-dashed border-gray-200 dark:border-gray-700">
                                        <div className="animate-spin w-8 h-8 border-4 border-gray-300 border-t-primary-500 rounded-full mx-auto mb-4" />
                                        <p>Lade Grammatik-Daten...</p>
                                    </div>
                                )}
                            </div>

                            {/* Quick Tips / Info Section */}
                            <div className="bg-indigo-50 dark:bg-indigo-900/20 border border-indigo-100 dark:border-indigo-800 rounded-lg p-6 flex gap-4">
                                <div className="bg-white dark:bg-gray-800 p-3 rounded-full h-fit shadow-sm">
                                    <Sparkles className="w-6 h-6 text-indigo-500" />
                                </div>
                                <div>
                                    <h3 className="font-bold text-indigo-900 dark:text-indigo-100 mb-1">
                                        Wusstest du schon?
                                    </h3>
                                    <p className="text-indigo-800 dark:text-indigo-200 text-sm leading-relaxed">
                                        Deine Grammatik-Fehler aus den Konversationen werden automatisch hier
                                        getrackt. Wenn du öfter Fehler bei einem bestimmten Thema machst (z.B.
                                        &quot;Dativ&quot;), wird das Thema hier als &quot;Ausbaufähig&quot;
                                        markiert und rutscht in deine Wiederholungsliste.
                                    </p>
                                </div>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </>
    );
}

function TabButton({
    active,
    onClick,
    icon,
    label,
}: {
    active: boolean;
    onClick: () => void;
    icon: React.ReactNode;
    label: string;
}) {
    return (
        <button
            onClick={onClick}
            className={`flex items-center gap-2 px-4 py-2 rounded-t-lg font-medium transition-all ${active
                    ? 'bg-white dark:bg-gray-800 text-primary-600 border-b-2 border-primary-600 -mb-[2px]'
                    : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-800/50'
                }`}
        >
            {icon}
            {label}
        </button>
    );
}

function StatCard({
    label,
    value,
    color,
    highlight = false,
}: {
    label: string;
    value: number | string;
    color: string;
    highlight?: boolean;
}) {
    return (
        <div
            className={`learning-card flex flex-col items-center justify-center p-6 transition-all ${highlight ? 'ring-2 ring-orange-400 ring-offset-2 dark:ring-offset-gray-900' : ''
                }`}
        >
            <span className="text-xs text-gray-500 dark:text-gray-400 font-medium uppercase tracking-wider mb-2">
                {label}
            </span>
            <span className={`text-4xl font-bold ${color.split(' ')[1]}`}>{value}</span>
        </div>
    );
}

export async function getServerSideProps(ctx: any) {
    const session = await getSession(ctx);
    if (!session) {
        return {
            redirect: {
                destination: '/auth/signin',
                permanent: false,
            },
        };
    }
    return { props: {} };
}
