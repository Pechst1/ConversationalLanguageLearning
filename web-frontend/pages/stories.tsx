import React from 'react';
import { getSession } from 'next-auth/react';
import Link from 'next/link';
import { BookOpen, Star, Clock, Lock, Play, ChevronRight, Upload, Globe } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';

interface Story {
    id: string;
    title: string;
    subtitle: string | null;
    source_book: string | null;
    source_author: string | null;
    target_levels: string[];
    themes: string[];
    estimated_duration_minutes: number;
    cover_image_url: string | null;
    is_unlocked: boolean;
    progress: {
        current_chapter_title: string | null;
        completion_percentage: number;
        status: string;
        last_played_at: string | null;
    } | null;
}

interface StoriesPageProps {
    stories: Story[];
}

import { useState } from 'react';
import { useRouter } from 'next/router';
import UploadBookModal from '@/components/story/UploadBookModal';
import { ImportStoryModal } from '@/components/stories/ImportStoryModal';

export default function StoriesPage({ stories }: StoriesPageProps) {
    const router = useRouter();
    const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);

    const handleUploadSuccess = () => {
        router.replace(router.asPath); // Refresh props
    };

    return (
        <div className="space-y-8 p-4">
            {/* Header */}
            <div className="flex items-center justify-between border-b-4 border-black pb-6 bg-white p-4 shadow-[4px_4px_0px_0px_#000]">
                <div>
                    <h1 className="text-4xl font-extrabold text-black uppercase tracking-tight">
                        Story Adventures
                    </h1>
                    <p className="text-gray-600 font-bold mt-1">
                        Lerne Französisch durch interaktive Geschichten
                    </p>
                </div>
                <div className="flex items-center gap-4">
                    <Button
                        onClick={() => setIsUploadModalOpen(true)}
                        variant="outline"
                        className="font-bold border-2 border-black shadow-[4px_4px_0px_0px_#000] bg-white text-black hover:bg-gray-50"
                        leftIcon={<Upload className="h-4 w-4" />}
                    >
                        Buch hochladen
                    </Button>
                    <div className="flex items-center gap-2 px-4 py-2 bg-bauhaus-yellow border-2 border-black shadow-[4px_4px_0px_0px_#000]">
                        <BookOpen className="h-5 w-5" />
                        <span className="font-bold">{stories.length} Stories</span>
                    </div>
                </div>
            </div>

            {/* Featured Story */}
            {stories.length > 0 && (
                <div className="relative">
                    <FeaturedStoryCard story={stories[0]} />
                </div>
            )}

            {/* All Stories Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {stories.map((story) => (
                    <StoryCard key={story.id} story={story} />
                ))}
            </div>

            {/* Empty State */}
            {stories.length === 0 && (
                <Card className="border-4 border-black shadow-[8px_8px_0px_0px_#000]">
                    <CardContent className="p-12 text-center">
                        <BookOpen className="h-16 w-16 mx-auto mb-4 text-gray-400" />
                        <h3 className="text-2xl font-bold mb-2">Keine Stories verfügbar</h3>
                        <p className="text-gray-600">
                            Story-Inhalte werden bald verfügbar sein.
                        </p>
                        <Button
                            onClick={() => setIsUploadModalOpen(true)}
                            variant="outline"
                            className="mt-4 font-bold border-2 border-black shadow-[4px_4px_0px_0px_#000] text-black"
                        >
                            Erstes Buch hochladen
                        </Button>
                    </CardContent>
                </Card>
            )}

            <UploadBookModal
                isOpen={isUploadModalOpen}
                onClose={() => setIsUploadModalOpen(false)}
                onSuccess={handleUploadSuccess}
            />
        </div>
    );
}

function FeaturedStoryCard({ story }: { story: Story }) {
    const hasProgress = story.progress && story.progress.status !== 'not_started';

    return (
        <Card className="border-4 border-black shadow-[8px_8px_0px_0px_#000] overflow-hidden">
            <div className="grid grid-cols-1 lg:grid-cols-2">
                {/* Left: Cover Image or Placeholder */}
                <div className="bg-gradient-to-br from-bauhaus-blue via-indigo-600 to-purple-700 p-8 flex items-center justify-center min-h-[300px]">
                    {story.cover_image_url ? (
                        <img
                            src={story.cover_image_url}
                            alt={story.title}
                            className="max-h-[280px] object-contain"
                        />
                    ) : (
                        <div className="text-center text-white">
                            <div className="text-8xl mb-4">🌹</div>
                            <p className="text-lg font-bold opacity-80">{story.source_book}</p>
                        </div>
                    )}
                </div>

                {/* Right: Details */}
                <div className="p-8 flex flex-col justify-between">
                    <div>
                        {/* Badges */}
                        <div className="flex flex-wrap gap-2 mb-4">
                            {story.target_levels.map((level) => (
                                <span
                                    key={level}
                                    className="px-3 py-1 bg-bauhaus-yellow border-2 border-black font-bold text-sm shadow-[2px_2px_0px_0px_#000]"
                                >
                                    {level}
                                </span>
                            ))}
                            <span className="px-3 py-1 bg-white border-2 border-black font-bold text-sm shadow-[2px_2px_0px_0px_#000] flex items-center gap-1">
                                <Clock className="h-4 w-4" />
                                {story.estimated_duration_minutes} Min
                            </span>
                        </div>

                        <h2 className="text-3xl font-black uppercase mb-2">{story.title}</h2>
                        {story.subtitle && (
                            <p className="text-lg text-gray-600 font-medium mb-4">{story.subtitle}</p>
                        )}

                        {story.source_author && (
                            <p className="text-sm text-gray-500 font-bold mb-4">
                                Nach {story.source_author}
                            </p>
                        )}

                        {/* Themes */}
                        <div className="flex flex-wrap gap-2 mb-6">
                            {story.themes.slice(0, 4).map((theme) => (
                                <span
                                    key={theme}
                                    className="px-2 py-1 bg-gray-100 text-gray-700 text-sm font-medium rounded"
                                >
                                    {theme}
                                </span>
                            ))}
                        </div>

                        {/* Progress */}
                        {hasProgress && story.progress && (
                            <div className="mb-6">
                                <div className="flex justify-between text-sm font-bold mb-2">
                                    <span>Fortschritt</span>
                                    <span>{story.progress.completion_percentage}%</span>
                                </div>
                                <div className="w-full h-4 bg-gray-200 border-2 border-black">
                                    <div
                                        className="h-full bg-bauhaus-blue transition-all"
                                        style={{ width: `${story.progress.completion_percentage}%` }}
                                    />
                                </div>
                                {story.progress.current_chapter_title && (
                                    <p className="text-sm text-gray-600 mt-2">
                                        Aktuell: {story.progress.current_chapter_title}
                                    </p>
                                )}
                            </div>
                        )}
                    </div>

                    {/* CTA */}
                    <Link href={`/story/${story.id}`}>
                        <Button
                            className="w-full h-14 text-lg font-bold shadow-[4px_4px_0px_0px_#000] border-2 border-black"
                            leftIcon={<Play className="h-5 w-5" />}
                        >
                            {hasProgress ? 'Fortsetzen' : 'Story starten'}
                        </Button>
                    </Link>
                </div>
            </div>
        </Card>
    );
}

function StoryCard({ story }: { story: Story }) {
    const isLocked = !story.is_unlocked;
    const hasProgress = story.progress && story.progress.status !== 'not_started';

    return (
        <Card className={`border-4 border-black shadow-[8px_8px_0px_0px_#000] hover:translate-y-[-4px] transition-transform ${isLocked ? 'opacity-60' : ''}`}>
            {/* Cover */}
            <div className="h-40 bg-gradient-to-br from-bauhaus-blue to-purple-600 flex items-center justify-center relative">
                {story.cover_image_url ? (
                    <img
                        src={story.cover_image_url}
                        alt={story.title}
                        className="h-full w-full object-cover"
                    />
                ) : (
                    <div className="text-6xl">🌹</div>
                )}

                {isLocked && (
                    <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                        <Lock className="h-12 w-12 text-white" />
                    </div>
                )}

                {/* Level Badge */}
                <div className="absolute top-3 right-3 flex gap-1">
                    {story.target_levels.slice(0, 2).map((level) => (
                        <span
                            key={level}
                            className="px-2 py-1 bg-bauhaus-yellow border-2 border-black font-bold text-xs shadow-[2px_2px_0px_0px_#000]"
                        >
                            {level}
                        </span>
                    ))}
                </div>
            </div>

            <CardContent className="p-4">
                <h3 className="text-xl font-black uppercase mb-1 line-clamp-1">{story.title}</h3>
                {story.source_author && (
                    <p className="text-sm text-gray-500 font-medium mb-3">
                        {story.source_author}
                    </p>
                )}

                {/* Duration & Themes */}
                <div className="flex items-center gap-2 text-sm text-gray-600 mb-4">
                    <Clock className="h-4 w-4" />
                    <span>{story.estimated_duration_minutes} Min</span>
                </div>

                {/* Progress Bar */}
                {hasProgress && story.progress && (
                    <div className="mb-4">
                        <div className="w-full h-2 bg-gray-200 border border-black">
                            <div
                                className="h-full bg-bauhaus-blue"
                                style={{ width: `${story.progress.completion_percentage}%` }}
                            />
                        </div>
                    </div>
                )}

                {/* Action */}
                <Link href={isLocked ? '#' : `/story/${story.id}`}>
                    <Button
                        variant="outline"
                        className="w-full border-2 border-black shadow-[4px_4px_0px_0px_#000] font-bold"
                        disabled={isLocked}
                        rightIcon={<ChevronRight className="h-4 w-4" />}
                    >
                        {isLocked ? 'Gesperrt' : hasProgress ? 'Fortsetzen' : 'Spielen'}
                    </Button>
                </Link>
            </CardContent>
        </Card>
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

        const res = await fetch(`${baseUrl}/api/v1/stories`, { headers });

        if (!res.ok) {
            console.error('Failed to fetch stories:', res.status);
            return { props: { stories: [] } };
        }

        const stories = await res.json();

        // Filter out imported stories as they belong to the Learn/Conversational framework
        const filteredStories = stories.filter((story: any) =>
            !story.themes?.includes('imported')
        );

        return {
            props: {
                stories: filteredStories,
            },
        };
    } catch (error) {
        console.error('Failed to fetch stories:', error);
        return {
            props: {
                stories: [],
            },
        };
    }
}
